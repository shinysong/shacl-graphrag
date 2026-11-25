"""Authored source-only graph fixtures, independent enumerated expectations."""
from copy import deepcopy
import sqlite3

import pytest

from apps.factory_lab.workspace_database import DatabaseSourceError, SQLiteSources
from apps.factory_lab.workspace_database_adapter import DatabaseWorkspaceAdapter
from apps.factory_lab.workspace_query_contracts import ReviewedQueryContracts


@pytest.fixture
def graph(tmp_path):
    def make(edges=None, nodes=None, *, text=False, **limits):
        path = tmp_path / ('graph' + str(len(list(tmp_path.glob('*.sqlite')))) + '.sqlite')
        keytype = 'TEXT COLLATE NOCASE' if text else 'INTEGER'
        with sqlite3.connect(path) as con:
            con.executescript(f'CREATE TABLE nodes (id {keytype} PRIMARY KEY, name TEXT); CREATE TABLE edges (id INTEGER PRIMARY KEY, src {keytype} REFERENCES nodes(id), dst {keytype} REFERENCES nodes(id), kind TEXT);')
            con.executemany('INSERT INTO nodes VALUES (?, ?)', nodes or [(i, f'N{i}') for i in range(7)])
            con.executemany('INSERT INTO edges VALUES (?,?,?,?)', edges if edges is not None else [
                (1,0,1,'fs'),(2,0,1,'fs'),(3,0,2,'fs'),(4,1,3,'fs'),(5,2,3,'fs'),
                (6,3,0,'fs'),(7,3,3,'fs'),(8,3,4,'other'),(9,5,6,'fs')])
        registry = SQLiteSources(tmp_path / (path.stem+'registry'))
        adapter = DatabaseWorkspaceAdapter(registry); draft = adapter.create(registry.register(path)['source_id'])
        for entry in draft['entries']: entry.update(status='approved',interpretation='Authored fixture field')
        ids = {(e['source']['file'],e['source']['column']):e['id'] for e in draft['entries']}
        engine = ReviewedQueryContracts(adapter, **limits)
        review = dict(actor='test operator',note='Authored source interpretation',revision=1,human_confirmed=True)
        relations={}
        for col in ('src','dst'):
            rel=engine.propose_relation(draft,dict(id=col,child_entry_id=ids['edges',col],parent_entry_id=ids['nodes','id'],interpretation='Directed endpoint',join_policy='left_many_to_one_preserve_root'),origin={})
            relations[col]=engine.approve_relation(draft,rel,**review)
        spec=dict(id='downstream',title='Potential downstream candidates',question_scope='Downstream via authored fs edges',query_kind='directed_reachability',edge_id_entry_id=ids['edges','id'],source_entry_id=ids['edges','src'],destination_entry_id=ids['edges','dst'],node_entry_id=ids['nodes','id'],source_relation_id='src',destination_relation_id='dst',direction='forward',node_key_type='text' if text else 'integer',comparison='binary_exact',parameters={'seed':'text' if text else 'integer','kind':'text'},seed_parameter='seed',seed_policy='require_existing_node',include_seed=False,node_semantics='distinct_reachable',endpoint_policy='require_existing_node',edge_filters=[dict(entry_id=ids['edges','kind'],op='eq',parameter='kind',value_type='text')],projection=[dict(entry_id=ids['nodes','name'],name='name')],budgets=dict(max_depth=8,max_nodes=50,max_edges=100),output_kind='potential_impact_candidates',limitations=['Not change approval'],policy_references=[])
        def run(changes=None, parameters=None, selected_relations=None):
            target=deepcopy(spec); target.update(changes or {})
            rs=relations if selected_relations is None else selected_relations
            pending=engine.propose(draft,target,relations=rs,origin={})
            approved=engine.approve(draft,pending,relations=rs,**review)
            return engine.execute(draft,approved,parameters or {'seed':'a' if text else 0,'kind':'fs'},relations=rs)
        return engine,draft,relations,spec,run
    return make


def test_cycle_diamond_parallel_and_filter(graph):
    *_,run=graph()
    r=run()
    assert r['version']=='reviewed-query-reachability-1'
    assert r['closure_complete'] and r['total_output_rows']==3
    assert [(x['node_id'],x['minimum_depth'],x['predecessor_id'],x['witness_edge_id']) for x in r['rows']]==[('1',1,'0','1'),('2',1,'0','3'),('3',2,'1','4')]
    assert r['rows'][-1]['witness_path']==['0','1','3']
    assert r['traversal_observations']['examined_edges']==7
    reverse=run({'direction':'reverse'}, {'seed':3,'kind':'fs'})
    assert [x['node_id'] for x in reverse['rows']]==['1','2','0']


