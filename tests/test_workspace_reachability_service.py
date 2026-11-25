"""Durable traversal approvals and incomplete outcomes over an authored graph."""
from copy import deepcopy
import sqlite3

from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_service import WorkspaceService


def test_saved_traversal_bounds_reuse_and_stale_dependency(tmp_path):
    source = tmp_path / 'graph.sqlite'
    with sqlite3.connect(source) as con:
        con.executescript('''CREATE TABLE nodes(id INTEGER PRIMARY KEY);
            CREATE TABLE edges(id INTEGER PRIMARY KEY, src INTEGER REFERENCES nodes(id),
                               dst INTEGER REFERENCES nodes(id), relation TEXT);
            INSERT INTO nodes VALUES(0),(1),(2),(3),(4);
            INSERT INTO edges VALUES(10,0,1,'depends'),(11,1,2,'depends'),
                (12,2,0,'depends'),(13,0,3,'other');''')
    registry = SQLiteSources(tmp_path / 'registry')
    pack = registry.register(source, label='Authored directed cycle')
    svc = WorkspaceService(tmp_path / 'workspace.sqlite', database_registry=registry)
    row = svc.handle({'action': 'create_database', 'title': 'Directed lifecycle',
                      'source_id': pack['source_id'], 'metadata': {}, 'domain': 'generic'})
    row = svc.handle({'action': 'change', 'id': row['id'], 'revision': row['revision'],
        'decisions': [{'entry_id': e['id'], 'status': 'approved', 'target': 'source_only',
                      'note': 'Authored test review', 'interpretation': 'Recorded source field'}
                     for e in row['draft']['entries']]})
    def field(table, column):
        return next(e['id'] for e in row['draft']['entries']
                    if e['source']['file'] == table and e['source']['column'] == column)
    def call(action, key, **body):
        return svc.handle({'action': action, 'id': row['id'], 'revision': row['revision'],
                           'request_key': key, **body})['operation']
    saved_relations = []
    for endpoint in ['src', 'dst']:
        p = call('database_relation_propose', endpoint, spec={
            'id': endpoint, 'child_entry_id': field('edges', endpoint),
            'parent_entry_id': field('nodes', 'id'), 'interpretation': 'Recorded endpoint',
            'join_policy': 'left_many_to_one_preserve_root'}, origin={'kind': 'authored_test'})
        assert p['state'] == 'completed', p
        a = call('database_relation_approve', endpoint + '_approved',
                 proposal_operation_id=p['id'], note='Review endpoint', human_confirmed=True)
        assert a['state'] == 'completed', a
        saved_relations.append(a['id'])
    spec = {'id': 'downstream', 'title': 'Downstream candidates',
        'question_scope': 'Follow depends edges, exclude seed', 'query_kind': 'directed_reachability',
        'edge_id_entry_id': field('edges', 'id'), 'source_entry_id': field('edges', 'src'),
        'destination_entry_id': field('edges', 'dst'), 'node_entry_id': field('nodes', 'id'),
        'source_relation_id': 'src', 'destination_relation_id': 'dst',
        'direction': 'forward', 'node_key_type': 'integer', 'comparison': 'binary_exact',
        'parameters': {'seed': 'integer', 'relation': 'text'}, 'seed_parameter': 'seed',
        'seed_policy': 'require_existing_node', 'include_seed': False,
        'node_semantics': 'distinct_reachable', 'endpoint_policy': 'require_existing_node',
        'edge_filters': [{'entry_id': field('edges', 'relation'), 'op': 'eq',
                          'parameter': 'relation', 'value_type': 'text'}],
        'projection': [], 'budgets': {'max_depth': 1, 'max_nodes': 10, 'max_edges': 20},
        'output_kind': 'potential_impact_candidates', 'limitations': ['Authored software fixture'],
        'policy_references': []}
    def approve(query, prefix):
        p = call('database_query_propose', prefix+'_proposal', spec=query,
                 origin={'kind': 'authored_test'}, relation_operation_ids=saved_relations)
        assert p['state'] == 'completed', p
        a = call('database_query_approve', prefix+'_approve', proposal_operation_id=p['id'],
                 note='Review bounds and direction', human_confirmed=True)
        assert a['state'] == 'completed', a
        return a
    limited = approve(spec, 'limited')
    params = {'seed': 0, 'relation': 'depends'}
    first = call('database_query_execute', 'first', approval_operation_id=limited['id'], parameters=params)
    assert first['state'] == 'completed', first
    artifact = first['result']['artifact']
    assert artifact['closure_complete'] is False
    assert artifact['total_output_rows'] is None
    assert [r['node_id'] for r in artifact['rows']] == ['1']
    assert call('database_query_execute', 'first', approval_operation_id=limited['id'], parameters=params) == first
    expanded = deepcopy(spec)
    expanded['budgets']['max_depth'] = 5
    complete = approve(expanded, 'expanded')
    assert complete['result']['artifact']['fingerprint'] != limited['result']['artifact']['fingerprint']
    second = call('database_query_execute', 'second', approval_operation_id=complete['id'], parameters=params)
    assert second['state'] == 'completed', second
    result = second['result']['artifact']
    assert result['closure_complete'] is True and result['total_output_rows'] == 2
    assert [r['node_id'] for r in result['rows']] == ['1', '2']
    missing = call('database_query_execute', 'missing', approval_operation_id=complete['id'],
                   parameters={'seed': 99, 'relation': 'depends'})
    assert missing['state'] == 'failed', missing
    row = svc.handle({'action': 'change', 'id': row['id'], 'revision': row['revision'],
        'decisions': [{'entry_id': field('edges', 'relation'), 'status': 'pending',
                      'target': 'source_only', 'note': '', 'interpretation': ''}]})
    stale = call('database_query_execute', 'stale', approval_operation_id=complete['id'], parameters=params)
    assert stale['state'] == 'failed', stale
    assert svc.store.operation(row['id'], second['id']) == second
    assert svc.store.operation(row['id'], first['id']) == first
