# Live partial manufacturing hierarchy v3
User authorized8hresearch15:12:55–23:12:55UTC and existingDB use. Priorv2blocked on prestartupdenominator and terminalcleanup; retained. Fixedstart17:05–17:15,readiness17:25,datarequestcutoff17:33,cleanupcutoff17:35,stopguardinitiation17:35,terminaltarget18:00UTC. Terminaltarget isnotguaranteed by asynchronousAWS: boundedpolling records unresolved and guard retries onfailure; no falsecompletion. No paidcalls/newAWSinfra/downloads. Same2publishedObjectType projections,62classes150modelobjects each,248dependentquestions×4adapters992slots; n10s124membershipsupported124ancestorunsupportedselectedadapteronly. No externaldefinitions/fullOPC/QA/performance/RDFsuperiority. Sourcehierarchyhelper/config/rawXML omitted previouslyreviewed butunverifiedbythisreview.

```python
"""Selected published hierarchy live adapters. No gold or LLM calls."""
import json,hashlib,datetime as dt,urllib.request
from pathlib import Path
from rdflib import RDF,RDFS,OWL,Graph,URIRef
from owlrl import DeductiveClosure,OWLRL_Semantics
import hierarchy as h
import transport as t
ARMS=('neo4j_cypher_paths','n10s_category','neptune_sparql_paths','neptune_external_owlrl')

def triples(p,materialized):
 g=Graph()
 for a,b in p['edges']:g.add((h.u(a),RDFS.subClassOf,h.u(b)))
 for a,b in p['types']:g.add((h.u(a),RDF.type,h.u(b)))
 if materialized:
  for c in p['allclasses']:g.add((h.u(c),RDF.type,OWL.Class))
  DeductiveClosure(OWLRL_Semantics,axiomatic_triples=False,datatype_axioms=False).expand(g)
 return sorted({(h.u(a).n3(),RDFS.subClassOf.n3(),h.u(b).n3()) for a in p['allclasses'] for b in p['allclasses'] if a!=b and (h.u(a),RDFS.subClassOf,h.u(b)) in g}|{(h.u(o).n3(),RDF.type.n3(),h.u(c).n3()) for o in p['objects'] for c in p['allclasses'] if (h.u(o),RDF.type,h.u(c)) in g})

class Neo:
 def __init__(self,namespace):self.namespace=namespace;self.owned=False
 def request(self,q,params=None,cleanup=False):
  if dt.datetime.now(dt.timezone.utc)>=t.CUTOFF-dt.timedelta(seconds=0 if cleanup else 120):raise RuntimeError('cutoff')
  data=json.dumps({'statements':[{'statement':q,'parameters':{'run':self.namespace,**(params or {})}}]}).encode()
  req=urllib.request.Request('http://127.0.0.1:7475/db/neo4j/tx/commit',data,{'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=30) as r:b=json.load(r)
  if b.get('errors'):raise RuntimeError(json.dumps(b['errors']))
  r=b['results'][0];return [dict(zip(r['columns'],x['row'],strict=True)) for x in r['data']]
 def load(self,p):
  if self.request('MATCH(n:SubtypeOwned {run:$run}) RETURN count(n) AS n')[0]['n']:raise ValueError('nonempty_namespace')
  self.owned=True
  self.request('UNWIND $ids AS id CREATE(:SubtypeOwned:SubtypeClass {run:$run,id:id})',{'ids':sorted(p['allclasses'])})
  self.request('UNWIND $ids AS id CREATE(:SubtypeOwned:SubtypeObject {run:$run,id:id})',{'ids':sorted(p['objects'])})
  self.request('UNWIND $edges AS e MATCH(a:SubtypeClass {run:$run,id:e[0]}),(b:SubtypeClass {run:$run,id:e[1]}) CREATE(a)-[:SUBTYPE]->(b)',{'edges':sorted(p['edges'])})
  self.request('UNWIND $edges AS e MATCH(a:SubtypeObject {run:$run,id:e[0]}),(b:SubtypeClass {run:$run,id:e[1]}) CREATE(a)-[:TYPEOF]->(b)',{'edges':sorted(p['types'])})
 def query(self,q,n10s=False):
  if n10s:
   if q['kind']!='model_object_members':raise NotImplementedError('ancestor_not_in_selected_n10s_adapter')
   statement='MATCH(c:SubtypeClass {run:$run,id:$target}) CALL n10s.inference.nodesInCategory(c,{inCatRel:"TYPEOF",subCatRel:"SUBTYPE"}) YIELD node WHERE node:SubtypeObject AND node.run=$run RETURN DISTINCT node.id AS id'
  elif q['kind']=='ancestors':statement='MATCH(s:SubtypeClass {run:$run,id:$target})-[:SUBTYPE*1..]->(n:SubtypeClass) WHERE n.run=$run AND n.id<>$target RETURN DISTINCT n.id AS id'
  else:statement='MATCH(n:SubtypeObject {run:$run})-[:TYPEOF]->(:SubtypeClass)-[:SUBTYPE*0..]->(c:SubtypeClass {run:$run,id:$target}) RETURN DISTINCT n.id AS id'
  return sorted(r['id'] for r in self.request(statement,{'target':q['target']}))
 def cleanup(self):
  if not self.owned:return {'not_owned':True}
  self.request('MATCH(n:SubtypeOwned {run:$run}) DETACH DELETE n',cleanup=True)
  return {'remaining':self.request('MATCH(n:SubtypeOwned {run:$run}) RETURN count(n) AS n',cleanup=True)[0]['n']}

def sparql(store,q,p,materialized=False):
 target=h.u(q['target']).n3();sc=RDFS.subClassOf.n3();typ=RDF.type.n3()
 if q['kind']=='ancestors':pattern=target+' '+sc+('' if materialized else '+')+' ?x'
 else:pattern='?x '+typ+('' if materialized else '/'+sc+'*')+' '+target
 query='SELECT DISTINCT ?x WHERE {GRAPH '+store.graph+' {'+pattern+'}}'
 result=store.request(query);decode={str(h.u(k)):k for k in p['allclasses']|p['objects']}
 return sorted({decode[r['x']['value']] for r in result['results']['bindings'] if r['x']['type']=='uri'})

def prepare(config,out):
 cfg=json.loads(Path(config).read_text());out=Path(out);out.mkdir(parents=True,exist_ok=False)
 if len(cfg['sources'])!=2 or len(cfg['questions'])!=248:raise ValueError('scope_count')
 if len({(q['source_index'],q['kind'],q['target']) for q in cfg['questions']})!=248 or any(q['source_index'] not in (0,1) for q in cfg['questions']):raise ValueError('scope_identity')
 plan=[{**q,'arm':a} for q in cfg['questions'] for a in ARMS];(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');return cfg,plan

def run(config,out,prepared=False):
 out=Path(out)
 if prepared:
  cfg=json.loads(Path(config).read_text());plan=json.loads((out/'plan.json').read_text())
  if plan!=[{**q,'arm':a} for q in cfg['questions'] for a in ARMS] or (out/'rows.jsonl').exists():raise ValueError('prepared_plan_changed_or_rows_exist')
 else:cfg,plan=prepare(config,out)
 rows=[];clean=[];metadata=[];fatal=None
 def emit(row):
  rows.append(row)
  with (out/'rows.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
 try:
  for i,s in enumerate(cfg['sources']):
   raw=Path(s['path']).read_bytes()
   if hashlib.sha256(raw).hexdigest()!=s['projection_sha256']:raise ValueError('projection_hash_mismatch')
   d=json.loads(raw)
   if d['sha256']!=s['original_xml_sha256']:raise ValueError('original_hash_metadata_mismatch')
   p=h.project(d);expected={(i,k,c) for c in p['defined_classes'] for k in ('ancestors','model_object_members')}
   if {(q['source_index'],q['kind'],q['target']) for q in cfg['questions'] if q['source_index']==i}!=expected:raise ValueError('target_matrix')
   namespace='backend-subtype-real-20261107-v'+str(i);neo=Neo(namespace);rawdb=None;closuredb=None;loaderror=None
   try:
    try:
     neo.load(p);rawdb=t.NeptuneStore(namespace+'-raw');rawdb.load(triples(p,False));closuredb=t.NeptuneStore(namespace+'-closure');closuredb.load(triples(p,True))
     metadata.append({'source_index':i,'raw_triples':len(triples(p,False)),'materialized_selected_triples':len(triples(p,True))})
    except Exception as e:loaderror=type(e).__name__+': '+str(e)
    for item in [q for q in plan if q['source_index']==i]:
     row=dict(item)
     try:
      if item['arm']=='n10s_category' and item['kind']=='ancestors':row.update(status='unsupported_selected_adapter',values=[])
      else:
       if loaderror:raise RuntimeError(loaderror)
       a=item['arm'];values=neo.query(item,a=='n10s_category') if a.startswith(('neo4j','n10s')) else sparql(closuredb if a=='neptune_external_owlrl' else rawdb,item,p,a=='neptune_external_owlrl')
       row.update(status='completed',values=values)
     except Exception as e:row.update(status='load_dependency_failed' if loaderror else 'query_failed',error=type(e).__name__+': '+str(e),values=[])
     emit(row)
   finally:
    cleanup_bad=False
    for name,store in [('neo4j',neo),('neptune_raw',rawdb),('neptune_closure',closuredb)]:
     if store is None:continue
     try:
      receipt=store.cleanup()
      if store.owned and receipt.get('remaining') not in (0,False):raise RuntimeError('not_empty')
      clean.append({'source_index':i,'store':name,'status':'completed','receipt':receipt})
     except Exception as e:clean.append({'source_index':i,'store':name,'status':'failed','error':str(e)});cleanup_bad=True
     (out/'cleanup.json').write_text(json.dumps(clean,indent=2)+'\n')
    if cleanup_bad:raise RuntimeError('stop_after_unresolved_cleanup')
 except Exception as e:fatal=type(e).__name__+': '+str(e)
 finally:
  identity=lambda q:(q['source_index'],q['kind'],q['target'],q['arm']);done={identity(r) for r in rows}
  for item in plan:
   if identity(item) not in done:emit({**item,'status':'not_run_after_failure','error':fatal,'values':[]})
  summary={'planned':len(plan),'emitted':len(rows),'statuses':{s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})},'fatal':fatal,'metadata':metadata,'limits':['Selected partial published hierarchy; external definitions absent','n10s unsupported rows refer only to this adapter, not general product capability','No engine performance, QA, full OPC or RDF superiority claim']}
  (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 return summary
if __name__=='__main__':
 import sys
 print(run(sys.argv[1],sys.argv[2]))

```
## Neptune transport excerpt
```python
class NeptuneStore:
    name = 'neptune_sparql'
    def __init__(self, namespace):
        if not re.fullmatch(r'backend-[a-z0-9-]{1,60}',namespace):
            raise ValueError('owned namespace required')
        import boto3
        self.session=boto3.Session(region_name='ap-northeast-2')
        account=self.session.client('sts').get_caller_identity()['Account']
        if account != '985658740608': raise ValueError('wrong account')
        self.graph=uri('graph:'+namespace)
        self.owned=False
    def request(self, query, update=False, cleanup=False):
        if dt.datetime.now(dt.timezone.utc) >= CUTOFF-dt.timedelta(seconds=0 if cleanup else 120):
            raise RuntimeError('Neptune operational cutoff; no extension')
        from botocore.awsrequest import AWSRequest
        from botocore.auth import SigV4Auth
        from urllib.parse import urlencode
        body=urlencode({'update' if update else 'query':query}).encode()
        request=AWSRequest(method='POST',url=ENDPOINT,data=body,headers={'Content-Type':'application/x-www-form-urlencoded','Accept':'application/sparql-results+json'})
        SigV4Auth(self.session.get_credentials().get_frozen_credentials(),'neptune-db','ap-northeast-2').add_auth(request)
        req=urllib.request.Request(ENDPOINT,body,dict(request.headers))
        with urllib.request.urlopen(req,timeout=30) as response:
            raw=response.read()
        return json.loads(raw) if raw else {}
    def load(self, triples):
        if self.request(f'ASK {{GRAPH {self.graph} {{?s ?p ?o}}}}')['boolean']:
            raise ValueError('nonempty graph')
        self.owned=True
        data=' .\n'.join(' '.join(t) for t in triples)+' .'
        self.request(f'INSERT DATA {{GRAPH {self.graph} {{{data}}}}}',update=True)
    def cleanup(self):
        if not self.owned: return {'namespace_not_owned':True}
        self.request(f'CLEAR GRAPH {self.graph}',update=True,cleanup=True)
        return {'remaining':self.request(f'ASK {{GRAPH {self.graph} {{?s ?p ?o}}}}',cleanup=True)['boolean']}

```
Helper URI uses urn:shacl-study:backend: plus percentencodedkey; CUTOFF17:35; endpointfixedexistingSeoulNeptune. NormalHTTPtimeout30, STSdefaultSDK. Sourceproject/OWL-RL helper omitted.
