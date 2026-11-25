"""Trusted restore preserves real scripted-question query history without calls."""
from hashlib import sha256
import json
import sqlite3

import pytest

from apps.factory_lab.workspace_backup import create_backup, restore_backup
from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_service import WorkspaceService
from apps.factory_lab.workspace_source_documents import DocumentSources
from apps.factory_lab.workspace_store import WorkspaceStore
from test_workspace_database_question_service import ready, request  # real local fixture, scripted model


def test_restore_query_question_and_advisory_history_without_originals(ready, tmp_path):
    svc, row, gateway, approved, path, registry = ready
    question = svc.handle(request(row))['operation']
    child_id = question['result']['child_operations'][0]['operation_id']
    child = svc.store.operation(row['id'], child_id)
    # Generic saved external advisory/association history must not be filtered by kind.
    advisory, _ = svc.store.begin(row['id'], row['revision'], 'advisory', 'future_advisory_kind',
                                {'parent_operation_id': child_id})
    svc.store.finish(advisory['id'], 'completed', result={'advisory_only': True, 'parent': child_id})
    saved_advisory = svc.store.operation(row['id'], advisory['id'])
    doc_file = tmp_path / 'policy.txt'
    doc_file.write_text('Operator reference only.\n')
    docs = DocumentSources(tmp_path / 'docs', registry)
    source = row['draft']['database']
    document = docs.register(doc_file, source_id=source['source_id'], snapshot_sha256=source['snapshot_sha256'])
    svc.store.save_review_buffer(row['id'], row['revision'], 0, {'note': 'Unfinished review'})
    cancelled, _ = svc.store.begin(row['id'], row['revision'], 'cancelled', 'question', {})
    svc.store.request_cancel(row['id'], 'cancelled')
    svc.store.finish(cancelled['id'], 'cancelled', result={'phase': 'cancelled'})
    before = svc.store.operations(row['id'])
    bundle = tmp_path / 'backup'
    result = create_backup(path, registry.root, docs.root, bundle)
    # Mutable originals and original registries are unavailable after relocation.
    (tmp_path / 'source.sqlite').unlink()
    doc_file.unlink()
    registry.root.rename(tmp_path / 'old-registry')
    docs.root.rename(tmp_path / 'old-docs')
    restored = tmp_path / 'restored'
    restore_backup(bundle, restored, manifest_sha256=result['manifest_sha256'], trusted_local=True)
    restored_registry = SQLiteSources(restored / 'databases')
    restored_docs = DocumentSources(restored / 'documents', restored_registry)
    restarted = WorkspaceService(restored / 'workspace.sqlite', database_registry=restored_registry,
                                 source_documents=restored_docs)
    assert restarted.store.operations(row['id']) == before
    assert restarted.store.operation(row['id'], child_id) == child
    assert restarted.store.operation(row['id'], advisory['id']) == saved_advisory
    assert restarted.store.review_buffer(row['id']) == svc.store.review_buffer(row['id'])
    assert restarted.store.cancel_requested(cancelled['id'])
    replay = restarted.handle(request(row))
    assert replay['reused'] and replay['operation'] == question
    assert len(gateway.calls) == 2
    assert restarted.store.get(row['id']) == svc.store.get(row['id'])
    assert restored_docs.inspect(document['document_id'], source_id=source['source_id'],
        snapshot_sha256=source['snapshot_sha256'])['document_sha256'] == document['document_sha256']
    assert restored_registry.check_drift(source['source_id'])['status'] == 'source_unavailable'
    assert restored_docs.check_drift(document['document_id'], source_id=source['source_id'],
        snapshot_sha256=source['snapshot_sha256'])['status'] == 'source_unavailable'
    assert restarted.view(row['id'])['draft'] == row['draft']


def test_wal_snapshot_and_failed_history_preserved(ready, tmp_path):
    svc, row, _, _, path, registry = ready
    with sqlite3.connect(path) as writer:
        writer.execute('PRAGMA journal_mode=WAL')
        writer.execute('PRAGMA wal_autocheckpoint=0')
        writer.execute('UPDATE workspaces SET title=? WHERE id=?', ('Committed WAL title', row['id']))
        writer.commit()
        op, _ = svc.store.begin(row['id'], row['revision'], 'failed', 'test', {})
        svc.store.finish(op['id'], 'failed', error='Preserved failure')
        receipt = create_backup(path, registry.root, None, tmp_path / 'backup')
    restore_backup(tmp_path / 'backup', tmp_path / 'restore', manifest_sha256=receipt['manifest_sha256'], trusted_local=True)
    restored = WorkspaceStore(tmp_path / 'restore/workspace.sqlite')
    assert restored.get(row['id'])['title'] == 'Committed WAL title'
    assert restored.operations(row['id']) == svc.store.operations(row['id'])


def test_running_operation_fails_without_publishing(ready, tmp_path):
    svc, row, _, _, path, registry = ready
    svc.store.begin(row['id'], row['revision'], 'running', 'test', {})
    with pytest.raises(ValueError, match='Quiesce'):
        create_backup(path, registry.root, None, tmp_path / 'backup')
    assert not (tmp_path / 'backup').exists()


def test_corrupt_member_and_untrusted_restore_rejected(ready, tmp_path):
    _, _, _, _, path, registry = ready
    bundle = tmp_path / 'backup'
    receipt = create_backup(path, registry.root, None, bundle)
    dest = tmp_path / 'restore'
    with pytest.raises(ValueError, match='trusted-local'):
        restore_backup(bundle, dest, manifest_sha256=receipt['manifest_sha256'])
    with pytest.raises(ValueError, match='manifest hash'):
        restore_backup(bundle, dest, manifest_sha256='0' * 64, trusted_local=True)
    (bundle / 'workspace.sqlite').write_bytes(b'broken')
    with pytest.raises(ValueError, match='integrity'):
        restore_backup(bundle, dest, manifest_sha256=receipt['manifest_sha256'], trusted_local=True)
    assert not dest.exists()


def test_destination_isolation_and_manifest_traversal(ready, tmp_path):
    _, _, _, _, path, registry = ready
    with pytest.raises(ValueError, match='isolated'):
        create_backup(path, registry.root, None, registry.root / 'nested')
    receipt = create_backup(path, registry.root, None, tmp_path / 'backup')
    with pytest.raises(ValueError, match='not exist'):
        restore_backup(tmp_path / 'backup', registry.root, manifest_sha256=receipt['manifest_sha256'], trusted_local=True)
    manifest_path = tmp_path / 'backup/manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    manifest['files']['../escape'] = {'bytes': 0, 'sha256': sha256(b'').hexdigest()}
    data = json.dumps(manifest).encode(); manifest_path.write_bytes(data)
    with pytest.raises(ValueError, match='member path'):
        restore_backup(tmp_path / 'backup', tmp_path / 'restore', manifest_sha256=sha256(data).hexdigest(), trusted_local=True)
    assert not (tmp_path / 'restore').exists()
    assert not (tmp_path / 'escape').exists()


def test_missing_registered_input_fails_closed(ready, tmp_path):
    _, row, _, _, path, registry = ready
    (registry.root / (row['draft']['database']['source_id'] + '.sqlite')).unlink()
    with pytest.raises(OSError):
        create_backup(path, registry.root, None, tmp_path / 'backup')
    assert not (tmp_path / 'backup').exists()
