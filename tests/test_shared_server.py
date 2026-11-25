"""Actual HTTP access boundary with injected model-free workspace calls."""
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace

from apps.factory_lab.public_runtime import Demo
from apps.factory_lab.public_server import make_server
from apps.factory_lab.shared_access import AccessConfig, AccessStore
from apps.factory_lab.shared_server import attach, COOKIE


class SharedHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.demo = Demo(self.root/'demo')
        access = AccessStore((self.root/'access').resolve(),
            config=AccessConfig(datetime.now(timezone.utc)+timedelta(hours=1)), pin='offline-pin-123')
        self.origin = 'https://offline-shared-test.trycloudflare.com'
        origin_file = self.root/'origin.json'
        origin_file.write_text(json.dumps({'origin': self.origin}))
        self.server = attach(make_server(self.demo, 0), access=access,
                             origin_file=origin_file, share_id='offline-share')
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def req(self, path, body=None, *, cookie='', csrf='', origin=None, raw=None, method=None, operator_key=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'Host': f'127.0.0.1:{self.server.server_port}'}
        if cookie: headers['Cookie'] = cookie
        if csrf: headers['X-CSRF-Token'] = csrf
        if operator_key is not None: headers['X-Factory-Operator-Key'] = operator_key
        if body is not None or raw is not None:
            headers.update({'Origin': self.origin if origin is None else origin,
                            'Content-Type': 'application/json'})
        data = raw if raw is not None else json.dumps(body) if body is not None else None
        conn.request(method or ('POST' if data is not None else 'GET'), path, data, headers)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def login(self):
        status, headers, _ = self.req('/api/shared/login', {'pin': 'offline-pin-123'})
        self.assertEqual(status, 200)
        self.assertIn('Secure; HttpOnly; SameSite=Strict', headers['Set-Cookie'])
        return headers['Set-Cookie'].split(';', 1)[0]

    def test_auth_origin_csrf_static_and_logout(self):
        self.assertEqual(self.req('/api/config')[0], 401)
        self.assertEqual(self.req('/review_inventory.js')[0], 401)
        self.assertIn('인증번호'.encode(), self.req('/')[2])
        self.assertEqual(self.req('/api/shared/login', {'pin': 'offline-pin-123'}, origin='https://evil.example')[0], 403)
        self.assertEqual(self.req('/api/shared/login', raw='{"pin":"a","pin":"b"}')[0], 400)
        cookie = self.login()
        config = json.loads(self.req('/api/config', cookie=cookie)[2])
        self.assertFalse(config['live_enabled'])
        csrf = config['csrf']
        self.assertIn(b'/shared-ui.js', self.req('/workspace', cookie=cookie)[2])
        self.assertIn(b'/review_inventory.js', self.req('/workspace', cookie=cookie)[2])
        self.assertEqual(self.req('/review_inventory.js', cookie=cookie)[0], 200)
        self.assertEqual(self.req('/.env', cookie=cookie)[0], 404)
        self.assertEqual(self.req('/api/workspace', {'action': 'list', 'archived': False}, cookie=cookie)[0], 403)
        self.assertEqual(self.req('/api/workspace', {'action': 'list', 'archived': False}, cookie=cookie, csrf=csrf)[0], 200)
        self.assertEqual(self.req('/api/workspace', {'action': 'ask'}, cookie=cookie, csrf=csrf)[0], 409)
        self.assertEqual(self.server.access.quota_status().count, 0)
        self.assertEqual(self.req('/api/runs', {}, cookie=cookie, csrf=csrf)[0], 403)
        self.assertEqual(self.req('/api/shared/logout', {}, cookie=cookie, csrf=csrf)[0], 200)
        self.assertEqual(self.req('/api/config', cookie=cookie)[0], 401)

    def test_private_operator_attribution_cannot_be_selected_by_browser(self):
        cookie = self.login()
        csrf = json.loads(self.req('/api/config', cookie=cookie)[2])['csrf']
        self.server.operator_secret = 'a' * 64
        self.demo.gateway = SimpleNamespace(session={}, config={'model': 'offline-no-model'})
        self.server.workspace.handle = lambda body: {'accepted': True}
        body = {'action': 'ask', 'id': 'offline-workspace', 'revision': 1,
                'request_key': 'operator-1', 'question': 'test'}
        self.assertEqual(self.req('/api/workspace', body, cookie=cookie, csrf=csrf,
                                  operator_key='spoof')[0], 403)
        self.assertEqual(self.server.access.quota_status().count, 0)
        self.assertEqual(self.req('/api/workspace', body, cookie=cookie, csrf=csrf,
                                  operator_key='a'*64)[0], 200)
        self.assertEqual(self.server.access.quota_status().count, 0)
        # Same request cannot change actor, even if the caller knows the shared PIN.
        self.assertEqual(self.req('/api/workspace', body, cookie=cookie, csrf=csrf)[0], 403)
        human = body | {'request_key': 'human-1', 'actor': 'operator_test'}
        self.assertEqual(self.req('/api/workspace', human, cookie=cookie, csrf=csrf)[0], 200)
        self.assertEqual(self.server.access.quota_status().count, 1)
        raw = self.req('/api/config', cookie=cookie)[2]
        self.assertNotIn(('a'*64).encode(), raw)
        self.assertEqual(json.loads(raw)['shared']['quota_scope'], 'human_operations_only')

    def test_daily_reservation_before_injected_work_and_replay(self):
        cookie = self.login()
        csrf = json.loads(self.req('/api/config', cookie=cookie)[2])['csrf']
        self.demo.gateway = SimpleNamespace(session={}, config={'model': 'offline-no-model'})
        # Actual HTTP plus quota; injected terminal work does not call a model.
        self.server.workspace.handle = lambda body: {'accepted': True}
        def payload(i):
            return {'action': 'ask', 'id': 'offline-workspace', 'revision': 1,
                    'request_key': f'key-{i}', 'question': 'test'}
        for i in range(10):
            self.assertEqual(self.req('/api/workspace', payload(i), cookie=cookie, csrf=csrf)[0], 200)
        self.assertEqual(self.req('/api/workspace', payload(10), cookie=cookie, csrf=csrf)[0], 429)
        self.assertEqual(self.req('/api/workspace', payload(0), cookie=cookie, csrf=csrf)[0], 200)
        conflict = payload(0) | {'question': 'different'}
        self.assertEqual(self.req('/api/workspace', conflict, cookie=cookie, csrf=csrf)[0], 403)
        self.assertEqual(self.server.access.quota_status().count, 10)

    def test_native_budget_preflight_rejects_before_human_quota_or_job(self):
        cookie=self.login();csrf=json.loads(self.req('/api/config',cookie=cookie)[2])['csrf']
        attach(self.server,access=self.server.access,origin_file=self.root/'origin.json',
               share_id='offline-share',semantic_enabled=True)
        self.assertTrue(json.loads(self.req('/api/shared/status',cookie=cookie)[2])['auto_ontology']['semantic_enabled'])
        self.server.native_readiness=lambda:{'ready':False,'reason':'reservation_limit',
            'message':'내부 비용 예약 한도 · 계정 잔액 아님', 'reserved_usd':'9.634100000',
            'reservation_cap_usd':'10.000000000','next_chat_reservation_usd':'1.200000000'}
        self.server.start_job=lambda *a:self.fail('No native job expected')
        status=json.loads(self.req('/api/shared/status',cookie=cookie)[2])['auto_ontology']
        self.assertFalse(status['semantic_enabled']);self.assertEqual(status['budget']['reason'],'reservation_limit')
        code,_,raw=self.req('/api/shared/extensions',{'id':'offline-db','revision':1,'request_key':'budget-denied','mode':'semantic'},cookie=cookie,csrf=csrf)
        self.assertEqual(code,409);self.assertIn('예약',json.loads(raw)['error'])
        self.assertEqual(self.server.access.quota_status().count,0)

    def test_saved_job_exposes_observed_stage_and_proposal_navigation_receipt(self):
        import time
        row=self.server.workspace.handle({'action':'example','domain':'commerce'})
        store=self.server.workspace.store;started=threading.Event();release=threading.Event()
        def invocation(body):
            op,_=store.begin(row['id'],1,body['request_key'],'extension_generation',{'mode':'catalog'})
            store.checkpoint(op['id'],{'status':'reserved_before_launch'})
            started.set();release.wait(3)
            imported,_=store.begin(row['id'],1,'fake-import','extension_import',{})
            store.finish(imported['id'],'completed',result={'fields':[{'kind':'column'}],
                'concepts':[{'kind':'concept'}],'relations':[{}],'unsupported':[],'unresolved_references':[]})
            store.finish(op['id'],'completed',result={'mode':'catalog','import_operation_id':imported['id']})
            return {'operation':store.operation(row['id'],op['id'])}
        attach(self.server,access=self.server.access,origin_file=self.root/'origin.json',
            share_id='offline-share',extensions=SimpleNamespace(handle=invocation))
        cookie=self.login();csrf=json.loads(self.req('/api/config',cookie=cookie)[2])['csrf']
        try:
            code,_,raw=self.req('/api/shared/extensions',{'id':row['id'],'revision':1,'request_key':'stage-test','mode':'catalog'},cookie=cookie,csrf=csrf)
            self.assertEqual(code,202);job=json.loads(raw);self.assertTrue(started.wait(1))
            progress=json.loads(self.req('/api/shared/jobs/'+job['id'],cookie=cookie)[2])
            self.assertEqual(progress['stage'],'native_processing');release.set()
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                result=json.loads(self.req('/api/shared/jobs/'+job['id'],cookie=cookie)[2])
                if result['state']=='completed':break
                time.sleep(.01)
            self.assertEqual(result['state'],'completed')
            self.assertEqual(result['summary']['physical_columns'],1)
            self.assertEqual(result['summary']['origin'],'external_proposal')
            self.assertEqual(result['summary']['workspace'],row['id'])
            self.assertEqual(self.server.access.quota_status().count,0)
        finally:release.set()

    def test_failed_inner_generation_is_not_a_completed_public_job(self):
        import time
        row=self.server.workspace.handle({'action':'example','domain':'commerce'});store=self.server.workspace.store
        def fail(body):
            op,_=store.begin(row['id'],1,body['request_key'],'extension_generation',{'mode':'catalog'})
            store.finish(op['id'],'failed',error='injected model-free failure')
            return {'operation':store.operation(row['id'],op['id'])}
        attach(self.server,access=self.server.access,origin_file=self.root/'origin.json',
            share_id='offline-share',extensions=SimpleNamespace(handle=fail))
        cookie=self.login();csrf=json.loads(self.req('/api/config',cookie=cookie)[2])['csrf']
        _,_,raw=self.req('/api/shared/extensions',{'id':row['id'],'revision':1,'request_key':'failed-test','mode':'catalog'},cookie=cookie,csrf=csrf)
        job=json.loads(raw);deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            result=json.loads(self.req('/api/shared/jobs/'+job['id'],cookie=cookie)[2])
            if result['state']=='failed':break
            time.sleep(.01)
        self.assertEqual(result['state'],'failed');self.assertIsNone(result['summary'])


if __name__ == '__main__':
    unittest.main()
