"""Authored receipt boundary tests; no actual native/provider execution."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from apps.factory_lab.auto_ontology_bridge import UPSTREAM_COMMIT
from apps.factory_lab.workspace_extension_receipt import associate_invocation
from apps.factory_lab.workspace_extension_receipt_cli import associate_saved_import
from apps.factory_lab.workspace_extensions import import_auto_ontology
from apps.factory_lab.workspace_store import WorkspaceStore


def digest(raw):
    return sha256(raw).hexdigest()


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'invocation'
        self.folder.mkdir(mode=0o700)
        self.iid = 'a' * 32
        self.source_id = 'b' * 32
        self.source = b'authored source bytes, not actual upstream execution'
        self.raw = b'data_layer: {}\nsemantic_layer: {}\n'
        self.schema = [{'name': 'authored', 'rows': 1}]
        self.proposal = import_auto_ontology(self.raw, base_workspace_digest='c' * 64,
            source_hashes={'authored': digest(self.source)})
        files = {'native-export.yaml': self.raw, self.iid + '.sqlite': self.source,
                 'schema.json': json.dumps(self.schema, indent=2).encode()}
        for name, raw in files.items():
            (self.folder / name).write_bytes(raw)
            (self.folder / name).chmod(0o600)
        self.receipt = {'format': 'auto-ontology-invocation-1', 'invocation_id': self.iid,
            'source_id': self.source_id, 'source_sha256': digest(self.source),
            'schema_sha256': digest(json.dumps(self.schema, sort_keys=True).encode()),
            'upstream_commit': UPSTREAM_COMMIT, 'mode': 'catalog',
            'status': 'returned_requires_review', 'returncode': 0,
            'semantic_status': 'not_requested', 'fallback_status': 'not_applicable',
            'connector_binding': {'database_name': self.iid, 'resolver': 'official_get_connectors',
                                  'snapshot_sha256': digest(self.source)},
            'stages': [{'stage': 'official_catalog_ingest_without_embeddings', 'status': 'returned'},
                       {'stage': 'official_scoped_native_export', 'status': 'returned',
                        'result': {'sha256': digest(self.raw), 'bytes': len(self.raw)}}],
            'outputs': [{'name': name, 'sha256': digest(raw), 'bytes': len(raw)}
                        for name, raw in files.items()]}
        self.save_receipt()

    def save_receipt(self):
        (self.folder / 'receipt.json').write_text(json.dumps(self.receipt))
        (self.folder / 'receipt.json').chmod(0o600)

    def link(self, **overrides):
        args = dict(invocation_dir=self.folder, current_source_id=self.source_id,
                    current_source_bytes=self.source, current_workspace_digest='c' * 64,
                    operator_id='test operator annotation')
        args.update(overrides)
        return associate_invocation(self.proposal, **args)

    def test_exact_link_preserves_original_and_pending(self):
        before = deepcopy(self.proposal)
        result = self.link()
        self.assertEqual(result['status'], 'linked')
        self.assertTrue(result['local_source_link_verified'])
        self.assertFalse(result['producer_authenticated'])
        self.assertFalse(result['upstream_input_verified'])
        self.assertEqual(result['approval'], 'not_granted')
        self.assertEqual(self.proposal, before)
        self.assertEqual(base64.b64decode(result['raw_receipt_base64']),
                         (self.folder / 'receipt.json').read_bytes())

    def test_tampered_export_source_and_schema_rejected(self):
        for name in ('native-export.yaml', self.iid + '.sqlite', 'schema.json'):
            with self.subTest(name=name):
                path = self.folder / name
                before = path.read_bytes()
                path.write_bytes(before + b' ')
                self.assertEqual(self.link()['status'], 'rejected')
                path.write_bytes(before)

    def test_status_pin_count_and_connector_are_checked(self):
        mutations = [lambda r: r.update(upstream_commit='0' * 40),
                     lambda r: r.update(status='failed'),
                     lambda r: r.update(returncode=True),
                     lambda r: r['stages'][0].update(status='failed'),
                     lambda r: r['stages'].pop(0),
                     lambda r: r['stages'][-1]['result'].update(bytes=0),
                     lambda r: r['outputs'][0].update(bytes=0),
                     lambda r: r['connector_binding'].update(snapshot_sha256='0' * 64),
                     lambda r: r.update(semantic_status='verified')]
        original = deepcopy(self.receipt)
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.receipt = deepcopy(original)
                mutate(self.receipt)
                self.save_receipt()
                result = self.link()
                self.assertEqual(result['status'], 'rejected')
                self.assertIsNotNone(result['raw_receipt_base64'])

    def test_current_binding_and_proposal_claims_cannot_be_forged(self):
        for args in ({'current_source_id': 'f' * 32}, {'current_source_bytes': b'new'},
                     {'current_workspace_digest': 'f' * 64}):
            with self.subTest(args=args):
                self.assertEqual(self.link(**args)['status'], 'rejected')
        self.proposal['verified'] = True
        self.assertEqual(self.link()['status'], 'rejected')

    def test_missing_untrusted_or_symlink_artifact_is_explicit_loss(self):
        path = self.folder / 'receipt.json'
        path.unlink()
        self.assertTrue(self.link()['losses'])
        self.save_receipt()
        path.chmod(0o666)
        self.assertTrue(self.link()['losses'])
        path.chmod(0o600)
        target = self.root / 'copied.json'
        path.rename(target)
        path.symlink_to(target)
        self.assertTrue(self.link()['losses'])

    def test_semantic_return_preserves_unverified_status_and_ledger(self):
        self.receipt.update(mode='semantic', semantic_status='not_verified',
            fallback_status='unknown_inspect_native_logs_and_gateway', request_id='request',
            reservation_id='reservation', cost_status='unreconciled_gateway_ledger_required')
        self.receipt['stages'][:1] = [
            {'stage': 'official_catalog_and_embedding_ingest', 'status': 'returned'},
            {'stage': 'official_semantic_compile', 'status': 'returned'}]
        self.save_receipt()
        linked = self.link()
        self.assertEqual(linked['status'], 'linked')
        self.assertEqual(linked['invocation_semantic_status'], 'not_verified')
        self.assertEqual(linked['invocation_reservation_id'], 'reservation')

    def test_invalid_json_preserved_but_not_linked(self):
        raw = b'{"verified":true,"verified":true}'
        (self.folder / 'receipt.json').write_bytes(raw)
        linked = self.link()
        self.assertEqual(linked['status'], 'rejected')
        self.assertEqual(base64.b64decode(linked['raw_receipt_base64']), raw)

    def saved_inputs(self):
        store = WorkspaceStore(self.root / 'workspace.sqlite')
        row = store.create('Receipt fixture', {'adapter': 'registered-database-1',
            'sources': [{'name': 'authored', 'sha256': digest(self.source)}],
            'database': {'source_id': self.source_id, 'snapshot_sha256': digest(self.source)}})
        proposal = import_auto_ontology(self.raw, base_workspace_digest=row['digest'],
                                       source_hashes={'authored': digest(self.source)})
        operation, _ = store.begin(row['id'], 1, 'import', 'extension_import', {})
        store.finish(operation['id'], 'completed', result=proposal)
        source = self.source
        class Registry:
            def _record(self, source_id):
                return {}
            def _data(self, record):
                return source
        args = dict(workspace_id=row['id'], revision=1, import_operation_id=operation['id'],
                    invocation_dir=self.folder, operator_id='test operator', request_key='association')
        return store, Registry(), args, operation['id'], proposal

    def test_durable_association_and_disabled_replay_leave_import_unchanged(self):
        store, registry, args, import_id, proposal = self.saved_inputs()
        result = associate_saved_import(store, registry, **args)
        self.assertEqual(result['operation']['state'], 'completed')
        self.assertEqual(result['operation']['kind'], 'extension_invocation_association')
        (self.folder / 'receipt.json').unlink()
        replay = associate_saved_import(store, None, **args)
        self.assertTrue(replay['reused'])
        self.assertEqual(result['operation'], replay['operation'])
        self.assertEqual(store.operation(args['workspace_id'], import_id)['result'], proposal)

    def test_rejected_attempt_retained_and_never_automatically_retried(self):
        store, registry, args, _, _ = self.saved_inputs()
        self.receipt['status'] = 'failed'
        self.save_receipt()
        first = associate_saved_import(store, registry, **args)
        self.assertEqual(first['operation']['state'], 'failed')
        self.assertIsNotNone(first['operation']['result']['raw_receipt_base64'])
        self.receipt['status'] = 'returned_requires_review'
        self.save_receipt()
        self.assertEqual(associate_saved_import(store, None, **args)['operation'], first['operation'])
        args['request_key'] = 'explicit-new-attempt'
        self.assertEqual(associate_saved_import(store, registry, **args)['operation']['state'], 'completed')

    def test_quota_failure_terminates_without_losing_original_import(self):
        store, registry, args, import_id, proposal = self.saved_inputs()
        with store.connect() as db:
            size = db.execute("SELECT SUM(length(CAST(content AS BLOB))) FROM revisions").fetchone()[0]
            size += db.execute("SELECT SUM(length(CAST(request AS BLOB))+COALESCE(length(CAST(result AS BLOB)),0)) FROM operations").fetchone()[0]
        request = {'import_operation_id': args['import_operation_id'],
                   'invocation_directory': str(Path(args['invocation_dir']).absolute()),
                   'operator_id': args['operator_id']}
        from apps.factory_lab.workspace_store import encode
        cap = size + len(encode(request).encode()) + 1
        with patch('apps.factory_lab.workspace_store.MAX_STORED_BYTES', cap):
            failed = associate_saved_import(store, registry, **args)
        self.assertEqual(failed['operation']['state'], 'failed')
        self.assertIsNone(failed['operation']['result'])
        self.assertIn('could not be stored', failed['operation']['error'])
        self.assertEqual(store.operation(args['workspace_id'], import_id)['result'], proposal)
        (self.folder / 'receipt.json').unlink()
        replay = associate_saved_import(store, None, **args)
        self.assertTrue(replay['reused'])
        self.assertEqual(replay['operation'], failed['operation'])

    def test_group_writable_receipt_is_rejected_with_explicit_loss(self):
        (self.folder / 'receipt.json').chmod(0o660)
        result = self.link()
        self.assertEqual(result['status'], 'rejected')
        self.assertIsNone(result['raw_receipt_base64'])
        self.assertTrue(result['losses'])
