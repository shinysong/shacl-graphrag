"""Actual local fixed-query lifecycle with scripted provider responses."""
from copy import deepcopy
import json
import sqlite3

import pytest

from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_service import WorkspaceService
from apps.factory_lab import workspace_database_question_service as routing


class Gateway:
    config = {'model': 'scripted-offline', 'provider': 'test-only'}
    def __init__(self):
        self.calls = []; self.selected = None; self.before_call = None
    def call(self, parent, messages):
        self.calls.append((parent, deepcopy(messages)))
        if self.before_call: self.before_call(len(self.calls))
        packet = json.loads(messages[1]['content'])
        if 'catalog' in packet:
            ident = self.selected or packet['catalog'][0]['approval_operation_id']
            answer = {'calls': [{'approval_operation_id': ident, 'parameters': {'minimum': 2}}],
                      'unresolved': ['Source truth unverified']}
        else:
            answer = {'answer': 'Scripted description of the executed rows', 'citations': ['e1'], 'unresolved': []}
        return {'content': json.dumps(answer), 'receipt': {'call_id': f'local-{len(self.calls)}'}}


@pytest.fixture
def ready(tmp_path):
    source = tmp_path / 'source.sqlite'
    with sqlite3.connect(source) as con:
        con.executescript('CREATE TABLE "unfamiliar table" (code INTEGER, units INTEGER);'
                          'INSERT INTO "unfamiliar table" VALUES (1,1),(2,3),(3,5);')
    registry = SQLiteSources(tmp_path / 'registry'); pack = registry.register(source)
    gateway = Gateway(); path = tmp_path / 'workspace.sqlite'
    svc = WorkspaceService(path, database_registry=registry, question_gateway=gateway)
    row = svc.handle({'action': 'create_database', 'title': 'Unfamiliar schema',
        'source_id': pack['source_id'], 'metadata': {}, 'domain': 'unfamiliar'})
    row = svc.handle({'action': 'change', 'id': row['id'], 'revision': row['revision'],
        'decisions': [{'entry_id': e['id'], 'status': 'approved', 'target': 'source_only',
                      'note': '', 'interpretation': 'Recorded source field'} for e in row['draft']['entries']]})
    def field(name): return next(e['id'] for e in row['draft']['entries'] if e['source']['column'] == name)
    ref = {'entry_id': field('units'), 'alias': 'u'}
    spec = {'id': 'unit_count', 'title': 'Count matching units', 'question_scope': 'Count rows with units at least minimum',
        'root': {'entry_id': field('code'), 'alias': 'u'}, 'joins': [], 'parameters': {'minimum': 'integer'},
        'filters': [{'field': ref, 'op': 'gte', 'parameter': 'minimum'}], 'projection': [], 'group_by': [],
        'aggregates': [{'op': 'count_rows', 'name': 'records'}], 'distinct': False, 'output_kind': 'recorded_facts',
        'limitations': ['Test fixture only'], 'policy_references': [],
        'null_policy': 'exclude_from_aggregates_preserve_projection', 'empty_groups': 'absent', 'measure_grain': 'u'}
    def call(action, key, **body):
        op = svc.handle({'action': action, 'id': row['id'], 'revision': row['revision'],
                         'request_key': key, **body})['operation']
        assert op['state'] == 'completed', op
        return op
    pending = call('database_query_propose', 'propose', spec=spec, origin={'kind': 'software_test'}, relation_operation_ids=[])
    approved = call('database_query_approve', 'approve', proposal_operation_id=pending['id'],
                    note='Reviewed test contract', human_confirmed=True)
    return svc, row, gateway, approved, path, registry


def request(row, key='ask'):
    return {'action': 'ask', 'id': row['id'], 'revision': row['revision'],
            'request_key': key, 'question': 'Count rows whose units are at least two'}


