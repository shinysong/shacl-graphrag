"""Whole registered database reuse through saved workspace operations."""
import base64
from copy import deepcopy
import json
import threading

import httpx
import pytest
import yaml

from apps.factory_lab.workspace_service import WorkspaceService
from apps.factory_lab.public_runtime import Demo
from apps.factory_lab.public_server import make_server
from tests.test_workspace_database_adapter import workspace


@pytest.fixture
def service(workspace, tmp_path):
    adapter, draft, _ = workspace
    service = WorkspaceService(tmp_path / 'workspaces.sqlite', database_registry=adapter.registry)
    row = service.handle({'action': 'create_database', 'title': 'Arbitrary schema',
                          'source_id': draft['database']['source_id'], 'metadata': {},
                          'domain': 'organization'})
    return service, row


def field(row, column):
    return next(e for e in row['draft']['entries'] if e['source']['file'] == 'odd records'
                and e['source']['column'] == column)


def lookup(service, row, entry, value, key='lookup'):
    return service.handle({'action': 'lookup', 'id': row['id'], 'revision': row['revision'],
                           'request_key': key, 'selection': {'entry_id': entry['id'], 'value': value}})


def test_create_pending_review_query_export_restore(service, tmp_path):
    svc, row = service
    assert not row['model_questions']['enabled'] and not row['model_proposals']['enabled']
    assert row['mapping_targets'] == ['source_only']
    assert row['row_lookup_catalog'] == []
    key = field(row, 'arbitrary key')
    failed = lookup(svc, row, key, 12016, 'pending')['operation']
    assert failed['state'] == 'failed'
    decisions = [{'entry_id': field(row, column)['id'], 'status': 'approved',
                  'target': 'source_only', 'note': '', 'interpretation': 'Reviewed raw field'}
                 for column in ('arbitrary key', 'unfamiliar field')]
    reviewed = svc.handle({'action': 'change', 'id': row['id'], 'revision': 1, 'decisions': decisions})
    assert reviewed['revision'] == 2
    response = lookup(svc, reviewed, key, 12016)
    result = response['operation']['result']
    assert response['operation']['state'] == 'completed'
    assert result['records'][0]['values'] == {'arbitrary key': 12016, 'unfamiliar field': 'value-12016'}
    assert result['total_source_rows'] == 12017
    assert result['total_matching_rows'] == 1
    assert result['workspace']['draft_digest'] == reviewed['digest']
    assert lookup(svc, reviewed, key, 12016)['reused']
    assert svc.store.operation(row['id'], failed['id']) == failed
    exported = svc.handle({'action': 'export', 'id': row['id'], 'revision': 2})
    imported = svc.handle({'action': 'import', 'title': 'Imported', 'bundle': exported})
    assert imported['id'] != row['id'] and imported['row_lookup_catalog'] == reviewed['row_lookup_catalog']
    with pytest.raises(ValueError, match='not configured'):
        WorkspaceService(tmp_path / 'missing.sqlite').handle({'action': 'import', 'title': 'No registry', 'bundle': exported})
    diff = svc.handle({'action': 'diff', 'id': row['id'], 'before': 1, 'after': 2})
    assert len(diff['decision_changes']) == 2


def proposal(svc, row, name='odd records'):
    doc = {'data_layer': {'databases': [{'id': 'db', 'schemas': [{'id': 'schema', 'tables': [
        {'id': 'table', 'name': name, 'columns': [
            {'id': 'column-key', 'name': 'arbitrary key'},
            {'id': 'column-value', 'name': 'unfamiliar field'}]}]}]}]}, 'semantic_layer': {}}
    doc['data_layer']['foreign_keys'] = [{'source_column_id': 'column-key',
                                         'target_column_id': 'column-value'}]
    return svc.handle({'action': 'extension_import', 'id': row['id'], 'revision': row['revision'],
                       'request_key': 'import-proposal',
                       'raw_base64': base64.b64encode(yaml.safe_dump(doc).encode()).decode()})['operation']


def decisions(row, op):
    return [{'candidate_id': c['id'], 'entry_id': field(row, c['source_payload']['name'])['id'],
             'target': 'source_only', 'interpretation': 'Explicit reviewed meaning',
             'note': 'User decision', 'manual_binding': ''} for c in op['result']['fields']]


