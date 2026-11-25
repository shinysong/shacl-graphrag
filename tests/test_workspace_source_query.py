"""Actual full-snapshot reads and approved-field boundaries, not model accuracy."""
from copy import deepcopy
import sqlite3
import pytest
from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_database_adapter import DatabaseWorkspaceAdapter
from apps.factory_lab import workspace_source_query as q
from apps.factory_lab.workspace_service import WorkspaceService

@pytest.fixture
def setup(tmp_path):
    path=tmp_path/'input.sqlite'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE records(code TEXT, units, private TEXT);CREATE TABLE other(code TEXT);')
        db.executemany('INSERT INTO records VALUES(?,?,?)',[(str(i),i,'hidden') for i in range(70)]+[('null',None,'hidden'),('text','99','hidden')])
    registry=SQLiteSources(tmp_path/'registry');source=registry.register(path)
    adapter=DatabaseWorkspaceAdapter(registry);draft=adapter.create(source['source_id'])
    for e in draft['entries']:
        if e['source']['column']!='private':e.update(status='approved',interpretation='Reviewed recorded field')
    ids={(e['source']['file'],e['source']['column']):e['id'] for e in draft['entries']}
    return adapter,draft,ids,registry

def args(ids,value=68):return {'projection':[ids['records','code'],ids['records','units']],'filters':[{'entry_id':ids['records','units'],'op':'gt','value':value}]}

def test_full_snapshot_no_query_approval_and_no_unreviewed_projection(setup):
    a,d,ids,_=setup;before=deepcopy(d);r=q.execute(a,d,args(ids))
    assert r['records']==[{'code':'69','units':69}]
    assert r['total_source_rows']==72 and r['total_matching_rows']==1
    assert r['excluded_by_filter_type_rows']==2 and r['source_version']==d['database']['snapshot_sha256']
    assert d==before

def test_truncation_duplicates_zero_and_nulls(setup):
    a,d,ids,_=setup;r=q.execute(a,d,args(ids,-1));assert r['returned_count']==50 and r['total_matching_rows']==70 and r['truncated']
    r=q.execute(a,d,args(ids,100));assert r['records']==[] and r['total_matching_rows']==0
    x=args(ids);x['filters'][0].update(op='eq',value=None);r=q.execute(a,d,x);assert r['records']==[{'code':'null','units':None}]

@pytest.mark.parametrize('change',[lambda x,ids:x['projection'].append(ids['records','private']),lambda x,ids:x['projection'].append(ids['other','code']),lambda x,ids:x['filters'][0].update(value='0'),lambda x,ids:x['filters'][0].update(value=True),lambda x,ids:x['filters'][0].update(value=float('inf')),lambda x,ids:x['filters'][0].update(op='sql'),lambda x,ids:x.update(sql='DELETE FROM records')])
def test_reject_permission_type_join_and_sql(setup,change):
    a,d,ids,_=setup;x=args(ids);change(x,ids)
    with pytest.raises(ValueError):q.execute(a,d,x)

def test_source_hash_and_review_drift(setup):
    a,d,ids,registry=setup;x=args(ids);d['entries'][1]['status']='pending'
    with pytest.raises(ValueError):q.execute(a,d,x)
    path=registry.root/(d['database']['source_id']+'.sqlite');path.chmod(0o600);path.write_bytes(b'changed')
    with pytest.raises(ValueError):q.execute(a,d,x)

def test_actual_service_model_selection_creates_child_without_query_approval(setup,tmp_path):
    a,d,ids,registry=setup
    class Gateway:
        config={'model':'offline-fixture'}
        def __init__(self):self.calls=0
        def call(self,parent,messages):
            import json
            self.calls+=1
            if self.calls==1:return {'content':json.dumps({'calls':[{'tool':'query_source','arguments':args(ids)}],'unresolved':[]})}
            return {'content':json.dumps({'answer':'Recorded row 69; no order eligibility claim.','citations':['e1'],'unresolved':[]})}
    gateway=Gateway();service=WorkspaceService(tmp_path/'workspaces.sqlite',database_registry=registry,question_gateway=gateway)
    row=service.handle({'action':'create_database','title':'Test','domain':'generic','source_id':d['database']['source_id'],'metadata':{}})
    changes=[{'entry_id':e['id'],'status':e['status'],'target':e['target'],'note':e['note'],'interpretation':e['interpretation']} for e in d['entries']]
    row=service.handle({'action':'change','id':row['id'],'revision':row['revision'],'decisions':changes})
    request={'action':'ask','id':row['id'],'revision':row['revision'],'request_key':'one','question':'Find recorded units above68'}
    result=service.handle(request)['operation'];assert result['state']=='completed',result
    assert result['result']['evidence'][0]['result']['records']==[{'code':'69','units':69}]
    assert gateway.calls==2
    child=service.store.operation(row['id'],result['result']['child_operations'][0]['operation_id'])
    assert child['state']=='completed' and child['kind']=='database_source_query'
    service.handle(request);assert gateway.calls==2

@pytest.mark.parametrize('scenario',['denied','cancelled','revision_changed'])
def test_failed_cancelled_or_stale_child_is_retained_without_retry(setup,tmp_path,monkeypatch,scenario):
    import json
    a,d,ids,registry=setup
    class Gateway:
        config={'model':'offline-fixture'}
        calls=0
        parent=None
        def call(self,parent,messages):
            self.calls+=1;self.parent=parent
            x=args(ids)
            if scenario=='denied':x['projection'].append(ids['records','private'])
            return {'content':json.dumps({'calls':[{'tool':'query_source','arguments':x}],'unresolved':[]})}
    gateway=Gateway();svc=WorkspaceService(tmp_path/'s.sqlite',database_registry=registry,question_gateway=gateway)
    row=svc.handle({'action':'create_database','title':'Test','domain':'generic','source_id':d['database']['source_id'],'metadata':{}})
    decisions=[{'entry_id':e['id'],'status':e['status'],'target':e['target'],'note':e['note'],'interpretation':e['interpretation']} for e in d['entries']]
    row=svc.handle({'action':'change','id':row['id'],'revision':row['revision'],'decisions':decisions})
    original=q.execute
    def execute(*args_,**kwargs):
        result=original(*args_,**kwargs)
        if scenario=='cancelled':
            import time
            svc.store.request_cancel(row['id'],'boundary');time.sleep(.06) # exceed existing 50ms durable cancel poll cache
        if scenario=='revision_changed':
            changed=deepcopy(row['draft']);changed['entries'][0]['interpretation']+=' changed';svc.store.save(row['id'],changed,row['revision'])
        return result
    monkeypatch.setattr(q,'execute',execute)
    request={'action':'ask','id':row['id'],'revision':row['revision'],'request_key':'boundary','question':'Read recorded values'}
    parent=svc.handle(request)['operation'];children=[o for o in svc.store.operations(row['id']) if o['kind']=='database_source_query']
    assert len(children)==1 and children[0]['state']==('cancelled' if scenario=='cancelled' else 'failed')
    assert parent['state']==('cancelled' if scenario=='cancelled' else 'failed' if scenario=='revision_changed' else 'completed')
    assert gateway.calls==1 and parent['result']['child_operations'][0]['operation_id']==children[0]['id']
    svc.handle(request);assert gateway.calls==1