def test_actual_query_parity_restart_and_disabled_dependency_replay(ready):
    svc, row, gateway, approval, path, registry = ready
    assert svc.view(row['id'])['model_questions']['enabled']
    assert not svc.view(row['id'])['model_proposals']['enabled']
    typed = svc.handle({'action': 'database_query_execute', 'id': row['id'], 'revision': row['revision'],
        'request_key': 'typed', 'approval_operation_id': approval['id'], 'parameters': {'minimum': 2}})['operation']
    response = svc.handle(request(row)); op = response['operation']
    assert op['state'] == 'completed', op
    result = op['result']; evidence = result['evidence'][0]['result']
    assert evidence['artifact'] == typed['result']['artifact']
    assert evidence['artifact']['rows'] == [{'records': 2}]
    child = svc.store.operation(row['id'], evidence['execution_operation_id'])
    assert child['id'] == result['child_operations'][0]['operation_id']
    assert child['request']['approval_operation_id'] == approval['id']
    assert result['catalog_preflight']['complete']
    descriptor = result['catalog'][0]
    assert all(descriptor[k] == value for k, value in approval['result']['artifact']['spec'].items())
    assert descriptor['distinct'] is False
    assert {f['column'] for f in descriptor['fields']} == {'code', 'units'}
    assert all(f['table'] == 'unfamiliar table' for f in descriptor['fields'])
    assert all(f['reviewed_interpretation'] == 'Recorded source field' for f in descriptor['fields'])
    assert all(f['reviewed_target'] == 'source_only' for f in descriptor['fields'])
    assert str(path.parent) not in json.dumps(descriptor)
    assert result['model_responses'][0]['receipt']['call_id'] == 'local-1'
    assert len(gateway.calls) == 2
    # Neither source adapter nor question gateway is needed to replay the parent.
    restarted = WorkspaceService(path)
    replay = restarted.handle(request(row))
    assert replay['reused'] and replay['operation'] == op
    assert len(gateway.calls) == 2


def test_unadvertised_choice_preserved_without_query_execution(ready):
    svc, row, gateway, *_ = ready
    gateway.selected = 'not-approved'
    op = svc.handle(request(row))['operation']
    assert op['state'] == 'failed'
    assert op['result']['plan']['calls'][0]['approval_operation_id'] == 'not-approved'
    assert op['result']['child_operations'] == []
    assert len(gateway.calls) == 1


def test_revoked_field_excludes_old_approval_but_allows_source_exploration(ready):
    svc, row, gateway, approval, *_ = ready
    entry = row['draft']['entries'][0]
    row = svc.handle({'action': 'change', 'id': row['id'], 'revision': row['revision'],
        'decisions': [{'entry_id': entry['id'], 'status': 'pending', 'target': 'source_only', 'note': '', 'interpretation': ''}]})
    def explore_call(parent, messages):
        gateway.calls.append((parent, deepcopy(messages)))
        packet=json.loads(messages[1]['content'])
        response=({'calls':[{'tool':'explore_repository','arguments':{'action':'overview'}}],
                   'unresolved':['Business query approval is stale']} if 'catalog' in packet else
                  {'answer':'Saved schema only','citations':['e1'],'unresolved':['Business query approval is stale']})
        return {'content':json.dumps(response)}
    gateway.call=explore_call
    op = svc.handle(request(row))['operation']
    assert op['state'] == 'completed'
    assert op['result']['catalog'] == []
    assert op['result']['catalog_preflight']['exclusions'][0]['approval_operation_id'] == approval['id']
    assert op['result']['unresolved']
    assert len(gateway.calls) == 2
    assert op['result']['child_operations'] == []


def test_catalog_pagination_and_failed_approval_exclusion(ready):
    svc, row, gateway, approval, *_ = ready
    for n in range(22):
        op, _ = svc.store.begin(row['id'], row['revision'], f'filler-{n}', 'lookup', {})
        svc.store.finish(op['id'], 'failed', error='Authored test record')
    failed, _ = svc.store.begin(row['id'], row['revision'], 'failed-approval', 'database_query_approve', {})
    svc.store.finish(failed['id'], 'failed', error='Authored failed approval')
    op = svc.handle(request(row))['operation']
    assert op['state'] == 'completed', op
    assert op['result']['catalog_preflight']['scanned_count'] > 20
    assert op['result']['catalog'][0]['approval_operation_id'] == approval['id']
    assert op['result']['catalog_preflight']['exclusions'][0]['state'] == 'failed'


def test_scan_limit_stops_before_provider(ready, monkeypatch):
    svc, row, gateway, *_ = ready
    monkeypatch.setattr(routing, 'MAX_SCAN', 2)
    op = svc.handle(request(row))['operation']
    assert op['state'] == 'failed'
    assert 'scan limit' in op['error']
    assert gateway.calls == []
    assert not op['result']['catalog_preflight']['complete']


def test_candidate_limit_stops_before_provider(ready, monkeypatch):
    svc, row, gateway, *_ = ready
    monkeypatch.setattr(routing.coordinator, 'MAX_CATALOG', 0)
    op = svc.handle(request(row))['operation']
    assert op['state'] == 'failed'
    assert 'executable approvals' in op['error']
    assert gateway.calls == []


