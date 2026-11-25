"""Saved external relation lifecycle using authored source-only native fixtures."""
import base64
from copy import deepcopy
import json
import sqlite3

import pytest
import yaml

from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_service import WorkspaceService


@pytest.fixture
def scenario(tmp_path):
    source = tmp_path / 'source.sqlite'
    with sqlite3.connect(source) as con:
        con.executescript('''CREATE TABLE owners(id INTEGER PRIMARY KEY, label TEXT);
            CREATE TABLE lines(id INTEGER PRIMARY KEY, owner INTEGER REFERENCES owners(id), qty INTEGER);
            INSERT INTO owners VALUES(1,'A'),(2,'B');
            INSERT INTO lines VALUES(10,1,3),(11,1,5),(12,2,7);''')
    registry = SQLiteSources(tmp_path / 'registry')
    registered = registry.register(source)
    svc = WorkspaceService(tmp_path / 'workspace.sqlite', database_registry=registry)
    row = svc.handle({'action':'create_database','title':'Authored external lifecycle',
        'source_id':registered['source_id'],'metadata':{},'domain':'generic'})
    row = svc.handle({'action':'change','id':row['id'],'revision':row['revision'],
        'decisions':[{'entry_id':e['id'],'status':'approved','target':'source_only',
                      'note':'Authored local review','interpretation':'Recorded field'}
                     for e in row['draft']['entries']]})
    ids = {(e['source']['file'], e['source']['column']):e['id'] for e in row['draft']['entries']}
    doc = {'data_layer':{'databases':[{'id':'db','schemas':[{'id':'main','name':'main',
        'tables':[{'id':'lines','name':'lines','columns':[{'id':'child','name':'owner'}]},
                  {'id':'owners','name':'owners','columns':[{'id':'parent','name':'id'}]}]}]}],
        'foreign_keys':[{'source_column_id':'child','target_column_id':'parent'}],
        'joins':[{'source_table_id':'lines','target_table_id':'owners'}]},
        'semantic_layer':{'terms':[{'id':'term','represents':['owners'],'columns_attributes':[
            {'id':'attr','column_id':'parent'}]}], 'concepts':[{'id':'concept','term_ids':['term'],
            'keys':[{'id':'key','column_ids':['parent']}]}], 'semantic_fks':[
                {'column_id':'child','concept_key_id':'key','column_attribute_id':'attr','use_in_join_paths':True}]}}
    def call(action, key, **body):
        return svc.handle({'action':action,'id':row['id'],'revision':row['revision'],
                           'request_key':key,**body})
    imported = call('extension_import','import',raw_base64=base64.b64encode(yaml.safe_dump(doc).encode()).decode())['operation']
    assert imported['state'] == 'completed'
    candidates = {c['kind']:c['id'] for c in imported['result']['relations']}
    spec = {'id':'owner_link','child_entry_id':ids['lines','owner'],
            'parent_entry_id':ids['owners','id'],'interpretation':'Recorded owner, preserving line grain',
            'join_policy':'left_many_to_one_preserve_root'}
    def propose(key='relation', **changes):
        return call('database_external_relation_propose',key,operation_id=imported['id'],
            candidate_id=candidates['semantic_fks'],spec=changes.get('spec',spec),
            edit_reason=changes.get('edit_reason',''))['operation']
    def query_spec():
        ref=lambda t,c,a:{'entry_id':ids[t,c],'alias':a}
        label=ref('owners','label','o')
        return {'id':'quantity_by_owner','title':'Recorded quantity','question_scope':'Sum source quantities per owner',
            'root':ref('lines','id','l'),'joins':[{'relation_id':'owner_link','child_alias':'l','parent_alias':'o'}],
            'parameters':{},'filters':[],'projection':[{'field':label,'name':'owner'}],'group_by':[label],
            'aggregates':[{'op':'sum','field':ref('lines','qty','l'),'name':'qty'}],'distinct':False,
            'output_kind':'recorded_facts','limitations':['Authored software fixture'], 'policy_references':[],
            'null_policy':'exclude_from_aggregates_preserve_projection','empty_groups':'absent','measure_grain':'l'}
    return svc,row,call,imported,candidates,spec,propose,query_spec


def approved_query(scenario):
    svc,row,call,imported,candidates,spec,propose,query_spec=scenario
    rel=propose()
    assert rel['state']=='completed',rel
    approval=call('database_relation_approve','relation-approve',proposal_operation_id=rel['id'],
                  note='Explicit edited interpretation reviewed',human_confirmed=True)['operation']
    assert approval['state']=='completed',approval
    query=call('database_query_propose','query',spec=query_spec(),origin={'kind':'authored'},
               relation_operation_ids=[approval['id']])['operation']
    assert query['state']=='completed',query
    qa=call('database_query_approve','query-approve',proposal_operation_id=query['id'],
            note='Reviewed query grain',human_confirmed=True)['operation']
    assert qa['state']=='completed',qa
    return rel,approval,query,qa


