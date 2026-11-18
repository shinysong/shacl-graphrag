"""Concurrent actual HTTP checkpoint reads; scripted gateway, no paid calls."""
import tempfile
import threading
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx
from apps.factory_lab.public_runtime import Demo
from apps.factory_lab.public_server import make_server
from tests.test_workspace_rows import prepared
from tests.test_workspace_question import Gateway, FINAL

class SlowGateway(Gateway):
    def __init__(self):
        super().__init__([{'calls':[{'tool':'source_rows','arguments':{'entry_id':'map:lines.csv:order_no','value':'A'}}],'unresolved':[]},FINAL])
        self.entered=[threading.Event(),threading.Event()];self.release=[threading.Event(),threading.Event()]
    def call(self,key,messages):
        index=len(self.calls);self.entered[index].set()
        if not self.release[index].wait(10):raise RuntimeError('Test gateway release timeout')
        return super().call(key,messages)

class ProgressTests(unittest.TestCase):
    def test_checkpoint_reads_while_execution_lock_held_and_duplicate_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            server=make_server(Demo(Path(tmp)),0);thread=threading.Thread(target=server.serve_forever);thread.start()
            gateway=SlowGateway();server.workspace.question_gateway=gateway;row=prepared(server.workspace)
            url=f'http://127.0.0.1:{server.server_port}/api/workspace';headers={'X-CSRF-Token':server.token}
            request={'action':'ask','id':row['id'],'revision':2,'request_key':'slow','question':'Show A'}
            def post(body,auth=True):
                with httpx.Client(trust_env=False,timeout=15) as client:return client.post(url,json=body,headers=headers if auth else {})
            progress={'action':'progress','id':row['id'],'request_key':'slow'}
            try:
                self.assertEqual(post(progress).json()['state'],'not_recorded')
                self.assertEqual(post(progress,False).status_code,403)
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future=pool.submit(post,request)
                    try:
                        self.assertTrue(gateway.entered[0].wait(5))
                        first=post(progress);self.assertEqual(first.status_code,200);self.assertEqual(first.json()['phase'],'planning')
                        self.assertNotIn('result',first.json());self.assertNotIn('request',first.json())
                        self.assertEqual(post(request).status_code,409)
                        self.assertEqual(post({**progress,'files':[]}).status_code,400)
                        gateway.release[0].set();self.assertTrue(gateway.entered[1].wait(5))
                        second=post(progress).json();self.assertEqual(second['phase'],'answering');self.assertEqual(second['tools_completed'],1)
                    finally:
                        for event in gateway.release:event.set()
                    self.assertEqual(future.result().json()['operation']['state'],'completed')
                self.assertEqual(post(progress).json()['state'],'completed')
                self.assertTrue(post(request).json()['reused']);self.assertEqual(len(gateway.calls),2)
                self.assertEqual(post({**progress,'id':'another-workspace'}).json()['state'],'not_recorded')
            finally:
                for event in gateway.release:event.set()
                server.shutdown();server.server_close();thread.join()
