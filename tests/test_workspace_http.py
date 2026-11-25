import tempfile
import threading
import unittest
from pathlib import Path
import httpx
from apps.factory_lab.public_runtime import Demo
from apps.factory_lab.public_server import make_server

class WorkspaceHTTPTests(unittest.TestCase):
    def test_restart_recovery_host_token_and_shared_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace_id=None
            for start in range(2):
                demo=Demo(Path(directory));server=make_server(demo,0)
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                try:
                    with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}') as client:
                        page=client.get('/workspace')
                        self.assertEqual(page.status_code,200)
                        self.assertIn('검토·승인',page.text)
                        self.assertIn('id="area-chat"',page.text)
                        for asset in ('workspace.js','workspace.css'):
                            self.assertEqual(client.get('/'+asset).status_code,200)
                        headers={'X-CSRF-Token':client.get('/api/config').json()['csrf']}
                        listing={'action':'list','archived':False}
                        self.assertEqual(client.post('/api/workspace',json=listing).status_code,403)
                        self.assertEqual(client.post('/api/workspace',json=listing,headers={**headers,'Origin':'https://invalid.test'}).status_code,403)
                        if start==0:
                            response=client.post('/api/workspace',json={'action':'example','domain':'commerce'},headers=headers)
                            self.assertEqual(response.status_code,200,response.text)
                            workspace_id=response.json()['id']
                        else:
                            response=client.post('/api/workspace',json=listing,headers=headers)
                            self.assertEqual(response.json()['workspaces'][0]['id'],workspace_id)
                            row=client.post('/api/workspace',json={'action':'get','id':workspace_id,'revision':None},headers=headers).json()
                            self.assertEqual(row['revision'],1)
                            self.assertTrue(all(e['status']=='pending' for e in row['draft']['entries']))
                        demo.lock.acquire()
                        try:self.assertEqual(client.post('/api/workspace',json=listing,headers=headers).status_code,409)
                        finally:demo.lock.release()
                        self.assertEqual(client.get('/api/config').json()['budget']['attempts'],0)
                finally:
                    server.shutdown();server.server_close();thread.join()
