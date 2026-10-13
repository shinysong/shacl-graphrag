"""Offline software checks with invented entities, not study measurements."""
import hashlib
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import httpx
from rdflib import Graph

from scripts import run_comparison_study as study


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.ids = ['A'*18+'01', 'B'*18+'02', 'C'*18+'03']
        self.dataset = {'entities': {x: {'lei': x, 'name': 'Fixture'} for x in self.ids}}
        self.item = {'lei': self.ids[0], 'kind': 'parent', 'parent': self.ids[1], 'split': 'development'}
        self.subject = study.core.LEI[self.ids[0]]
        self.shapes = Graph().parse(study.core.FIX / 'shapes.ttl')
        self.config = json.loads((study.core.FIX / 'config.json').read_text())
        self.config.update(protocol_version='0.5-study1', stage='development', repeat_count=3,
                           evidence_format='structured')

    def evidence(self, variant):
        source = study.core.build_case(self.dataset, self.item, variant)
        return source, study.core.omit(study.old.retrieve(source, self.subject), self.subject, variant)

    def test_campaign_cumulative_concurrent_and_failed_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ledger.json'
            def reserve(i):
                try:
                    study.CampaignBudget(path).reserve(0.5, str(i))
                    return True
                except study.CriticalAbort:
                    return False
            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(sum(pool.map(reserve, range(20))), 10)
            ledger = json.loads(path.read_text())
            self.assertEqual((ledger['attempts'], ledger['reserved_usd']), (10, 5))
            with self.assertRaises(study.CriticalAbort):
                study.CampaignBudget(path).reserve(0.01, 'next-run')
            # No completion/refund operation: reservations survive process/run failure.
            self.assertEqual(len(ledger['reservations']), 10)

    def test_failed_post_is_reserved_before_transmission(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            ledger = output / 'campaign.json'
            self.config['campaign_ledger_path'] = str(ledger)
            prompt = output / 'prompt.txt'
            prompt.write_text('Fixture judge')
            destination = output / 'attempt'
            destination.mkdir()
            def fail_post(request):
                self.assertEqual(json.loads(ledger.read_text())['attempts'], 1)
                self.assertEqual(json.loads((output / 'budget.json').read_text())['calls'], 1)
                raise httpx.ConnectError('offline fixture failure', request=request)
            client = httpx.Client(transport=httpx.MockTransport(fail_post))
            with patch.object(study.old, 'dotenv_values', return_value={'OPENROUTER_API_KEY': 'fixture'}), \
                    patch.object(study.old.httpx, 'Client', return_value=client):
                gateway = study.StudyGateway(self.config, output, prompt)
                with self.assertRaises(httpx.ConnectError):
                    gateway.generate('Fixture question', '[]', destination)
                gateway.close()
            self.assertEqual(json.loads(ledger.read_text())['attempts'], 1)
            self.assertGreater(json.loads(ledger.read_text())['reserved_usd'], 0)

    def test_concurrent_gateways_isolate_row_cost_and_share_run_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            self.config['campaign_ledger_path'] = str(output / 'campaign.json')
            self.config.update(max_llm_calls=8, max_cost_usd=1)
            coordinator = study.RunBudget(self.config, output)
            prompt = output / 'prompt.txt'
            prompt.write_text('Fixture')
            barrier = threading.Barrier(4)
            original_client = httpx.Client
            def respond(request):
                barrier.wait(timeout=5)
                return httpx.Response(200, json={
                    'usage': {'cost': 0.000001}, 'choices': [{'message': {'content': json.dumps({
                        'status': 'answer', 'kind': 'judgement', 'value': 'pass', 'evidence_ids': []})}}]})
            def client_factory(*args, **kwargs):
                return original_client(transport=httpx.MockTransport(respond))
            def work(index):
                destination = output / str(index)
                destination.mkdir()
                gateway = study.StudyGateway(self.config, output, prompt, coordinator)
                try:
                    gateway.generate(str(index), '[]', destination)
                    return gateway.budget()
                finally:
                    gateway.close()
            with patch.object(study.old, 'dotenv_values', return_value={'OPENROUTER_API_KEY': 'fixture'}), \
                    patch.object(study.old.httpx, 'Client', side_effect=client_factory), \
                    ThreadPoolExecutor(max_workers=4) as pool:
                rows = list(pool.map(work, range(8)))
            self.assertTrue(all(row['calls'] == 1 and row['reported_usd'] == 0.000001 for row in rows))
            self.assertEqual(coordinator.budget()['calls'], 8)
            self.assertAlmostEqual(coordinator.budget()['reported_usd'], 0.000008)
            self.assertEqual(json.loads((output / 'campaign.json').read_text())['attempts'], 8)

    def test_concurrent_run_cap_blocks_before_campaign_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.config.update(campaign_ledger_path=str(Path(tmp) / 'campaign.json'), max_llm_calls=3)
            coordinator = study.RunBudget(self.config, Path(tmp))
            def reserve(index):
                try:
                    coordinator.reserve(0.001)
                    return True
                except study.CriticalAbort:
                    return False
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(sum(pool.map(reserve, range(20))), 3)
            self.assertEqual(coordinator.budget()['calls'], 3)
            self.assertEqual(json.loads((Path(tmp) / 'campaign.json').read_text())['attempts'], 3)

    def test_critical_abort_drains_inflight_and_preserves_grid(self):
        barrier = threading.Barrier(4)
        stopped = threading.Event()
        rows = [{'condition': 'llm', 'status': 'error', 'error_type': 'NotExecuted',
                 'source_answerable': True, 'answer': None, 'cost': {}} for _ in range(12)]
        def worker(index):
            barrier.wait(timeout=5)
            if index == 0:
                stopped.set()
            else:
                stopped.wait(timeout=5)
            return {'status': 'error' if index == 0 else 'ok', 'cost': {'calls': 1}}, (
                study.CriticalAbort('FixtureBlocker') if index == 0 else None)
        for index, result, critical in study.bounded_results(range(12), worker, 4, stopped):
            rows[index].update(result)
        self.assertEqual(sum(row['cost'].get('calls', 0) for row in rows), 4)
        self.assertEqual(sum(row['cost'] == {} for row in rows), 8)
        self.assertEqual(study.summarize(rows)['llm']['total'], 12)

    def test_directory_failure_is_an_explicit_row_error(self):
        source, first = self.evidence('clean')
        with tempfile.TemporaryDirectory() as tmp, patch.object(Path, 'mkdir', side_effect=PermissionError('fixture')):
            result, critical = study.execute_row((source, first, self.subject), 'none', self.shapes,
                                                  Path(tmp) / 'row', self.config, Path(tmp), Path(tmp) / 'prompt', None)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_type'], 'PermissionError')
        self.assertIsInstance(critical, study.CriticalAbort)

    def test_client_close_failure_preserves_completed_trace_and_cost(self):
        source, first = self.evidence('clean')
        completed = {'status': 'ok', 'answer': {'status': 'answer', 'kind': 'parent', 'value': self.ids[1]},
                     'trace': [{'attempt': 0, 'judgement': 'pass'}], 'runtime_ms': 2,
                     'cost': {'calls': 1, 'reported_usd': 0.001}}
        class CloseFailure:
            def close(self):
                raise OSError('fixture close failure')
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(study, 'StudyGateway', return_value=CloseFailure()), \
                patch.object(study, 'run_condition', return_value=(completed, None)):
            result, critical = study.execute_row((source, first, self.subject), 'llm', self.shapes,
                                                  Path(tmp) / 'row', self.config, Path(tmp), Path(tmp) / 'prompt', None)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['cleanup_error_type'], 'OSError')
        self.assertEqual(result['trace'], [{'attempt': 0, 'judgement': 'pass'}])
        self.assertEqual(result['cost'], {'calls': 1, 'reported_usd': 0.001})
        self.assertEqual(result['answer_before_cleanup_error']['status'], 'answer')
        self.assertIsInstance(critical, study.CriticalAbort)

    def test_unexpected_future_failure_drains_other_completed_calls(self):
        barrier = threading.Barrier(4)
        stopped = threading.Event()
        def worker(index):
            barrier.wait(timeout=5)
            if index == 0:
                raise OSError('unexpected fixture worker failure')
            self.assertTrue(stopped.wait(timeout=5))
            return {'status': 'ok', 'cost': {'calls': 1}}, None
        returned = list(study.bounded_results(range(12), worker, 4, stopped))
        self.assertEqual({index for index, _, _ in returned}, {0, 1, 2, 3})
        failed = next(result for index, result, _ in returned if index == 0)
        self.assertEqual(failed['error_type'], 'OSError')
        self.assertEqual(sum(result['cost'].get('calls', 0) for _, result, _ in returned), 3)
        self.assertTrue(stopped.is_set())

    def test_attempt_limit_independent_of_dollars(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'ledger.json'
            study.atomic_write(path, {'attempts': 3200, 'reserved_usd': 0.01, 'reservations': []})
            with self.assertRaises(study.CriticalAbort):
                study.CampaignBudget(path).reserve(0.0001, 'run')

    def test_evaluation_hash_guard(self):
        payload = b'invalid-json-is-not-opened-by-validation'
        self.config.update(stage='evaluation', frozen=True, expected_dataset_sha256=hashlib.sha256(payload).hexdigest())
        study.validate_config(self.config, payload)
        for wrong, limit in [(b'changed', None), (payload, 1)]:
            with self.assertRaises(ValueError):
                study.validate_config(self.config, wrong, limit)
        self.config['frozen'] = False
        with self.assertRaises(ValueError):
            study.validate_config(self.config, payload)

    def test_structured_projection_contains_only_current_evidence(self):
        _, first = self.evidence('retrieval_type_missing')
        payload = study.evidence_payload(first, self.subject, 'structured')
        self.assertEqual(payload['facts'], study.core.canonical(first))
        self.assertEqual(payload['parent_candidates'][0]['types'], [])
        self.assertEqual(set(payload), {'subject', 'facts', 'parent_candidates', 'reason_literals'})
        for forbidden in ('gold', 'variant', 'source_answerable', 'raw_entities'):
            self.assertNotIn(forbidden, json.dumps(payload))
        _, absent = self.evidence('retrieval_relation_missing')
        self.assertEqual(study.evidence_payload(absent, self.subject, 'structured')['parent_candidates'], [])

    def test_hybrid_intersection_and_short_circuit(self):
        for variant, llm, expected, calls in [('wrong_class', 'pass', 'abstain', 0),
                                              ('clean', 'fail', 'abstain', 1),
                                              ('clean', 'pass', 'answer', 1),
                                              ('source_relation_missing', 'pass', 'abstain', 2)]:
            with self.subTest(variant=variant, llm=llm), tempfile.TemporaryDirectory() as tmp:
                source, first = self.evidence(variant)
                with patch.object(study, 'model_judge', return_value=(llm, {})) as judge:
                    row, critical = study.run_condition(source, first, self.subject, 'hybrid', self.shapes, Path(tmp))
                self.assertIsNone(critical)
                self.assertEqual(row['answer']['status'], expected)
                self.assertEqual(judge.call_count, calls)

    def test_llm_and_hybrid_use_identical_input(self):
        source, first = self.evidence('clean')
        requests = []
        class FakeGateway:
            def generate(self, question, evidence, destination):
                requests.append((question, evidence))
                return {'status': 'answer', 'kind': 'judgement', 'value': 'pass', 'evidence_ids': [],
                        'checks': {'cardinality': 'pass', 'parent_type': 'pass', 'exception_reason': 'not_applicable'}}, {}
        with tempfile.TemporaryDirectory() as tmp:
            for condition in ('llm', 'hybrid'):
                study.run_condition(source, first, self.subject, condition, self.shapes,
                                    Path(tmp) / condition, FakeGateway(), 'structured')
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0], requests[1])

    def test_failure_trace_and_denominator(self):
        source, first = self.evidence('clean')
        with tempfile.TemporaryDirectory() as tmp, patch.object(study, 'model_judge', side_effect=ValueError('fixture')):
            row, critical = study.run_condition(source, first, self.subject, 'llm', self.shapes, Path(tmp))
        self.assertIsNone(critical)
        self.assertEqual(row['status'], 'error')
        self.assertEqual(len(row['trace']), 1)
        row.update(condition='llm', source_answerable=True)
        summary = study.summarize([row, {**row, 'error_type': 'NotExecuted'}])['llm']
        self.assertEqual((summary['total'], summary['errors'], summary['accuracy_all']), (2, 2, 0))


if __name__ == '__main__':
    unittest.main()
