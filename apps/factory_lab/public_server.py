"""Local first-release entry point. Replay requires no credentials or network."""
import argparse
import fcntl
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .public_runtime import Demo, read
from .store import dumps

STATIC = Path(__file__).parent / 'public_static'
LEGACY_STATIC = Path(__file__).parent / 'static'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def send(self, value, status=200, mime='application/json; charset=utf-8'):
        raw = value if isinstance(value, bytes) else dumps(value).encode()
        self.send_response(status)
        for key, val in {'Content-Type': mime, 'Content-Length': str(len(raw)), 'Cache-Control': 'no-store',
                         'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
                         'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"}.items():
            self.send_header(key, val)
        self.end_headers()
        try: self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError): pass

    def local(self):
        return self.headers.get('Host') in (f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}')

    def do_GET(self):
        if not self.local(): return self.send({'error': 'Host rejected'}, 403)
        path = urlsplit(self.path).path
        demo = self.server.demo
        try:
            if path == '/api/commerce':
                from .commerce import catalog
                return self.send(catalog(self.server.commerce_data))
            if path == '/api/config': return self.send(demo.config() | {'csrf': self.server.token})
            if path == '/api/runs': return self.send(demo.store.runs())
            if path.startswith('/api/examples/'):
                return self.send(demo.replays[path.split('/')[-1]])
            if path.startswith('/api/runs/'):
                rid = path.split('/')[-1]
                return self.send({'run': demo.store.get(rid), 'events': demo.store.events(rid)})
            files = {'/marked.js': (STATIC/'vendor/marked.js', 'text/javascript'),
                     '/prepare': (STATIC/'prepare.html', 'text/html'),
                     '/workspace': (STATIC/'workspace.html', 'text/html'),
                     '/workspace.js': (STATIC/'workspace.js', 'text/javascript'),
                     '/review_inventory.js': (STATIC/'review_inventory.js', 'text/javascript'),
                     '/workspace.css': (STATIC/'workspace.css', 'text/css'),
                     '/prepare.js': (STATIC/'prepare.js', 'text/javascript'),
                     '/prepare.css': (STATIC/'prepare.css', 'text/css'),
                     '/purify.js': (STATIC/'vendor/purify.js', 'text/javascript'),
                     '/': (STATIC/'index.html', 'text/html'), '/app.js': (STATIC/'app.js', 'text/javascript'),
                     '/style.css': (LEGACY_STATIC/'style.css', 'text/css'), '/public.css': (STATIC/'public.css', 'text/css'),
                     '/cytoscape.js': (LEGACY_STATIC/'vendor/cytoscape-3.34.3.min.js', 'text/javascript')}
            if path in files:
                file, mime = files[path]
                return self.send(file.read_bytes(), mime=mime+'; charset=utf-8')
            return self.send({'error': 'Not found'}, 404)
        except (KeyError, ValueError): return self.send({'error': 'Unknown example or run'}, 404)
        except Exception: return self.send({'error': 'Local server error'}, 500)

    def do_POST(self):
        origins = (None, f'http://localhost:{self.server.server_port}', f'http://127.0.0.1:{self.server.server_port}')
        if not self.local() or self.headers.get('Origin') not in origins or not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), self.server.token):
            return self.send({'error': 'Origin/token rejected'}, 403)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            maximum = 32_000_000 if self.path in ('/api/preparation','/api/workspace') else 12000
            if not 0 < size <= maximum: raise ValueError('Body size')
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict): raise ValueError('Object required')
            # Progress reads and a narrow durable cancellation signal bypass the
            # execution lock. Both retain the same origin/token checks above.
            if self.path=='/api/workspace' and body.get('action') in ('progress','cancel'):
                try:return self.send(self.server.workspace.handle(body))
                except ValueError as exc:return self.send({'error':str(exc)[:1000]},400)
            if self.path in ('/api/preparation','/api/workspace'):
                if not self.server.demo.lock.acquire(blocking=False):
                    raise RuntimeError('One local execution is already active')
                try:
                    service = self.server.workspace if self.path=='/api/workspace' else self.server.preparation
                    try:
                        result, status = service.handle(body), 200
                    except ValueError as exc:
                        # Expected bounded validation errors; UI renders as text only.
                        result, status = {'error':str(exc)[:1000]}, 400
                    # Freeze response bytes while state is protected, then release
                    # before network I/O so a completed response cannot race cleanup.
                    raw = dumps(result).encode()
                finally:
                    self.server.demo.lock.release()
                return self.send(raw, status)
            if self.path == '/api/commerce':
                from .commerce import run_case
                if set(body) != {'case_id'} or not isinstance(body['case_id'], str):
                    raise ValueError('Commerce case required')
                if not self.server.demo.lock.acquire(blocking=False):
                    raise RuntimeError('One local execution is already active')
                try:
                    return self.send(run_case(body['case_id'], self.server.commerce_data))
                finally:
                    self.server.demo.lock.release()
            if self.path == '/api/diagnostics':
                from .diagnostics import run_case, historical_trace
                if set(body) != {'case_id'} or not isinstance(body['case_id'], str):
                    raise ValueError('Diagnostic case required')
                demo = self.server.demo
                if not demo.lock.acquire(blocking=False):
                    raise RuntimeError('One local execution is already active')
                try:
                    return self.send(historical_trace(body['case_id']) if body['case_id'].startswith('history-') else run_case(body['case_id']))
                finally:
                    demo.lock.release()
            if self.path == '/api/runs': return self.send({'id': self.server.demo.start(body)}, 202)
            if self.path.startswith('/api/runs/') and self.path.endswith('/cancel'):
                self.server.demo.cancel(self.path.split('/')[3])
                return self.send({'cancel_requested': True})
            return self.send({'error': 'Not found'}, 404)
        except (ValueError, KeyError, TypeError): return self.send({'error': 'Invalid input'}, 400)
        except RuntimeError as exc: return self.send({'error': str(exc)}, 409)
        except Exception: return self.send({'error': 'Local server error'}, 500)

    def do_OPTIONS(self): self.send({'error': 'Cross-origin access disabled'}, 403)


