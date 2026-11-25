"""Injected native receipts only; no services, provider or upstream execution."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import yaml

from apps.factory_lab.shared_extensions import SharedExtensions
from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_extensions import UPSTREAM
from apps.factory_lab.workspace_service import WorkspaceService


class SharedExtensionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / 'input.sqlite'
        with sqlite3.connect(source) as connection:
            connection.execute('CREATE TABLE records (id INTEGER PRIMARY KEY, name TEXT)')
            connection.execute("INSERT INTO records VALUES (1, 'sample')")
        self.registry = SQLiteSources(self.root / 'registry')
        self.registered = self.registry.register(source, label='Test registered snapshot')
        self.workspace = WorkspaceService(self.root / 'workspace.sqlite', database_registry=self.registry)
        self.row = self.workspace.handle({'action': 'create_database', 'title': 'Native test',
            'domain': 'generic', 'source_id': self.registered['source_id'], 'metadata': {}})
        self.before = copy.deepcopy(self.row['draft'])
        self.calls = []
        self.document = {'data_layer': {'databases': []}, 'semantic_layer': {}}
        self.status = 'returned_requires_review'
        self.receipt_change = lambda value: value
        self.service = SharedExtensions(self.workspace, self.registry, self.invoke, self.root / 'private-native')

    def body(self, key='request-1', mode='catalog'):
        return {'id': self.row['id'], 'revision': self.row['revision'], 'request_key': key, 'mode': mode}

    def invoke(self, registry, source_id, *, output_root, mode):
        self.calls.append((registry, source_id, output_root, mode))
        # Attempt and checkpoint must be durable before an external invocation.
        operations = self.workspace.store.operations(self.row['id'])
        generation = next(item for item in operations
                          if item['kind'] == 'extension_generation' and item['state'] == 'running')
        self.assertEqual(generation['state'], 'running')
        self.assertEqual(generation['result']['status'], 'reserved_before_launch')
        native_id = 'b' * 32
        target = output_root / native_id
        target.mkdir(parents=True)
        raw = yaml.safe_dump(self.document).encode()
        (target / 'native-export.yaml').write_bytes(raw)
        receipt = {'invocation_id': native_id, 'mode': mode, 'status': self.status,
            'source_id': source_id, 'source_sha256': self.registered['snapshot_sha256'],
            'upstream_commit': UPSTREAM['commit'],
            'outputs': [{'name': 'native-export.yaml', 'bytes': len(raw),
                         'sha256': hashlib.sha256(raw).hexdigest()}],
            'reason': '/private/config/password-not-public',
            'operator_config': {'password': 'dummy-operator-secret'}}
        if mode == 'semantic':
            receipt['gateway_observation'] = {'new_provider_attempts': 2, 'new_cache_hits': 0,
                                             'internal_model_error_observed': False}
        return self.receipt_change(receipt)

    def test_actual_store_pending_import_and_private_receipt_without_approval(self):
        result = self.service.handle(self.body())
        operation = result['operation']
        self.assertEqual(operation['state'], 'completed')
        self.assertEqual(operation['result']['status'], 'pending_review')
        self.assertFalse(operation['result']['paid'])
        self.assertEqual(operation['result']['input_scope'], 'complete_source_metadata_only')
        imported = self.workspace.store.operation(self.row['id'], operation['result']['import_operation_id'])
        self.assertEqual(imported['kind'], 'extension_import')
        self.assertEqual(imported['result']['status'], 'pending')
        self.assertEqual(self.workspace.store.get(self.row['id'])['draft'], self.before)
        self.assertEqual(self.workspace.store.get(self.row['id'])['revision'], self.row['revision'])
        public = json.dumps(result)
        self.assertNotIn(str(self.root), public)
        self.assertNotIn('dummy-operator-secret', public)
        self.assertNotIn('password-not-public', public)
        self.assertIn('dummy-operator-secret', (self.root / 'private-native' / operation['id'] / 'returned-receipt.json').read_text())
        self.assertEqual(self.calls[0][0], self.registry)
        self.assertEqual(self.calls[0][1], self.registered['source_id'])

    def test_replay_never_reinvokes_or_requires_artifacts(self):
        first = self.service.start(self.body())
        (self.calls[0][2] / ('b' * 32) / 'native-export.yaml').unlink()
        replay = self.service.start(self.body())
        self.assertTrue(replay['reused'])
        self.assertEqual(replay['operation'], first['operation'])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.workspace.store.operations(self.row['id'])), 2)
        with self.assertRaises(ValueError):
            self.service.start(self.body(mode='semantic'))

    def test_korean_native_receipt_imports_original_proposal_without_approval(self):
        def korean(receipt):
            receipt['gateway_observation']['requested_description_language'] = 'ko'
            return receipt
        self.receipt_change = korean
        result = self.service.start(self.body(mode='semantic'))
        self.assertEqual(result['operation']['state'], 'completed')
        self.assertEqual(result['operation']['result']['native_model_execution']['requested_description_language'], 'ko')
        self.assertEqual(self.workspace.store.get(self.row['id'])['draft'], self.before)
        self.assertEqual(self.workspace.store.get(self.row['id'])['revision'], self.row['revision'])

    def test_native_receipt_rejects_unknown_or_invalid_language_metadata(self):
        for index, extra in enumerate(({'requested_description_language': 'en'},
                                      {'requested_description_language': None},
                                      {'unverified_language': 'ko'})):
            self.receipt_change = lambda r, extra=extra: {**r, 'gateway_observation': {**r['gateway_observation'], **extra}}
            result = self.service.start(self.body(key=f'bad-language-{index}', mode='semantic'))
            self.assertEqual(result['operation']['state'], 'failed')
        self.assertEqual(self.workspace.store.get(self.row['id'])['draft'], self.before)

    def test_failed_native_attempt_is_preserved_and_not_retried(self):
        self.status = 'timed_out'
        first = self.service.start(self.body())
        self.assertEqual(first['operation']['state'], 'failed')
        self.assertEqual(first['operation']['result']['last_stage'], 'timed_out')
        self.assertIsNone(first['operation']['result']['import_operation_id'])
        self.assertEqual(self.service.start(self.body())['operation'], first['operation'])
        self.assertEqual(len(self.calls), 1)

    def test_semantic_scope_is_distinct_and_does_not_grant_approval(self):
        result = self.service.start(self.body(mode='semantic'))
        self.assertTrue(result['operation']['result']['paid'])
        self.assertEqual(result['operation']['result']['input_scope'], 'complete_small_source_semantic')
        self.assertEqual(result['operation']['result']['approval'], 'not_granted')

    def test_semantic_export_without_model_work_or_with_model_failure_is_not_imported(self):
        for index, observation in enumerate((None,
                {'new_provider_attempts': 0, 'new_cache_hits': 0, 'internal_model_error_observed': False},
                {'new_provider_attempts': 1, 'new_cache_hits': 0, 'internal_model_error_observed': True})):
            self.receipt_change = lambda r, value=observation: {**r, 'gateway_observation': value}
            result = self.service.start(self.body(key=f'partial-{index}', mode='semantic'))
            self.assertEqual(result['operation']['state'], 'failed')
            self.assertIsNone(result['operation']['result']['import_operation_id'])
        self.assertEqual(result['operation']['result']['approval'], 'not_granted')

    def test_browser_paths_extra_fields_and_non_database_are_rejected(self):
        for key, value in [('source_id', '/etc/passwd'), ('output_root', '/tmp'), ('config', {})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.service.start({**self.body(), key: value})
        factory = self.workspace.handle({'action': 'example', 'domain': 'factory'})
        with self.assertRaises(ValueError):
            self.service.start({**self.body(), 'id': factory['id'], 'revision': factory['revision']})
        self.assertEqual(self.calls, [])

    def test_receipt_binding_hash_and_identity_rejections_have_no_import(self):
        mutations = [lambda r: {**r, 'source_sha256': 'a' * 64},
                     lambda r: {**r, 'source_id': 'a' * 32},
                     lambda r: {**r, 'upstream_commit': 'wrong'},
                     lambda r: {**r, 'mode': 'semantic'},
                     lambda r: {**r, 'invocation_id': '../escape'},
                     lambda r: {**r, 'outputs': []}]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                self.receipt_change = mutation
                result = self.service.start(self.body(key=f'wrong-{index}'))
                self.assertEqual(result['operation']['state'], 'failed')
                self.assertIsNone(result['operation']['result']['import_operation_id'])
        self.assertFalse(any(item['kind'] == 'extension_import' for item in self.workspace.store.operations(self.row['id'])))

    def test_configuration_in_export_is_not_published_or_imported(self):
        self.document['data_layer']['credentials'] = {'password': 'dummy-export-secret'}
        result = self.service.start(self.body())
        self.assertEqual(result['operation']['state'], 'failed')
        self.assertNotIn('dummy-export-secret', json.dumps(result))
        self.assertIsNone(result['operation']['result']['import_operation_id'])

    def test_exception_details_are_private_and_attempt_not_retried(self):
        def failed(*args, **kwargs):
            self.calls.append('failed')
            raise RuntimeError('/private/provider-secret')
        self.service.invocation = failed
        result = self.service.start(self.body())
        self.assertEqual(result['operation']['state'], 'failed')
        self.assertNotIn('provider-secret', json.dumps(result))
        self.assertTrue(self.service.start(self.body())['reused'])
        self.assertEqual(len(self.calls), 1)

    def test_interrupted_checkpoint_replay_never_invokes(self):
        row = self.workspace.store.get(self.row['id'], self.row['revision'])
        operation, _ = self.workspace.store.begin(row['id'], row['revision'], 'interrupted',
            'extension_generation', {'mode': 'catalog', 'base_digest': row['digest']})
        self.workspace.store.checkpoint(operation['id'], {'status': 'reserved_before_launch'})
        self.workspace.store.recover_interrupted()
        result = self.service.start(self.body(key='interrupted'))
        self.assertTrue(result['reused'])
        self.assertEqual(result['operation']['state'], 'interrupted')
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
