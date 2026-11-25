"""Mocked transport provenance; not a model or billing effectiveness result."""
import httpx
from unittest.mock import patch
from apps.factory_lab.public_runtime import PublicGateway
from apps.factory_lab.store import Store
from tests.test_factory_public import CFG


def test_receipt_uses_actual_provider_and_same_ledger(tmp_path):
    store=Store(tmp_path/'state.sqlite'); g=PublicGateway(store,tmp_path,CFG,'secret-not-returned');rid=store.create({})
    body={'id':'generation-1','model':'returned/model','provider':'returned-provider',
          'usage':{'cost':.0001,'prompt_tokens':10,'completion_tokens':10},
          'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'{}'}}]}
    response=httpx.Response(200,json=body,request=httpx.Request('POST','https://openrouter.ai/api/v1/chat/completions'))
    with patch('httpx.Client') as client:
        client.return_value.__enter__.return_value.post.return_value=response
        result=g.call_with_receipt(rid,[{'role':'user','content':'hello'}])
    receipt=result['receipt'];assert receipt['returned_model']=='returned/model'
    assert receipt['returned_provider']=='returned-provider' and receipt['requested_provider']==CFG['provider']
    assert receipt['call_id'] and receipt['config_sha256']==g.session['config_sha256']
    assert store.budget()['attempts']==1 and store.budget()['unresolved']==0


def test_missing_provider_is_unknown_and_legacy_call_unchanged(tmp_path):
    store=Store(tmp_path/'state.sqlite');g=PublicGateway(store,tmp_path,CFG,'secret');rid=store.create({})
    body={'usage':{'cost':.0001},'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}
    response=httpx.Response(200,json=body,request=httpx.Request('POST','https://openrouter.ai/api/v1/chat/completions'))
    with patch('httpx.Client') as client:
        client.return_value.__enter__.return_value.post.return_value=response
        result=g.call_with_receipt(rid,[{'role':'user','content':'hello'}])
        assert result['receipt']['returned_provider'] is None and result['receipt']['returned_model'] is None
        assert g.call(rid,[{'role':'user','content':'hello'}])=={'content':'{}'}
    assert store.budget()['attempts']==2