def test_external_batch_review_late_row_reuse_and_provenance(service):
    svc, row = service
    original = proposal(svc, row)
    assert original['state'] == 'completed' and original['result']['status'] == 'pending'
    assert original['result']['relations'][0]['status'] == 'pending'
    request = {'action': 'extension_review_batch', 'id': row['id'], 'revision': 1,
               'request_key': 'review-batch', 'operation_id': original['id'],
               'decisions': decisions(row, original)}
    reviewed = svc.handle(request)['operation']
    assert reviewed['state'] == 'completed', reviewed
    after = svc.view(row['id'])
    assert after['revision'] == 2
    assert after['draft']['relationship_proposals'] == row['draft']['relationship_proposals']
    assert all(not p['executable'] for p in after['draft']['relationship_proposals'])
    result = lookup(svc, after, field(row, 'arbitrary key'), 12016)['operation']['result']
    assert result['records'][0]['values']['unfamiliar field'] == 'value-12016'
    annotation = result['scope']['extension_reviews'][0]
    assert annotation['operation_id'] == original['id']
    assert annotation['source']['sha256'] == after['draft']['database']['snapshot_sha256']
    assert not annotation['producer_authenticated']
    assert svc.store.operation(row['id'], original['id']) == original
    assert svc.handle(request)['reused']
    exported = svc.handle({'action': 'export', 'id': row['id'], 'revision': 2})
    imported = svc.handle({'action': 'import', 'title': 'Annotated import', 'bundle': exported})
    assert imported['draft']['extension_reviews'] == after['draft']['extension_reviews']


def test_corrupted_snapshot_failures_are_saved_and_old_proposals_stay_pending(service):
    svc, row = service
    op = proposal(svc, row)
    source_id = row['draft']['database']['source_id']
    snapshot = svc.database_adapter.registry.root / (source_id + '.sqlite')
    snapshot.chmod(0o600)
    with snapshot.open('ab') as stream:
        stream.write(b'changed bytes')
    failed_lookup = lookup(svc, row, field(row, 'arbitrary key'), 12016)['operation']
    assert failed_lookup['state'] == 'failed' and 'integrity' in failed_lookup['error']
    reviewed = svc.handle({'action': 'extension_review_batch', 'id': row['id'], 'revision': 1,
                          'request_key': 'corrupt-review', 'operation_id': op['id'],
                          'decisions': decisions(row, op)})['operation']
    assert reviewed['state'] == 'failed' and 'integrity' in reviewed['error']
    assert svc.store.get(row['id'])['revision'] == 1
    assert svc.store.operation(row['id'], op['id']) == op


def test_external_wrong_target_and_manual_binding_fail_closed(service):
    svc, row = service
    op = proposal(svc, row, name='unrelated')
    decision = decisions(row, op)[0]
    request = {'action': 'extension_review', 'id': row['id'], 'revision': 1,
               'request_key': 'review', 'operation_id': op['id'], **decision}
    failed = svc.handle(request)['operation']
    assert failed['state'] == 'failed' and 'manual' in failed['error']
    failed = svc.handle({**request, 'request_key': 'wrong-target', 'manual_binding': 'Explicit match',
                         'target': 'products.id'})['operation']
    assert failed['state'] == 'failed'
    assert svc.store.get(row['id'])['revision'] == 1
    successful = svc.handle({**request, 'request_key': 'manual', 'manual_binding': 'Explicit match'})['operation']
    assert successful['state'] == 'completed'


def test_generic_unsupported_actions_and_mutation_do_not_call_gateway(service):
    svc, row = service
    disabled = svc.handle({'action': 'ask', 'request_key': 'ask',
        'question': 'Interpret documents', 'id': row['id'], 'revision': 1})['operation']
    assert disabled['state'] == 'failed'
    assert 'not enabled' in disabled['error']
    requests = [dict(action='execute', request_key='execute', case_id='anything'),
                dict(action='suggest', request_key='suggest'),
                dict(action='refresh', files=[])]
    for body in requests:
        with pytest.raises(ValueError, match='Unsupported database'):
            svc.handle({**body, 'id': row['id'], 'revision': 1})
    assert svc.store.get(row['id'])['revision'] == 1
    with pytest.raises(ValueError):
        svc.handle({'action': 'create_database', 'title': 'Path', 'source_id': '/etc/passwd',
                    'metadata': {}, 'domain': 'generic'})


