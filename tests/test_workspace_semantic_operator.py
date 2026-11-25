"""Offline operator boundary tests; fake transport/processes, no provider calls.

Real subprocess tests exercise Linux session/reaping behavior, not upstream or
model execution. No PostgreSQL or HTTP service is started by these tests.
"""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from apps.factory_lab import auto_ontology_semantic_cli as operator
from apps.factory_lab.auto_ontology_bridge import BridgeLimits
from apps.factory_lab.extension_gateway import Gateway, Denied, Response
from apps.factory_lab.workspace_database import SQLiteSources


def offline_budget():
    common = {'provider': 'offline-fixture', 'input_nanodollars_per_token': 1,
              'max_input_tokens': 32, 'verification': 'Authored offline test ceilings, not provider prices',
              'reservation_nanodollars': 100, 'billing_output_tokens': 0}
    return {'format': 'auto-ontology-semantic-budget-1', 'wall_timeout_seconds': 1,
            'bridge_limits': asdict(BridgeLimits(timeout_seconds=1)),
            'config': {'models': [
                {**common, 'alias': operator.CHAT, 'actual_id': 'offline/chat', 'kind': 'chat',
                 'output_nanodollars_per_token': 1, 'max_output_tokens': 16},
                {**common, 'alias': operator.EMBED, 'actual_id': 'offline/embedding', 'kind': 'embedding',
                 'output_nanodollars_per_token': 0, 'max_output_tokens': 0}],
                'call_cap': 4, 'chat_attempt_cap': 2, 'embedding_attempt_cap': 2,
                'per_call_nanodollars': 100, 'total_nanodollars': 400,
                'deadline_epoch': time.time()+1000, 'timeout_seconds': 1,
                'max_request_bytes': 4096, 'max_response_bytes': 65536}}


