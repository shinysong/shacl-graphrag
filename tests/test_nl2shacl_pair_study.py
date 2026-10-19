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
from nl2shacl_pair_study import Runner, Stop, atomic


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.now = datetime(2026, 10, 16, 12, tzinfo=UTC)
        self.cfg = dict(model='test/model', max_calls=2, max_usd=1, max_tokens=10,
                        input_price_per_million=.5, output_price_per_million=3.6,
                        deadline_utc='2026-10-16T13:00:00Z', external_ledgers=[], daily_cap=500)
        self.rows = [dict(id='case1', language=lang, system_prompt='Generate Turtle.', user_prompt='Input') for lang in ('en', 'ko')]
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
        self.assertFalse(request['reasoning']['enabled'])

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
        for field, value in [('max_calls', 121), ('max_usd', 5.01)]:
            original = self.cfg[field]
            self.cfg[field] = value
            with self.assertRaisesRegex(ValueError, 'CampaignLimitExceedsAuthorization'):
                self.runner()
            self.cfg[field] = original

    def test_missing_external_ledger_fails_closed(self):
        self.cfg['external_ledgers'] = [str(self.out / 'missing.json')]
        with self.assertRaises(FileNotFoundError):
            self.runner().run()
        self.assertFalse(self.calls)


if __name__ == '__main__':
    unittest.main()
