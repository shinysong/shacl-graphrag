"""Offline integration of workbench parsing and the actual accounting Runner."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from rule_workbench.core import demo_project
from rule_workbench import transport


class WorkbenchTransportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.cfg = {
            'schema_version': 1,
            'models': {'test/model': {'input_price_per_million': .5, 'output_price_per_million': 3}},
            'max_calls': 2, 'daily_cap': 1000, 'max_usd': 1,
            'max_reported_usd': 1, 'max_tokens': 1000,
            'deadline_utc': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            'external_ledgers': [], 'timeout_seconds': 5,
        }
        self.write_config()
        # Do not inspect or lock real campaign ledgers, read .env, or use a live client.
        for name, value in [('ROOT', self.root), ('WORK', self.work)]:
            patcher = patch.object(transport, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.project = demo_project()
        self.documents = [{'name': 'policy.md', 'segments': [{'text': 'Amount is required.', 'line': 4}]}]
        self.content = json.dumps({'rules': [{
            'text': 'Require amount', 'segment_id': 'd0:s0', 'quote': 'Amount is required.',
            'table_id': 'suppliers', 'column': '금액', 'kind': 'required',
            'params': {'min': None, 'max': None, 'values': [], 'other_column': '',
                       'target_table': '', 'target_column': ''},
            'rationale': 'Explicit requirement', 'questions': [],
        }], 'notes': []})
        self.calls = []

    def write_config(self):
        (self.work / 'session.json').write_text(json.dumps(self.cfg))

    def client(self, *, status=200, finish='stop'):
        def respond(request):
            self.calls.append(request)
            # Reservation must already exist when a request reaches the transport.
            self.assertEqual(transport.budget_status()['attempts'], len(self.calls))
            if status != 200:
                return httpx.Response(status, json={'error': {'message': 'offline failure'}})
            return httpx.Response(200, json={
                'model': 'test/model', 'usage': {'cost': .00001},
                'choices': [{'finish_reason': finish, 'message': {'content': self.content}}],
            })
        client = httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(client.close)
        return client

    def generate(self, client, documents=None):
        return transport.generate_candidates(self.project, self.documents if documents is None else documents,
                                             'test/model', work=self.work, client=client)

    def test_actual_runner_success_and_cached_reuse_exclude_source_rows(self):
        self.project['tables'][0]['rows'][0]['금액'] = 'ROW_SECRET'
        original = copy.deepcopy(self.project)
        client = self.client()
        first = self.generate(client)
        second = self.generate(client)
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(first['cached'])
        self.assertTrue(second['cached'])
        self.assertEqual(first['request_id'], second['request_id'])
        self.assertEqual(first['rules'][0]['status'], 'draft')
        self.assertEqual(first['rules'][0]['source']['line'], 4)
        self.assertEqual(self.project, original)
        request = json.loads(self.calls[0].content)
        self.assertEqual(request['response_format']['type'], 'json_schema')
        self.assertTrue(request['response_format']['json_schema']['strict'])
        self.assertFalse(request['provider']['allow_fallbacks'])
        self.assertNotIn('ROW_SECRET', self.calls[0].content.decode())
        self.assertEqual(transport.budget_status()['attempts'], 1)
        self.assertEqual(transport.budget_status()['unknown_cost_attempts'], 0)

    def test_failed_request_and_changed_request_never_retry_unresolved_cost(self):
        client = self.client(status=503)
        for _ in range(2):
            with self.assertRaises(ValueError):
                self.generate(client)
        changed = copy.deepcopy(self.documents)
        changed[0]['segments'][0]['text'] += ' New clause.'
        with self.assertRaises(ValueError):
            self.generate(client, changed)
        self.assertEqual(len(self.calls), 1)
        status = transport.budget_status()
        self.assertEqual(status['attempts'], 1)
        self.assertEqual(status['unknown_cost_attempts'], 1)
        self.assertGreater(status['reserved_usd'], 0)
        self.assertEqual(len(list((self.work / 'calls').glob('*/call-0000/failure.json'))), 1)

    def test_truncation_preserved_without_partial_import_or_second_call(self):
        original = copy.deepcopy(self.project)
        client = self.client(finish='length')
        for _ in range(2):
            with self.assertRaises(ValueError):
                self.generate(client)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.project, original)
        self.assertFalse(list((self.work / 'calls').glob('*/parsed.json')))
        failures = list((self.work / 'calls').glob('*/parse-failure.json'))
        self.assertEqual(json.loads(failures[0].read_text())['reason'], 'NonStopFinishReason')
        self.assertEqual(transport.budget_status()['attempts'], 1)

    def test_cumulative_call_cap_across_distinct_request_directories(self):
        self.cfg['max_calls'] = 1
        self.write_config()
        client = self.client()
        self.generate(client)
        changed = copy.deepcopy(self.documents)
        changed[0]['segments'][0]['text'] += ' New clause.'
        with self.assertRaisesRegex(ValueError, 'BudgetLimit'):
            self.generate(client, changed)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(transport.budget_status()['attempts'], 1)
        self.assertTrue(self.generate(client)['cached'])

    def test_dollar_and_deadline_limits_stop_before_http(self):
        client = self.client()
        self.cfg['max_usd'] = .00000001
        self.write_config()
        with self.assertRaisesRegex(ValueError, 'BudgetLimit'):
            self.generate(client)
        self.cfg['max_usd'] = 1
        self.cfg['deadline_utc'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.write_config()
        with self.assertRaisesRegex(ValueError, 'Deadline'):
            self.generate(client)
        self.assertEqual(self.calls, [])
