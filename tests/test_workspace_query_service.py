"""Actual saved query approval and full snapshot aggregation through service."""
import pytest
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_workspace_database_adapter import workspace


def test_scalar_query_saved_provenance_failure_and_dependency(tmp_path):
    import sqlite3
    from apps.factory_lab.workspace_database import SQLiteSources
    source = tmp_path / 'source.sqlite'
    with sqlite3.connect(source) as con:
        con.executescript("CREATE TABLE customers(id INTEGER, tier TEXT);"
                          "CREATE TABLE promotions(id INTEGER, tier TEXT);"
                          "INSERT INTO customers VALUES(1,'gold'),(2,NULL);"
                          "INSERT INTO promotions VALUES(10,'gold'),(11,'silver');")
    registry = SQLiteSources(tmp_path / 'registry')
    pack = registry.register(source, label='Authored scalar lifecycle')
    svc = WorkspaceService(tmp_path / 'workspace.sqlite', database_registry=registry)
    row = svc.handle({'action': 'create_database', 'title': 'Scalar lifecycle',
                      'source_id': pack['source_id'], 'metadata': {}, 'domain': 'generic'})
    row = svc.handle({'action': 'change', 'id': row['id'], 'revision': row['revision'],
        'decisions': [{'entry_id': e['id'], 'status': 'approved', 'target': 'source_only',
                      'note': 'Authored test review', 'interpretation': 'Recorded field'}
                     for e in row['draft']['entries']]})
    def field(table, column):
        return next(e['id'] for e in row['draft']['entries']
                    if e['source']['file'] == table and e['source']['column'] == column)
    def call(action, key, **body):
        return svc.handle({'action': action, 'id': row['id'], 'revision': row['revision'],
                           'request_key': key, **body})['operation']
    spec = {'id': 'same_snapshot_tier', 'title': 'Recorded tier matches',
        'question_scope': 'Match recorded promotion tier to selected customer tier',
        'root': {'entry_id': field('promotions', 'id'), 'alias': 'p'}, 'joins': [],
        'parameters': {'customer_id': 'integer'},
        'scalar_bindings': [{'name': 'tier', 'table_entry_id': field('customers', 'id'),
            'selector_entry_id': field('customers', 'id'), 'selector_type': 'integer',
            'parameter': 'customer_id', 'value_entry_id': field('customers', 'tier'),
            'value_type': 'text', 'cardinality': 'exactly_one',
            'null_policy': 'require_nonnull', 'comparison': 'binary_exact'}],
        'filters': [{'op': 'eq', 'left': {'kind': 'field', 'entry_id': field('promotions', 'tier'), 'alias': 'p'},
            'right': {'kind': 'scalar', 'binding': 'tier'}, 'value_type': 'text',
            'null_policy': 'unknown_excluded', 'comparison': 'binary_exact'}],
        'projection': [{'field': {'entry_id': field('promotions', 'id'), 'alias': 'p'}, 'name': 'promotion_id'}],
        'group_by': [], 'aggregates': [], 'distinct': False, 'output_kind': 'recorded_facts',
        'limitations': ['Authored software test only'], 'policy_references': [],
        'null_policy': 'exclude_from_aggregates_preserve_projection', 'empty_groups': 'absent', 'measure_grain': 'p'}
    proposed = call('database_query_propose', 'propose', spec=spec, origin={'kind': 'authored_test'}, relation_operation_ids=[])
    assert proposed['state'] == 'completed', proposed
    approved = call('database_query_approve', 'approve', proposal_operation_id=proposed['id'],
                    note='Reviewed exact source selection', human_confirmed=True)
    assert approved['state'] == 'completed', approved
    result = call('database_query_execute', 'execute', approval_operation_id=approved['id'], parameters={'customer_id': 1})
    assert result['state'] == 'completed', result
    assert result['result']['artifact']['rows'] == [{'promotion_id': 10}]
    assert result['result']['artifact']['scalar_binding_observations']
    assert call('database_query_execute', 'execute', approval_operation_id=approved['id'], parameters={'customer_id': 1}) == result
    for name, parameters, reason in [('absent', {'customer_id': 99}, 'absent'),
                                     ('null', {'customer_id': 2}, 'null_value'),
                                     ('injection', {'customer_id': 1, 'tier': 'silver'}, 'parameters')]:
        failed = call('database_query_execute', name, approval_operation_id=approved['id'], parameters=parameters)
        assert failed['state'] == 'failed', failed
        assert reason in str(failed['error']), failed
    row = svc.handle({'action': 'change', 'id': row['id'], 'revision': row['revision'], 'decisions': [
        {'entry_id': field('customers', 'tier'), 'status': 'pending', 'target': 'source_only', 'note': '', 'interpretation': ''}]})
    stale = call('database_query_execute', 'stale', approval_operation_id=approved['id'], parameters={'customer_id': 1})
    assert stale['state'] == 'failed'
    assert svc.store.operation(row['id'], result['id']) == result


