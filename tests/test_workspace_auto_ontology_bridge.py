"""Offline bridge boundaries; fake child is not native upstream acceptance."""
import json
import os
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from apps.factory_lab.auto_ontology_bridge import (
    AutoOntologyError, BridgeLimits, child_environment, invoke, _bound_connector,
)
from apps.factory_lab.workspace_database import SQLiteSources


class BridgeTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = SQLiteSources(self.root / 'registry')
        self.config = {'postgres': {'host': '127.0.0.1', 'port': 5432,
                                   'user': 'test', 'password': 'local-test-only', 'database': 'test'}}
        self.options = {'output_root': self.root / 'runs', 'upstream_root': self.root,
                        'python_executable': Path(sys.executable), 'operator_config': self.config}

    def source(self, table='measurements', rows=3, cell='value'):
        path = self.root / (table + '.sqlite')
        with sqlite3.connect(path) as con:
            con.execute('CREATE TABLE "' + table + '" (id INTEGER PRIMARY KEY, reading TEXT)')
            con.executemany('INSERT INTO "' + table + '" VALUES (?, ?)', [(i, cell) for i in range(rows)])
        return self.registry.register(path)['source_id']

    def semantic_options(self):
        return {**self.options, 'mode': 'semantic', 'operator_config': {
            **self.config, 'gateway': {'endpoint': 'http://127.0.0.1:12345/v1',
                'token': 'test-no-provider', 'chat_model': 'test-chat', 'embedding_model': 'test-embed'},
            'request_id': 'test-request', 'reservation_id': 'test-reservation'}}

    def test_environment_ignores_ambient_credentials_and_proxies(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'must-not-leak', 'HTTP_PROXY': 'bad',
                                     'DEFAULT_MODELS_API_KEY': 'must-not-leak', 'PYTHONPATH': 'bad'}):
            env = child_environment(self.config, 'catalog')
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertNotIn('HTTP_PROXY', env)
        self.assertNotIn('PYTHONPATH', env)
        self.assertNotIn('must-not-leak', str(env))
        self.assertEqual(env['PYTHON_DOTENV_DISABLED'], '1')
        self.assertEqual(env['REASONING_ENDPOINT'], 'http://127.0.0.1:1/v1')

    def test_semantic_requires_gateway_and_bindings(self):
        with self.assertRaises(AutoOntologyError):
            child_environment(self.config, 'semantic')
        config = {**self.config, 'gateway': {'endpoint': 'https://provider.example/v1',
                  'token': 'only-gateway-token', 'chat_model': 'chat', 'embedding_model': 'embed'},
                  'request_id': 'req', 'reservation_id': 'reserved'}
        with self.assertRaises(AutoOntologyError):
            child_environment(config, 'semantic')
        config['gateway']['endpoint'] = 'http://127.0.0.1:12345/v1'
        self.assertEqual(child_environment(config, 'semantic')['EMBED_MODEL'], 'embed')
        with self.assertRaises(AutoOntologyError):
            child_environment(config, 'catalog')
        del config['reservation_id']
        with self.assertRaises(AutoOntologyError):
            child_environment(config, 'semantic')

    def test_rejected_semantic_does_not_start_process(self):
        with patch('apps.factory_lab.auto_ontology_bridge.subprocess.Popen') as start:
            receipt = invoke(self.registry, self.source(), mode='semantic', **self.options)
        start.assert_not_called()
        self.assertEqual(receipt['status'], 'rejected_or_launch_failed')
        self.assertIn('gateway', receipt['reason'])
        self.assertEqual(len(list((self.root / 'runs').glob('*/receipt.json'))), 1)
        self.assertNotIn('local-test-only', json.dumps(receipt))

    def test_row_cap_preserves_exact_rejection_and_original(self):
        source = self.source(rows=4)
        before = self.registry._data(self.registry._record(source))
        with patch('apps.factory_lab.auto_ontology_bridge._verify_upstream'), patch('apps.factory_lab.auto_ontology_bridge.subprocess.Popen') as start:
            receipt = invoke(self.registry, source, limits=BridgeLimits(max_rows_per_table=3), **self.semantic_options())
        start.assert_not_called()
        self.assertEqual(receipt['reason'], 'Registered source exceeds per-table row bound')
        self.assertEqual(before, self.registry._data(self.registry._record(source)))

    def test_cell_and_source_size_rejections(self):
        source = self.source(cell='many bytes')
        with patch('apps.factory_lab.auto_ontology_bridge._verify_upstream'):
            for limits, message in [(BridgeLimits(max_cell_bytes=2), 'cell byte'),
                                    (BridgeLimits(max_source_bytes=2), 'byte limit')]:
                receipt = invoke(self.registry, source, limits=limits, **self.semantic_options())
                self.assertIn(message, receipt['reason'])

    def test_large_catalog_is_complete_metadata_without_cell_materialization(self):
        source = self.source(rows=1501, cell='larger than configured cell bound')
        before = self.registry._data(self.registry._record(source))
        statements = []
        original_connection = self.registry._connection
        @contextmanager
        def observed_connection(data):
            with original_connection(data) as connection:
                connection.set_trace_callback(statements.append)
                yield connection
        with patch('apps.factory_lab.auto_ontology_bridge._verify_upstream'), \
                patch.object(self.registry, '_connection', observed_connection), \
                patch('apps.factory_lab.auto_ontology_bridge.subprocess.Popen') as start:
            # A mocked child returning zero is not actual native ingestion.
            start.return_value.returncode = 0
            receipt = invoke(self.registry, source,
                limits=BridgeLimits(max_rows_per_table=3, max_cell_bytes=2), **self.options)
        start.assert_called_once()
        self.assertEqual(receipt['status'], 'returned_requires_review')
        self.assertEqual(receipt['input_scope'], 'complete_source_metadata_only')
        self.assertEqual(receipt['local_preflight']['per_table_rows'], {'measurements': 1501})
        self.assertEqual(receipt['local_preflight']['total_rows'], 1501)
        self.assertFalse(receipt['local_preflight']['cell_values_materialized'])
        self.assertFalse(receipt['local_preflight']['row_and_cell_limits_apply'])
        self.assertEqual(receipt['upstream_profiling'], {'status': 'not_requested', 'actual_rows_observed': None})
        self.assertFalse(receipt['upstream_input']['sampled'])
        self.assertEqual(receipt['upstream_input']['sha256'], receipt['source_sha256'])
        self.assertEqual(receipt['stages'], [])  # mock supplied no native observations
        self.assertTrue(any('SELECT count(*) FROM "measurements"' == sql for sql in statements))
        self.assertFalse(any(sql.upper().startswith('SELECT * FROM') for sql in statements))
        folder = self.root / 'runs' / receipt['invocation_id']
        self.assertEqual((folder / (receipt['invocation_id'] + '.sqlite')).read_bytes(), before)
        self.assertEqual(before, self.registry._data(self.registry._record(source)))

    def test_large_semantic_source_rejected_without_child_or_sampling(self):
        source = self.source(rows=1501)
        before = self.registry._data(self.registry._record(source))
        with patch('apps.factory_lab.auto_ontology_bridge._verify_upstream'), \
                patch('apps.factory_lab.auto_ontology_bridge.subprocess.Popen') as start:
            receipt = invoke(self.registry, source, **self.semantic_options())
        start.assert_not_called()
        self.assertEqual(receipt['reason'], 'Registered source exceeds per-table row bound')
        self.assertEqual(receipt['stages'], [])
        self.assertEqual(before, self.registry._data(self.registry._record(source)))
        self.assertEqual(len(list((self.root / 'runs').glob('*/receipt.json'))), 1)

    def test_small_semantic_receipt_keeps_actual_profile_coverage_unknown(self):
        with patch('apps.factory_lab.auto_ontology_bridge._verify_upstream'), \
                patch('apps.factory_lab.auto_ontology_bridge.subprocess.Popen') as start:
            start.return_value.returncode = 0
            receipt = invoke(self.registry, self.source(), **self.semantic_options())
        self.assertEqual(receipt['input_scope'], 'complete_small_source_semantic')
        self.assertTrue(receipt['local_preflight']['row_and_cell_limits_apply'])
        self.assertTrue(receipt['local_preflight']['cell_values_materialized'])
        self.assertEqual(receipt['upstream_profiling'], {'status': 'not_verified', 'actual_rows_observed': None})

    def test_catalog_preflight_deadline_interrupt_retains_rejection(self):
        source = self.source()
        before = self.registry._data(self.registry._record(source))
        expired = False
        def expensive_catalog(connection):
            nonlocal expired
            expired = True
            connection.execute('WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL '
                               'SELECT x+1 FROM n WHERE x<100000) SELECT sum(x) FROM n').fetchone()
            self.fail('Progress handler should interrupt before this point')
        with patch('apps.factory_lab.auto_ontology_bridge._verify_upstream'), \
                patch('apps.factory_lab.auto_ontology_bridge.time.monotonic', lambda: 100 if expired else 0), \
                patch.object(self.registry, '_catalog', expensive_catalog), \
                patch('apps.factory_lab.auto_ontology_bridge.subprocess.Popen') as start:
            receipt = invoke(self.registry, source, **self.options)
        start.assert_not_called()
        self.assertEqual(receipt['status'], 'rejected_or_launch_failed')
        self.assertEqual(receipt['reason'], 'Registered source preflight exceeded time limit')
        self.assertEqual(before, self.registry._data(self.registry._record(source)))

    def test_source_drift_is_not_repaired(self):
        source = self.source()
        snapshot = self.registry.root / (source + '.sqlite')
        snapshot.chmod(0o600)
        snapshot.write_bytes(b'bad')
        with patch('apps.factory_lab.auto_ontology_bridge._verify_upstream'), patch('apps.factory_lab.auto_ontology_bridge.subprocess.Popen') as start:
            receipt = invoke(self.registry, source, **self.options)
        start.assert_not_called()
        self.assertEqual(receipt['status'], 'rejected_or_launch_failed')
        self.assertEqual(snapshot.read_bytes(), b'bad')

    def test_non_native_child_failure_retains_bytes_and_unique_attempts(self):
        # Real subprocess lifecycle, intentionally no upstream execution or network.
        fake = self.root / 'fake-python'
        fake.write_text('#!/bin/sh\nprintf "partial native log\\n" >&2\nexit 7\n')
        fake.chmod(0o700)
        options = {**self.options, 'python_executable': fake}
        receipts = []
        with patch('apps.factory_lab.auto_ontology_bridge._verify_upstream'):
            for table in ('sensors', 'departments'):
                receipts.append(invoke(self.registry, self.source(table), **options))
        self.assertNotEqual(receipts[0]['source_sha256'], receipts[1]['source_sha256'])
        self.assertNotEqual(receipts[0]['schema_sha256'], receipts[1]['schema_sha256'])
        for receipt in receipts:
            self.assertEqual(receipt['status'], 'failed')
            self.assertEqual(receipt['returncode'], 7)
            self.assertEqual(receipt['semantic_status'], 'not_requested')
            folder = self.root / 'runs' / receipt['invocation_id']
            self.assertEqual((folder / 'stderr.log').read_text(), 'partial native log\n')
            self.assertTrue(any(o['name'] == 'stderr.log' for o in receipt['outputs']))
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)

    def test_timeout_preserves_log(self):
        fake = self.root / 'slow-python'
        fake.write_text('#!/bin/sh\nprintf "started\\n"\nsleep 30\n')
        fake.chmod(0o700)
        with patch('apps.factory_lab.auto_ontology_bridge._verify_upstream'):
            receipt = invoke(self.registry, self.source(), limits=BridgeLimits(timeout_seconds=1),
                             **{**self.options, 'python_executable': fake})
        self.assertEqual(receipt['status'], 'timed_out')
        folder = self.root / 'runs' / receipt['invocation_id']
        self.assertEqual((folder / 'stdout.log').read_text(), 'started\n')

    def test_views_are_explicitly_unsupported(self):
        path = self.root / 'views.sqlite'
        with sqlite3.connect(path) as con:
            con.executescript('CREATE TABLE facts(id); CREATE VIEW visible AS SELECT * FROM facts;')
        source = self.registry.register(path)['source_id']
        with patch('apps.factory_lab.auto_ontology_bridge._verify_upstream'):
            receipt = invoke(self.registry, source, **self.options)
        self.assertIn('Views are unsupported', receipt['reason'])

    def test_official_resolver_binding_is_shared_and_source_exact(self):
        # Fake resolver models the official shared cache, not semantic success.
        # Verify the physical SQLite path using actual PRAGMA database_list.
        source = self.source()
        snapshot = self.registry.root / (source + '.sqlite')
        class Frame:
            def __init__(self, rows): self.rows = rows
            def to_dict(self, orient):
                self.assert_orient = orient
                return self.rows
        class Connector:
            database_name = snapshot.stem
            dialect = 'sqlite'
            def execute(self, sql):
                with sqlite3.connect(snapshot) as con:
                    con.row_factory = sqlite3.Row
                    return Frame([dict(row) for row in con.execute(sql)])
        connector = Connector()
        seen = []
        def resolve():
            seen.append(os.environ['CONNECTION_STRINGS'])
            return [connector]
        with patch.dict(os.environ, {}, clear=True):
            owned = _bound_connector(snapshot, lambda: [], resolve)
            profile = _bound_connector(snapshot, lambda: [], resolve, expected=owned)
            export = _bound_connector(snapshot, lambda: [], resolve, expected=owned)
        self.assertIs(owned, profile)
        self.assertIs(profile, export)
        self.assertEqual(len(set(seen)), 1)
        self.assertTrue(seen[0].endswith(source + '.sqlite'))
        # A matching basename is insufficient: physical snapshot must match.
        other = self.root / 'other' / snapshot.name
        other.parent.mkdir()
        other.write_bytes(snapshot.read_bytes())
        with self.assertRaisesRegex(AutoOntologyError, 'owned snapshot'):
            _bound_connector(other, lambda: [], resolve)

    def test_saved_catalog_connections_are_rejected_before_resolution(self):
        from unittest.mock import Mock
        resolve = Mock()
        with self.assertRaisesRegex(AutoOntologyError, 'saved connections'):
            _bound_connector(self.root / 'owned.sqlite', lambda: [{'database': 'foreign'}], resolve)
        resolve.assert_not_called()

    def test_resolver_ambiguity_and_changed_identity_are_rejected(self):
        from types import SimpleNamespace
        snapshot = self.root / 'owned.sqlite'
        connector = SimpleNamespace(database_name='owned', dialect='sqlite')
        for connectors, expected, reason in [([], None, 'exactly one'),
                ([connector, connector], None, 'exactly one'),
                ([SimpleNamespace(database_name='foreign', dialect='sqlite')], None, 'different database'),
                ([connector], object(), 'changed during invocation')]:
            with self.subTest(reason=reason), self.assertRaisesRegex(AutoOntologyError, reason):
                _bound_connector(snapshot, lambda: [], lambda: connectors, expected=expected)

    def test_limits_do_not_accept_bools_or_unbounded_samples(self):
        for limits in (BridgeLimits(max_tables=True), BridgeLimits(max_rows_per_table=1001)):
            with self.assertRaises(AutoOntologyError):
                limits.validate()


if __name__ == '__main__':
    unittest.main()
