"""Cooperative cancellation on actual concurrent HTTP, scripted model only."""
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx
from apps.factory_lab.public_runtime import Demo
from apps.factory_lab.public_server import make_server
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_workspace_rows import prepared


class CancelTests(unittest.TestCase):
    def test_http_cancel_retains_inflight_response_and_prevents_followup(self):
        for action in ('ask','suggest'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as tmp:
                entered=threading.Event();release=threading.Event();calls=[]
                class Slow:
                    config={'model':'scripted'}
                    def call(self,rid,messages):
                        calls.append(messages);entered.set()
                        if not release.wait(10):raise RuntimeError('Test timeout')
                        if action=='ask':return {'content':json.dumps({'calls':[],'unresolved':[]})}
                        packet=json.loads(messages[1]['content'])
                        return {'content':json.dumps({'choices':[{'id':e['id'],'target':'','reason':'Unknown'} for e in packet['entries']]})}
                server=make_server(Demo(Path(tmp)),0)
                server.workspace.question_gateway=Slow();server.workspace.proposal_gateway=Slow()
                row=prepared(server.workspace)
                thread=threading.Thread(target=server.serve_forever);thread.start()
                url=f'http://127.0.0.1:{server.server_port}/api/workspace'
                headers={'X-CSRF-Token':server.token}
                def post(body,auth=True):
                    with httpx.Client(trust_env=False,timeout=15) as client:
                        return client.post(url,json=body,headers=headers if auth else {})
                request={'action':action,'id':row['id'],'revision':2,'request_key':'cancel-test'}
                if action=='ask':request['question']='show data'
                cancel={'action':'cancel','id':row['id'],'request_key':'cancel-test'}
                try:
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future=pool.submit(post,request)
                        try:
                            self.assertTrue(entered.wait(5))
                            self.assertEqual(post(cancel,False).status_code,403)
                            self.assertEqual(post(cancel|{'id':'wrong'}).status_code,400)
                            response=post(cancel)
                            self.assertEqual(response.status_code,200)
                            self.assertEqual(response.json()['state'],'running')
                            self.assertTrue(response.json()['cancel_requested'])
                            self.assertTrue(post(cancel).json()['cancel_requested'])
                        finally:release.set()
                        result=future.result().json()['operation']
                    self.assertEqual(result['state'],'cancelled')
                    self.assertEqual(len(calls),1)
                    self.assertTrue(post(request).json()['reused'])
                    self.assertEqual(len(calls),1)
                    self.assertEqual(post(cancel).json()['state'],'cancelled')
                    if action=='ask':self.assertEqual(len(result['result']['model_responses']),1)
                    else:
                        self.assertIn('draft',result['result'])
                        self.assertEqual(post({'action':'adopt_suggestions','id':row['id'],'revision':2,'operation_id':result['id']}).status_code,400)
                    self.assertEqual(server.workspace.store.get(row['id'])['revision'],2)
                    restored=WorkspaceService(server.workspace.store.path)
                    self.assertTrue(restored.handle(cancel)['cancel_requested'])
                finally:
                    release.set();server.shutdown();server.server_close();thread.join()