def make_server(demo, port=9261, commerce_data=None, workspace_model_proposals=False, workspace_questions=False,
                workspace_reasoner_binary=None, workspace_database_registry=None, workspace_document_registry=None):
    from .preparation_service import PreparationService
    from .workspace_service import WorkspaceService
    from .commerce import DEFAULT, load
    commerce_data = Path(commerce_data) if commerce_data else DEFAULT
    load(commerce_data)
    if workspace_model_proposals and demo.gateway is None:
        raise ValueError('Workspace model proposals require an explicit live config')
    if workspace_questions and demo.gateway is None:
        raise ValueError('Workspace questions require an explicit live config')
    reasoner = None
    database_registry = None
    if workspace_database_registry is not None:
        from .workspace_database import SQLiteSources
        registry_path = Path(workspace_database_registry).resolve(strict=True)
        if not registry_path.is_dir():
            raise ValueError('Configured database registry must be an existing directory')
        database_registry = SQLiteSources(registry_path)
    source_documents = None
    if workspace_document_registry is not None:
        from .workspace_source_documents import DocumentSources
        if database_registry is None:
            raise ValueError('Source documents require a configured database registry')
        document_path = Path(workspace_document_registry).resolve(strict=True)
        if not document_path.is_dir():
            raise ValueError('Configured document registry must be an existing directory')
        source_documents = DocumentSources(document_path, database_registry)
    if workspace_reasoner_binary is not None:
        from .workspace_reasoning import LocalReasoner
        binary = Path(workspace_reasoner_binary).resolve(strict=True)
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError('Configured local reasoner must be executable')
        reasoner = LocalReasoner(binary)
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.commerce_data = commerce_data
    server.demo = demo
    server.preparation = PreparationService()
    server.workspace = WorkspaceService(demo.directory/'workspaces.sqlite',
                                        proposal_gateway=demo.gateway if workspace_model_proposals else None,
                                        question_gateway=demo.gateway if workspace_questions else None,
                                        local_reasoner=reasoner,
                                        database_registry=database_registry, source_documents=source_documents)
    server.token = secrets.token_hex(32)
    return server


def main():
    p = argparse.ArgumentParser(description='Factory Lab: saved examples by default; explicit BYOK for live execution')
    p.add_argument('--port', type=int, default=9261)
    p.add_argument('--data-dir', type=Path, default=Path('_workspace/factory-lab-public'))
    p.add_argument('--live-config', type=Path, help='Explicitly enable paid BYOK calls; see examples/factory_lab/live-config.example.json')
    p.add_argument('--commerce-data', type=Path, help='Local shop schema v1 JSON; see docs/setup/commerce-data.md')
    p.add_argument('--workspace-model-proposals', action='store_true',
                   help='Opt in to user-triggered workspace model proposals under the live-config shared budget')
    p.add_argument('--workspace-questions',action='store_true',
                   help='Opt in to two-call workspace question episodes using the shared live-config budget')
    p.add_argument('--workspace-reasoner-binary', type=Path,
                   help='Opt in to a trusted local OpenOntologies executable; uploaded RDF only, no paid API')
    p.add_argument('--workspace-database-registry', type=Path,
                   help='Opt in to an existing operator-managed SQLite snapshot registry; browser paths are not accepted')
    p.add_argument('--workspace-document-registry', type=Path,
                   help='Optional private registry of hash-bound source text documents')
    args = p.parse_args()
    os.umask(0o077)
    args.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (args.data_dir/'server.lock').open('a+')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: p.error('A server already owns this data directory')
    try:
        demo = Demo(args.data_dir, read(args.live_config) if args.live_config else None)
        server = make_server(demo, args.port, args.commerce_data,args.workspace_model_proposals,args.workspace_questions,
                             workspace_reasoner_binary=args.workspace_reasoner_binary,
                             workspace_database_registry=args.workspace_database_registry,
                             workspace_document_registry=args.workspace_document_registry)
        server.workspace.store.recover_interrupted()
    except (ValueError, OSError) as exc: p.error(str(exc))
    print(f'Factory Lab: http://localhost:{server.server_port}/ | '+('LIVE BYOK enabled' if demo.gateway else 'Saved examples only; no API calls'), flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        demo.cancel_event.set()
        if demo.worker: demo.worker.join(timeout=90)
        server.server_close()
        lock.close()


if __name__ == '__main__': main()