def test_full_saved_join_query_provenance_and_replay(scenario):
    svc,row,call,imported,candidates,spec,propose,_=scenario
    rel,approval,query,qa=approved_query(scenario)
    result=call('database_query_execute','execute',approval_operation_id=qa['id'],parameters={})
    assert result['operation']['state']=='completed',result
    artifact=result['operation']['result']['artifact']
    assert artifact['rows']==[{'owner':'A','qty':8},{'owner':'B','qty':7}]
    origin=artifact['provenance']['dependencies']['relations']['owner_link']['origin']
    assert origin['import_operation_id']==imported['id']
    assert origin['raw_sha256']==imported['result']['raw_sha256']
    assert origin['original_candidate']['kind']=='semantic_fks'
    assert origin['edited_spec']==spec
    assert origin['upstream']==imported['result']['upstream']
    replay=call('database_query_execute','execute',approval_operation_id=qa['id'],parameters={})
    assert replay['reused'] and replay['operation']==result['operation']
    assert propose()==rel


def test_rejection_is_durable_selection_only_and_does_not_revoke(scenario):
    svc,row,call,imported,candidates,spec,propose,_=scenario
    _,approval,_,qa=approved_query(scenario)
    body={'operation_id':imported['id'],'candidate_id':candidates['semantic_fks'],'reason':'Not selected for a later proposal'}
    rejected=call('database_external_relation_reject','reject',**body)
    assert rejected['operation']['state']=='completed'
    r=rejected['operation']['result']
    assert r['status']=='rejected' and 'artifact' not in r
    assert r['scope']=='candidate_selection_only_not_existing_relation_revocation'
    assert call('database_external_relation_reject','reject',**body)['operation']==rejected['operation']
    assert call('database_query_execute','after-rejection',approval_operation_id=qa['id'],parameters={})['operation']['state']=='completed'
    fresh=propose('explicit-reproposal')
    assert fresh['state']=='completed' and fresh['id']!=approval['id']
    catalog=svc.handle({'action':'database_review_catalog','id':row['id'],'revision':row['revision'],
                        'category':'relation','cursor':None})
    item=next(x for x in catalog['items'] if x['operation_id']==rejected['operation']['id'])
    assert item['decision']=='rejected' and item['approval_operation_id'] is None
    assert item['proposal_operation_id'] is None


def test_existing_pending_proposal_remains_approvable_after_selection_rejection(scenario):
    _,_,call,imported,candidates,_,propose,_=scenario
    pending=propose('pending-before-rejection')
    rejected=call('database_external_relation_reject','exclude-after-pending',
        operation_id=imported['id'],candidate_id=candidates['semantic_fks'],reason='Selection only')
    assert rejected['operation']['state']=='completed'
    approved=call('database_relation_approve','approve-existing-pending',
        proposal_operation_id=pending['id'],note='Explicitly approve existing saved proposal',human_confirmed=True)
    assert approved['operation']['state']=='completed'
    assert approved['operation']['request']['proposal_operation_id']==pending['id']
    assert approved['operation']['result']['artifact']['origin']==pending['result']['artifact']['origin']


def test_unsupported_relation_can_be_rejected_but_not_proposed(scenario):
    _,_,call,imported,candidates,spec,_,_=scenario
    body={'operation_id':imported['id'],'candidate_id':candidates['joins']}
    failed=call('database_external_relation_propose','unsupported',**body,spec=spec,edit_reason='')['operation']
    assert failed['state']=='failed' and 'Unsupported relation kind' in failed['error']
    rejected=call('database_external_relation_reject','reject-unsupported',**body,reason='No supported column contract')['operation']
    assert rejected['state']=='completed'
    blank=call('database_external_relation_reject','blank',**body,reason='')['operation']
    assert blank['state']=='failed'


def test_edited_endpoint_still_needs_physical_fk_gate(scenario):
    _,row,_,_,_,spec,propose,_=scenario
    edited=deepcopy(spec)
    edited['parent_entry_id']=next(e['id'] for e in row['draft']['entries'] if e['source']['column']=='label')
    missing_reason=propose('no-reason',spec=edited)
    assert missing_reason['state']=='failed' and 'explicit reason' in missing_reason['error']
    not_fk=propose('not-fk',spec=edited,edit_reason='Intentional authored unsupported endpoint')
    assert not_fk['state']=='failed' and 'declared single-column foreign keys' in not_fk['error']


@pytest.mark.parametrize('origin',[{'format':'external-relation-origin-1'},
                                  {'kind':'reviewed_external_candidate_binding'}])
def test_client_cannot_forge_reserved_origin(scenario,origin):
    _,_,call,_,_,spec,_,_=scenario
    result=call('database_relation_propose','forged',spec=spec,origin=origin)['operation']
    assert result['state']=='failed' and 'saved external candidate' in result['error']


