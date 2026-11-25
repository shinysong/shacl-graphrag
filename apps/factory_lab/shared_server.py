"""Authenticated temporary workspace for one trusted group, never multi-tenant.

The cloudflared connector must rewrite Host to this loopback listener. Public
Origin is read from an operator-owned file, never X-Forwarded-Host. No arbitrary
proxy targets, filesystem routes, provider credentials, or SQL are accepted.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from http.cookies import SimpleCookie
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit

from .public_server import Handler, make_server, STATIC
from .public_runtime import Demo, PublicGateway
from .shared_access import AccessStore, AccessConfig, AccessError, QuotaExceeded
from .extension_gateway import Gateway, Denied, ledger_totals

COOKIE = '__Host-factory_session'
PAID_ACTIONS = {'ask', 'suggest', 'extension_localize'}


class NoRetryGateway(Gateway):
    """Persistently stop native provider traffic after any failed request.

    Upstream embedding SDK may retry against its dummy endpoint. Those requests
    must never turn into another paid provider call after the first failure.
    """
    def __init__(self, *args, description_language=None, **kwargs):
        if description_language not in (None,'ko'):raise ValueError('Unsupported description language')
        self.description_language=description_language
        super().__init__(*args, **kwargs)
        self._replay_lock = threading.Lock()
        self.cache = self.ledger.with_suffix('.request-cache.sqlite')
        with sqlite3.connect(self.cache) as db:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS requests (digest TEXT PRIMARY KEY, state TEXT NOT NULL, status INTEGER, body BLOB, hits INTEGER NOT NULL DEFAULT 0)')
            incomplete = db.execute("SELECT count(*) FROM requests WHERE state='running'").fetchone()[0]
        self.cache.chmod(0o600)
        with self._db() as db:
            unresolved = db.execute('SELECT count(*) FROM attempts a LEFT JOIN completions c ON a.id=c.attempt WHERE c.attempt IS NULL').fetchone()[0]
        if incomplete or unresolved:
            save(self.ledger.with_suffix('.paid-stop.json'),
                 {'stopped': True, 'reason': 'Unresolved native attempt or response cache; operator inspection required'})

    def readiness(self):
        """Read-only first-chat capacity, not a reservation or whole-run estimate."""
        with self._db() as db:
            totals = ledger_totals(db, self.config.reservation_accounting)
            count, total = totals['attempts'], totals['used']
            chats = db.execute("SELECT count(*) FROM attempts WHERE route='/v1/chat/completions'").fetchone()[0]
        cfg = self.config
        reserved = total + cfg.inherited_reserved_nanodollars
        chat = next((m for m in cfg.models if m.kind == 'chat'), None)
        required = (chat.reservation_nanodollars or cfg.per_call_nanodollars) if chat else cfg.per_call_nanodollars
        reason = None
        if self.clock() + cfg.timeout_seconds > cfg.deadline_epoch:
            reason = 'deadline'
        elif (count + cfg.inherited_attempts >= cfg.call_cap or
              (cfg.chat_attempt_cap and chats >= cfg.chat_attempt_cap) or
              reserved + required > cfg.total_nanodollars):
            reason = 'reservation_limit'
        elif self.ledger.with_suffix('.paid-stop.json').exists():
            reason = 'inspection_required'
        messages = {
            'deadline': '외부 의미 생성의 실행 기한이 종료됐습니다.',
            'reservation_limit': '외부 의미 생성의 내부 비용 예약 한도에 도달했습니다. OpenRouter 잔액 부족을 뜻하지 않습니다. 운영자 검토가 필요하며 자동 재시도하지 않습니다.',
            'inspection_required': '이전 외부 의미 생성이 중단되어 운영자 확인이 필요합니다. 자동 재시도하지 않습니다.'}
        return {'ready': reason is None, 'reason': reason, 'message': messages.get(reason, ''),
                'reserved_usd': f'{reserved / 1_000_000_000:.9f}',
                'reservation_cap_usd': f'{cfg.total_nanodollars / 1_000_000_000:.9f}',
                'accounting': cfg.reservation_accounting,
                'unconfirmed_hold_usd': f'{totals["held"] / 1_000_000_000:.9f}',
                'historical_debit_usd': f'{cfg.inherited_reserved_nanodollars / 1_000_000_000:.9f}',
                'next_chat_reservation_usd': f'{required / 1_000_000_000:.9f}',
                'scope': 'first_chat_capacity_not_whole_run_or_account_balance'}

    def handle(self, route, payload):
        if route == '/v1/chat/completions' and self.description_language == 'ko':
            if not isinstance(payload,dict) or not isinstance(payload.get('messages'),list):
                raise Denied('Native chat messages required')
            payload={**payload,'messages':[*payload['messages'],{'role':'system','content':
                'Write human-readable descriptions, definitions, explanations and relationship meanings in Korean. '
                'Keep JSON schema, SQL, database/table/column names, identifiers, enum values and reference IDs unchanged. '
                'Preserve uncertainty and source scope. Do not add business rules or approve anything. '
                'This output-language instruction does not alter any required response structure.'}]}
        # An identical native request is a replay, even after a lost HTTP reply.
        # Persist the successful response before the HTTP adapter sends bytes.
        from .extension_gateway import Response
        # Upstream embeds batches of up to32 texts. Keep the audited core's
        # one-text full-context reservation and genuine vector validation for
        # EACH input, then restore the batch shape expected by its SDK.
        if route == '/v1/embeddings' and isinstance(payload, dict) and isinstance(payload.get('input'), list) and len(payload['input']) > 1:
            inputs = payload['input']
            if len(inputs) > 32 or any(not isinstance(s, str) or not s for s in inputs):
                raise Denied('Native embedding batch exceeds 32 nonempty texts')
            rows, tokens, model = [], 0, None
            for index, text in enumerate(inputs):
                response = self.handle(route, payload | {'input': [text]})
                body = json.loads(response.body)
                rows.append(body['data'][0] | {'index': index})
                tokens += body.get('usage', {}).get('prompt_tokens', 0)
                model = body.get('model', model)
            raw = json.dumps({'object': 'list', 'data': rows, 'model': model,
                              'usage': {'prompt_tokens': tokens, 'total_tokens': tokens}}).encode()
            if len(raw) > self.config.max_response_bytes:
                raise Denied('Combined embedding result exceeds response boundary')
            return Response(200, raw)
        stop = self.ledger.with_suffix('.paid-stop.json')
        digest = hashlib.sha256(json.dumps([route, payload], sort_keys=True,
            ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()).hexdigest()
        with self._replay_lock:
            with sqlite3.connect(self.cache) as db:
                row = db.execute('SELECT state,status,body FROM requests WHERE digest=?', (digest,)).fetchone()
                if row and row[0] == 'completed':
                    db.execute('UPDATE requests SET hits=hits+1 WHERE digest=?', (digest,))
                    return Response(row[1], row[2])
            if stop.exists() or row:
                raise Denied('Native paid traffic stopped; operator inspection required')
            with sqlite3.connect(self.cache) as db:
                db.execute('PRAGMA synchronous=FULL')
                db.execute("INSERT INTO requests(digest,state) VALUES(?,'running')", (digest,))
            try:
                response = super().handle(route, payload)
                raw = response.body.replace(self._secret.encode(), b'[REDACTED]')
                with sqlite3.connect(self.cache) as db:
                    db.execute('PRAGMA synchronous=FULL')
                    db.execute("UPDATE requests SET state='completed',status=?,body=? WHERE digest=?", (response.status, raw, digest))
                return Response(response.status, raw)
            except BaseException as exc:
                save(stop, {'stopped': True, 'failure_class': type(exc).__name__,
                            'at': datetime.now(timezone.utc).isoformat()})
                with sqlite3.connect(self.cache) as db:
                    db.execute("UPDATE requests SET state='failed' WHERE digest=?", (digest,))
                raise


def save(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False))
    tmp.chmod(0o600)
    tmp.replace(path)


class SharedHandler(Handler):
    def setup(self):
        self.request.settimeout(20)
        super().setup()

    def send(self, value, status=200, mime='application/json; charset=utf-8'):
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        headers = {'Content-Type': mime, 'Content-Length': str(len(raw)), 'Cache-Control': 'no-store',
                   'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
                   'Referrer-Policy': 'no-referrer',
                   'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"}
        if getattr(self, 'session_cookie', None) is not None:
            headers['Set-Cookie'] = self.session_cookie
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def token(self):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            return cookies[COOKIE].value if COOKIE in cookies else ''
        except Exception:
            return ''

    def authenticated(self):
        try:
            return self.server.access.authenticate(self.token())
        except AccessError:
            return False

    def origin_valid(self):
        try:
            value = json.loads(self.server.origin_file.read_text())['origin']
            parsed = urlsplit(value)
            if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.trycloudflare.com') or parsed.path or parsed.query or parsed.fragment or parsed.port or parsed.username:
                return False
            return self.headers.get_all('Origin', []) == [value]
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def body(self):
        lengths = self.headers.get_all('Content-Length', [])
        if (self.headers.get('Transfer-Encoding') or len(lengths) != 1 or
                not lengths[0].isascii() or not lengths[0].isdigit() or
                self.headers.get_content_type() != 'application/json'):
            raise ValueError('Bounded JSON required')
        maximum = 8_000_000 if self.path == '/api/workspace' else 12000
        length = int(lengths[0])
        if not 0 < length <= maximum:
            raise ValueError('Body size exceeded')
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError('Incomplete body')
        def unique(pairs):
            obj = {}
            for key, val in pairs:
                if key in obj:
                    raise ValueError('Duplicate JSON key')
                obj[key] = val
            return obj
        obj = json.loads(raw, object_pairs_hook=unique,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        if not isinstance(obj, dict):
            raise ValueError('Object required')
        return obj, raw

    def do_GET(self):
        if not self.local():
            return self.send({'error': 'Host rejected'}, 403)
        path = urlsplit(self.path).path
        if self.path != path:
            return self.send({'error': 'Query strings are unsupported'}, 400)
        if path == '/health':
            return self.send({'share_id': self.server.share_id, 'mode': 'authenticated-workspace'})
        if path in ('/shared-login.js', '/shared.css'):
            file = STATIC/path[1:]
            return self.send(file.read_bytes(), mime='text/javascript' if path.endswith('.js') else 'text/css')
        if not self.authenticated():
            if path in ('/', '/workspace', '/login'):
                return self.send((STATIC/'shared-login.html').read_bytes(), mime='text/html; charset=utf-8')
            return self.send({'error': '인증번호로 로그인하세요.'}, 401)
        if path in ('/', '/workspace'):
            html = (STATIC/'workspace.html').read_text()
            html = html.replace('</head>', '<link rel="stylesheet" href="/shared.css"><script src="/shared-ui.js" defer></script></head>')
            html = html.replace('단일 사용자 · 로컬 저장', '인증 사용자끼리 공유 · 서버 저장')
            return self.send(html.encode(), mime='text/html; charset=utf-8')
        if path == '/shared-ui.js':
            return self.send((STATIC/'shared-ui.js').read_bytes(), mime='text/javascript; charset=utf-8')
        if path == '/api/shared/status':
            return self.send(self.server.shared_status())
        if path.startswith('/api/shared/jobs/'):
            return self.server.job_status(self, path.rsplit('/', 1)[-1])
        if path == '/api/config':
            return self.send(self.server.demo.config() | {'csrf': self.server.token,
                             'shared': self.server.shared_status()})
        # The normal static allowlist and safe read routes remain available only
        # to authenticated members. No directory traversal or proxy forwarding.
        return super().do_GET()

    def reserve(self, body, action):
        # Only a private operator credential can identify verification traffic.
        # Browser payloads, PIN sessions and forwarded headers confer no bypass.
        supplied = self.headers.get_all('X-Factory-Operator-Key', [])
        actor = 'human'
        if supplied:
            expected = self.server.operator_secret
            if len(supplied) != 1 or not expected or not secrets.compare_digest(supplied[0], expected):
                raise AccessError('Operator credential rejected')
            actor = 'operator_test'
        self.server.access.reserve_paid_operation(self.token(), action=action,
            workspace=body.get('id', 'factory-demo'), request_key=body.get('request_key', ''),
            revision=str(body.get('revision', '1')),
            request_digest=hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                separators=(',', ':')).encode()).hexdigest(), actor=actor)

    def do_POST(self):
        if not self.local() or not self.origin_valid():
            return self.send({'error': 'Origin rejected'}, 403)
        try:
            if self.path == '/api/shared/login':
                body, _ = self.body()
                if set(body) != {'pin'} or not isinstance(body['pin'], str):
                    raise ValueError('PIN required')
                token = self.server.access.login(body['pin'])
                if not token:
                    return self.send({'error': '인증번호가 다르거나 시도 한도에 도달했습니다. 잠시 후 다시 시도하세요.'}, 401)
                self.session_cookie = f'{COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=28800'
                return self.send({'authenticated': True})
            if not self.authenticated():
                return self.send({'error': '인증번호로 로그인하세요.'}, 401)
            if not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), self.server.token):
                return self.send({'error': 'Token rejected'}, 403)
            body, raw = self.body()
            if self.path == '/api/shared/logout':
                self.server.access.logout(self.token())
                self.session_cookie = f'{COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=0'
                return self.send({'authenticated': False})
            if self.path == '/api/shared/extensions':
                if set(body) != {'id', 'revision', 'request_key', 'mode'}:
                    raise ValueError('Extension request fields required')
                if body['mode'] == 'semantic':
                    native = self.server.shared_status()['auto_ontology']
                    if not native['semantic_enabled']:
                        return self.send({'error': native.get('unavailable_reason') or '외부 의미 생성의 유료 실행은 아직 열리지 않았습니다.'}, 409)
                    self.reserve(body, 'auto-ontology')
                return self.server.start_job(self, body)
            if self.path == '/api/workspace':
                if body.get('action') in PAID_ACTIONS:
                    if self.server.demo.gateway is None:
                        return self.send({'error': '유료 실행이 비활성화되어 있습니다.'}, 409)
                    self.reserve(body, body['action'])
            elif self.path == '/api/runs':
                # Legacy demo lacks persistent request keys. Only the idempotent
                # workspace question path is available in the shared deployment.
                return self.send({'error': '자료실의 질문하기를 이용하세요.'}, 403)
            else:
                return self.send({'error': 'Route disabled in shared deployment'}, 404)
            # Parent checks the operator loopback origin and original CSRF token.
            self.headers.replace_header('Origin', f'http://127.0.0.1:{self.server.server_port}')
            self.rfile = io.BytesIO(raw)
            return super().do_POST()
        except QuotaExceeded:
            return self.send({'error': '오늘의 전체 사용자 합산 유료 실행 10회를 사용했습니다. 한국시간 자정에 초기화됩니다.'}, 429)
        except AccessError:
            return self.send({'error': '접근 기한·인증·동일 요청 정보를 확인하세요.'}, 403)
        except (ValueError, TypeError, KeyError):
            return self.send({'error': '요청 형식이나 실행 범위를 확인하세요.'}, 400)

    def do_PUT(self):
        return self.send({'error': 'Method disabled'}, 405)
    do_PATCH = do_PUT
    do_DELETE = do_PUT


def attach(server, *, access, origin_file, share_id, extensions=None, semantic_enabled=False, operator_secret=None):
    if operator_secret is not None and (not isinstance(operator_secret, str) or len(operator_secret) < 64):
        raise ValueError('Private operator credential must contain at least 64 characters')
    server.operator_secret = operator_secret
    server.RequestHandlerClass = SharedHandler
    server.access, server.origin_file, server.share_id = access, Path(origin_file), share_id
    server.semantic_enabled = semantic_enabled
    jobs = server.demo.directory/'shared-jobs'
    jobs.mkdir(mode=0o700, exist_ok=True)
    joblock = threading.Lock()
    for path in jobs.glob('*.json'):
        saved = json.loads(path.read_text())
        if saved.get('state') in ('queued', 'running'):
            save(path, {**saved, 'state': 'interrupted', 'error': 'Server restarted; no automatic retry'})

    def status():
        stopped = getattr(server, 'native_stop', Path('/nonexistent-factory-native-stop')).exists()
        readiness = server.native_readiness() if hasattr(server, 'native_readiness') else None
        return {'quota': asdict(access.quota_status()), 'timezone': 'Asia/Seoul',
                'expires': access.config.deadline.isoformat(), 'shared_workspace': True,
                'quota_scope': 'human_operations_only', 'operator_costs_in_total_budget': True,
                'auto_ontology': {'configured': extensions is not None,
                    'semantic_enabled': semantic_enabled and not stopped and (readiness is None or readiness['ready']),
                    'unavailable_reason': (readiness['message'] if readiness and not readiness['ready'] else
                        '이전 외부 실행이 중단되어 운영자 확인이 필요합니다.' if stopped else ''),
                    'budget': readiness},
                'notice': '인증 사용자는 자료와 실행 기록을 공유합니다. 민감한 정보는 올리지 마세요.'}
    server.shared_status = status

    def job_status(handler, jid):
        if len(jid) != 64 or any(c not in '0123456789abcdef' for c in jid):
            return handler.send({'error': 'Unknown job'}, 404)
        path = jobs/(jid+'.json')
        if not path.is_file():
            return handler.send({'error': 'Unknown job'}, 404)
        saved = json.loads(path.read_text())
        if saved.get('state') in ('queued', 'running') and isinstance(saved.get('workspace'), str):
            with server.workspace.store.connect() as db:
                row = db.execute('SELECT result FROM operations WHERE workspace=? AND request_key=?',
                                 (saved['workspace'], saved.get('request_key'))).fetchone()
            result = json.loads(row['result'] or '{}') if row else {}
            saved['stage'] = ('saving_proposal' if result.get('status') == 'export_ready_for_pending_import'
                              else 'native_processing' if result.get('status') == 'reserved_before_launch'
                              else saved.get('stage', 'source_check'))
        return handler.send(saved)
    server.job_status = job_status

    def start_job(handler, body):
        if extensions is None:
            return handler.send({'error': 'NVIDIA 확장이 설정되지 않았습니다.'}, 409)
        jid = hashlib.sha256(json.dumps([body['id'],body['revision'],body['request_key'],body['mode']]).encode()).hexdigest()
        path = jobs/(jid+'.json')
        with joblock:
            if path.exists():
                return handler.send(json.loads(path.read_text()))
            if not server.demo.lock.acquire(blocking=False):
                return handler.send({'error': '다른 실행이 진행 중입니다.'}, 409)
            context = {'id': jid, 'mode': body['mode'], 'workspace': body['id'],
                       'revision': body['revision'], 'request_key': body['request_key']}
            save(path, {**context, 'state': 'queued', 'stage': 'queued'})
            def run():
                try:
                    save(path, {**context, 'state': 'running', 'stage': 'source_check'})
                    result = extensions.handle(body)
                    completed = result.get('operation', {}).get('state') == 'completed'
                    from .workspace_extension_summary import latest
                    summary = latest(server.workspace.store, body['id'], body['revision']) if completed else None
                    if summary and summary['operation_id'] != result['operation'].get('result', {}).get('import_operation_id'):
                        summary = None
                    save(path, {**context, 'state': 'completed' if completed else 'failed',
                                'stage': 'pending_review' if completed else 'failed',
                                'result': result, 'summary': summary})
                except Exception:
                    save(path, {**context, 'state': 'failed', 'stage': 'failed',
                                'error': '외부 실행을 완료하지 못했습니다. 보존된 실행 기록을 확인하세요. 자동 재시도하지 않습니다.'})
                finally:
                    server.demo.lock.release()
            threading.Thread(target=run, daemon=True).start()
        return handler.send({'id': jid, 'state': 'queued', 'mode': body['mode']}, 202)
    server.start_job = start_job
    return server


def main(argv=None):
    """Operator-only startup. Config contains private paths, never browser input."""
    import fcntl
    from dotenv import dotenv_values
    from .auto_ontology_bridge import invoke, BridgeLimits
    from .workspace_database import SQLiteSources
    from .shared_extensions import SharedExtensions
    from .auto_ontology_semantic_cli import budget_config
    from .extension_gateway import Gateway
    from .extension_gateway_http import create_server, openrouter_transport

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    cfg = json.loads(args.config.read_text())
    directory = Path(cfg['data_dir']).resolve()
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    owner = (directory/'server.lock').open('a+')
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    deadline = datetime.fromisoformat(cfg['expires'])
    if deadline.tzinfo is None or not 0 < deadline.timestamp()-time.time() <= 31*86400:
        raise ValueError('Explicit future aware expiry required')
    access = AccessStore(directory/'access', config=AccessConfig(deadline),
                         pin=Path(cfg['pin_file']).read_text().strip())
    live = cfg.get('live_config')
    if live:
        if live.get('absolute_deadline') != cfg['expires'] or str(live.get('max_usd')) != '10':
            raise ValueError('Workspace ledger must bind fixed deadline and USD10 allocation')
        # Secrets remain in the parent process. Native children get only a fresh
        # dummy bearer and loopback reservation gateway via bridge.clean env.
        key = os.environ.get('OPENROUTER_API_KEY') or dotenv_values(Path(__file__).resolve().parents[2]/'.env').get('OPENROUTER_API_KEY')
        def gateway_factory(store, root, config, _):
            return PublicGateway(store, root, config, key)
        demo = Demo(directory/'runtime', live, gateway_factory=gateway_factory)
    else:
        demo = Demo(directory/'runtime')
        key = None
    server = make_server(demo, cfg['port'], workspace_model_proposals=bool(live),
        workspace_questions=bool(live), workspace_reasoner_binary=cfg.get('reasoner_binary'),
        workspace_database_registry=cfg.get('registry'), workspace_document_registry=cfg.get('document_registry'))
    server.workspace.store.recover_interrupted()
    extension = None
    budget_server = None
    gateway = None
    if cfg.get('upstream'):
        op = cfg['upstream']
        registry = SQLiteSources(Path(cfg['registry']))
        operator = json.loads(Path(op['postgres_config']).read_text())
        semantic_config = None
        if op.get('budget') and live:
            budget, limits = budget_config(json.loads(Path(op['budget']).read_text()))
            if budget.total_nanodollars != 10_000_000_000 or budget.deadline_epoch != deadline.timestamp():
                raise ValueError('Native ledger must bind fixed deadline and USD10 allocation')
            gateway = NoRetryGateway(directory/'native-campaign.sqlite', budget, key, openrouter_transport, description_language='ko')
            dummy = secrets.token_hex(32)
            budget_server = create_server(gateway, dummy)
            threading.Thread(target=budget_server.serve_forever, daemon=True).start()
            semantic_config = {'endpoint': f'http://127.0.0.1:{budget_server.server_port}/v1',
                               'token': dummy, 'chat_model': 'openai/auto-ontology-reasoning',
                               'embedding_model': 'openai/auto-ontology-embedding'}
        else:
            limits = BridgeLimits(timeout_seconds=600)
        def invocation(reg, source_id, *, output_root, mode):
            configured = dict(operator)
            if mode == 'semantic':
                if semantic_config is None:
                    raise ValueError('Paid native generation disabled')
                configured.update(gateway=semantic_config, request_id=output_root.parent.name,
                                  reservation_id=output_root.parent.name)
            def activity():
                with gateway._db() as db:
                    count = db.execute('SELECT count(*) FROM attempts').fetchone()[0]
                with sqlite3.connect(gateway.cache) as db:
                    hits = db.execute('SELECT coalesce(sum(hits),0) FROM requests').fetchone()[0]
                return count, hits
            before = activity() if mode == 'semantic' else None
            receipt = invoke(reg, source_id, output_root=output_root,
                          upstream_root=op['root'], python_executable=op['python'],
                          operator_config=configured, mode=mode, limits=limits)
            if mode == 'semantic':
                # Upstream may log internal model failures but return normally.
                # An export alone must never be labelled successful LLM work.
                logfile = output_root / receipt['invocation_id'] / 'stderr.log'
                log = logfile.read_text(errors='replace') if logfile.is_file() else ''
                failed = (gateway.ledger.with_suffix('.paid-stop.json').exists() or
                          'invoke_with_structured_output failed' in log or 'giving up after' in log)
                attempts, hits = activity()
                receipt['gateway_observation'] = {'new_provider_attempts': attempts-before[0],
                                                  'new_cache_hits': hits-before[1],
                                                  'internal_model_error_observed': failed,
                                                  'requested_description_language': 'ko'}
                if failed or not ((attempts-before[0]) or (hits-before[1])):
                    receipt['upstream_return_status'] = receipt['status']
                    receipt['status'] = 'failed'
                    receipt['failure_reason'] = 'Native model work failed or was not observed; export is not semantic success'
            return receipt
        extension = SharedExtensions(server.workspace, registry, invocation, directory/'native')
    operator_path = directory/'operator-test.key'
    if not operator_path.exists():
        fd = os.open(operator_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(secrets.token_hex(32))
    AccessStore._private(operator_path, is_directory=False)
    operator_secret = operator_path.read_text().strip()
    attach(server, access=access, origin_file=cfg['origin_file'], share_id=cfg['share_id'],
           extensions=extension, semantic_enabled=gateway is not None, operator_secret=operator_secret)
    if gateway:
        server.native_stop = gateway.ledger.with_suffix('.paid-stop.json')
        server.native_readiness = gateway.readiness
    def expire():
        server.shutdown()
    timer = threading.Timer(max(0, deadline.timestamp()-time.time()), expire)
    timer.daemon = True
    timer.start()
    print(json.dumps({'port': server.server_port, 'share_id': cfg['share_id'],
                      'mode': 'authenticated-workspace', 'live': bool(live), 'expires': cfg['expires']}), flush=True)
    try:
        server.serve_forever()
    finally:
        timer.cancel()
        server.server_close()
        if budget_server:
            budget_server.shutdown()
            budget_server.server_close()
        if gateway:
            gateway.close()
        owner.close()


if __name__ == '__main__':
    main()
