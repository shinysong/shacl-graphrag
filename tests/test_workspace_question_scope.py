"""Authored offline scope-record tests; no evaluation data or semantic oracle."""
from copy import deepcopy
import hashlib
import json
import sqlite3

import pytest

from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_service import WorkspaceService
from apps.factory_lab.workspace_source_documents import DocumentSources
from apps.factory_lab.workspace_question_scope import handle


@pytest.fixture
def context(tmp_path):
    path = tmp_path / 'authored.sqlite'
    with sqlite3.connect(path) as con:
        con.executescript('CREATE TABLE observations (id INTEGER, description TEXT); '
                          "INSERT INTO observations VALUES (1, 'review supplied by operator');")
    registry = SQLiteSources(tmp_path / 'registry')
    source = registry.register(path, label='Authored scope test')
    svc = WorkspaceService(tmp_path / 'workspace.sqlite', database_registry=registry)
    row = svc.handle({'action': 'create_database', 'title': 'Scope test',
                      'source_id': source['source_id'], 'metadata': {}, 'domain': 'generic'})
    row = svc.handle({'action': 'change', 'id': row['id'], 'revision': row['revision'],
                     'decisions': [{'entry_id': e['id'], 'status': 'approved',
                                    'target': 'source_only', 'note': '',
                                    'interpretation': 'Authored recorded field'}
                                   for e in row['draft']['entries']]})
    return svc, row


def request(row, **changes):
    return {'action': 'database_question_scope', 'id': row['id'], 'revision': row['revision'],
            'request_key': 'scope', 'question': 'What independent verification is available?',
            'unresolved_requirements': ['Independent verification record'],
            'reason_kind': 'needs_external_verification',
            'assessment_note': 'I have not supplied an independent verification source.',
            'evidence_operation_ids': [], 'human_confirmed': True, **changes}


def record(svc, row, **changes):
    body = request(row, **changes)
    return handle(svc, body['action'], body, row)


def query(svc, row):
    entry = row['draft']['entries'][0]['id']
    field = {'entry_id': entry, 'alias': 'r'}
    spec = {'id': 'authored', 'title': 'Recorded observations',
            'question_scope': 'Read authored recorded IDs', 'root': field,
            'joins': [], 'parameters': {}, 'filters': [],
            'projection': [{'field': field, 'name': 'recorded_id'}],
            'group_by': [], 'aggregates': [], 'distinct': False,
            'output_kind': 'recorded_facts', 'limitations': ['Authored offline test'],
            'policy_references': [], 'null_policy': 'exclude_from_aggregates_preserve_projection',
            'empty_groups': 'absent', 'measure_grain': 'r'}
    def call(action, key, **body):
        op = svc.handle({'action': action, 'id': row['id'], 'revision': row['revision'],
                         'request_key': key, **body})['operation']
        assert op['state'] == 'completed', op
        return op
    proposed = call('database_query_propose', 'query', spec=spec,
                    origin={'kind': 'authored_test'}, relation_operation_ids=[])
    approved = call('database_query_approve', 'approve', proposal_operation_id=proposed['id'],
                    note='Authored review', human_confirmed=True)
    return call('database_query_execute', 'execute', approval_operation_id=approved['id'], parameters={})


def document(svc, row, tmp_path):
    binding = {k: row['draft']['database'][k] for k in ('source_id', 'snapshot_sha256')}
    path = tmp_path / 'authored.txt'
    path.write_text('An authored source paragraph; no completeness claim.\n')
    docs = DocumentSources(tmp_path / 'documents', svc.database_adapter.registry)
    saved = docs.register(path, **binding, label='Authored note', version='1')
    svc.source_documents = docs
    paragraph = docs.inspect(saved['document_id'], **binding)['paragraphs'][0]
    reviewed = svc.handle({'action': 'database_document_review', 'id': row['id'],
        'revision': row['revision'], 'request_key': 'doc-review',
        'document_id': saved['document_id'], 'paragraph_id': paragraph['paragraph_id'],
        'document_sha256': saved['document_sha256'], 'interpretation': 'An authored note only.'})['operation']
    return svc.handle({'action': 'database_document_read', 'id': row['id'],
        'revision': row['revision'], 'request_key': 'doc-read',
        'review_operation_id': reviewed['id']})['operation']