@pytest.mark.parametrize('stage',['relation_approve','query_propose','query_approve','query_execute','reject'])
def test_current_revision_revalidated_at_every_stage(scenario,stage):
    svc,row,call,imported,candidates,_,_,query_spec=scenario
    rel,approval,query,qa=approved_query(scenario)
    e=row['draft']['entries'][0]
    updated=svc.handle({'action':'change','id':row['id'],'revision':row['revision'],
        'decisions':[{'entry_id':e['id'],'status':'approved','target':'source_only',
                      'note':'New review','interpretation':'Changed interpretation'}]})
    row.update(updated)
    args={
        'relation_approve':{'proposal_operation_id':rel['id'],'note':'Review','human_confirmed':True},
        'query_propose':{'spec':query_spec(),'origin':{},'relation_operation_ids':[approval['id']]},
        'query_approve':{'proposal_operation_id':query['id'],'note':'Review','human_confirmed':True},
        'query_execute':{'approval_operation_id':qa['id'],'parameters':{}},
        'reject':{'operation_id':imported['id'],'candidate_id':candidates['joins'],'reason':'Stale candidate'},
    }[stage]
    action='database_external_relation_reject' if stage=='reject' else 'database_'+stage
    result=call(action,'stale-'+stage,**args)['operation']
    assert result['state']=='failed' and 'current workspace revision' in result['error'],result


def test_saved_import_tampering_is_detected_on_query_execution(scenario):
    svc,row,call,imported,_,_,_,_=scenario
    _,_,_,qa=approved_query(scenario)
    altered=deepcopy(imported['result'])
    altered['relations'][0]['source_payload']['target_column_id']='invented'
    with svc.store.connect() as con:
        con.execute('UPDATE operations SET result=? WHERE id=?',(json.dumps(altered),imported['id']))
    result=call('database_query_execute','tampered',approval_operation_id=qa['id'],parameters={})['operation']
    assert result['state']=='failed' and 'original native bytes' in result['error']


def test_changed_snapshot_failure_is_saved_and_not_retried(scenario):
    svc,row,call,_,_,_,_,_=scenario
    _,_,_,qa=approved_query(scenario)
    registry=svc.database_adapter.registry
    snapshot=registry.root/(row['draft']['database']['source_id']+'.sqlite')
    original=snapshot.read_bytes()
    snapshot.chmod(0o600)
    snapshot.write_bytes(original+b'changed')
    failed=call('database_query_execute','changed-source',approval_operation_id=qa['id'],parameters={})
    assert failed['operation']['state']=='failed'
    assert 'integrity mismatch' in failed['operation']['error']
    snapshot.write_bytes(original)
    snapshot.chmod(0o400)
    replay=call('database_query_execute','changed-source',approval_operation_id=qa['id'],parameters={})
    assert replay['reused'] and replay['operation']==failed['operation']
    assert call('database_query_execute','explicit-source-retry',approval_operation_id=qa['id'],parameters={})['operation']['state']=='completed'


def test_reject_unknown_candidate_does_not_create_decision(scenario):
    _,_,call,imported,_,_,_,_=scenario
    failed=call('database_external_relation_reject','unknown',operation_id=imported['id'],
                candidate_id='not-in-import',reason='Unknown')['operation']
    assert failed['state']=='failed' and failed['result'] is None


def test_external_proposal_catalog_exposes_reference_not_approval(scenario):
    svc,row,_,imported,_,_,propose,_=scenario
    proposal=propose()
    catalog=svc.handle({'action':'database_review_catalog','id':row['id'],'revision':row['revision'],
                        'category':'relation','cursor':None})
    item=next(x for x in catalog['items'] if x['operation_id']==proposal['id'])
    assert item['external_relation'] is True
    assert item['import_operation_id']==imported['id']
    assert item['approval_operation_id'] is None and item['artifact_state']=='pending'


@pytest.mark.parametrize('action',['database_external_relation_propose','database_external_relation_reject'])
def test_withdraw_before_launch_replays_without_proposal_or_rejection(scenario,action):
    svc,row,call,imported,candidates,spec,_,_=scenario
    request={'operation_id':imported['id'],'candidate_id':candidates['semantic_fks']}
    request.update({'spec':spec,'edit_reason':''} if action.endswith('_propose') else {'reason':'Not selected'})
    withdrawal={'action':'withdraw_pending','id':row['id'],'revision':row['revision'],
                'request_key':'withdraw-external','kind':action,'request':request}
    first=svc.handle(withdrawal)
    assert first['withdrawn'] and first['operation']['state']=='cancelled'
    assert first['operation']['result'] is None
    replay=call(action,'withdraw-external',**request)
    assert replay['reused'] and replay['operation']==first['operation']
    again=svc.handle(withdrawal)
    assert again['reused'] and not again['withdrawn'] and again['operation']==first['operation']
