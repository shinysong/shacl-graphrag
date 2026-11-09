from pathlib import Path
import json,subprocess,time,uuid,sys
sys.path.insert(0,str(Path.cwd()))
from scripts.graphrag_neo4j import Neo4jSource
b=Path('_workspace/rag-backends-continuation-20261102');name='rag-source-'+uuid.uuid4().hex[:12];cid=None;receipt={'name':name,'commands':[]}
def run(cmd,timeout=30):
 try:r=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
 except Exception as exc:r=subprocess.CompletedProcess(cmd,124 if isinstance(exc,subprocess.TimeoutExpired) else 125,'',f'{type(exc).__name__}: {exc}')
 receipt['commands'].append({'argv':cmd,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});return r
try:
 image='sha256:f1e52d4dc6da122468c4a3c1050a4f5e117f6d3268625237c34d49166f0d6082'
 cmd=['docker','run','-d','--pull','never','--name',name,'--label','research-owner='+name,'--cpus','2','--memory','2g','--memory-swap','2g','-p','127.0.0.1:17474:7474','-e','NEO4J_AUTH=none','-e','NEO4J_server_memory_heap_initial__size=512m','-e','NEO4J_server_memory_heap_max__size=512m','-e','NEO4J_server_memory_pagecache_size=256m',image]
 r=run(cmd);cid=r.stdout.strip() if r.returncode==0 else None
 if r.returncode:raise RuntimeError('docker start failed')
 run(['docker','inspect',cid]);db=Neo4jSource('http://127.0.0.1:17474',name);deadline=time.monotonic()+90
 while True:
  try:db.query('RETURN 1 AS ready');break
  except Exception:
   if time.monotonic()>deadline:raise TimeoutError('startup deadline')
   time.sleep(2)
 cmd=['timeout','--kill-after=5s','120s','uv','run','--locked','--offline','python','-m','scripts.check_graphrag_neo4j','--manifest',str(b/'neo4j-manifest.json'),'--output','research/refined-hybrid-1/neo4j-source-001','--endpoint','http://127.0.0.1:17474','--namespace',name]
 receipt['runner_exit']=run(cmd,timeout=135).returncode
finally:
 if cid:
  run(['docker','logs',cid]);receipt['cleanup_exit']=run(['docker','rm','-fv',cid]).returncode
  proof=run(['docker','ps','-aq','--filter','id='+cid]);receipt['removed']=proof.returncode==0 and not proof.stdout.strip()
 else:
  # A failed docker start may leave an owned stopped container. Remove only if label matches.
  probe=run(['docker','inspect','--format','{{index .Config.Labels "research-owner"}}',name])
  if probe.returncode==0 and probe.stdout.strip()==name:
   receipt['cleanup_exit']=run(['docker','rm','-fv',name]).returncode
   proof=run(['docker','ps','-aq','--filter','name=^/'+name+'$']);receipt['removed']=proof.returncode==0 and not proof.stdout.strip()
 (b/'neo4j-execution.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'runner_exit':receipt.get('runner_exit'),'removed':receipt.get('removed')}))