def test_saved_contract_aggregate_reuse_and_revoked_dependency(workspace,tmp_path):
    adapter,draft,_=workspace
    svc=WorkspaceService(tmp_path/'workspace.sqlite',database_registry=adapter.registry)
    row=svc.handle({'action':'create_database','title':'Own DB','source_id':draft['database']['source_id'],'metadata':{},'domain':'generic'})
    entries=[e for e in row['draft']['entries'] if (e['source']['file'],e['source']['column']) in
             {('odd records','source code'),('authors','code'),('authors','label')}]
    row=svc.handle({'action':'change','id':row['id'],'revision':1,'decisions':[
        {'entry_id':e['id'],'status':'approved','target':'source_only','note':'','interpretation':'Source field reviewed'} for e in entries]})
    def entry(table,col):return next(e['id'] for e in entries if e['source']['file']==table and e['source']['column']==col)
    def call(action,key,**body):
        result=svc.handle({'action':action,'id':row['id'],'revision':row['revision'],'request_key':key,**body})
        assert result['operation']['state']=='completed',result
        return result['operation']
    rel=call('database_relation_propose','rel',spec={'id':'ownership','child_entry_id':entry('odd records','source code'),
        'parent_entry_id':entry('authors','code'),'interpretation':'Declared source ownership',
        'join_policy':'left_many_to_one_preserve_root'},origin={'kind':'user_configuration'})
    relapproved=call('database_relation_approve','rel-review',proposal_operation_id=rel['id'],note='Reviewed declared endpoints',human_confirmed=True)
    root={'entry_id':entry('odd records','source code'),'alias':'r'}
    label={'entry_id':entry('authors','label'),'alias':'a'}
    spec={'id':'by_author','title':'Records by author','question_scope':'Count recorded rows by referenced author',
          'root':root,'joins':[{'relation_id':'ownership','child_alias':'r','parent_alias':'a'}],
          'parameters':{},'filters':[],'projection':[{'field':label,'name':'author'}],'group_by':[label],
          'aggregates':[{'op':'count_rows','name':'records'}],'distinct':False,'output_kind':'recorded_facts',
          'limitations':['Recorded source only'],'policy_references':[],
          'null_policy':'exclude_from_aggregates_preserve_projection','empty_groups':'absent','measure_grain':'r'}
    proposal=call('database_query_propose','query',spec=spec,origin={'kind':'user_configuration'},relation_operation_ids=[relapproved['id']])
    approved=call('database_query_approve','query-review',proposal_operation_id=proposal['id'],note='Reviewed row-grain count',human_confirmed=True)
    executed=call('database_query_execute','execute',approval_operation_id=approved['id'],parameters={})
    assert executed['result']['artifact']['rows']==[{'author':'Example','records':12017}]
    assert call('database_query_execute','execute',approval_operation_id=approved['id'],parameters={})==executed
    # Changing only a required field interpretation invalidates saved contracts.
    row=svc.handle({'action':'change','id':row['id'],'revision':row['revision'],'decisions':[
        {'entry_id':entry('authors','label'),'status':'pending','target':'source_only','note':'','interpretation':''}]})
    failed=svc.handle({'action':'database_query_execute','id':row['id'],'revision':row['revision'],'request_key':'stale',
                       'approval_operation_id':approved['id'],'parameters':{}})['operation']
    assert failed['state']=='failed'
    assert svc.store.operation(row['id'],executed['id'])==executed


@pytest.mark.parametrize('failure', ['missing_adapter', 'changed_snapshot'])
def test_query_source_failure_is_durable_and_never_retried(workspace, tmp_path, failure):
    adapter, draft, _ = workspace
    svc = WorkspaceService(tmp_path / 'durable.sqlite', database_registry=adapter.registry)
    row = svc.handle({'action': 'create_database', 'title': 'Source failure',
                      'source_id': draft['database']['source_id'], 'metadata': {}, 'domain': 'generic'})
    # A missing source must be recorded before contract validation, without
    # pretending this deliberately empty definition has a valid approval.
    request = {'action': 'database_query_propose', 'id': row['id'], 'revision': row['revision'],
               'request_key': 'source-failure', 'spec': {}, 'origin': {}, 'relation_operation_ids': []}
    record = adapter.registry._record(draft['database']['source_id'])
    snapshot = adapter.registry.root / (record['source_id'] + '.sqlite')
    original = snapshot.read_bytes()
    if failure == 'missing_adapter':
        svc.database_adapter = None
    else:
        # Fault injection explicitly bypasses the registry's read-only snapshot.
        snapshot.chmod(0o600)
        snapshot.write_bytes(original + b'changed snapshot')
    first = svc.handle(request)
    assert first['operation']['state'] == 'failed'
    assert first['reused'] is False
    assert first['operation']['request']['spec'] == {}
    assert ('not configured' if failure == 'missing_adapter' else 'integrity mismatch') in first['operation']['error'].lower()
    # Repairing the connection does not implicitly rerun the failed attempt.
    svc.database_adapter = adapter
    if failure == 'changed_snapshot':
        snapshot.write_bytes(original)
        snapshot.chmod(0o400)
    second = svc.handle(request)
    assert second['reused'] is True and second['operation'] == first['operation']
    # An explicit new request is a new attempt and now reaches spec validation.
    fresh = svc.handle({**request, 'request_key': 'explicit-new-attempt'})
    assert fresh['operation']['state'] == 'failed'
    assert fresh['operation']['id'] != first['operation']['id']
    assert fresh['operation']['error'] != first['operation']['error']
