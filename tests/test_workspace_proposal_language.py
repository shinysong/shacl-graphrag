import json
from copy import deepcopy
from types import SimpleNamespace
import pytest
from apps.factory_lab.workspace_service import WorkspaceService
from apps.factory_lab.workspace_database import SQLiteSources


def fixture(tmp_path, reply=None):
    registry=tmp_path/'registry';registry.mkdir()
    calls=[]
    def invoke(rid,messages):
        values=json.loads(messages[-1]['content']);calls.append(values)
        if reply is not None:return {'role':'assistant','content':reply}
        return {'role':'assistant','content':json.dumps({'translations':[{'candidate_id':v['candidate_id'],'meaning_ko':'원본에 기록된 상품 식별 번호',
            'current_meaning_ko':'검토한 상품 번호' if v['current_interpretation'] else ''} for v in values]})}
    service=WorkspaceService(tmp_path/'workspaces.sqlite',database_registry=SQLiteSources(registry),proposal_gateway=SimpleNamespace(call=invoke,config={'model':'offline-translation-fixture'}))
    row=service.handle({'action':'example_database'})
    table=next(s for s in row['draft']['sources'] if s['name']=='products')
    entry=next(e for e in row['draft']['entries'] if e['source']['file']=='products' and e['source']['column']=='sku')
    op,_=service.store.begin(row['id'],1,'fixture-import','extension_import',{})
    service.store.finish(op['id'],'completed',result={'concepts':[{'id':'t','kind':'table','source_payload':{'name':'products'}}],
        'fields':[{'id':'candidate','parent_id':'t','kind':'column','source_payload':{'name':'sku','description':'Recorded product identifier'}}]})
    request={'action':'extension_localize','id':row['id'],'revision':1,'request_key':'translate', 'operation_id':op['id'],'candidate_ids':['candidate']}
    return service,row,request,calls


def test_korean_suggestion_saved_replay_preserves_approval_and_original(tmp_path):
    service,row,request,calls=fixture(tmp_path);before=deepcopy(service.store.get(row['id']))
    result=service.handle(request);assert result['operation']['state']=='completed'
    assert service.handle(request)['reused'] and len(calls)==1
    after=service.store.get(row['id']);assert after['draft']==before['draft'] and after['digest']==before['digest']
    translated=service.view(row['id'])['proposal_korean'][request['operation_id']]['candidate']
    assert translated['meaning_ko']=='원본에 기록된 상품 식별 번호' and translated['current_meaning_ko']==''
    assert all(e['status']=='pending' for e in after['draft']['entries'])
    original=service.store.operation(row['id'],request['operation_id'])
    assert original['result']['fields'][0]['source_payload']['description']=='Recorded product identifier'
    after['draft']['entries'][0]['interpretation']='수정된 의미'
    service.store.save(row['id'],after['draft'],1)
    assert service.view(row['id'])['proposal_korean']=={}


@pytest.mark.parametrize('reply', ['not json','{"translations":[]}',json.dumps({'translations':[{'candidate_id':'candidate','meaning_ko':'Only English','current_meaning_ko':''}]}),json.dumps({'translations':[{'candidate_id':'wrong','meaning_ko':'다른 후보','current_meaning_ko':''}]})])
def test_invalid_response_retained_failed_without_retry(tmp_path,reply):
    service,row,request,calls=fixture(tmp_path,reply)
    assert service.handle(request)['operation']['state']=='failed'
    assert service.handle(request)['reused'] and len(calls)==1
    assert service.view(row['id'])['proposal_korean']=={}


def test_input_scope_rejects_duplicates_and_unknown_without_call(tmp_path):
    service,row,request,calls=fixture(tmp_path)
    for ids in ([],['candidate']*2,['unknown']):
        with pytest.raises(ValueError):service.handle({**request,'candidate_ids':ids})
    assert not calls


def test_current_approved_meaning_translated_for_display_without_reapproval(tmp_path):
    service,row,request,calls=fixture(tmp_path)
    draft=service.store.get(row['id'])['draft']
    entry=next(e for e in draft['entries'] if e['source']['file']=='products' and e['source']['column']=='sku')
    entry.update(status='approved',interpretation='Previously reviewed product identifier')
    updated=service.store.save(row['id'],draft,1);before=deepcopy(updated)
    result=service.handle({**request,'revision':2})
    assert result['operation']['state']=='completed'
    translated=service.view(row['id'])['proposal_korean'][request['operation_id']]['candidate']
    assert translated['current_meaning_ko']=='검토한 상품 번호'
    assert service.store.get(row['id'])['draft']==before['draft']
    assert service.store.get(row['id'])['revision']==2


def test_saved_response_processing_is_new_record_not_rewritten_failure(tmp_path):
    service,row,request,calls=fixture(tmp_path)
    # PublicGateway returns an assistant message dict; a wrong adapter type must fail.
    invoke=service.proposal_gateway.call
    service.proposal_gateway.call=lambda rid,messages:'legacy-wrong-message-type'
    failed=service.handle(request)['operation'];assert failed['state']=='failed'
    service.proposal_gateway.call=invoke
    service.proposal_gateway.recovery_receipt={'kind':'offline_unit_fixture','original_failed_operation_id':failed['id'],'new_provider_calls':0}
    recovered=service.handle({**request,'request_key':'new-processing'})['operation']
    assert recovered['state']=='completed'
    assert recovered['result']['processing_recovery']['original_failed_operation_id']==failed['id']
    assert service.store.operation(row['id'],failed['id'])==failed
    assert service.store.get(row['id'])['revision']==1


def test_single_json_fence_is_unwrapped_without_semantic_repair(tmp_path):
    text=json.dumps({'translations':[{'candidate_id':'candidate','meaning_ko':'기록된 상품 식별 번호','current_meaning_ko':''}]})
    service,row,request,calls=fixture(tmp_path,'```json\n'+text+'\n```')
    result=service.handle(request)['operation'];assert result['state']=='completed'
    assert result['result']['message_format']=='single_json_fence'
    assert result['result']['translations']['candidate']['meaning_ko']=='기록된 상품 식별 번호'