class SemanticOperatorTests(unittest.TestCase):
    def test_explicit_v2_settlement_config_keeps_v1_fixed_and_requires_carry_binding(self):
        budget=offline_budget();cfg,_=operator.budget_config(budget)
        self.assertEqual(cfg.reservation_accounting,'fixed')
        budget['format']='auto-ontology-semantic-budget-2'
        budget['config'].update(reservation_accounting='settled',inherited_attempts=0,
            inherited_reserved_nanodollars=0,prior_ledger_path='',prior_ledger_sha256='',campaign_lock_path='')
        cfg,_=operator.budget_config(budget);self.assertEqual(cfg.reservation_accounting,'settled')
        budget['config']['inherited_attempts']=1
        with self.assertRaises(Denied):operator.budget_config(budget)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = self.root/'source.sqlite'
        with sqlite3.connect(source) as db:
            db.execute('CREATE TABLE parts(id INTEGER PRIMARY KEY, name TEXT)')
            db.execute("INSERT INTO parts VALUES(1,'authored')")
        self.registry = SQLiteSources(self.root/'registry')
        self.record = self.registry.register(source)
        self.budget = self.root/'budget.json'
        self.budget.write_text(json.dumps(offline_budget()))
        self.pg = self.root/'postgres.json'
        self.pg.write_text(json.dumps({'postgres': {'host': '127.0.0.1', 'port': 54321,
                        'user': 'offline', 'password': 'local-fixture-password', 'database': 'offline'}}))
        self.pg.chmod(0o600)
        self.identity = {'commit': 'offline-test-pinned-identity', 'files': {}}
        self.patches = [patch.object(operator, 'upstream_identity', return_value=self.identity),
                        patch.object(operator, 'code_identity', return_value={'offline': 'frozen'})]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def prepare(self, name='run'):
        return operator.prepare(registry=self.registry.root, source_id=self.record['source_id'],
            upstream_root=self.root/'installed', upstream_python=sys.executable,
            postgres_config=self.pg, budget=self.budget, output=self.root/name,
            request_id='offline-authored-case', authorization_reference='Offline fixture only; no paid authorization')

    def execute(self, prepared, **kwargs):
        return operator.execute(prepared['manifest'], prepared['manifest_sha256'],
            authorize_paid_execution=True, ready_check=lambda pg: None,
            secret_reader=lambda: 'offline-fixture-secret', **kwargs)

    def test_prepare_offline_creates_no_ledger_or_gateway_and_no_credential_value(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'MUST-NOT-READ-OR-COPY'}), \
             patch.object(operator, 'Gateway', side_effect=AssertionError('no gateway')), \
             patch.object(operator.socket, 'create_connection', side_effect=AssertionError('no network')):
            result = self.prepare()
        manifest = Path(result['manifest'])
        self.assertEqual(result['status'], 'prepared_not_executed')
        self.assertFalse((manifest.parent/'campaign.sqlite').exists())
        self.assertEqual(set(p.name for p in manifest.parent.iterdir()), {'manifest.json'})
        raw = manifest.read_text()
        self.assertNotIn('MUST-NOT-READ-OR-COPY', raw)
        self.assertNotIn('local-fixture-password', raw)
        self.assertEqual(json.loads(raw)['source']['per_table_rows'], {'parts': 1})
        self.assertEqual(manifest.stat().st_mode & 0o077, 0)
        with self.assertRaises(operator.OperatorError):
            self.prepare()

    def test_budget_template_is_nonexecutable(self):
        template = operator.ROOT/'examples/factory_lab/extensions/operator/semantic-budget.example.json'
        with self.assertRaises((ValueError, TypeError)):
            operator.budget_config(json.loads(template.read_text()))

    def test_exact_aliases_and_no_continuation(self):
        for field, value in [('inherited_attempts', 1), ('prior_ledger_path', '/any'), ('campaign_lock_path', '/any')]:
            budget = offline_budget()
            budget['config'][field] = value
            with self.assertRaises(operator.OperatorError):
                operator.budget_config(budget)
        budget = offline_budget()
        budget['config']['models'][0]['alias'] = 'openai/auto-ontology-other'
        with self.assertRaises(operator.OperatorError):
            operator.budget_config(budget)
        budget = offline_budget()
        budget['config']['models'][0]['input_nanodollars_per_token'] = 1000
        with self.assertRaises(ValueError):
            operator.budget_config(budget)

    def test_registry_record_cannot_redirect_requested_id(self):
        prepared = self.prepare()
        original = self.registry.root/(self.record['source_id']+'.json')
        new = dict(self.record)
        new['source_id'] = 'a'*32
        original.write_text(json.dumps(new))
        with self.assertRaises(operator.OperatorError):
            operator.source_identity(self.registry.root, self.record['source_id'], BridgeLimits())
        result = self.execute(prepared)
        self.assertFalse(result['provider_secret_read'])
        self.assertEqual(result['status'], 'failed_or_interrupted')

    def test_manifest_hash_and_explicit_authorization(self):
        prepared = self.prepare()
        with self.assertRaises(operator.OperatorError):
            operator.execute(prepared['manifest'], prepared['manifest_sha256'])
        with self.assertRaises(operator.OperatorError):
            operator.execute(prepared['manifest'], '0'*64, authorize_paid_execution=True)
        self.assertFalse((self.root/'run'/'execution.claim').exists())

    def test_mutated_bindings_fail_before_credential_and_retain_claim(self):
        changes = ('source', 'postgres', 'budget', 'code', 'upstream', 'deadline')
        for index, change in enumerate(changes):
            with self.subTest(change=change):
                prepared = self.prepare('mutation-'+str(index))
                manifest = json.loads(Path(prepared['manifest']).read_text())
                if change == 'source':
                    target = self.registry.root/(self.record['source_id']+'.sqlite')
                    original = target.read_bytes(); target.chmod(0o600); target.write_bytes(original+b'x')
                elif change == 'postgres':
                    original = self.pg.read_bytes(); self.pg.write_bytes(original+b' ')
                elif change == 'budget':
                    original = self.budget.read_bytes(); self.budget.write_bytes(original+b' ')
                context = (patch.object(operator, 'code_identity', return_value={}) if change == 'code' else
                           patch.object(operator, 'upstream_identity', return_value={}) if change == 'upstream' else
                           patch.object(operator.time, 'time', return_value=manifest['budget']['config']['deadline_epoch']+1) if change == 'deadline' else
                           patch.object(operator, 'CHAT', operator.CHAT))
                try:
                    with context, patch.object(operator, 'catalog_ready', side_effect=AssertionError('too late')):
                        result = operator.execute(prepared['manifest'], prepared['manifest_sha256'],
                            authorize_paid_execution=True,
                            secret_reader=lambda: self.fail('credential accessed before binding validation'))
                    self.assertEqual(result['status'], 'failed_or_interrupted')
                    self.assertFalse(result['provider_secret_read'])
                    self.assertTrue((Path(prepared['manifest']).parent/'execution.claim').exists())
                    self.assertFalse((Path(prepared['manifest']).parent/'campaign.sqlite').exists())
                finally:
                    if change == 'source':target.write_bytes(original)
                    elif change == 'postgres':self.pg.write_bytes(original)
                    elif change == 'budget':self.budget.write_bytes(original)

    def test_existing_ledger_or_prior_execution_cannot_be_reused(self):
        prepared = self.prepare()
        ledger = self.root/'run'/'campaign.sqlite'
        ledger.write_bytes(b'prior unresolved campaign, do not overwrite')
        before = ledger.read_bytes()
        with self.assertRaises(operator.OperatorError):self.execute(prepared)
        self.assertEqual(ledger.read_bytes(), before)
        second = self.prepare('second')
        (self.root/'second'/'execution.claim').write_text('already attempted')
        with self.assertRaises(FileExistsError):self.execute(second)

    def test_no_secret_in_child_environment_and_fake_execution_labeled(self):
        prepared = self.prepare()
        output = self.root/'run'
        code = ("import os,sys,json,hashlib; from pathlib import Path; "
                "raw=sys.stdin.buffer.read(); Path(sys.argv[1]).write_text(json.dumps({"
                "'provider_env_present':'OPENROUTER_API_KEY' in os.environ,"
                "'proxy_present':'HTTPS_PROXY' in os.environ,'secret_sha256':hashlib.sha256(raw).hexdigest()}))")
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'parent-never-inherited', 'HTTPS_PROXY': 'private-proxy'}):
            result = self.execute(prepared, worker_command=[sys.executable, '-c', code, str(output/'pipe-check.json')])
        report = json.loads((output/'pipe-check.json').read_text())
        self.assertFalse(report['provider_env_present']); self.assertFalse(report['proxy_present'])
        self.assertEqual(report['secret_sha256'], hashlib.sha256(b'offline-fixture-secret').hexdigest())
        self.assertEqual(result['status'], 'offline_fixture_returned')
        self.assertTrue(result['process']['cleanup']['verified'])
        self.assertEqual(result['accounting']['reported_cost_status'], 'no_attempts')
        for name in ('execution.json', 'worker.stdout', 'worker.stderr', 'process.json'):
            self.assertNotIn('offline-fixture-secret', (output/name).read_text())

    @unittest.skipUnless(sys.platform == 'linux', 'Linux process supervision')
    def test_nested_new_session_child_reaped_on_timeout_and_interruption(self):
        for interrupted in (False, True):
            with self.subTest(interrupted=interrupted):
                folder = self.root/('interrupt' if interrupted else 'timeout'); folder.mkdir(mode=0o700)
                child_file = folder/'child.json'
                # Actual nested process deliberately escapes worker's session, like the bridge.
                nested = "import time; time.sleep(60)"
                code = ("import sys,subprocess,time,json; from pathlib import Path; "
                        "sys.stdin.buffer.read(); p=subprocess.Popen([sys.executable,'-c',sys.argv[2]],start_new_session=True); "
                        "Path(sys.argv[1]).write_text(json.dumps({'pid':p.pid})); time.sleep(60)")
                result = operator.supervise([sys.executable, '-c', code, str(child_file), nested],
                    'offline-only-secret', folder, 1, time.time()+10,
                    interruption=(lambda: child_file.exists()) if interrupted else None)
                self.assertTrue(child_file.exists(), result)
                pid = json.loads(child_file.read_text())['pid']
                self.assertIsNone(operator.proc_record(pid), result)
                self.assertTrue(result['cleanup']['verified'], result)
                self.assertEqual(result['status'], 'interrupted' if interrupted else 'wall_or_absolute_timeout')
                self.assertGreaterEqual(len(result['cleanup']['owned_identities']), 2)

    def test_cleanup_failure_never_reports_success(self):
        prepared = self.prepare()
        fake = {'status': 'exited', 'returncode': 0, 'cleanup': {'verified': False, 'remaining': [{'pid': 123}]}}
        with patch.object(operator, 'supervise', return_value=fake):
            result = self.execute(prepared, worker_command=['offline-fixture-no-execution'])
        self.assertEqual(result['status'], 'failed_or_interrupted')
        self.assertFalse(result['process']['cleanup']['verified'])

    def test_reused_pid_is_not_signaled(self):
        class Finished:
            pid = 9999999
            def poll(self):return 0
        old = {'pid': Finished.pid, 'start': 10, 'ppid': os.getpid(), 'state': 'S'}
        reused = {**old, 'start': 11, 'ppid': 1}
        with patch.object(operator, 'proc_table', return_value={}), \
             patch.object(operator, 'proc_record', return_value=reused), \
             patch.object(operator.os, 'kill') as kill, \
             patch.object(operator.os, 'waitpid', side_effect=ChildProcessError):
            result = operator.kill_owned_tree(Finished(), set(), old)
        kill.assert_not_called()
        self.assertTrue(result['verified'])  # Reused unrelated PID is not ours.

    def test_worker_passes_only_dummy_to_bridge_and_retains_pending_scope(self):
        prepared = self.prepare()
        manifest = json.loads(Path(prepared['manifest']).read_text())
        captured = {}
        class OfflineServer:
            server_address = ('127.0.0.1', 54322)
            def serve_forever(self):pass
            def shutdown(self):pass
            def server_close(self):pass
        def fake_invoke(registry, source_id, **kwargs):
            captured.update(kwargs)
            self.assertEqual(source_id, self.record['source_id'])
            return {'status': 'returned_requires_review', 'invocation_id': 'offline-fixture',
                    'source_id': manifest['source']['source_id'], 'source_sha256': manifest['source']['sha256']}
        with patch.object(operator, 'create_server', return_value=OfflineServer()), \
             patch.object(operator.bridge, 'invoke', side_effect=fake_invoke):
            code = operator.worker_run(manifest, 'offline-provider-secret',
                transport=lambda *args: self.fail('No transport expected in scripted bridge test'))
        self.assertEqual(code, 0)
        config = captured['operator_config']
        self.assertEqual(config['gateway']['chat_model'], operator.CHAT)
        self.assertEqual(config['gateway']['embedding_model'], operator.EMBED)
        self.assertNotEqual(config['gateway']['token'], 'offline-provider-secret')
        self.assertNotIn('offline-provider-secret', json.dumps(config))
        self.assertEqual(captured['mode'], 'semantic')
        self.assertEqual(json.loads((self.root/'run'/'worker-result.json').read_text())['approval'], 'not_granted')

    def test_fast_exit_missing_root_identity_still_verifies_reaping(self):
        folder = self.root/'fast'; folder.mkdir()
        result = operator.supervise([sys.executable, '-c', 'import sys; sys.stdin.buffer.read()'],
                                    'offline-secret', folder, 2, time.time()+10)
        self.assertTrue(result['cleanup']['verified'], result)
        self.assertIsNone(operator.proc_record(result['pid']))

    def test_gateway_failed_fake_transport_reserves_without_refund(self):
        cfg, _ = operator.budget_config(offline_budget())
        calls = []
        def transport(route, body, secret, timeout, maximum):
            calls.append(json.loads(body))
            self.assertEqual(secret, 'offline-provider-secret')
            return Response(503, b'{"error":"authored failure"}')
        ledger = self.root/'authored-ledger.sqlite'
        gateway = Gateway(ledger, cfg, 'offline-provider-secret', transport)
        try:
            for _ in range(2):
                with self.assertRaises(Denied):
                    gateway.handle('/v1/chat/completions', {'model': operator.CHAT,
                        'messages': [{'role': 'user', 'content': 'offline fixture'}], 'max_tokens': 8})
            with self.assertRaises(Denied):
                gateway.handle('/v1/chat/completions', {'model': operator.CHAT,
                    'messages': [{'role': 'user', 'content': 'offline fixture'}], 'max_tokens': 8})
        finally:
            gateway.close()
        summary = operator.ledger_summary(ledger)
        self.assertEqual(len(calls), 2)
        self.assertEqual(summary['attempts'], 2)
        self.assertEqual(summary['reserved_nanodollars'], 200)
        self.assertEqual(summary['failed_completions'], 2)
        self.assertIsNone(summary['reported_cost_usd'])
        self.assertFalse(summary['reservations_refunded'])
        self.assertFalse(calls[0]['provider']['allow_fallbacks'])

    def test_unresolved_and_partial_reported_cost_are_distinct(self):
        cfg, _ = operator.budget_config(offline_budget())
        ledger = self.root/'accounting.sqlite'
        gateway = Gateway(ledger, cfg, 'offline-secret', lambda *args: Response(200,
                          b'{"choices":[],"usage":{"cost":0.000001}}'))
        gateway.handle('/v1/chat/completions', {'model': operator.CHAT,
            'messages': [{'role': 'user', 'content': 'offline'}], 'max_tokens': 8})
        gateway.close()
        with sqlite3.connect(ledger) as db:
            db.execute('INSERT INTO attempts(started,route,alias,model,original,request,sha256,reserved) VALUES(?,?,?,?,?,?,?,?)',
                       (time.time(), '/v1/chat/completions', operator.CHAT, 'offline/chat', '{}', '{}', 'a'*64, 100))
        summary = operator.ledger_summary(ledger)
        self.assertEqual(summary['unresolved_attempts'], 1)
        self.assertEqual(summary['missing_reported_cost_records'], 1)
        self.assertEqual(summary['reported_cost_usd'], '0.000001')
        self.assertEqual(summary['reserved_nanodollars'], 200)


if __name__ == '__main__':
    unittest.main()
