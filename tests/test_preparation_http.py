import tempfile
import threading
import unittest
from pathlib import Path
import httpx
from apps.factory_lab.public_runtime import Demo
from apps.factory_lab.public_server import make_server
from tests.test_preparation import approved
from apps.factory_lab.preparation import freeze


class PreparationHTTPTests(unittest.TestCase):
    def test_import_execute_token_lock_and_session_limit(self):
        with tempfile.TemporaryDirectory() as t:
            demo=Demo(Path(t)/'runs')
            server=make_server(demo,0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}') as c:
                    headers={'X-CSRF-Token':c.get('/api/config').json()['csrf']}
                    payload={'action':'import','bundle':freeze(approved())}
                    self.assertEqual(c.post('/api/preparation',json=payload).status_code,403)
                    response=c.post('/api/preparation',json=payload,headers=headers)
                    self.assertEqual(response.status_code,200,response.text)
                    key=response.json()['id']
                    result=c.post('/api/preparation',json={'action':'execute','id':key,'case_id':'ready'},headers=headers)
                    self.assertEqual(result.status_code,200,result.text)
                    self.assertTrue(result.json()['result']['shacl']['conforms'])
                    demo.lock.acquire()
                    try:
                        self.assertEqual(c.post('/api/preparation',json={'action':'freeze','id':key},headers=headers).status_code,409)
                    finally:demo.lock.release()
                    for _ in range(3):
                        self.assertEqual(c.post('/api/preparation',json={'action':'example','adapter':'factory-csv-1'},headers=headers).status_code,200)
                    listing=c.post('/api/preparation',json={'action':'list'},headers=headers).json()['sessions']
                    self.assertEqual(len(listing),4)
                    recovered=c.post('/api/preparation',json={'action':'get','id':listing[-1]['id']},headers=headers)
                    self.assertEqual(recovered.json()['draft']['adapter'],'factory-csv-1')
                    invalid=c.post('/api/preparation',json={'action':'freeze','id':listing[-1]['id']},headers=headers)
                    self.assertEqual(invalid.status_code,400)
                    self.assertNotEqual(invalid.json()['error'],'Invalid input')
                    self.assertEqual(c.post('/api/preparation',json={'action':'example','adapter':'factory-csv-1'},headers=headers).status_code,400)
                    self.assertEqual(c.post('/api/preparation',json={'action':'close','id':key},headers=headers).status_code,200)
                    self.assertEqual(c.post('/api/preparation',json={'action':'execute','id':key,'case_id':'ready'},headers=headers).status_code,400)
                    self.assertEqual(c.get('/api/config').json()['budget']['attempts'],0)
                    self.assertEqual(c.get('/prepare').status_code,200)
            finally:
                server.shutdown();server.server_close();thread.join()


    def test_response_is_frozen_and_unlocks_before_network_send(self):
        from unittest.mock import patch
        from apps.factory_lab.public_server import Handler
        observed=[]
        original=Handler.send
        def inspect_send(handler,value,status=200,mime='application/json; charset=utf-8'):
            if handler.command=='POST' and handler.path in ('/api/preparation','/api/workspace'):
                observed.append((handler.path,status,isinstance(value,bytes),handler.server.demo.lock.locked()))
            return original(handler,value,status,mime)
        with tempfile.TemporaryDirectory() as t:
            server=make_server(Demo(Path(t)/'runs'),0)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                with patch.object(Handler,'send',inspect_send), httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}') as c:
                    headers={'X-CSRF-Token':c.get('/api/config').json()['csrf']}
                    for path in ('/api/preparation','/api/workspace'):
                        body=({'action':'list'} if path=='/api/preparation' else
                              {'action':'create','domain':'commerce','title':'HTTP test',
                               'metadata':{'snapshot_id':'v1','as_of':'2026-11-17','currency':'KRW'},
                               'files':[{'name':'x.csv','content':'id\nA\n'}]})
                        response=c.post(path,json=body,headers=headers)
                        self.assertEqual(response.status_code,200,response.text)
                        response.json()
                        response=c.post(path,json={'action':'unsupported'},headers=headers)
                        self.assertEqual(response.status_code,400,response.text)
                        self.assertIn('error',response.json())
                self.assertEqual(len(observed),4)
                self.assertTrue(all(frozen and not locked for _,_,frozen,locked in observed),observed)
            finally:
                server.shutdown();server.server_close();thread.join()
