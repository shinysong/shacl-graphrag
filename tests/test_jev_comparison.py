"""Offline invented fixtures only; no API calls or benchmark measurements."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from scripts import run_jev_comparison_smoke as jev


def metadata():
    return {'data': {'id': jev.MODEL, 'endpoints': [
        {'name': 'TypeSafe | ' + jev.CANONICAL_MODEL, 'provider_name': 'TypeSafe',
         'status': 0, 'pricing': {'prompt': str(jev.PRICE), 'completion': '0', 'discount': 0}}]}}


def response(choices=None, cost=.0001):
    choices = choices or {'cardinality': 'pass', 'parent_type': 'pass', 'exception_reason': 'not_applicable'}
    return {'model': jev.CANONICAL_MODEL, 'provider': 'TypeSafe', 'usage': {'cost': cost},
            'answers': {name: {'type': 'choice', 'choice': choices[name],
                               'probabilities': {key: int(key == choices[name]) for key in q['criteria']}}
                        for name, q in jev.QUESTIONS.items()}}


class JevTests(unittest.TestCase):
    def setUp(self):
        self.ids = ['A'*18+'01', 'B'*18+'02', 'C'*18+'03']
        self.dataset = {'entities': {x: {'lei': x, 'name': 'Fixture'} for x in self.ids}}
        self.item = {'lei': self.ids[0], 'kind': 'parent', 'parent': self.ids[1], 'split': 'development'}
        self.subject = jev.core.LEI[self.ids[0]]

    def test_probabilities_composition_and_malformed(self):
        self.assertEqual(jev.validate_answers(response())[0], 'pass')
        self.assertEqual(jev.validate_answers(response({'cardinality': 'unknown', 'parent_type': 'not_applicable',
                                                      'exception_reason': 'not_applicable'}))[0], 'unknown')
        for invalid in (float('nan'), float('inf'), -.1, 1.1, True):
            data = response()
            data['answers']['cardinality']['probabilities']['pass'] = invalid
            with self.assertRaises(ValueError):
                jev.validate_answers(data)
        data = response()
        data['answers']['cardinality']['probabilities']['unknown'] = .2
        with self.assertRaises(ValueError):
            jev.validate_answers(data)
        data = response()
        data['answers']['cardinality']['choice'] = 'fail'
        with self.assertRaises(ValueError):
            jev.validate_answers(data)
        data = response()
        data['model'] = 'typesafe/jev-latest'
        with self.assertRaises(jev.study.CriticalAbort):
            jev.validate_answers(data)

    def test_metadata_rejects_dynamic_missing_negative_and_extra_price(self):
        jev.validate_metadata(metadata())
        for value in ('-1', 'dynamic', 'nan', '0', '.0001'):
            data = metadata()
            data['data']['endpoints'][0]['pricing']['prompt'] = value
            with self.assertRaises((ValueError, jev.study.CriticalAbort)):
                jev.validate_metadata(data)
        data = metadata()
        data['data']['endpoints'][0]['pricing']['request'] = '.01'
        with self.assertRaises(jev.study.CriticalAbort):
            jev.validate_metadata(data)

    def test_reservation_persisted_before_http_and_wire_has_no_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / 'attempt'
            directory.mkdir()
            ledger = root / 'campaign.json'
            captured = []
            def handle(request):
                if request.method == 'GET':
                    return httpx.Response(200, json=metadata())
                self.assertEqual(json.loads(ledger.read_text())['attempts'], 1)
                self.assertEqual(json.loads((root / 'budget.json').read_text())['calls'], 1)
                captured.append(json.loads(request.content))
                self.assertEqual(request.content, (directory / 'request.json').read_bytes())
                return httpx.Response(200, json=response())
            with patch.object(jev, 'dotenv_values', return_value={'OPENROUTER_API_KEY': 'fixture'}):
                gateway = jev.JevGateway(root, client=httpx.Client(transport=httpx.MockTransport(handle)),
                                         campaign=jev.study.CampaignBudget(ledger))
            source = jev.core.build_case(self.dataset, self.item, 'clean')
            self.assertEqual(gateway.judge(source, self.subject, directory)[0], 'pass')
            self.assertEqual(gateway.budget()['reserved_usd'], .002)
            self.assertEqual(set(captured[0]['state']), {'QUESTION_SUBJECT', 'question', 'evidence'})
            self.assertNotIn('gold', json.dumps(captured[0]))
            gateway.close()

    def test_missing_cost_overrun_and_network_abort_without_refund(self):
        for failure in ('missing', 'overrun', 'network'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                directory = root / 'attempt'
                directory.mkdir()
                ledger = root / 'campaign.json'
                posts = []
                def handle(request, posts=posts, failure=failure):
                    if request.method == 'GET':
                        return httpx.Response(200, json=metadata())
                    posts.append(request)
                    if failure == 'network':
                        raise httpx.ConnectError('offline', request=request)
                    return httpx.Response(200, json=response(cost=None if failure == 'missing' else 1))
                with patch.object(jev, 'dotenv_values', return_value={'OPENROUTER_API_KEY': 'fixture'}):
                    gateway = jev.JevGateway(root, client=httpx.Client(transport=httpx.MockTransport(handle)),
                                             campaign=jev.study.CampaignBudget(ledger))
                source = jev.core.build_case(self.dataset, self.item, 'clean')
                with self.assertRaises(jev.study.CriticalAbort):
                    gateway.judge(source, self.subject, directory)
                self.assertEqual(len(posts), 1)
                self.assertEqual(json.loads(ledger.read_text())['reserved_usd'], .002)
                self.assertTrue((directory / 'error.json').exists())
                gateway.close()

    def test_malformed_cost_envelopes_stop_runtime_and_preserve_raw_response(self):
        envelopes = [[], None, {'usage': None}, {'usage': []}, {'usage': 'invalid'},
                     {'usage': {'cost': True}}, {'usage': {'cost': '0.001'}}]
        for envelope in envelopes:
            with self.subTest(envelope=envelope), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                ledger = root / 'campaign.json'
                posts = []
                wire = json.dumps(envelope)
                def handle(request, wire=wire, posts=posts):
                    if request.method == 'GET':
                        return httpx.Response(200, json=metadata())
                    posts.append(request)
                    return httpx.Response(200, text=wire)
                with patch.object(jev, 'dotenv_values', return_value={'OPENROUTER_API_KEY': 'fixture'}):
                    gateway = jev.JevGateway(root, client=httpx.Client(transport=httpx.MockTransport(handle)),
                                             campaign=jev.study.CampaignBudget(ledger))
                source = jev.core.build_case(self.dataset, self.item, 'clean')
                row, critical = jev.run_case(source, source, self.subject, gateway, root / 'case')
                self.assertIsInstance(critical, jev.study.CriticalAbort)
                self.assertEqual(str(critical), 'MissingOrInvalidReportedCost')
                self.assertEqual(row['status'], 'error')
                self.assertEqual(row['extra_retrievals'], 0)
                self.assertEqual(row['judge_calls'], 1)
                self.assertEqual(len(posts), 1)
                self.assertEqual(gateway.budget()['missing_cost'], 1)
                self.assertEqual(json.loads((root / 'budget.json').read_text())['missing_cost'], 1)
                self.assertEqual(json.loads(ledger.read_text())['reserved_usd'], .002)
                self.assertEqual((root / 'case/attempt-0/response.txt').read_text(), wire)
                gateway.close()

    def test_local_caps_prevent_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts = []
            def handle(request):
                if request.method == 'POST':
                    posts.append(request)
                return httpx.Response(200, json=metadata())
            with patch.object(jev, 'dotenv_values', return_value={'OPENROUTER_API_KEY': 'fixture'}):
                gateway = jev.JevGateway(root, client=httpx.Client(transport=httpx.MockTransport(handle)),
                                         campaign=jev.study.CampaignBudget(root / 'campaign.json'))
            source = jev.core.build_case(self.dataset, self.item, 'clean')
            for calls, reserved in ((72, 0), (0, .20)):
                gateway.calls, gateway.reserved = calls, reserved
                with self.assertRaises(jev.study.CriticalAbort):
                    gateway.judge(source, self.subject, root)
            self.assertEqual(posts, [])
            gateway.close()

    def test_full_caps_enforced_before_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posts = []
            def handle(request):
                if request.method == 'POST':
                    posts.append(request)
                return httpx.Response(200, json=metadata())
            declared = dict(jev.FULL_CAPS)
            with patch.object(jev, 'dotenv_values', return_value={'OPENROUTER_API_KEY': 'fixture'}):
                gateway = jev.JevGateway(root, caps=declared,
                                         client=httpx.Client(transport=httpx.MockTransport(handle)),
                                         campaign=jev.study.CampaignBudget(root / 'campaign.json'))
            declared['max_llm_calls'] = 999  # Caller mutation cannot expand accepted caps.
            source = jev.core.build_case(self.dataset, self.item, 'clean')
            for calls, reserved in ((432, 0), (0, 1.0)):
                gateway.calls, gateway.reserved = calls, reserved
                with self.assertRaises(jev.study.CriticalAbort):
                    gateway.judge(source, self.subject, root)
            self.assertEqual(posts, [])
            gateway.close()

    def test_same_source_retry_and_no_retry_on_fail(self):
        class Fake:
            def __init__(self, verdicts):
                self.verdicts = iter(verdicts)
                self.evidence = []
            def budget(self):
                return {'calls': len(self.evidence)}
            def judge(self, evidence, subject, directory):
                self.evidence.append(jev.core.canonical(evidence))
                return next(self.verdicts), {}
        source = jev.core.build_case(self.dataset, self.item, 'retrieval_relation_missing')
        first = jev.core.omit(jev.old.retrieve(source, self.subject), self.subject, 'retrieval_relation_missing')
        with tempfile.TemporaryDirectory() as tmp:
            gateway = Fake(['unknown', 'pass'])
            row, critical = jev.run_case(source, first, self.subject, gateway, Path(tmp))
            self.assertIsNone(critical)
            self.assertEqual(row['answer']['value'], self.item['parent'])
            self.assertEqual(row['extra_retrievals'], 1)
            self.assertNotEqual(gateway.evidence[0], gateway.evidence[1])
        with tempfile.TemporaryDirectory() as tmp:
            gateway = Fake(['fail'])
            row, _ = jev.run_case(source, first, self.subject, gateway, Path(tmp))
            self.assertEqual(row['extra_retrievals'], 0)
            self.assertEqual(row['answer']['status'], 'abstain')
        with tempfile.TemporaryDirectory() as tmp:
            gateway = Fake(['unknown', 'unknown'])
            row, _ = jev.run_case(source, first, self.subject, gateway, Path(tmp))
            self.assertEqual(row['judge_calls'], 2)
            self.assertEqual(row['answer']['status'], 'abstain')

    def _offline_schedule(self, all_development=False, heldout=False):
        class Fake:
            def __init__(self, output, *, caps):
                self.calls = 0
            def budget(self):
                return {'calls': self.calls, 'reserved_usd': 0., 'reported_usd': 0., 'missing_cost': 0}
            def judge(self, evidence, subject, directory):
                self.calls += 1
                return jev.core.code_judge(evidence, subject), {}
            def close(self):
                pass
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('scripts/run_comparison_study.py', 'scripts/run_gleif_comparison.py',
                         'scripts/run_gleif_pilot.py', 'uv.lock', 'pyproject.toml'):
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(jev.ROOT / name, destination)
            dataset = dict(self.dataset, cohort=[self.item, {'lei': self.ids[2], 'kind': 'exception',
                            'reason': 'NATURAL_PERSONS', 'split': 'development'}])
            if all_development:
                cohort = []
                for i in range(12):
                    lei = f'{i:020d}'
                    dataset['entities'][lei] = {'lei': lei, 'name': 'Invented fixture'}
                    cohort.append({'lei': lei, 'kind': 'parent' if i < 6 else 'exception',
                                   'split': 'reserved' if heldout else 'development',
                                   **({'parent': self.ids[1]} if i < 6 else {'reason': 'NATURAL_PERSONS'})})
                dataset['cohort'] = cohort
            fixture = root / 'fixture.json'
            fixture.write_text(json.dumps(dataset))
            digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
            with patch.object(jev, 'ROOT', root), patch.object(jev, 'DEVELOPMENT', fixture), \
                    patch.object(jev, 'DEVELOPMENT_SHA', digest), patch.object(jev, 'JevGateway', Fake):
                self.assertEqual(jev.main(['--all-development'] if all_development else []), int(heldout))
            record = json.loads(next((root / 'runs').glob('*/record.json')).read_text())
            if heldout:
                self.assertEqual(record['status'], 'failed')
                self.assertEqual(record['rows'], [])
                self.assertNotIn('budget', record)
                return
            self.assertEqual(len(record['cases']), 72 if all_development else 12)
            self.assertEqual(len(record['rows']), 216 if all_development else 36)
            self.assertEqual(record['config']['mode'], 'all-development' if all_development else 'smoke')
            self.assertEqual(record['config']['max_llm_calls'], 432 if all_development else 72)
            self.assertEqual(record['config']['max_cost_usd'], 1.0 if all_development else .20)
            self.assertEqual(record['protocol'], '0.5-jev-dev-full1' if all_development else '0.5-jev-dev-smoke1')
            self.assertEqual(record['status'], 'completed')
            self.assertTrue(all(r['status'] == 'ok' for r in record['rows']))
            self.assertTrue(all(r['error_type'] is None for r in record['rows']))
            self.assertEqual({r['repeat'] for r in record['rows']}, {0, 1, 2})
            self.assertTrue(all(c['source_sha256'] for c in record['cases']))

    def test_offline_smoke_schedule_preserved(self):
        self._offline_schedule()

    def test_offline_all_development_schedule(self):
        self._offline_schedule(all_development=True)

    def test_all_development_rejects_heldout_rows(self):
        self._offline_schedule(all_development=True, heldout=True)

    def test_arbitrary_caps_rejected_before_client_creation(self):
        for caps in ({}, {'max_llm_calls': 432, 'max_cost_usd': 2},
                     {'max_llm_calls': 72, 'max_cost_usd': float('nan')},
                     {'max_llm_calls': 72., 'max_cost_usd': .20},
                     {'max_llm_calls': 432, 'max_cost_usd': True}):
            with self.subTest(caps=caps), patch.object(jev.httpx, 'Client') as client:
                with self.assertRaises(ValueError):
                    jev.JevGateway(Path('unused'), caps=caps)
                client.assert_not_called()

    def test_evaluation_override_unavailable(self):
        with self.assertRaises(SystemExit):
            jev.main(['--dataset', 'reserved.json'])


if __name__ == '__main__':
    unittest.main()
