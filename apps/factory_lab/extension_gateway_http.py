"""Loopback adapter and single-attempt OpenRouter transport.

No service starts on import. Operator supplies an already reviewed Gateway and a fresh
per-run dummy bearer (never the real provider credential). urllib ignores proxy env,
rejects redirects and never retries. Socket and response deadlines are bounded; OS DNS
resolution is outside Python's socket timeout and must also be bounded by the launcher.
The loopback service is not a process or network sandbox. No request/access logs.
"""
from __future__ import annotations

import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import socket
import threading
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .extension_gateway import Denied, Gateway, Response

ROUTES = frozenset({'/v1/chat/completions', '/v1/embeddings'})


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def openrouter_transport(route: str, body: bytes, secret: str,
                         timeout: float, max_response_bytes: int) -> Response:
    """Exactly one POST to a fixed HTTPS origin; no redirects, retries or proxy env."""
    if (route not in ROUTES or type(body) is not bytes or not secret
            or '\r' in secret or '\n' in secret
            or not math.isfinite(timeout) or timeout <= 0
            or type(max_response_bytes) is not int or max_response_bytes <= 0):
        raise Denied('invalid transport arguments')
    request = Request('https://openrouter.ai/api' + route, data=body,
                      headers={'Authorization': 'Bearer ' + secret,
                               'Content-Type': 'application/json', 'Accept': 'application/json'},
                      method='POST')
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    deadline = time.monotonic() + timeout
    try:
        response = opener.open(request, timeout=timeout)
    except HTTPError as exc:
        response = exc  # retain non-2xx body, including refused redirects
    reader = response.fp if isinstance(response, HTTPError) else response
    with response:
        chunks = []
        size = 0
        # One byte over the cap is retained so the core records the bounded partial
        # response as a failed attempt. Never drain an unbounded provider response.
        while size <= max_response_bytes:
            if reader.isclosed():
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('response deadline reached')
            # urllib's HTTPS response wraps http.client.HTTPResponse. Fail closed
            # if an alternative runtime cannot expose its socket for deadline reset.
            sock = getattr(getattr(getattr(reader, 'fp', None), 'raw', None), '_sock', None)
            if sock is None:
                raise Denied('cannot enforce response socket deadline')
            sock.settimeout(remaining)
            chunk = reader.read1(min(65536, max_response_bytes + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        return Response(response.status, b''.join(chunks))


def _error_body(message, code):
    return json.dumps({'error': {'message': message, 'type': 'gateway_error',
                                 'param': None, 'code': code}}).encode()


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 4

    def process_request(self, request, client_address):
        if not self.slots.acquire(timeout=0.25):
            body = _error_body('gateway concurrency limit', 'concurrency_limit')
            try:
                request.settimeout(1)
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n'
                    b'Content-Type: application/json\r\nContent-Length: ' + str(len(body)).encode()
                    + b'\r\n\r\n' + body)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        pass  # no credentials, request bodies or traceback in server logs


class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        self.request.settimeout(self.server.client_timeout)
        super().setup()

    def log_message(self, *args):
        pass

    def _reply(self, status, body):
        self.close_connection = True
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        self._reply(code, _error_body('unsupported HTTP request', 'invalid_request'))

    def handle_expect_100(self):
        self._reply(400, _error_body('Expect header denied', 'invalid_request'))
        return False

    def do_POST(self):
        auth = self.headers.get_all('Authorization', [])
        expected = 'Bearer ' + self.server.dummy_token
        if len(auth) != 1 or not hmac.compare_digest(auth[0].encode(), expected.encode()):
            self._reply(401, _error_body('dummy bearer required', 'unauthorized'))
            return
        if self.path not in ROUTES:
            self._reply(404, _error_body('route denied', 'invalid_route'))
            return
        lengths = self.headers.get_all('Content-Length', [])
        if (self.headers.get('Transfer-Encoding') is not None or len(lengths) != 1
                or not lengths[0].isascii() or not lengths[0].isdigit()
                or self.headers.get_content_type() != 'application/json'):
            self._reply(400, _error_body('bounded JSON content length required', 'invalid_request'))
            return
        length = int(lengths[0])
        if not 0 < length <= self.server.gateway.config.max_request_bytes:
            self._reply(413, _error_body('request too large or empty', 'request_limit'))
            return
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('incomplete body')
            # Duplicate keys and nonfinite values are ambiguous; reject before reserve.
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('duplicate key')
                    result[key] = value
                return result
            def invalid_constant(value):
                raise ValueError('nonfinite JSON')
            payload = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
        except (ValueError, UnicodeError, OSError):
            self._reply(400, _error_body('invalid or incomplete JSON', 'invalid_request'))
            return
        try:
            result = self.server.gateway.handle(self.path, payload)
        except Denied as exc:
            # Core messages are controlled, but never expose exception detail to child.
            budget = str(exc) in {'campaign reservation limit reached', 'campaign deadline reached'}
            self._reply(402 if budget else 400, _error_body(
                'campaign limit reached; stop run' if budget else 'request rejected or attempt failed; inspect ledger',
                'campaign_limit' if budget else 'attempt_rejected'))
            return
        except Exception:
            self._reply(400, _error_body('gateway failure; stop run and inspect ledger', 'gateway_failure'))
            return
        self._reply(result.status, result.body)


def create_server(gateway: Gateway, dummy_token: str, *, concurrency: int = 1,
                  client_timeout: float = 15) -> ThreadingHTTPServer:
    """Bind an ephemeral IPv4 loopback port; caller owns serve/shutdown lifecycle."""
    if (not isinstance(dummy_token, str) or len(dummy_token) < 16
            or not dummy_token.isascii() or any(c.isspace() for c in dummy_token)
            or dummy_token == gateway._secret):
        raise Denied('fresh per-run dummy token of at least 16 ASCII characters required')
    if type(concurrency) is not int or not 1 <= concurrency <= 4:
        raise Denied('concurrency must be 1..4')
    if not math.isfinite(client_timeout) or not 0 < client_timeout <= 60:
        raise Denied('bounded client timeout required')
    server = _Server(('127.0.0.1', 0), _Handler)
    server.gateway = gateway
    server.dummy_token = dummy_token
    server.slots = threading.BoundedSemaphore(concurrency)
    server.client_timeout = client_timeout
    return server