def test_database_source_list_and_buffer_never_approves(service, tmp_path):
    svc, row = service
    public = svc.handle({'action': 'database_sources'})
    assert public['enabled'] and public['sources'][0]['total_rows'] == 12018
    assert public['sources'][0]['table_count'] == 2
    assert str(tmp_path) not in json.dumps(public)
    assert WorkspaceService(tmp_path / 'disabled.sqlite').handle({'action': 'database_sources'}) == {
        'enabled': False, 'sources': [], 'truncated': False}
    entry = field(row, 'arbitrary key')
    content = {'entries': [{'entry_id': entry['id'], 'status': 'approved', 'target': 'source_only',
                           'interpretation': '', 'note': ''}], 'policies': []}
    svc.handle({'action': 'save_review_buffer', 'id': row['id'], 'revision': 1,
                'generation': 0, 'content': content})
    assert svc.view(row['id'])['row_lookup_catalog'] == []
    assert lookup(svc, row, entry, 12016)['operation']['state'] == 'failed'


def test_optional_reasoning_receipt_does_not_approve_database_fields(service):
    from apps.factory_lab.workspace_reasoning import LocalReasoner
    svc, row = service
    calls=[]
    def runner(binary, raw, **kwargs):
        calls.append((binary, raw, kwargs['profile']))
        return {'status':'completed','test_runner':True}
    svc.local_reasoner=LocalReasoner('operator-configured-test-runner',runner=runner)
    assert svc.view(row['id'])['local_reasoning']['enabled']
    request={'action':'local_reasoning','id':row['id'],'revision':1,'request_key':'reason',
             'profile':'rdfs','asserted_base64':base64.b64encode(b'<urn:a> <urn:p> <urn:b> .').decode()}
    operation=svc.handle(request)['operation']
    assert operation['state']=='completed'
    assert operation['result']['workspace_membership']=='unverified'
    assert operation['result']['approval']=='not_granted'
    assert svc.store.get(row['id'])['draft']==row['draft']
    assert svc.handle(request)['reused'] and len(calls)==1


@pytest.mark.parametrize('configured', [False, True])
def test_public_server_registry_configuration_http(workspace, tmp_path, configured):
    adapter, draft, _ = workspace
    server = make_server(Demo(tmp_path / 'runs'), 0,
                         workspace_database_registry=adapter.registry.root if configured else None)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}') as client:
            headers = {'X-CSRF-Token': client.get('/api/config').json()['csrf']}
            response = client.post('/api/workspace', json={'action': 'database_sources'}, headers=headers)
            assert response.status_code == 200
            assert response.json()['enabled'] is configured
            payload = {'action': 'create_database', 'title': 'HTTP generic', 'domain': 'finance',
                       'source_id': draft['database']['source_id'], 'metadata': {}}
            response = client.post('/api/workspace', json=payload, headers=headers)
            assert response.status_code == (200 if configured else 400)
            if configured:
                assert response.json()['draft']['adapter'] == 'registered-database-1'
                assert response.json()['row_lookup_catalog'] == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_withdraw_reviewed_query_before_late_request_never_executes(service):
    svc, row = service
    request = {'approval_operation_id': 'not-yet-existing', 'parameters': {}}
    envelope = {'id': row['id'], 'revision': row['revision'], 'request_key': 'withdraw-query'}
    withdrawn = svc.handle({'action': 'withdraw_pending', **envelope,
                            'kind': 'database_query_execute', 'request': request})
    assert withdrawn['withdrawn']
    assert withdrawn['operation']['state'] == 'cancelled'
    late = svc.handle({'action': 'database_query_execute', **envelope, **request})
    assert late['operation'] == withdrawn['operation']
    assert len(svc.store.operations(row['id'])) == 1
    with pytest.raises(ValueError):
        svc.handle({'action': 'withdraw_pending', **envelope,
                    'kind': 'database_query_execute', 'request': {**request, 'parameters': {'x': 1}}})
    with pytest.raises(ValueError):
        svc.handle({'action': 'withdraw_pending', **envelope,
                    'kind': 'database_documents', 'request': {'offset': 0}})


def test_withdraw_paragraph_review_preserves_existing_attempt(service):
    svc, row = service
    request = {'document_id': 'doc', 'paragraph_id': 'paragraph',
               'document_sha256': 'a' * 64, 'interpretation': 'Recorded review'}
    op, _ = svc.store.begin(row['id'], row['revision'], 'already-running',
                            'database_document_review', request)
    result = svc.handle({'action': 'withdraw_pending', 'id': row['id'],
                         'revision': row['revision'], 'request_key': 'already-running',
                         'kind': 'database_document_review', 'request': request})
    assert not result['withdrawn']
    assert result['operation']['id'] == op['id']
    assert result['operation']['state'] == 'running'
