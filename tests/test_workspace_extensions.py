"""Offline boundary checks. Fixtures are mocked native-schema documents, not paid outputs.

Shape follows NVIDIA auto-ontology's pinned model_interchange/schemas.py and
its mock-backed test_model_interchange.py. No upstream compilation is claimed.
"""
import base64
import copy
import hashlib
import unittest

import yaml

from apps.factory_lab.workspace_extensions import (
    ExtensionParseError, UnsupportedExport, import_auto_ontology,
)


def mocked_native_document():
    return {'data_layer': {'databases': [{'id': 'db-1', 'dialect': 'sqlite', 'schemas': [
        {'id': 'schema-1', 'name': 'main', 'database_name': 'pilot', 'tables': [
            {'id': 'table-1', 'name': 'components', 'columns': [
                {'id': 'column-1', 'name': 'component_id', 'type': 'INTEGER',
                 'sample_values': [1, 2], 'is_nullable': False}]}]}]}],
        'foreign_keys': [{'source_column_id': 'column-1', 'target_column_id': 'column-1'}]},
        'semantic_layer': {'terms': [{'id': 'term-1', 'name': 'Component',
            'represents': ['table-1'], 'columns_attributes': [
                {'id': 'attribute-1', 'name': 'Identifier', 'column_id': 'column-1'}]}],
            'concepts': [{'id': 'concept-1', 'term_ids': ['term-1'],
                          'keys': [{'id': 'key-1', 'column_ids': ['column-1']}]}],
            'semantic_fks': [{'column_id': 'column-1', 'concept_key_id': 'key-1',
                              'column_attribute_id': 'attribute-1', 'use_in_join_paths': True}]}}


def convert(document=None, raw=None, **kwargs):
    return import_auto_ontology(raw if raw is not None else yaml.safe_dump(
        document if document is not None else mocked_native_document()).encode(),
        base_workspace_digest=kwargs.get('base_workspace_digest', 'a' * 64),
        source_hashes=kwargs.get('source_hashes', {'pilot.sqlite': 'b' * 64}))