def test_record_inventory_explicit_evidence_hashes_and_no_automatic_calls(context, tmp_path, monkeypatch):
    svc, row = context
    executed = query(svc, row)
    read = document(svc, row, tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('Scope recording must not execute an answer or call a model')
    from apps.factory_lab.workspace_query_contracts import ReviewedQueryContracts
    monkeypatch.setattr(ReviewedQueryContracts, 'execute', forbidden)
    svc.question_gateway = forbidden
    svc.proposal_gateway = forbidden
    result = record(svc, row, evidence_operation_ids=[executed['id'], read['id']])['operation']
    assert result['state'] == 'completed', result
    data = result['result']
    assert data['status'] == 'reviewer_stated_unresolved'
    assert data['scope_verified'] is data['absence_verified'] is False
    assert data['source'] == row['draft']['database']
    assert data['schema_inventory'][0]['name'] == 'observations'
    assert data['schema_inventory'][0]['row_count'] == 1
    assert 'sample' not in data['schema_inventory'][0]
    assert len(data['evidence']) == 2
    for actual, saved in zip(data['evidence'], [executed, read]):
        encoded = json.dumps(saved['result'], ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode()
        assert actual['result_sha256'] == hashlib.sha256(encoded).hexdigest()
    assert data['evidence'][0]['summary']['saved_row_count'] == 1
    assert data['evidence'][1]['summary']['paragraph_sha256']
    assert record(svc, row, evidence_operation_ids=[executed['id'], read['id']])['reused']
    # No supplied evidence is also honest: no silent selection of these operations.
    empty = record(svc, row, request_key='no-selection')['operation']['result']
    assert empty['evidence'] == []


@pytest.mark.parametrize('change', [
    {'question': ''}, {'question': 'x' * 4001}, {'assessment_note': ''},
    {'assessment_note': 'x' * 4001}, {'human_confirmed': 1},
    {'unresolved_requirements': []}, {'unresolved_requirements': ['x'] * 21},
    {'unresolved_requirements': ['x' * 1001]}, {'unresolved_requirements': [42]},
    {'reason_kind': 'verified_absent'}, {'reason_kind': []},
    {'evidence_operation_ids': ['x', 'x']}, {'evidence_operation_ids': [None]},
    {'evidence_operation_ids': ['x' * 201]}, {'evidence_operation_ids': 'all'},
    {'unrequested_answer': 'fabricated'},
])
def test_invalid_records_are_durable_and_replayable(context, change):
    svc, row = context
    first = record(svc, row, **change)
    assert first['operation']['state'] == 'failed'
    svc.database_adapter = None
    assert record(svc, row, **change) == {**first, 'reused': True}


def test_disabled_optional_dependencies_and_all_reason_labels(context):
    svc, row = context
    assert svc.source_documents is None and svc.local_reasoner is None
    for reason in ('source_not_supplied', 'retrieval_not_performed', 'unsupported_operation',
                   'needs_external_verification'):
        result = record(svc, row, request_key=reason, reason_kind=reason)['operation']
        assert result['state'] == 'completed'
        assert result['result']['absence_verified'] is False


@pytest.mark.parametrize('failure', ['unavailable', 'changed_snapshot'])
def test_restore_failure_reserved_and_replay_before_dependencies(context, failure):
    svc, row = context
    adapter = svc.database_adapter
    if failure == 'unavailable':
        svc.database_adapter = None
    else:
        path = adapter.registry.root / (row['draft']['database']['source_id'] + '.sqlite')
        original = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(original + b'changed')
    first = record(svc, row)
    assert first['operation']['state'] == 'failed'
    svc.database_adapter = adapter
    if failure != 'unavailable':
        path.write_bytes(original)
        path.chmod(0o400)
    assert record(svc, row) == {**first, 'reused': True}
    assert record(svc, row, request_key='explicit-new')['operation']['state'] == 'completed'


def test_saved_success_replay_history_and_new_stale_rejected(context):
    svc, row = context
    first = record(svc, row)
    changed = deepcopy(row['draft'])
    changed['metadata'] = {'new_revision': True}
    svc.store.save(row['id'], changed, row['revision'])
    svc.database_adapter = None
    assert record(svc, row) == {**first, 'reused': True}
    assert svc.store.operation(row['id'], first['operation']['id']) == first['operation']
    with pytest.raises(ValueError, match='current active revision'):
        record(svc, row, request_key='new-old-revision')
    assert first['operation']['id'] in svc.store.historical_operation_ids(row['id'], row['revision'] + 1)


def test_references_reject_cross_workspace_wrong_kind_failed_stale_and_missing(context):
    svc, row = context
    executed = query(svc, row)
    wrong = record(svc, row, request_key='wrong-kind')['operation']
    failed = record(svc, row, request_key='failed', human_confirmed=False)['operation']
    for oid in (wrong['id'], failed['id'], 'does-not-exist'):
        assert record(svc, row, request_key=oid, evidence_operation_ids=[oid])['operation']['state'] == 'failed'
    other = svc.store.create('Other workspace', row['draft'])
    other = svc.store.get(other['id'])
    assert record(svc, other, evidence_operation_ids=[executed['id']])['operation']['state'] == 'failed'
    changed = deepcopy(row['draft'])
    changed['metadata'] = {'revision': 'changed'}
    svc.store.save(row['id'], changed, row['revision'])
    current = svc.store.get(row['id'])
    assert record(svc, current, request_key='stale-evidence', evidence_operation_ids=[executed['id']])['operation']['state'] == 'failed'


def test_document_unavailable_and_source_binding_rejected(context, tmp_path):
    svc, row = context
    read = document(svc, row, tmp_path)
    svc.source_documents = None
    failed = record(svc, row, evidence_operation_ids=[read['id']])['operation']
    assert failed['state'] == 'failed' and 'unavailable' in failed['error']
    executed = query(svc, row)
    # Explicit synthetic store corruption is not an end-user accepted artifact.
    corrupt = deepcopy(executed['result'])
    corrupt['artifact']['provenance']['source']['snapshot_sha256'] = '0' * 64
    with svc.store.connect() as db:
        db.execute('UPDATE operations SET result=? WHERE id=?',
                   (json.dumps(corrupt), executed['id']))
    failed = record(svc, row, request_key='wrong-binding', evidence_operation_ids=[executed['id']])['operation']
    assert failed['state'] == 'failed' and 'binding' in failed['error']


def test_size_bound_is_saved_failure(context, monkeypatch):
    svc, row = context
    from apps.factory_lab import workspace_question_scope as scope
    monkeypatch.setattr(scope, 'MAX_RECORD_BYTES', 10)
    failed = record(svc, row)['operation']
    assert failed['state'] == 'failed' and 'byte bound' in failed['error']


def test_public_dispatch_restart_replay_and_request_conflict(context):
    svc, row = context
    body = request(row)
    first = svc.handle(body)
    assert first['operation']['state'] == 'completed', first
    restarted = WorkspaceService(svc.store.path)
    assert restarted.handle(body) == {**first, 'reused': True}
    assert restarted.handle({'action': 'operation', 'id': row['id'],
                             'operation_id': first['operation']['id']}) == first['operation']
    with pytest.raises(ValueError, match='different'):
        restarted.handle({**body, 'assessment_note': 'Changed request under the same key'})
