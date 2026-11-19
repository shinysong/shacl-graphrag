"""Actual PublicGateway and SQLite integration with mocked HTTP, no network."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import httpx
import test_workspace_preflight
from scripts.workspace_proposal_campaign import execute, export_attempts
from scripts.workspace_proposal_preflight import inspect


class CampaignHTTPTests(unittest.TestCase):
    def test_gateway_billing_and_retention(self):
        for scenario in ('success', 'success_low', 'missing_cost', 'truncated', 'http_error'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                messages, config = test_workspace_preflight.PreflightTests().fixture(root)
                manifest = json.loads((root/'manifest.json').read_text())
                raw = (root/'one-messages.json').read_bytes()
                second_messages = [{'role':'user','content':'Distinct second packet'}]
                second_raw = json.dumps(second_messages).encode()
                (root/'two-messages.json').write_bytes(second_raw)
                manifest['records'].append(dict(manifest['records'][0], id='two', messages_sha256=hashlib.sha256(second_raw).hexdigest()))
                (root/'manifest.json').write_text(json.dumps(manifest))
                if scenario=='success_low':
                    config['reasoning_effort']='low'
                    endpoint=json.loads((root/'endpoints.json').read_text())
                    endpoint['data']['endpoints'][0]['supported_parameters'].append('reasoning')
                    (root/'endpoints.json').write_text(json.dumps(endpoint))
                config['max_calls'] = 2
                report = inspect(root, root/'endpoints.json', config)
                auth = {k: report[k] for k in ('config_sha256', 'manifest_sha256', 'endpoints_sha256')}
                auth.update(approved=True, approval_reference='Offline mock only',
                            deadline=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat())
                directory = root/'run'
                key = 'FAKE_TEST_KEY_NEVER_REAL'
                requests = []
                observations = []
                response_message = {'role': 'assistant', 'content': '{"relation_assessments":[]}'}

                def respond(request):
                    # A real reservation and case mapping must exist before HTTP.
                    with sqlite3.connect(directory/'state.sqlite') as db:
                        rows = db.execute("SELECT runs.config,calls.status FROM runs JOIN calls ON runs.id=calls.run_id ORDER BY calls.at").fetchall()
                    observations.append(rows)
                    payload = json.loads(request.content)
                    requests.append(payload)
                    body = {'choices': [{'finish_reason': 'length' if scenario=='truncated' else 'stop',
                                         'message': response_message}],
                            'usage': {} if scenario=='missing_cost' else {'cost': '0.001'},
                            'model': 'test/model', 'provider': 'test-provider'}
                    return httpx.Response(503 if scenario=='http_error' else 200, json=body)

                real_client = httpx.Client
                def client(**kwargs):
                    return real_client(transport=httpx.MockTransport(respond), **kwargs)
                with patch('apps.factory_lab.public_runtime.httpx.Client', side_effect=client), \
                     patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')):
                    result = execute(root, root/'endpoints.json', config, auth, directory, key)
                count = 2 if scenario.startswith('success') else 1
                self.assertEqual(len(requests), count)
                for index, payload in enumerate(requests):
                    rows = observations[index]
                    self.assertEqual(len(rows), index+1)
                    self.assertEqual(rows[-1][1], 'reserved')
                    self.assertEqual(json.loads(rows[-1][0])['case_id'], ('one','two')[index])
                    self.assertEqual(payload['messages'], (messages,second_messages)[index])
                    self.assertEqual(payload['temperature'], 0)
                    self.assertEqual(payload['max_tokens'], config['max_tokens'])
                    if scenario=='success_low':self.assertEqual(payload['reasoning'],{'effort':'low'})
                    else:self.assertNotIn('reasoning',payload)
                    self.assertFalse(payload['provider']['allow_fallbacks'])
                    self.assertEqual(payload['provider']['order'], [config['provider']])
                self.assertEqual(len(result['attempts']), count)
                self.assertEqual(result['budget']['attempts'], count)
                self.assertEqual(result['budget']['unresolved'], int(scenario=='missing_cost'))
                self.assertEqual(Decimal(result['budget']['reported_usd']),
                                 Decimal('0') if scenario=='missing_cost' else Decimal('0.001')*count)
                self.assertEqual(Decimal(result['budget']['reserved_nonrefunded_usd']),
                                 sum(Decimal(r['reserved_usd']) for r in report['records'][:count]))
                self.assertEqual((directory/'paid-stop.json').exists(), scenario=='missing_cost')
                self.assertEqual(export_attempts(directory), result)
                for attempt in result['attempts']:
                    self.assertEqual(attempt['status'], 'response' if scenario.startswith('success') else 'failed')
                    self.assertEqual(attempt['packet_sha256'], hashlib.sha256(raw if attempt['case_id']=='one' else second_raw).hexdigest())
                    if scenario.startswith('success'): self.assertEqual(attempt['message'], response_message)
                self.assertEqual(len(list((directory/'calls').glob('*-request.json'))), count)
                saved_responses = list((directory/'calls').glob('*-response.txt'))
                self.assertEqual(len(saved_responses), count)
                for path in directory.rglob('*'):
                    if path.is_file(): self.assertNotIn(key.encode(), path.read_bytes())
                for path in saved_responses:
                    self.assertEqual(json.loads(path.read_text())['choices'][0]['message'], response_message)
                with self.assertRaises(FileExistsError):
                    execute(root, root/'endpoints.json', config, auth, directory, key)
                self.assertEqual(len(requests), count)
