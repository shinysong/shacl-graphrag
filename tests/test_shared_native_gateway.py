"""Native SDK retries must not become repeated paid provider attempts."""
import sqlite3
from pathlib import Path
import tempfile
import time
import unittest
import threading
import json
from http.client import HTTPConnection
from apps.factory_lab.extension_gateway import Config, Model, Response, Denied
from apps.factory_lab.shared_server import NoRetryGateway


class NativeStopTests(unittest.TestCase):
    def test_korean_request_is_cached_separately_from_legacy_english(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger=Path(temporary)/'native.sqlite';sent=[]
            def transport(route,body,*args):
                sent.append(json.loads(body));return Response(200,b'{"usage":{"cost":0}}')
            cfg=self.config();base=NoRetryGateway(ledger,cfg,'offline-secret',transport)
            original=self.payload();base.handle('/v1/chat/completions',original);base.close()
            korean=NoRetryGateway(ledger,cfg,'offline-secret',transport,description_language='ko')
            korean.handle('/v1/chat/completions',original);korean.handle('/v1/chat/completions',original)
            self.assertEqual(len(sent),2)
            self.assertIn('in Korean',sent[1]['messages'][-1]['content'])
            self.assertEqual(original,self.payload())
            with sqlite3.connect(korean.cache) as db:self.assertEqual(db.execute('select count(*) from requests').fetchone()[0],2)
            korean.close()

    def test_http200_provider_error_never_settles_or_retries(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory() as temporary:
            ledger=Path(temporary)/'native.sqlite';sent=[]
            gateway=NoRetryGateway(ledger,replace(self.config(),reservation_accounting='settled'),
                'offline-secret',lambda *a:(sent.append(True) or Response(200,b'{"error":{"message":"provider failure"},"usage":{"cost":0.000000001}}')))
            with self.assertRaises(Denied):gateway.handle('/v1/chat/completions',self.payload())
            with self.assertRaises(Denied):gateway.handle('/v1/chat/completions',self.payload())
            self.assertEqual(len(sent),1);self.assertEqual(gateway.readiness()['unconfirmed_hold_usd'],'0.000000200')
            self.assertEqual(gateway.readiness()['reason'],'inspection_required')
            with sqlite3.connect(ledger) as db:self.assertEqual(db.execute('select error from completions').fetchone()[0],'Denied')
            gateway.close()

    def test_settled_native_requests_reuse_capacity_and_unknown_cost_stops(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory() as temporary:
            ledger=Path(temporary)/'native.sqlite';sent=[]
            cfg=replace(self.config(),reservation_accounting='settled',total_nanodollars=200)
            def transport(*a):
                sent.append(True);return Response(200,b'{"usage":{"cost":0.000000001}}')
            gateway=NoRetryGateway(ledger,cfg,'offline-secret',transport)
            gateway.handle('/v1/chat/completions',self.payload())
            # A different request is still blocked when the next full hold would exceed cap.
            self.assertFalse(gateway.readiness()['ready'])
            self.assertEqual(gateway.readiness()['reserved_usd'],'0.000000001')
            self.assertEqual(gateway.readiness()['unconfirmed_hold_usd'],'0.000000000')
            gateway.close()
        with tempfile.TemporaryDirectory() as temporary:
            ledger=Path(temporary)/'native.sqlite';sent=[]
            gateway=NoRetryGateway(ledger,replace(self.config(),reservation_accounting='settled'),
                'offline-secret',lambda *a:(sent.append(True) or Response(200,b'{"usage":{}}')))
            with self.assertRaises(Denied):gateway.handle('/v1/chat/completions',self.payload())
            with self.assertRaises(Denied):gateway.handle('/v1/chat/completions',self.payload()|{'max_tokens':9})
            self.assertEqual(len(sent),1);self.assertEqual(gateway.readiness()['reason'],'inspection_required')
            gateway.close()

    def test_readiness_reports_reserved_limit_without_spend_or_reset(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory() as temporary:
            ledger=Path(temporary)/'native.sqlite';calls=[]
            cfg=replace(self.config(),total_nanodollars=200)
            gateway=NoRetryGateway(ledger,cfg,'offline-secret',lambda *a:(calls.append(True) or Response(200,b'{"choices":[],"usage":{"cost":0}}')))
            self.assertTrue(gateway.readiness()['ready'])
            gateway.handle('/v1/chat/completions',self.payload())
            before=ledger.read_bytes()
            for _ in range(2):
                state=gateway.readiness()
                self.assertFalse(state['ready']);self.assertEqual(state['reason'],'reservation_limit')
                self.assertEqual(state['reserved_usd'],'0.000000200')
                self.assertIn('OpenRouter',state['message'])
            self.assertEqual(before,ledger.read_bytes());self.assertEqual(len(calls),1)
            ledger.with_suffix('.paid-stop.json').write_text('{"stopped":true}')
            self.assertEqual(gateway.readiness()['reason'],'reservation_limit')
            gateway.close()

    def test_readiness_separates_stop_and_deadline(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger=Path(temporary)/'native.sqlite'
            gateway=NoRetryGateway(ledger,self.config(),'offline-secret',lambda *a:self.fail('No transport expected'))
            ledger.with_suffix('.paid-stop.json').write_text('{"stopped":true}')
            self.assertEqual(gateway.readiness()['reason'],'inspection_required')
            gateway.clock=lambda:gateway.config.deadline_epoch
            self.assertEqual(gateway.readiness()['reason'],'deadline')
            gateway.close()

    def test_embedding_batch_reserves_each_genuine_vector_and_replays_without_charge(self):
        with tempfile.TemporaryDirectory() as temporary:
            cfg=Config(models=(Model(alias='openai/auto-ontology-embedding',actual_id='offline/embedding',kind='embedding',provider='offline',input_nanodollars_per_token=1,output_nanodollars_per_token=0,max_input_tokens=100,max_output_tokens=0,verification='offline context bounds'),),call_cap=10,per_call_nanodollars=100,total_nanodollars=1000,deadline_epoch=time.time()+60,timeout_seconds=1,max_request_bytes=4096,max_response_bytes=65536)
            calls=[]
            def transport(route,raw,*args):
                body=json.loads(raw);self.assertEqual(len(body['input']),1);self.assertEqual(body['dimensions'],2048)
                calls.append(body['input'][0]);return Response(200,json.dumps({'model':'offline/embedding','data':[{'index':0,'embedding':[.1]*2048}],'usage':{'prompt_tokens':3}}).encode())
            gateway=NoRetryGateway(Path(temporary)/'native.sqlite',cfg,'offline-secret',transport)
            payload={'model':'openai/auto-ontology-embedding','input':['first','second'],'input_type':'passage','truncate':'END','modality':'text'}
            first=json.loads(gateway.handle('/v1/embeddings',payload).body)
            replay=json.loads(gateway.handle('/v1/embeddings',payload).body)
            self.assertEqual(first,replay);self.assertEqual([d['index'] for d in first['data']],[0,1]);self.assertEqual(len(calls),2)
            with gateway._db() as db:self.assertEqual(db.execute('SELECT count(*),sum(reserved) FROM attempts').fetchone(),(2,200))
            gateway.close()

    @staticmethod
    def config():
        return Config(models=(Model(alias='openai/auto-ontology-reasoning',actual_id='offline/model',kind='chat',provider='offline',input_nanodollars_per_token=1,output_nanodollars_per_token=1,max_input_tokens=100,max_output_tokens=100,verification='offline test bounds'),),call_cap=10,per_call_nanodollars=200,total_nanodollars=2000,deadline_epoch=time.time()+60,timeout_seconds=1,max_request_bytes=4096,max_response_bytes=4096)

    @staticmethod
    def payload():
        return {'model':'openai/auto-ontology-reasoning','messages':[{'role':'user','content':'test'}],'max_tokens':10}

    def test_successful_lost_reply_replayed_across_restart_without_second_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger=Path(temporary)/'native.sqlite';calls=[];cfg=self.config()
            started=threading.Event()
            def transport(*args):
                calls.append(True)
                started.set()
                time.sleep(.05)
                return Response(200,b'{"choices":[],"usage":{"prompt_tokens":3}}')
            gateway=NoRetryGateway(ledger,cfg,'offline-secret',transport)
            from apps.factory_lab.extension_gateway_http import create_server
            server=create_server(gateway,'offline-dummy-token-123456')
            thread=threading.Thread(target=server.serve_forever);thread.start()
            try:
                conn=HTTPConnection('127.0.0.1',server.server_port,timeout=2)
                conn.request('POST','/v1/chat/completions',json.dumps(self.payload()),{'Authorization':'Bearer offline-dummy-token-123456','Content-Type':'application/json'})
                self.assertTrue(started.wait(2));conn.close()  # Actual lost HTTP peer.
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    with sqlite3.connect(gateway.cache) as db:
                        ready=db.execute("SELECT count(*) FROM requests WHERE state='completed'").fetchone()[0]
                    if ready:break
                    time.sleep(.01)
                self.assertTrue(ready)
            finally:
                server.shutdown();server.server_close();thread.join()
            gateway.close()
            again=NoRetryGateway(ledger,cfg,'offline-secret',transport)
            replay=again.handle('/v1/chat/completions',self.payload())
            self.assertEqual(replay.status,200);self.assertEqual(len(calls),1)
            with sqlite3.connect(ledger) as db:self.assertEqual(db.execute('SELECT count(*) FROM attempts').fetchone()[0],1)
            with sqlite3.connect(again.cache) as db:self.assertEqual(db.execute('SELECT hits FROM requests').fetchone()[0],1)
            again.close()

    def test_interrupted_attempt_blocks_new_request_after_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger=Path(temporary)/'native.sqlite';cfg=self.config();calls=[]
            gateway=NoRetryGateway(ledger,cfg,'offline-secret',lambda *a:calls.append(True))
            with gateway._db() as db:
                db.execute("INSERT INTO attempts(started,route,alias,model,original,request,sha256,reserved) VALUES(?,?,?,?,?,?,?,?)",(time.time(),'/v1/chat/completions','openai/auto-ontology-reasoning','offline/model','{}','{}','offline',200))
            gateway.close()
            again=NoRetryGateway(ledger,cfg,'offline-secret',lambda *a:calls.append(True))
            with self.assertRaises(Denied):again.handle('/v1/chat/completions',self.payload())
            self.assertEqual(calls,[])
            with sqlite3.connect(ledger) as db:self.assertEqual(db.execute('SELECT count(*) FROM attempts').fetchone()[0],1)
            again.close()

    def test_persistent_stop_blocks_provider_retry_before_another_reservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = Path(temporary)/'native.sqlite'
            config = Config(models=(Model(alias='openai/auto-ontology-reasoning',actual_id='offline/model',kind='chat',provider='offline',input_nanodollars_per_token=1,output_nanodollars_per_token=1,max_input_tokens=100,max_output_tokens=100,verification='offline test bounds'),),call_cap=10,per_call_nanodollars=200,total_nanodollars=2000,deadline_epoch=time.time()+60,timeout_seconds=1,max_request_bytes=4096,max_response_bytes=4096)
            calls=[]
            def transport(*args):
                calls.append(True)
                return Response(503,b'{"error":"offline failure"}')
            gateway = NoRetryGateway(ledger,config,'offline-secret',transport)
            payload={'model':'openai/auto-ontology-reasoning','messages':[{'role':'user','content':'test'}],'max_tokens':10}
            with self.assertRaises(Denied):gateway.handle('/v1/chat/completions',payload)
            gateway.close()
            again = NoRetryGateway(ledger,config,'offline-secret',transport)
            with self.assertRaises(Denied):again.handle('/v1/chat/completions',payload)
            self.assertEqual(len(calls),1)
            with sqlite3.connect(ledger) as db:self.assertEqual(db.execute('SELECT count(*) FROM attempts').fetchone()[0],1)
            again.close()
