"""Loopback-only chat API and SSE event stream. No public deployment."""
import argparse
import fcntl
import json
import secrets
import time
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .store import Store,WORK,dumps
from .agent import Runner
from .graph import snapshot,Graph

STATIC=Path(__file__).parent/'static'

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def headers_common(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
    def json(self,obj,code=200):
        raw=dumps(obj).encode();self.send_response(code);self.headers_common()
        self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def local(self):
        return self.headers.get('Host') in (f'localhost:{self.server.server_port}',f'127.0.0.1:{self.server.server_port}')
    def do_GET(self):
        if not self.local():return self.json({'error':'Host rejected'},403)
        u=urlsplit(self.path);path=u.path
        try:
            if path=='/api/config':
                session=json.loads((WORK/'session.json').read_text())
                model=json.loads((WORK/'model.json').read_text()) if (WORK/'model.json').exists() else {}
                return self.json({'csrf':self.server.token,'snapshots':['factory-v1','factory-v2','factory-v3'],'graph_backend':getattr(self.server.runner.graph,'name','neo4j_cypher'),
                    'model':model.get('model'),'provider':model.get('provider'),'deadline':session['deadline'],
                    'paid_enabled':(WORK/'execution-gate.json').exists() and datetime.now(timezone.utc)<datetime.fromisoformat(session['deadline']),
                    'cap_usd':session['max_usd'],'budget':self.server.store.budget()})
            if path=='/api/runs':return self.json(self.server.store.runs())
            if path=='/api/graph':
                version=parse_qs(u.query).get('snapshot',['factory-v2'])[0];d,sha=snapshot(version)
                return self.json({'source':'authored snapshot file, not a live DB query','sha256':sha,**d})
            if path.startswith('/api/runs/'):
                parts=path.strip('/').split('/');rid=parts[2];self.server.store.get(rid)
                if len(parts)==4 and parts[3]=='events':
                    after=int(self.headers.get('Last-Event-ID') or parse_qs(u.query).get('after',['0'])[0])
                    self.send_response(200);self.headers_common();self.send_header('Content-Type','text/event-stream; charset=utf-8');self.end_headers()
                    until=time.monotonic()+25
                    while time.monotonic()<until:
                        events=self.server.store.events(rid,after)
                        for e in events:
                            self.wfile.write(('id: '+str(e['seq'])+'\ndata: '+dumps(e)+'\n\n').encode());after=e['seq']
                        self.wfile.write(b': heartbeat\n\n');self.wfile.flush()
                        if self.server.store.get(rid)['status'] not in ('queued','running'):return
                        time.sleep(.3)
                    return
                if len(parts)==3:return self.json({'run':self.server.store.get(rid),'events':self.server.store.events(rid)})
            files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/vendor/cytoscape-3.34.3.min.js':'vendor/cytoscape-3.34.3.min.js'}
            if path in files:
                f=STATIC/files[path];raw=f.read_bytes();self.send_response(200);self.headers_common()
                self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[f.suffix[1:]])
                self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
            self.json({'error':'Not found'},404)
        except (BrokenPipeError,ConnectionResetError):pass
        except (KeyError,ValueError):self.json({'error':'Invalid request or unknown run'},400)
        except Exception:self.json({'error':'Server error; inspect local logs'},500)
    def do_POST(self):
        origin=self.headers.get('Origin')
        if not self.local() or origin not in (None,f'http://localhost:{self.server.server_port}',f'http://127.0.0.1:{self.server.server_port}') or not secrets.compare_digest(self.headers.get('X-CSRF-Token',''),self.server.token):
            return self.json({'error':'Request origin/token rejected'},403)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=12000:raise ValueError('Body size')
            body=json.loads(self.rfile.read(size))
            if self.path=='/api/runs':
                session=json.loads((WORK/'session.json').read_text())
                if datetime.now(timezone.utc)>=datetime.fromisoformat(session['deadline']):return self.json({'error':'이번 유료 실행 시간이 종료됐습니다. 저장된 기록은 계속 볼 수 있습니다.'},409)
                if not (WORK/'execution-gate.json').exists():return self.json({'error':'실행 전 검토가 아직 완료되지 않았습니다.'},409)
                return self.json({'id':self.server.runner.start(body)},202)
            if self.path.startswith('/api/runs/') and self.path.endswith('/cancel'):
                rid=self.path.split('/')[3];self.server.runner.cancel(rid);return self.json({'cancel_requested':True})
            self.json({'error':'Not found'},404)
        except (ValueError,KeyError,TypeError):self.json({'error':'Invalid input'},400)
        except RuntimeError as e:self.json({'error':str(e)},409)
    def do_OPTIONS(self):self.json({'error':'Cross-origin access disabled'},403)

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=9260);p.add_argument('--import-snapshots',action='store_true');p.add_argument('--graph-backend',choices=['neo4j','rdflib','neptune'],default='neo4j');p.add_argument('--neptune-authorization',type=Path);a=p.parse_args()
    if a.graph_backend=='neo4j':graph=Graph()
    elif a.graph_backend=='rdflib':
        from .rdf_graph import RDFLibGraph
        graph=RDFLibGraph()
    else:
        from .rdf_graph import NeptuneGraph
        if a.neptune_authorization is None:p.error('--neptune-authorization is required')
        graph=NeptuneGraph(a.neptune_authorization)
    if a.import_snapshots:
        if a.graph_backend=='rdflib':p.error('RDFLib uses isolated in-memory graphs')
        print(dumps([graph.load(v) for v in ('factory-v1','factory-v2','factory-v3')]));return
    WORK.mkdir(parents=True,exist_ok=True)
    process_lock=(WORK/'server.lock').open('a')
    fcntl.flock(process_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    store=Store();store.recover()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);server.daemon_threads=True
    server.store=store;server.runner=Runner(store,graph=graph);server.token=secrets.token_hex(32)
    print(f'Factory Lab on http://127.0.0.1:{a.port}',flush=True)
    server.serve_forever()

if __name__=='__main__':main()
