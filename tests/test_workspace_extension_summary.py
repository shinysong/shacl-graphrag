import json
from apps.factory_lab.workspace_store import WorkspaceStore
from apps.factory_lab.workspace_extension_summary import latest, summarize


def test_summary_does_not_call_imported_yaml_llm_or_approval():
    op={'id':'import','workspace':'w','revision':1,'kind':'extension_import','state':'completed',
        'result':{'fields':[{'kind':'column'},{'kind':'column_attribute'}],
                  'concepts':[{'kind':'table'},{'kind':'concept'}],'relations':[{'kind':'foreign_keys'},{'kind':'semantic_fks'},{'kind':'joins'}], 'unsupported':[{}]}}
    summary=summarize(op,current_revision=2)
    assert summary['origin']=='external_proposal' and summary['stale']
    assert summary['physical_columns']==1 and summary['semantic_fields']==1
    assert (summary['declared_relations'],summary['semantic_relations'],summary['other_relations'])==(1,1,1)
    generation={'state':'completed','result':{'mode':'semantic','import_operation_id':'import',
        'native_model_execution':{'internal_model_error_observed':False,'new_provider_attempts':1,'new_cache_hits':0}}}
    assert summarize(op,generation)['origin']=='observed_native_semantic_generation'
    generation['result']['native_model_execution']['internal_model_error_observed']=True
    assert summarize(op,generation)['origin']=='external_proposal'
    assert summary['status']=='saved_proposal_not_automatically_applied'


def test_latest_receipt_keeps_source_and_approval_unchanged(tmp_path):
    from apps.factory_lab.workspace_service import WorkspaceService
    service=WorkspaceService(tmp_path/'workspaces.sqlite')
    row=service.handle({'action':'example','domain':'commerce'})
    original=service.store.get(row['id'])
    op,_=service.store.begin(row['id'],1,'receipt-import','extension_import',{})
    service.store.finish(op['id'],'completed',result={'fields':[],'concepts':[],'relations':[],'unsupported':[]})
    receipt=latest(service.store,row['id'],1)
    assert receipt['operation_id']==op['id'] and receipt['origin']=='external_proposal'
    assert service.store.get(row['id'])['digest']==original['digest']