def test_failed_child_retains_durable_reference(ready, monkeypatch):
    svc, row, gateway, *_ = ready
    original = routing.queries.handle
    def broken(service, action, body, current, **kwargs):
        changed = dict(body, parameters={'minimum': 'wrong-type'})
        return original(service, action, changed, current, **kwargs)
    monkeypatch.setattr(routing.queries, 'handle', broken)
    op = svc.handle(request(row))['operation']
    assert op['state'] == 'completed', op
    assert op['result']['evidence'][0]['state'] == 'failed'
    child = svc.store.operation(row['id'], op['result']['child_operations'][0]['operation_id'])
    assert child['state'] == 'failed'
    assert len(gateway.calls) == 1
    assert op['result']['citations'] == []


def test_cancel_parent_during_child_stops_child_and_retains_reference(ready, monkeypatch):
    svc, row, gateway, *_ = ready
    original = routing.queries.handle
    def cancel_inside(service, action, body, current, **kwargs):
        svc.store.request_cancel(row['id'], 'ask')
        # Avoid waiting for polling interval: this tests actual composition and execution cancellation.
        kwargs['parent_cancel'] = lambda: True
        return original(service, action, body, current, **kwargs)
    monkeypatch.setattr(routing.queries, 'handle', cancel_inside)
    op = svc.handle(request(row))['operation']
    assert op['state'] == 'cancelled', op
    child = svc.store.operation(row['id'], op['result']['child_operations'][0]['operation_id'])
    assert child['state'] == 'cancelled'
    assert len(gateway.calls) == 1


def test_gateway_failure_does_not_erase_completed_child(ready):
    svc, row, gateway, *_ = ready
    def fail_answer(number):
        if number == 2: raise RuntimeError('Scripted provider outage')
    gateway.before_call = fail_answer
    op = svc.handle(request(row))['operation']
    assert op['state'] == 'failed'
    assert op['result']['evidence'][0]['result']['artifact']['rows'] == [{'records': 2}]
    assert svc.handle(request(row))['operation'] == op
    assert len(gateway.calls) == 2


def test_receipt_capable_gateway_is_preferred(ready):
    svc, row, gateway, *_ = ready
    calls = []
    def with_receipt(parent, messages):
        calls.append(parent)
        response = gateway.call(parent, messages)
        response['receipt'] = {'call_id': 'offline-safe-receipt', 'returned_provider': None}
        return response
    gateway.call_with_receipt = with_receipt
    op = svc.handle(request(row))['operation']
    assert op['state'] == 'completed', op
    assert len(calls) == 2
    assert op['result']['model_responses'][0]['receipt']['returned_provider'] is None


def test_unexpected_child_failure_still_links_saved_attempt(ready, monkeypatch):
    svc, row, gateway, *_ = ready
    def failure(service, action, body, current, **kwargs):
        child, _ = service.store.begin(row['id'], row['revision'], body['request_key'],
                                      action, {'approval_operation_id': body['approval_operation_id'],
                                               'parameters': body['parameters']})
        service.store.finish(child['id'], 'failed', error='Injected unexpected failure')
        raise RuntimeError('Injected failure after durable child finish')
    monkeypatch.setattr(routing.queries, 'handle', failure)
    op = svc.handle(request(row))['operation']
    assert op['state'] == 'failed'
    child = svc.store.operation(row['id'], op['result']['child_operations'][0]['operation_id'])
    assert child['state'] == 'failed'
    assert len(gateway.calls) == 1


def test_catalog_keeps_every_approved_traversal_setting(ready, monkeypatch):
    svc, row, gateway, approval, *_ = ready
    original = deepcopy(approval['result']['artifact'])
    # Projection-boundary regression: authoritative validation is independently
    # exercised by other tests. Here inject a validated traversal-shaped envelope
    # to ensure no endpoint/role/seed/comparison setting disappears in projection.
    original['spec'].update(query_kind='directed_reachability', source_entry_id='src',
        destination_entry_id='dst', node_entry_id='node', edge_id_entry_id='edge',
        source_relation_id='out', destination_relation_id='in', node_key_type='integer',
        direction='forward', comparison='binary_exact', seed_policy='require_existing_node',
        endpoint_policy='require_existing_node', include_seed=False, node_semantics='distinct_reachable')
    monkeypatch.setattr(routing, 'validate_approval', lambda *args: original)
    catalog = routing.build_catalog(svc, row, {}, lambda: False)
    assert len(catalog) == 1
    assert all(catalog[0][k] == v for k, v in original['spec'].items())
    assert catalog[0]['source_relation_id'] != catalog[0]['destination_relation_id']