def test_depth_boundary_exhaustion_and_extra_successor(graph):
    *_,run=graph()
    assert run({'budgets':dict(max_depth=2,max_nodes=50,max_edges=100)})['closure_complete']
    r=run({'budgets':dict(max_depth=1,max_nodes=50,max_edges=100)})
    assert r['incomplete_reasons']==['max_depth'] and r['total_output_rows'] is None
    assert r['discovered_count']==2 and not r['truncated']


def test_node_edge_and_display_bounds_are_separate(graph):
    *_,run=graph(max_rows=1)
    r=run()
    assert r['closure_complete'] and r['truncated'] and r['total_output_rows']==3 and r['returned_count']==1
    for key,value in [('max_nodes',2),('max_edges',1)]:
        budgets=dict(max_depth=8,max_nodes=50,max_edges=100); budgets[key]=value
        r=run({'budgets':budgets})
        assert key in r['incomplete_reasons'] and r['total_output_rows'] is None
    *_,run=graph(edges=[(1,0,0,'fs')])
    assert run({'budgets':dict(max_depth=1,max_nodes=1,max_edges=1)})['closure_complete']


def test_missing_seed_and_reachable_missing_endpoints(graph):
    *_,run=graph(edges=[(1,0,None,'fs'),(2,0,99,'fs'),(3,0,1,'fs'),(4,5,88,'fs')])
    r=run()
    assert r['incomplete_reasons']==['missing_endpoint','null_endpoint']
    assert [x['node_id'] for x in r['rows']]==['1']
    assert r['traversal_observations']['missing_reachable_endpoints']==1
    with pytest.raises(DatabaseSourceError,match='unresolved_seed:absent'):
        run(parameters={'seed':99,'kind':'fs'})


def test_relation_binding_and_unsupported_specs(graph):
    _,_,relations,_,run=graph()
    with pytest.raises(DatabaseSourceError,match='approval missing'):
        run(selected_relations={'src':relations['src']})
    with pytest.raises(DatabaseSourceError,match='Two distinct'):
        run({'destination_relation_id':'src'})
    with pytest.raises(DatabaseSourceError,match='server bound'):
        run({'budgets':dict(max_depth=129,max_nodes=10,max_edges=10)})
    with pytest.raises(DatabaseSourceError,match='Unsupported or missing'):
        run({'sql':'select 1'})


def test_binary_exact_and_reject_fk_collation_mismatch(graph):
    *_,run=graph(edges=[(1,'a','b','FS'),(2,'a','c','fs')],nodes=[('a','A'),('b','B'),('c','C')],text=True)
    assert [r['node_id'] for r in run()['rows']]==['c']
    *_,run=graph(edges=[(1,'a','B','fs')],nodes=[('a','A'),('b','B')],text=True)
    with pytest.raises(DatabaseSourceError,match='differs from binary'):
        run()


def test_preparatory_work_obeys_vm_budget_and_byte_failure(graph):
    *_,run=graph(max_steps=1)
    with pytest.raises(DatabaseSourceError,match='Snapshot query failed or exceeded time limit'):
        run()
    *_,run=graph(max_bytes=1024)
    with pytest.raises(DatabaseSourceError,match='byte limit'):
        run()


def test_signed64_identity_does_not_lose_browser_precision(graph):
    large = 2**63-1
    *_,run=graph(edges=[(1,0,large,'fs')],nodes=[(0,'seed'),(large,'large')])
    result=run()
    assert result['rows'][0]['node_id']==str(large)
    assert result['rows'][0]['witness_path']==['0',str(large)]


def test_deadline_fails_without_authoritative_partial(graph,monkeypatch):
    from types import SimpleNamespace
    from apps.factory_lab import workspace_query_reachability as traversal
    *_,run=graph()
    ticks=iter([0,100])
    monkeypatch.setattr(traversal,'time',SimpleNamespace(monotonic=lambda:next(ticks,100)))
    with pytest.raises(DatabaseSourceError,match='time limit'):
        run()


def test_malformed_typed_endpoint_rejected_without_coercion(graph):
    *_,run=graph(edges=[(1,0,'not-an-integer','fs')])
    with pytest.raises(DatabaseSourceError,match='declared contract type'):
        run()
