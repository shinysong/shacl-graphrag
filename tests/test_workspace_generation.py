"""Scripted gateway exercises integration, not actual model quality or billing."""
import json
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab.workspace_service import WorkspaceService


class ScriptedGateway:
    config={'model':'scripted-test-not-a-provider'}
    def __init__(self):self.calls=[]
    def call(self,operation_id,messages):
        self.calls.append(operation_id)
        packet=json.loads(messages[1]['content'])
        return {'content':json.dumps({'choices':[{'id':e['id'],'target':'orders.id' if e['source'].get('column')=='order_no' else '',
                       'reason':'Scripted test choice'} for e in packet['entries']]})}


class GenerationTests(unittest.TestCase):
    def test_public_server_requires_separate_model_proposal_opt_in(self):
        from apps.factory_lab.public_runtime import Demo
        from apps.factory_lab.public_server import make_server
        with tempfile.TemporaryDirectory() as tmp:
            demo=Demo(Path(tmp))
            with self.assertRaisesRegex(ValueError,'explicit live config'):
                make_server(demo,0,workspace_model_proposals=True)
            demo.gateway=ScriptedGateway()
            server=make_server(demo,0)
            try:self.assertIsNone(server.workspace.proposal_gateway)
            finally:server.server_close()
            server=make_server(demo,0,workspace_model_proposals=True)
            try:self.assertIs(server.workspace.proposal_gateway,demo.gateway)
            finally:server.server_close()

    def test_generation_is_separate_durable_and_explicitly_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db.sqlite';gateway=ScriptedGateway();service=WorkspaceService(path,gateway)
            original=service.handle({'action':'create','domain':'commerce','title':'Merchant','metadata':
                {'snapshot_id':'test','as_of':'2026-11-17','currency':'KRW'},
                'files':[{'name':'export.csv','content':'order_no,state\nO1,pending\n'}]})
            key=original['id'];request={'action':'suggest','id':key,'revision':1,'request_key':'generate-once'}
            first=service.handle(request);op=first['operation']
            self.assertEqual(op['state'],'completed')
            self.assertEqual(service.store.get(key)['draft'],original['draft'])
            self.assertEqual(gateway.calls,[op['id']])
            restarted=WorkspaceService(path)  # Disabled gateway can still recover a saved attempt.
            self.assertTrue(restarted.handle(request)['reused'])
            adopted=restarted.handle({'action':'adopt_suggestions','id':key,'revision':1,'operation_id':op['id']})
            self.assertEqual(adopted['revision'],2)
            self.assertTrue(all(e['status']=='pending' for e in adopted['draft']['entries']))
            self.assertEqual(restarted.store.get(key,1)['draft'],original['draft'])
            self.assertTrue(restarted.handle(request)['reused'])
            with self.assertRaises(ValueError):
                restarted.handle({'action':'adopt_suggestions','id':key,'revision':2,'operation_id':op['id']})
            self.assertEqual(len(gateway.calls),1)

    def test_disabled_and_failed_calls_are_retained_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=WorkspaceService(Path(tmp)/'db.sqlite')
            row=service.handle({'action':'example','domain':'commerce'})
            request={'action':'suggest','id':row['id'],'revision':1,'request_key':'disabled'}
            self.assertEqual(service.handle(request)['operation']['state'],'failed')
            self.assertTrue(service.handle(request)['reused'])
            gateway=ScriptedGateway()
            def fail(oid,messages):gateway.calls.append(oid);raise RuntimeError('Scripted provider failure')
            gateway.call=fail;service.proposal_gateway=gateway
            request['request_key']='failed'
            self.assertEqual(service.handle(request)['operation']['state'],'failed')
            self.assertTrue(service.handle(request)['reused'])
            self.assertEqual(len(gateway.calls),1)
