"""Offline pricing/packet controls, never live availability or model quality."""
import hashlib,json,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from scripts.workspace_proposal_preflight import inspect
from apps.factory_lab.public_runtime import PublicGateway

class PreflightTests(unittest.TestCase):
    def fixture(self,root):
        messages=[{'role':'user','content':'Authored 테스트'}];raw=json.dumps(messages).encode()
        (root/'one-messages.json').write_bytes(raw)
        (root/'manifest.json').write_text(json.dumps({'records':[{'id':'one','state':'captured_before_response','messages_sha256':hashlib.sha256(raw).hexdigest()}]}))
        endpoint={'data':{'id':'test/model','endpoints':[{'tag':'test-provider','status':0,'supported_parameters':['temperature','max_tokens'],'pricing':{'prompt':'0.000001','completion':'0.000002'},'max_completion_tokens':4096}]}}
        (root/'endpoints.json').write_text(json.dumps(endpoint))
        config={'model':'test/model','provider':'test-provider','prompt_per_million':'1','completion_per_million':'2','max_tokens':4096,'max_calls':1,'max_usd':'0.25','hours':1}
        return messages,config

    def test_matches_real_gateway_before_reservation_without_network(self):
        with tempfile.TemporaryDirectory() as tmp,patch('httpx.Client',side_effect=AssertionError('No network')):
            root=Path(tmp);messages,config=self.fixture(root)
            report=inspect(root,root/'endpoints.json',config)
            class Captured(Exception):pass
            amounts=[]
            class Store:
                def budget(self):return {'unresolved':0}
                def reserve(self,rid,amount,session):amounts.append(str(amount));raise Captured()
            gateway=PublicGateway(Store(),root,config,'scripted-not-a-key')
            with self.assertRaises(Captured):gateway.call('offline',messages)
            self.assertEqual(amounts,[report['total_reserved_usd']])
            self.assertFalse(report['paid_execution_ready'])

    def test_tamper_caps_and_provider_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);messages,config=self.fixture(root)
            for change in ({'max_usd':'0.000001'},{'prompt_per_million':'0.5'},{'provider':'other'},{'extra':1},{'reasoning_effort':'none'},{'reasoning_effort':'low'}):
                with self.subTest(change=change),self.assertRaises(ValueError):inspect(root,root/'endpoints.json',config|change)
            data=json.loads((root/'endpoints.json').read_text());data['data']['endpoints'][0]['supported_parameters']=['max_tokens'];(root/'endpoints.json').write_text(json.dumps(data))
            with self.assertRaises(ValueError):inspect(root,root/'endpoints.json',config)
            self.fixture(root);(root/'one-messages.json').write_text('[]')
            with self.assertRaises(ValueError):inspect(root,root/'endpoints.json',config)