class WorkspaceExtensionTests(unittest.TestCase):
    def test_mocked_native_shape_fields_references_and_provenance(self):
        raw = b'# retained exact comment\n' + yaml.safe_dump(mocked_native_document()).encode()
        result = convert(raw=raw)
        self.assertEqual(base64.b64decode(result['raw_base64']), raw)
        self.assertEqual(result['raw_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['upstream']['commit'], 'ee42eff638ebd136c1c4fe4ab290785f912bb4bc')
        self.assertEqual(result['validation_state'], 'parsed')
        self.assertEqual(len(result['concepts']), 5)
        self.assertEqual(len(result['fields']), 3)
        self.assertEqual(len(result['relations']), 2)
        self.assertTrue(all(r['target_id'] for r in result['references']))
        self.assertEqual(result['fields'][0]['source_payload']['sample_values'], [1, 2])
        self.assertEqual(result['base_workspace_digest'], 'a' * 64)

    def test_malicious_approval_and_sql_are_preserved_without_authority(self):
        document = mocked_native_document()
        document.update(status='approved', source_hashes={'forged': 'x'}, approved=True)
        document['semantic_layer']['terms'][0]['status'] = 'approved'
        document['semantic_layer']['sql_attributes'] = {'manual': [
            {'id': 'danger', 'sql': 'DROP TABLE components', 'approved': True}]}
        document['zones'] = [{'name': 'trusted', 'approved': 'true'}]
        result = convert(document)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['source_hashes'], {'pilot.sqlite': 'b' * 64})
        self.assertTrue(all(i['status'] == 'pending' for k in ('concepts', 'fields', 'relations') for i in result[k]))
        self.assertEqual(result['raw_document']['status'], 'approved')
        self.assertIn('DROP TABLE', str(result['unsupported']))
        self.assertTrue(any(x['reason'] == 'upstream_policy_not_inherited' for x in result['unsupported']))

    def test_unresolved_references_are_not_invented(self):
        doc = mocked_native_document()
        doc['semantic_layer']['terms'][0]['represents'] = ['absent-table']
        result = convert(doc)
        self.assertEqual(result['unresolved_references'][0]['source_id'], 'absent-table')
        self.assertIsNone(result['unresolved_references'][0]['target_id'])
        self.assertEqual(result['validation_state'], 'needs_review')

    def test_stable_source_ids_ignore_format_and_order_and_bind_new_snapshot(self):
        doc = mocked_native_document()
        first = convert(doc)
        second = convert(raw=yaml.safe_dump(doc, sort_keys=False).encode(), base_workspace_digest='c' * 64)
        self.assertEqual([i['id'] for i in first['concepts']], [i['id'] for i in second['concepts']])
        self.assertNotEqual(first['raw_sha256'], second['raw_sha256'])
        self.assertNotEqual(first['base_workspace_digest'], second['base_workspace_digest'])

    def test_parse_errors_and_unsupported_shape_are_separate(self):
        for raw in [b'!!python/object/apply:os.system ["false"]', b'a: 1\na: 2',
                    b'a: &a [*a]', b'\xff', b'[' * 40 + b']' * 40,
                    b'x' * 1_000_001, b'data_layer: [']:
            with self.subTest(raw=raw[:50]), self.assertRaises(ExtensionParseError):
                convert(raw=raw)
        for raw in [b'a: 1', b'[]', b'data_layer: []\nsemantic_layer: {}',
                    b'data_layer: {databases: text}\nsemantic_layer: {}']:
            with self.subTest(raw=raw), self.assertRaises(UnsupportedExport):
                convert(raw=raw)

    def test_duplicate_ids_and_invalid_binding_fail_closed(self):
        doc = mocked_native_document()
        doc['semantic_layer']['terms'].append(copy.deepcopy(doc['semantic_layer']['terms'][0]))
        with self.assertRaises(UnsupportedExport):
            convert(doc)
        with self.assertRaises(ValueError):
            convert(base_workspace_digest='not-a-digest')
        with self.assertRaises(ValueError):
            convert(source_hashes={'x': 'bad'})


class WorkspaceExtensionServiceTests(unittest.TestCase):
    """Real local service/store integration with mocked upstream YAML input."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from apps.factory_lab.workspace_service import WorkspaceService
        from tests.workspace_fixtures import approved
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'workspace.sqlite'
        self.service = WorkspaceService(self.path)
        self.row = self.service.store.create('Extension boundary fixture', approved())
        self.request = {'action': 'extension_import', 'id': self.row['id'],
                        'revision': self.row['revision'], 'request_key': 'native-1',
                        'raw_base64': base64.b64encode(yaml.safe_dump(mocked_native_document()).encode()).decode()}

    def test_pending_import_preserves_draft_and_approvals(self):
        before = copy.deepcopy(self.row)
        self.assertTrue(any(e['status'] == 'approved' for e in before['draft']['entries']))
        response = self.service.handle(self.request)
        self.assertFalse(response['reused'])
        operation = response['operation']
        self.assertEqual(operation['state'], 'completed')
        self.assertEqual(operation['kind'], 'extension_import')
        proposal = operation['result']
        self.assertEqual(proposal['status'], 'pending')
        self.assertEqual(proposal['base_workspace_digest'], before['digest'])
        self.assertEqual(proposal['source_hashes'], {s['name']: s['sha256'] for s in before['draft']['sources']})
        after = self.service.store.get(before['id'])
        self.assertEqual(after['draft'], before['draft'])
        self.assertEqual(after['revision'], before['revision'])
        self.assertEqual(after['digest'], before['digest'])

    def test_malformed_yaml_and_base64_are_saved_as_failed_immutable_operations(self):
        from apps.factory_lab.workspace_service import WorkspaceService
        for key, encoded in [('yaml-bad', base64.b64encode(b'data_layer: [').decode()),
                             ('base64-bad', '@@@not-base64')]:
            with self.subTest(key=key):
                request = {**self.request, 'request_key': key, 'raw_base64': encoded}
                operation = self.service.handle(request)['operation']
                self.assertEqual(operation['state'], 'failed')
                self.assertEqual(operation['request']['raw_base64'], encoded)
                self.assertIsNone(operation['result'])
                self.assertTrue(operation['error'])
                reopened = WorkspaceService(self.path)
                replay = reopened.handle(request)
                self.assertTrue(replay['reused'])
                self.assertEqual(replay['operation'], operation)
        self.assertEqual(self.service.store.get(self.row['id'])['draft'], self.row['draft'])
        self.assertEqual(len(self.service.store.operations(self.row['id'])), 2)

    def test_idempotency_restart_and_changed_request_conflict(self):
        from apps.factory_lab.workspace_service import WorkspaceService
        first = self.service.handle(self.request)['operation']
        restarted = WorkspaceService(self.path)
        again = restarted.handle(self.request)
        self.assertTrue(again['reused'])
        self.assertEqual(again['operation'], first)
        with self.assertRaisesRegex(ValueError, 'different input'):
            restarted.handle({**self.request, 'raw_base64': base64.b64encode(b'{}').decode()})
        self.assertEqual(len(restarted.store.operations(self.row['id'])), 1)

    def test_stale_new_import_rejected_but_historical_proposal_readable(self):
        from apps.factory_lab.workspace_service import WorkspaceService
        first = self.service.handle(self.request)['operation']
        changed = copy.deepcopy(self.row['draft'])
        changed['entries'][0]['note'] = 'Later local review note'
        latest = self.service.store.save(self.row['id'], changed, self.row['revision'])
        self.assertGreater(latest['revision'], self.row['revision'])
        with self.assertRaisesRegex(ValueError, 'current active revision'):
            self.service.handle({**self.request, 'request_key': 'stale-new'})
        reopened = WorkspaceService(self.path)
        saved = reopened.handle({'action': 'operation', 'id': self.row['id'], 'operation_id': first['id']})
        self.assertEqual(saved, first)
        self.assertEqual(saved['result']['base_workspace_digest'], self.row['digest'])
        # Replaying an old key reads the immutable operation; it does not
        # reserve a new operation or rebind the proposal to the new draft.
        self.assertTrue(reopened.handle(self.request)['reused'])
        self.assertEqual(len(reopened.store.operations(self.row['id'])), 1)
        self.assertEqual(reopened.store.get(self.row['id'])['draft'], changed)
