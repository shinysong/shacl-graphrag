"""Transport-mocked budget and restart checks; never calls OpenRouter."""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
import sys
import tempfile
import unittest

import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from nl2shacl_multimodel import Runner, Stop, atomic, canonical_digest


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.now = datetime(2026, 10, 16, 12, tzinfo=UTC)
        self.cfg = dict(models={'test/model': {'input_price_per_million':.5, 'output_price_per_million':3.6}}, max_calls=2, max_usd=1, max_reported_usd=1, max_tokens=10,
                        deadline_utc='2026-10-16T13:00:00Z', external_ledgers=[], daily_cap=500)
        self.rows = [dict(model='test/model', id='case1', language=lang, system_prompt='Generate Turtle.', user_prompt='Input') for lang in ('en', 'ko')]
        self.cfg['inputs_sha256'] = hashlib.sha256(json.dumps(self.rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.calls = []

    def runner(self, handler=None, rows=None):
        def respond(request):
            self.calls.append(request)
            ledger = json.loads((self.out / 'campaign-budget.json').read_text())
            self.assertEqual(ledger['attempts'], len(self.calls))
            if handler:
                return handler(request)
            return httpx.Response(200, json={'model': 'test/model', 'usage': {'cost': .0001}, 'choices': [{'message': {'content': '```turtle\n:a :b :c .\n```'}}]})
        client = httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(client.close)
        return Runner(self.cfg, self.rows if rows is None else rows, self.out, client, lambda: self.now)

    def test_success_restart_and_raw_output(self):
        runner = self.runner()
        self.assertEqual(runner.run()['completed_this_run'], 2)
        self.assertEqual(self.runner().run()['completed_this_run'], 0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual((self.out / 'call-0000/output.ttl').read_text(), '```turtle\n:a :b :c .\n```')
        request = json.loads(self.calls[0].content)
        self.assertFalse(request['provider']['allow_fallbacks'])
        self.assertNotIn('reasoning', request)
        self.assertNotIn('temperature', request)

    def test_campaign_cap_and_new_inputs(self):
        self.cfg['max_calls'] = 1
        with self.assertRaisesRegex(Stop, 'BudgetLimit'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)
        with self.assertRaisesRegex(ValueError, 'InputDigestMismatch'):
            self.runner(rows=[dict(self.rows[0], id='new')]).run()

    def test_dollar_cap_before_call(self):
        self.cfg['max_usd'] = .000001
        with self.assertRaisesRegex(Stop, 'BudgetLimit'):
            self.runner().run()
        self.assertFalse(self.calls)

    def test_deadline(self):
        self.cfg['deadline_utc'] = self.now.isoformat()
        with self.assertRaisesRegex(Stop, 'Deadline'):
            self.runner().run()
        self.assertFalse(self.calls)

    def test_duplicates_invalidated_before_call(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.runner(rows=[self.rows[0], self.rows[0]])
        self.assertFalse(self.calls)

    def test_error_reserved_and_never_retried(self):
        def fail(request):
            raise httpx.ReadTimeout('SECRET SHOULD NEVER BE LOGGED')
        with self.assertRaisesRegex(Stop, 'CallFailed'):
            self.runner(fail).run()
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            self.runner().run()
        saved = (self.out / 'call-0000/failure.json').read_text()
        self.assertNotIn('SECRET', saved)
        ledger = json.loads((self.out / 'campaign-budget.json').read_text())
        self.assertIsNone(ledger['reservations'][0]['reported_usd'])
        self.assertGreater(ledger['reservations'][0]['upper_usd'], 0)

    def test_unknown_cost_preserves_response_and_output(self):
        def unknown(request):
            return httpx.Response(200, json={'model': 'test/model', 'choices': [{'message': {'content': ':a :b :c .'}}]})
        with self.assertRaisesRegex(Stop, 'CallFailed'):
            self.runner(unknown).run()
        self.assertTrue((self.out / 'call-0000/response.json').exists())
        self.assertTrue((self.out / 'call-0000/output.ttl').exists())
        self.assertEqual(len(self.calls), 1)

    def test_cross_ledger_utc_count_and_own_count(self):
        external = self.out / 'old.json'
        atomic(external, {'reservations': [{'at': '2026-10-17T01:00:00+14:00'}]})
        self.cfg.update(external_ledgers=[str(external)], daily_cap=2)
        with self.assertRaisesRegex(Stop, 'BudgetLimit'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def test_interrupted_reservation_consumes_id_and_money(self):
        runner = self.runner()
        runner.reserve(self.rows[0], .99)
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            runner.run()
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            runner.reserve(self.rows[1], .02)
        self.assertFalse(self.calls)

    def test_frozen_inputs_reject_changes(self):
        variants = [
            [dict(self.rows[0], user_prompt='changed'), self.rows[1]],
            list(reversed(self.rows)),
            self.rows + [dict(self.rows[0], id='new')],
            self.rows[:1],
        ]
        for rows in variants:
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, 'InputDigestMismatch'):
                self.runner(rows=rows)
        self.assertFalse(self.calls)

    def test_consumed_row_hash_checked_before_skip(self):
        runner = self.runner()
        runner.run()
        ledger = json.loads(runner.ledger.read_text())
        ledger['reservations'][0]['input_sha256'] = 'altered'
        atomic(runner.ledger, ledger)
        with self.assertRaisesRegex(Stop, 'ConsumedInputMismatch'):
            runner.run()
        self.assertEqual(len(self.calls), 2)

    def test_authorization_limits(self):
        for field, value in [('max_calls', 601), ('max_usd', 50.01), ('max_reported_usd', 10.01), ('daily_cap', 1001), ('max_tokens', 8193)]:
            original = self.cfg[field]
            self.cfg[field] = value
            with self.assertRaisesRegex(ValueError, 'AuthorizationLimit'):
                self.runner()
            self.cfg[field] = original

    def test_missing_external_ledger_fails_closed(self):
        self.cfg['external_ledgers'] = [str(self.out / 'missing.json')]
        with self.assertRaises(FileNotFoundError):
            self.runner().run()
        self.assertFalse(self.calls)


    def test_limit_counts_new_attempts_and_multimodel_key(self):
        self.rows[1] = dict(self.rows[0], model='other/model')
        self.cfg['models']['other/model'] = dict(self.cfg['models']['test/model'], temperature=0, reasoning={'enabled': False}, response_aliases=['other/alias'])
        self.cfg['inputs_sha256'] = canonical_digest(self.rows)
        def respond(request):
            payload = json.loads(request.content)
            if payload['model'] == 'other/model':
                self.assertEqual(payload['temperature'], 0)
                self.assertFalse(payload['reasoning']['enabled'])
            return httpx.Response(200, json={'model': 'other/alias' if payload['model'] == 'other/model' else 'test/model', 'provider':'mock', 'usage':{'cost':.0001}, 'choices':[{'message':{'content':'raw'}}]})
        self.assertEqual(self.runner(respond).run(limit=1)['completed_this_run'], 1)
        self.assertEqual(self.runner(respond).run(limit=1)['completed_this_run'], 1)
        self.assertEqual(len(self.calls), 2)
        saved = json.loads((self.out / 'call-0001/metadata.json').read_text())
        self.assertEqual(saved['provider'], 'mock')
        self.assertGreaterEqual(saved['latency_seconds'], 0)

    def test_reported_guard_admits_using_upper_not_expected_cost(self):
        upper = self.runner().request(self.rows[0])[1]
        self.cfg['max_reported_usd'] = upper + .00005
        with self.assertRaisesRegex(Stop, 'BudgetLimit'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def test_nonrefunded_upper_cap(self):
        upper = self.runner().request(self.rows[0])[1]
        self.cfg['max_usd'] = upper * 1.9
        with self.assertRaisesRegex(Stop, 'BudgetLimit'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def test_configuration_hash_frozen(self):
        self.runner().run(limit=1)
        self.cfg['models']['test/model']['temperature'] = 0
        with self.assertRaisesRegex(Stop, 'LedgerMismatch'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def test_wrong_model_stops_all(self):
        def wrong(request):
            return httpx.Response(200, json={'model':'wrong/model', 'usage':{'cost':.0001}, 'choices':[{'message':{'content':'raw'}}]})
        with self.assertRaisesRegex(Stop, 'CallFailed'):
            self.runner(wrong).run()
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def test_excess_cost_never_retried(self):
        def excess(request):
            return httpx.Response(200, json={'model':'test/model', 'usage':{'cost':2}, 'choices':[{'message':{'content':'raw'}}]})
        with self.assertRaisesRegex(Stop, 'CallFailed'):
            self.runner(excess).run()
        ledger = json.loads((self.out / 'campaign-budget.json').read_text())
        self.assertEqual(ledger['reservations'][0]['reported_usd'], 2)
        self.assertEqual(ledger['reservations'][0]['status'], 'failed')
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def test_deadline_between_reservation_and_http(self):
        runner = self.runner()
        moments = iter([self.now, datetime(2026, 10, 16, 14, tzinfo=UTC)])
        runner.now = lambda: next(moments)
        with self.assertRaisesRegex(Stop, 'CallFailed'):
            runner.run()
        self.assertFalse(self.calls)
        self.assertEqual(runner.load()['attempts'], 1)
        self.assertEqual(runner.load()['reservations'][0]['status'], 'failed')

    def test_request_upper_uses_utf8_bytes_and_framing(self):
        self.rows[0]['user_prompt'] = '한글' * 10
        self.cfg['inputs_sha256'] = canonical_digest(self.rows)
        request, upper = self.runner().request(self.rows[0])
        expected = ((len(json.dumps(request, ensure_ascii=False).encode()) + 4096) * .5 + 10 * 3.6) / 1e6
        self.assertAlmostEqual(upper, expected, places=11)

    def test_explicit_reasoning_without_temperature(self):
        self.cfg['models']['test/model']['reasoning'] = {'effort':'none'}
        request, _ = self.runner().request(self.rows[0])
        self.assertNotIn('temperature', request)
        self.assertEqual(request['reasoning'], {'effort':'none'})

    def test_missing_external_on_completed_resume(self):
        ext = self.out / 'external.json'
        atomic(ext, {'reservations': []})
        self.cfg['external_ledgers'] = [str(ext)]
        self.runner().run()
        ext.unlink()
        with self.assertRaises(FileNotFoundError):
            self.runner().run()
        self.assertEqual(len(self.calls), 2)

    def predecessor(self, **fields):
        path = self.out / 'predecessor.json'
        reservation = dict(at=self.now.isoformat(), upper_usd=.2,
                           reported_usd=.01, status='completed')
        reservation.update(fields)
        atomic(path, {'attempts': 1, 'reservations': [reservation]})
        self.cfg['predecessor_ledgers'] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()}
        return path

    def test_predecessor_hash_checked_every_admission(self):
        path = self.predecessor()
        runner = self.runner()
        runner.run(limit=1)
        path.write_bytes(path.read_bytes() + b'\n')
        # Hash checked even before skipping the already completed input.
        with self.assertRaisesRegex(Stop, 'PredecessorDigestMismatch'):
            runner.run()
        self.assertEqual(len(self.calls), 1)

    def test_predecessor_consumes_campaign_call_cap(self):
        path = self.predecessor()
        original = path.read_bytes()
        with self.assertRaisesRegex(Stop, 'BudgetLimit'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(path.read_bytes(), original)

    def test_predecessor_nonrefunded_cost_cap(self):
        self.predecessor()
        self.cfg['max_usd'] = .2
        with self.assertRaisesRegex(Stop, 'BudgetLimit'):
            self.runner().run()
        self.assertFalse(self.calls)

    def test_predecessor_reported_cost_cap(self):
        self.predecessor()
        self.cfg['max_reported_usd'] = .01
        with self.assertRaisesRegex(Stop, 'BudgetLimit'):
            self.runner().run()
        self.assertFalse(self.calls)

    def test_predecessor_daily_count_without_double_counting(self):
        path = self.predecessor()
        self.cfg.update(max_calls=3, daily_cap=2, external_ledgers=[str(path), str(path)])
        with self.assertRaisesRegex(Stop, 'BudgetLimit'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def test_predecessor_daily_count_without_external_listing(self):
        self.predecessor()
        self.cfg.update(daily_cap=1)
        with self.assertRaisesRegex(Stop, 'BudgetLimit'):
            self.runner().run()
        self.assertFalse(self.calls)

    def test_unresolved_predecessor_fails_closed(self):
        self.predecessor(status='failed', reported_usd=None)
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            self.runner().run()
        self.assertFalse(self.calls)

    def test_invalid_predecessor_definitions(self):
        for mapping in ([], {'relative.json': 'a' * 64}, {str(self.out / 'old'): 'bad'},
                        {str(self.out / 'campaign-budget.json'): 'a' * 64}):
            self.cfg['predecessor_ledgers'] = mapping
            with self.subTest(mapping=mapping), self.assertRaisesRegex(ValueError, 'Predecessor'):
                self.runner()

    def test_missing_predecessor_fails_closed(self):
        path = self.predecessor()
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.runner().run()
        self.assertFalse(self.calls)

    def test_reasoning_8192_output_and_byte_bound(self):
        self.cfg['max_tokens'] = 8192
        self.cfg['models']['test/model']['reasoning'] = {'effort': 'medium'}
        request, upper = self.runner().request(self.rows[0])
        self.assertEqual(request['max_tokens'], 8192)
        self.assertEqual(request['reasoning'], {'effort': 'medium'})
        expected = ((len(json.dumps(request, ensure_ascii=False).encode()) + 4096) * .5 + 8192 * 3.6) / 1e6
        self.assertAlmostEqual(upper, expected, places=11)

    def test_timeout_default_and_configured_bounded_by_deadline(self):
        for timeout, deadline, expected in [(None, '13:00:00', 60), (180, '13:00:00', 180), (180, '12:00:30', 30)]:
            with self.subTest(timeout=timeout, deadline=deadline):
                self.cfg['deadline_utc'] = '2026-10-16T' + deadline + 'Z'
                if timeout is not None:
                    self.cfg['timeout_seconds'] = timeout
                runner = self.runner()
                # Each variant has its own bound ledger and output directory.
                runner.output = self.out / str(expected)
                runner.ledger = runner.output / 'campaign-budget.json'
                def respond(request):
                    self.assertEqual(request.extensions['timeout']['read'], expected)
                    return httpx.Response(200, json={'model': 'test/model', 'usage': {'cost': .0001}, 'choices': [{'message': {'content': 'raw'}}]})
                with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                    runner.client = client
                    runner.run(limit=1)

    def test_timeout_authorization_limits(self):
        for timeout in (0, -1, 181, True, '180', float('inf')):
            self.cfg['timeout_seconds'] = timeout
            with self.subTest(timeout=timeout), self.assertRaisesRegex(ValueError, 'AuthorizationLimit:timeout_seconds'):
                self.runner()

    def test_eight_model_inputs_supported(self):
        self.cfg['models'] = {'test/model' + str(i): self.cfg['models']['test/model'].copy() for i in range(8)}
        rows = [dict(self.rows[0], model=model) for model in self.cfg['models']]
        self.cfg['inputs_sha256'] = canonical_digest(rows)
        self.assertEqual(len(self.runner(rows=rows).rows), 8)


class IsolationTests(unittest.TestCase):
    setUp_base = RunnerTests.setUp
    runner = RunnerTests.runner
    predecessor = RunnerTests.predecessor
    def setUp(self):
        self.setUp_base()
        self.cfg['failure_policy'] = 'isolate_transient_models'
        self.cfg['models']['other/model'] = self.cfg['models']['test/model'].copy()
        self.rows += [dict(self.rows[0], model='other/model')]
        self.cfg.update(max_calls=10, inputs_sha256=canonical_digest(self.rows))

    def responder(self, failure):
        def respond(request):
            model = json.loads(request.content)['model']
            if model == 'test/model':
                if isinstance(failure, Exception):
                    raise failure
                return failure
            return httpx.Response(200, json={'model': model, 'usage': {'cost': .0001}, 'choices': [{'message': {'content': 'raw'}}]})
        return respond

    def test_isolation_quarantine_persists_and_limit_counts_failures(self):
        result = self.runner(self.responder(httpx.ReadTimeout('SECRET'))).run(limit=1)
        self.assertEqual(result['attempted_this_run'], 1)
        self.assertEqual(result['completed_this_run'], 0)
        result = self.runner(self.responder(httpx.ReadTimeout('SECRET'))).run()
        self.assertEqual(result['completed_this_run'], 1)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.runner().run()['attempted_this_run'], 0)
        self.assertNotIn('SECRET', (self.out / 'call-0000/failure.json').read_text())

    def test_isolation_http429_other_model_continues(self):
        result = self.runner(self.responder(httpx.Response(429, text='rate limited'))).run()
        self.assertEqual(result['completed_this_run'], 1)
        self.assertEqual(result['attempted_this_run'], 2)
        ledger = json.loads((self.out / 'campaign-budget.json').read_text())
        self.assertEqual(ledger['reservations'][0]['isolated_failure'], 'HTTP429')
        self.assertIsNone(ledger['reservations'][0]['reported_usd'])

    def test_isolation_connection_failure(self):
        result = self.runner(self.responder(httpx.ConnectError('SECRET'))).run()
        self.assertEqual(result['completed_this_run'], 1)
        self.assertEqual(len(self.calls), 2)

    def test_isolation_unsafe_http_stops(self):
        with self.assertRaisesRegex(Stop, 'CallFailed'):
            self.runner(self.responder(httpx.Response(500, json={'error':'server'}))).run()
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def test_isolation_429_excess_cost_stops(self):
        with self.assertRaisesRegex(Stop, 'CallFailed'):
            self.runner(self.responder(httpx.Response(429, json={'usage': {'cost': 2}}))).run()
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def test_isolation_429_model_mismatch_stops(self):
        with self.assertRaisesRegex(Stop, 'CallFailed'):
            self.runner(self.responder(httpx.Response(429, json={'model': 'wrong/model'}))).run()
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def test_isolation_inflight_blocks_all_models(self):
        runner = self.runner()
        runner.reserve(self.rows[0], .01)
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            runner.run()
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            runner.reserve(self.rows[-1], .01)
        self.assertFalse(self.calls)

    def test_isolation_unknown_success_cost_remains_blocker(self):
        response = httpx.Response(200, json={'model': 'test/model', 'choices': [{'message': {'content': 'raw'}}]})
        with self.assertRaisesRegex(Stop, 'CallFailed'):
            self.runner(self.responder(response)).run()
        with self.assertRaisesRegex(Stop, 'UnresolvedPriorAttempt'):
            self.runner().run()
        self.assertEqual(len(self.calls), 1)

    def approved_predecessor(self):
        path = self.predecessor(**{k: self.rows[0][k] for k in ('model', 'id', 'language')},
                                status='failed', reported_usd=None, input_sha256=canonical_digest(self.rows[0]))
        reservation = json.loads(path.read_text())['reservations'][0]
        self.cfg['predecessor_failure_allowlist'] = [dict(ledger=str(path), reservation_sha256=canonical_digest(reservation), failure_kind='HTTP429')]
        return path

    def test_isolation_predecessor_skip_and_manual_model_readmission(self):
        path = self.approved_predecessor()
        original = path.read_bytes()
        result = self.runner().run(limit=1)
        self.assertEqual(result['completed_this_run'], 1)
        self.assertEqual(json.loads((self.out / 'campaign-budget.json').read_text())['reservations'][0]['language'], 'ko')
        self.assertEqual(original, path.read_bytes())

    def test_isolation_unknown_cost_charged_to_both_caps(self):
        self.approved_predecessor()
        for cap in ('max_usd', 'max_reported_usd'):
            with self.subTest(cap=cap):
                self.cfg[cap] = .2
                with self.assertRaisesRegex(Stop, 'BudgetLimit'):
                    self.runner().run()
                self.cfg[cap] = 1
        self.assertFalse(self.calls)

    def test_isolation_predecessor_allowlist_tamper(self):
        path = self.approved_predecessor()
        saved = json.loads(path.read_text())
        saved['reservations'][0]['upper_usd'] = .01
        atomic(path, saved)
        with self.assertRaisesRegex(Stop, 'PredecessorDigestMismatch'):
            self.runner().run()
        self.cfg['predecessor_ledgers'][str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(Stop, 'FailureAllowlistMismatch'):
            self.runner().run()
        self.assertFalse(self.calls)

    def test_isolation_predecessor_input_mismatch(self):
        self.approved_predecessor()
        self.rows[0]['user_prompt'] = 'altered'
        self.cfg['inputs_sha256'] = canonical_digest(self.rows)
        with self.assertRaisesRegex(Stop, 'ConsumedInputMismatch'):
            self.runner().run()
        self.assertFalse(self.calls)


if __name__ == '__main__':
    unittest.main()
