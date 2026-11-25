"""Loopback-only integration and mocked urllib transport: no provider calls."""
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request

from apps.factory_lab.extension_gateway import Config, Denied, Gateway, Model, Response
from apps.factory_lab.extension_gateway_http import create_server, openrouter_transport, _NoRedirect

CHAT = '/v1/chat/completions'
TOKEN = 'per-run-dummy-credential'


def payload():
    return {'model':'openai/auto-ontology-reasoning', 'messages':[{'role':'user','content':'hello'}],
            'max_completion_tokens':100, 'response_format':{'type':'json_schema',
                'json_schema':{'name':'answer','strict':True,'schema':{'type':'object','properties':{},'additionalProperties':False}}}}


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.sent = []
        self.path = Path(self.temp.name) / 'ledger.sqlite'
        m = Model('openai/auto-ontology-reasoning','vendor/chat','chat','provider',10,20,50000,8192,'fixture')
        cfg = Config((m,),1,1000000,1000000,9999999999,10,20000,100000)
        def transport(*args):
            self.sent.append(args)
            return Response(200,b'{"choices":[],"usage":{"prompt_tokens":1}}')
        self.gateway = Gateway(self.path,cfg,'actual-secret-fixture',transport)
        self.server = create_server(self.gateway,TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def post(self, body=None, route=CHAT, token=TOKEN, extra=None):
        conn = http.client.HTTPConnection(*self.server.server_address,timeout=2)
        headers = {'Authorization':'Bearer '+token, 'Content-Type':'application/json'}
        headers.update(extra or {})
        conn.request('POST',route,body if body is not None else json.dumps(payload()),headers)
        response = conn.getresponse()
        result = response.status,json.loads(response.read())
        conn.close()
        return result

    def test_loopback_success_and_terminal_retry_budget(self):
        self.assertEqual(self.server.server_address[0],'127.0.0.1')
        self.assertEqual(self.post()[0],200)
        status,body = self.post()
        self.assertEqual(status,402)
        self.assertEqual(body['error']['code'],'campaign_limit')
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.sent[0][2],'actual-secret-fixture')
        self.assertNotIn('actual-secret-fixture',str(body))

    def test_auth_routes_json_and_size_rejected_before_transport(self):
        self.assertEqual(self.post(token='wrong')[0],401)
        self.assertEqual(self.post(route='/v1/chat/completions?x=1')[0],404)
        self.assertEqual(self.post(body='{"model":1,"model":2}')[0],400)
        self.assertEqual(self.post(body='{"x":NaN}')[0],400)
        self.assertEqual(self.post(body='x'*20001)[0],413)
        self.assertEqual(self.post(extra={'Transfer-Encoding':'chunked'})[0],400)
        self.assertEqual(self.post(body='{}')[0],400)
        self.assertEqual(self.sent,[])

    def test_concurrency_guard_does_not_reserve(self):
        self.server.slots.acquire()
        try:
            self.assertEqual(self.post()[0],503)
        finally:
            self.server.slots.release()
        self.assertEqual(self.sent,[])

    def test_dummy_credential_validation(self):
        for token in ('fakekey','actual-secret-fixture', 'has space but long enough'):
            with self.assertRaises(Denied):
                create_server(self.gateway,token)


class FakeResponse:
    def __init__(self, body=b'{"ok":true}',status=200):
        self.body = io.BytesIO(body)
        self.status = status
        self.timeouts = []
        self.fp = SimpleNamespace(raw=SimpleNamespace(_sock=SimpleNamespace(settimeout=self.timeouts.append)))
    @property
    def closed(self):
        return self.body.closed
    def close(self):
        self.body.close()
    def isclosed(self):
        return False
    def read1(self,n):
        return self.body.read(n)
    def __enter__(self):
        return self
    def __exit__(self,*args):
        self.body.close()


class TransportTests(unittest.TestCase):
    def test_real_urllib_response_wrappers_against_loopback_only(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                status = 429 if self.path.endswith('embeddings') else 200
                body = b'{"fixture":true}'
                self.send_response(status)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self,*args):
                pass
        server = HTTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        def local_request(url,**kwargs):
            self.assertTrue(url.startswith('https://openrouter.ai/api/v1/'))
            path = url.removeprefix('https://openrouter.ai/api')
            return Request(f'http://127.0.0.1:{server.server_port}' + path,**kwargs)
        try:
            with patch('apps.factory_lab.extension_gateway_http.Request',side_effect=local_request):
                for route,status in ((CHAT,200),('/v1/embeddings',429)):
                    result = openrouter_transport(route,b'{}','fixture',2,100)
                    self.assertEqual(result.status,status)
                    self.assertEqual(result.body,b'{"fixture":true}')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
    @patch('apps.factory_lab.extension_gateway_http.build_opener')
    def test_fixed_origin_no_proxy_no_retry_and_bounded_response(self,build):
        response = FakeResponse(b'x'*100)
        build.return_value.open.return_value = response
        result = openrouter_transport(CHAT,b'{}','secret',10,20)
        self.assertEqual(result.body,b'x'*21)
        build.return_value.open.assert_called_once()
        req = build.return_value.open.call_args.args[0]
        self.assertEqual(req.full_url,'https://openrouter.ai/api/v1/chat/completions')
        self.assertEqual(req.get_header('Authorization'),'Bearer secret')
        self.assertEqual(req.get_method(),'POST')
        proxy,redirect = build.call_args.args
        self.assertIsInstance(proxy,ProxyHandler)
        self.assertEqual(proxy.proxies,{})
        self.assertIsInstance(redirect,_NoRedirect)
        self.assertTrue(response.timeouts)

    @patch('apps.factory_lab.extension_gateway_http.build_opener')
    def test_error_and_redirect_response_captured_without_following(self,build):
        response = FakeResponse(b'{"error":"refused"}',302)
        error = HTTPError('https://openrouter.ai/api/v1/chat/completions',302,'redirect',{},response)
        # HTTPError delegates read/isclosed to supplied file, but its fp is that file.
        response.raw = response.fp.raw
        build.return_value.open.side_effect = error
        result = openrouter_transport(CHAT,b'{}','secret',10,100)
        self.assertEqual(result.status,302)
        self.assertEqual(result.body,b'{"error":"refused"}')
        build.return_value.open.assert_called_once()
        self.assertIsNone(_NoRedirect().redirect_request(Request('https://openrouter.ai'),None,302,'',{},'https://attacker.invalid'))

    @patch('apps.factory_lab.extension_gateway_http.build_opener')
    def test_timeout_not_retried_and_invalid_route_never_opens(self,build):
        build.return_value.open.side_effect = TimeoutError('fixture')
        with self.assertRaises(TimeoutError):
            openrouter_transport(CHAT,b'{}','secret',1,100)
        build.return_value.open.assert_called_once()
        with self.assertRaises(Denied):
            openrouter_transport('/v1/models',b'{}','secret',1,100)
        self.assertEqual(build.return_value.open.call_count,1)


if __name__ == '__main__':
    unittest.main()
