"""Offline semantic-contract checks, not empirical benchmark measurements."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from scripts import run_semantic_study as study


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.gold = study.fixtures()

    def test_frozen_opaque_fixture_and_no_gold_runtime(self):
        self.assertEqual(study.fixtures(), study.fixtures())
        self.assertEqual(len(self.cases), 10)
        for case in self.cases:
            self.assertEqual(set(case), {'id', 'query', 'questions', 'first', 'source'})
            self.assertEqual(len(case['questions']), 3)
            self.assertNotIn(self.gold[case['id']]['variant'], case['id'])
        wrong = self.cases[-1]
        self.assertNotIn(self.gold[wrong['id']]['candidate'], json.dumps(wrong))

    def test_policy_and_factual_truth_are_separate(self):
        for case in self.cases:
            outputs = []
            for judge in (study.code_judge, study.shacl_judge):
                output = study.run_case(case, 0, lambda payload, step, judge=judge: judge(payload))
                scores = study.evaluate(output, self.gold[case['id']])
                self.assertTrue(scores['policy_correct'], self.gold[case['id']])
                self.assertTrue(scores['first_decision_correct'])
                self.assertEqual(scores['wrong_answer'], self.gold[case['id']]['variant'] == 'false_fact')
                outputs.append(output)
            self.assertEqual(*outputs)

    def test_adversarial_record_constraints_and_date_boundaries(self):
        case = self.cases[0]
        original = case['first'][0]
        p = {'query': case['query'], 'records': [original], 'retrieval_available': False}
        for judge in (study.code_judge, study.shacl_judge):
            for mutation in ({'subject': 'other'}, {'relation': 'ultimate'}, {'status': 'ended'},
                             {'start': '2026-01-02'}, {'end': '2026-01-01'}):
                changed = copy.deepcopy(p)
                changed['records'][0].update(mutation)
                self.assertEqual(judge(changed)['decision'], 'abstain', mutation)
            for mutation in ({'start': '2026-01-01'}, {'end': '2026-01-02'}):
                changed = copy.deepcopy(p)
                changed['records'][0].update(mutation)
                self.assertEqual(judge(changed)['decision'], 'answer', mutation)

    def test_source_absence_versus_retrieval_omission(self):
        for variant, final in [('source_absence', 'abstain'), ('retrieval_omission', 'answer')]:
            case = next(c for c in self.cases if self.gold[c['id']]['variant'] == variant)
            seen = []
            def judge(payload, step, seen=seen):
                seen.append(payload)
                return study.code_judge(payload)
            result = study.run_case(case, 2, judge)
            self.assertEqual(result['retrieval_calls'], 1)
            self.assertEqual(result['answer']['decision'], final)
            self.assertEqual(seen[1]['records'], case['source'])
            self.assertFalse(seen[1]['retrieval_available'])
            self.assertNotIn('variant', json.dumps(seen))

    def test_independent_shacl_and_report(self):
        case = self.cases[5]
        with tempfile.TemporaryDirectory() as tmp, patch.object(study, 'code_judge', side_effect=AssertionError):
            path = Path(tmp) / 'report.ttl'
            result = study.shacl_judge({'query': case['query'], 'records': case['first'], 'retrieval_available': True}, path)
            self.assertEqual(result['decision'], 'abstain')
            self.assertIn('Conflicting candidates', path.read_text())

    def test_schema_citation_candidate_and_retrieval_checks(self):
        record = self.cases[0]['first'][0]
        for bad in [{'decision': 'answer', 'candidate': None, 'citations': []},
                    {'decision': 'answer', 'candidate': 'x', 'citations': 'bad'},
                    {'decision': 'abstain', 'candidate': record['candidate'], 'citations': []}]:
            with self.assertRaises(ValueError):
                study.check_response(bad, [record])
        with self.assertRaisesRegex(ValueError, 'RetrievalLimitExceeded'):
            study.run_case(self.cases[0], 0, lambda p, s: {'decision': 'retrieve', 'candidate': None, 'citations': []})

    def test_wrong_scope_and_candidate_are_scored_not_rejected(self):
        case = self.cases[0]
        wrong = case['first'][1]  # Ultimate record for a direct-parent question.
        result = study.run_case(case, 0, lambda p, s: {
            'decision': 'answer', 'candidate': wrong['candidate'], 'citations': [wrong['id']]})
        score = study.evaluate(result, self.gold[case['id']])
        self.assertTrue(score['wrong_answer'])
        self.assertFalse(score['evidence_applicable'])
        self.assertTrue(score['evidence_support'])
        result['answer']['candidate'] = 'uncited'
        self.assertFalse(study.evaluate(result, self.gold[case['id']])['evidence_support'])
        case = self.cases[3]  # Ended record, still a valid model outcome to score.
        ended = case['first'][0]
        result = study.run_case(case, 0, lambda p, s: {
            'decision': 'answer', 'candidate': ended['candidate'], 'citations': [ended['id']]})
        self.assertFalse(study.evaluate(result, self.gold[case['id']])['evidence_applicable'])

    def test_partial_trace_survives_schema_error(self):
        trace = []
        def judge(payload, step):
            return {'decision': 'retrieve', 'candidate': None, 'citations': []} if step == 0 else {'bad': True}
        with self.assertRaises(ValueError):
            study.run_case(self.cases[0], 0, judge, trace)
        self.assertEqual(len(trace), 2)
        self.assertEqual(trace[0]['decision'], 'retrieve')

    def test_known_cost_schema_error_continues_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'run'
            ledger = Path(tmp) / 'campaign.json'
            ledger.write_text(json.dumps({'attempts': 0, 'reserved_usd': 0, 'reservations': []}))
            cfg = study.config()
            cfg['campaign_ledger_path'] = str(ledger)
            calls = []
            def handler(request):
                calls.append(request)
                body = json.loads(request.content)
                payload = json.loads(body['messages'][1]['content'].split('Evidence:\n')[1])
                inner = study.code_judge(payload)
                value = 'invalid json' if len(calls) == 1 else json.dumps(inner)
                return httpx.Response(200, json={'usage': {'cost': 0.00001}, 'choices': [
                    {'message': {'content': value}, 'finish_reason': 'stop'}]})
            real_client = httpx.Client
            def client(**kwargs):
                return real_client(transport=httpx.MockTransport(handler), **kwargs)
            with patch.object(study, 'config', return_value=cfg), patch.object(study, 'fixtures', return_value=(self.cases[:1], self.gold)), patch.object(study, 'dotenv_values', return_value={'OPENROUTER_API_KEY': 'mock'}), patch.object(study.transport.old.httpx, 'Client', side_effect=client), patch('sys.argv', ['semantic', '--llm', '--output', str(output)]):
                study.main()
            record = json.loads((output / 'record.json').read_text())
            self.assertEqual(record['status'], 'complete')
            self.assertEqual(len(calls), 6)
            self.assertEqual(sum(r['status'] == 'error' for r in record['rows']), 1)
            self.assertEqual(record['unknown_cost_rows'], 0)

    def test_stale_followup_first_payload_paired_source_only_recovery(self):
        cases, gold = study.targeted_fixtures()
        self.assertEqual(len(cases), 2)
        baseline = {c['id']: c for c in self.cases}
        for case in cases:
            original = baseline[case['id']]
            for field in ('id', 'query', 'questions', 'first'):
                self.assertEqual(case[field], original[field])
            self.assertEqual(case['source'][:-1], original['source'])
            self.assertNotEqual(case['source'][-1]['candidate'], case['first'][0]['candidate'])
            self.assertNotIn(gold[case['id']]['candidate'], json.dumps(case['first']))
            for judge in (study.code_judge, study.shacl_judge):
                seen = []
                def observe(payload, step, judge=judge, seen=seen):
                    seen.append(payload)
                    return judge(payload)
                result = study.run_case(case, 0, observe)
                paired = []
                study.run_case(original, 0, lambda p, step, paired=paired: paired.append(p) or study.code_judge(p))
                self.assertEqual(seen[0], paired[0])
                self.assertEqual(result['retrieval_calls'], 1)
                self.assertTrue(study.evaluate(result, gold[case['id']])['correct_answer'])
                self.assertTrue(study.evaluate(result, gold[case['id']])['policy_correct'])

    def test_stale_followup_cli_bounded_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'followup'
            with patch('sys.argv', ['semantic', '--stale-followup', '--output', str(output)]):
                study.main()
            record = json.loads((output / 'record.json').read_text())
            cfg = json.loads((output / 'config.json').read_text())
            self.assertEqual(record['protocol'], 'semantic-stale-followup-1')
            self.assertTrue(record['posthoc_paired_followup'])
            self.assertEqual(record['planned_rows'], 24)
            self.assertEqual(cfg['max_llm_calls'], 24)
            self.assertEqual(cfg['max_cost_usd'], 0.1)
            self.assertTrue(all(r['correct_answer'] for r in record['rows']))

    def test_abstention_citations_are_a_policy_mismatch(self):
        case = self.cases[5]
        result = study.run_case(case, 0, lambda p, s: {
            'decision': 'abstain', 'candidate': None, 'citations': [case['first'][0]['id']]})
        self.assertFalse(study.evaluate(result, self.gold[case['id']])['policy_correct'])
        self.assertEqual(result['answer']['decision'], 'abstain')

    def test_flat_response_metadata_and_malformed_cost(self):
        for cost in (0.00001, None, '0.01', -1, float('nan'), 99):
            with self.subTest(cost=cost), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp)
                cfg = study.config()
                cfg['campaign_ledger_path'] = str(output / 'campaign.json')
                prompt = output / 'prompt.txt'
                prompt.write_text(study.PROMPT)
                path = output / 'attempt'
                path.mkdir()
                result = {'decision': 'answer', 'candidate': 'node', 'citations': ['record']}
                raw = {'model': 'openai/gpt-4o-mini', 'provider': 'Test', 'id': 'gen-test',
                       'usage': {'cost': cost}, 'choices': [{'message': {'content': json.dumps(result)},
                                                          'finish_reason': 'stop'}]}
                def handler(request, raw=raw):
                    return httpx.Response(200, text=json.dumps(raw))
                real_client = httpx.Client
                def client(handler=handler, real_client=real_client, **kwargs):
                    return real_client(transport=httpx.MockTransport(handler), **kwargs)
                with patch.object(study, 'dotenv_values', return_value={'OPENROUTER_API_KEY': 'mock'}), patch.object(study.httpx, 'Client', side_effect=client):
                    gateway = study.SemanticGateway(cfg, output, prompt)
                    if cost == 0.00001:
                        answer, metadata = gateway.generate('Question', 'Evidence', path)
                        self.assertEqual(answer, result)
                        self.assertEqual(metadata['provider'], 'Test')
                        self.assertEqual(metadata['finish_reason'], 'stop')
                        self.assertEqual(gateway.budget()['missing_cost'], 0)
                    else:
                        with self.assertRaises(study.UnknownCost):
                            gateway.generate('Question', 'Evidence', path)
                        self.assertEqual(gateway.budget()['missing_cost'], 1)
                        self.assertTrue(gateway.coordinator.stopped.is_set())
                    gateway.close()
                self.assertTrue((path / 'response.json').exists())
                self.assertEqual(json.loads((output / 'campaign.json').read_text())['attempts'], 1)

    def test_gateway_failed_post_preserves_prepost_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            cfg = study.config()
            cfg['campaign_ledger_path'] = str(output / 'campaign.json')
            prompt = output / 'prompt.txt'
            prompt.write_text(study.PROMPT)
            path = output / 'attempt'
            path.mkdir()
            def handler(request):
                self.assertEqual(json.loads((output / 'budget.json').read_text())['calls'], 1)
                self.assertEqual(json.loads((output / 'campaign.json').read_text())['attempts'], 1)
                raise httpx.ConnectError('offline mock')
            real_client = httpx.Client
            def client(**kwargs):
                return real_client(transport=httpx.MockTransport(handler), **kwargs)
            with patch.object(study, 'dotenv_values', return_value={'OPENROUTER_API_KEY': 'mock'}), patch.object(study.transport.old.httpx, 'Client', side_effect=client):
                gateway = study.SemanticGateway(cfg, output, prompt)
                with self.assertRaises(study.UnknownCost):
                    gateway.generate('Question', 'Evidence', path)
                gateway.close()
            self.assertEqual(json.loads((output / 'campaign.json').read_text())['attempts'], 1)
            self.assertTrue((path / 'request.json').exists())


if __name__ == '__main__':
    unittest.main()
