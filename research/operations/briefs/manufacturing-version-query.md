# Version-scoped manufacturing model queries

Status: design, unexecuted. Source: unchanged frozen MachineTool projection snapshots, previously inspected development data. No fresh heldout, no new physical operating facts. Existing workbooks remain main field/evidence illustration; actual manufacturing schema releases add version context.

Question: can saved old/new definitions coexist and can each adapter answer the same explicitly version-bound query after both releases are loaded? This extends prior seven-node backend parity; it does not establish engine superiority, ontology necessity or maintenance labor benefit.

Representation: version locator = original XML SHA256. Defined-node key = (source hash, namespace URI, numeric NodeId). Snapshot metadata records ModelUri, Version, PublicationDate and any ModelVersion separately. All assertions retain source snapshot. Defined nodes and unresolved reference targets must be distinct; a mentioned target is not a locally defined node. No reverse-reference completion or semantic inheritance performed: reference queries ask only explicitly serialized source relations. Existing parser excludes values/descriptions and full imported models. URI-only or display-Version-only maps are diagnostic alternatives, not endorsed standard identity rules.

Planned queries for each of two releases: (1) browse label for i5025; (2) declared parent for i5025; (3) explicit outgoing stored reference facts for i5025; (4) definitions of targets referenced from i5025, returning defined-in-selected-file vs not-defined-in-selected-file, never global missing; (5) SignalColor alias resolved namespace URI/numeric ID; (6) required IA model metadata exactly as declared, no dependency compatibility judgment. Two versions × six questions = twelve fixed contracts per adapter. Version constraints explicit in every query. No natural-language parsing claim.

All adapters get identical projected facts and contracts. First Python direct lookup vs SQLite/RDFLib with independently serialized output checks; actual Neo4j/Neptune only after review, bounded operation receipts and owned stop guard. Current resources remain stopped. No new infrastructure or paid LLM calls.

Failure denominator: record every source input, planned adapter/question and invalid-input control; if a source fails, its dependent questions fail and independent questions remain eligible. Never silently repair source/answers from expected results. Posthoc scorer reads retained rawXML locators and source hashes to verify declared fields, does not feed answers into runtime. Existing results untouched.

Controls: same numericID under different namespaces; missing requested source hash; existing reference target with no definition in selected file; a valid wrong version request produces that version's answer and is scored as a question-interpretation error only when a separately declared question contract demands another version. Never let a checker infer intended version from gold. Distinguish declared source version, selected evidence version and external truth.

Scope limit: exact file hashes here are reproducibility anchors, not OPC UA RequiredModels minimum-version compatibility rules. No safety/control recommendations. No automatic veto/repair. Record actual outputs/checks and omissions before any claims.

Implementation phase is OFFLINE ONLY SQL/RDFLib24slots. DirectPython/rawXMLscorer separate posthoc pending; actualDB notauthorizedbythisjob and remainsstopped. Runtimeimports historical transport helpers; fullimportedsource omitted, independentlyunverifiedinthispacket. Storedreferences represented asJSONliteral then explicit targetlookup, not native traversalperformance comparison. No assertions about fullOPCUAsemantics. Sourcefailure24slotcontrol coversonegoodonebad; filesystemfailures may preventdurablewrite andarenotguaranteedretained. Knownfixedsnapshots inspected; provenance rawXMLhash willbeposthocverified. No paidcalls.
```python
"""Version-scoped queries over frozen partial source projections; no inference."""
import json, importlib.util
from pathlib import Path

def load_module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
transport=load_module('research/manufacturing-answer-trace-1/manufacturing-v2-20261107-001/runtime.py','transport')
uri,field,val=transport.uri,transport.field,transport.val
MT='http://opcfoundation.org/UA/MachineTool/'
IA='http://opcfoundation.org/UA/IA/'

def key(namespace,number):return json.dumps([namespace,'i='+str(number)],separators=(',',':'))
def subject(sha,k):return uri('version-node:'+sha+':'+k)
def snapshot(sha):return uri('snapshot:'+sha)

def triples(data):
 sha=data['sha256'];out=set();s=snapshot(sha)
 out.add((s,field('source_hash'),val(sha)))
 for model in data['models']:
  out.add((s,field('model_metadata'),val(model['attributes'])))
  for required in model['required']:out.add((s,field('required_model'),val(required)))
 for alias,target in data['aliases'].items():out.add((s,field('alias:'+alias),val(target)))
 for k,n in data['nodes'].items():
  nuri=subject(sha,k)
  out.update([(nuri,field('snapshot'),s),(nuri,field('defined_key'),val(k)),(nuri,field('browse'),val(n['browse']))])
  if n['parent'] is not None:out.add((nuri,field('parent'),val(n['parent'])))
  for typ,forward,target in n['references']:
   # A serialized reference occurrence represented as a complete JSON value;
   # source selection is by version-qualified subject, not inferred edge closure.
   out.add((nuri,field('stored_reference'),val([typ,forward,target])))
 return sorted(out)

def decode(x):return json.loads(str(transport.from_n3(x)))

def query(store,sha,kind,namespace=MT,number=5025):
 anchor=subject(sha,key(namespace,number));snap=snapshot(sha);calls=[]
 def execute(patterns,project):
  result=store.query(patterns,project);calls.append({'patterns':patterns,'project':project,'rows':len(result)});return result
 if not execute([[snap,field('source_hash'),'?hash']],['?hash']):
  return {'status':'snapshot_not_loaded','values':[],'calls':calls}
 if kind=='alias':
  values=[decode(r['?value']) for r in execute([[snap,field('alias:SignalColor'),'?value']],['?value'])]
 elif kind=='required_ia':
  values=[decode(r['?value']) for r in execute([[snap,field('required_model'),'?value']],['?value'])]
  values=[v for v in values if v.get('ModelUri')==IA]
 else:
  if not execute([[anchor,field('defined_key'),'?key']],['?key']):
   return {'status':'node_not_defined_in_selected_file','values':[],'calls':calls}
  if kind in ('browse','parent','references','target_definitions'):
   f={'browse':'browse','parent':'parent','references':'stored_reference','target_definitions':'stored_reference'}[kind]
   values=[decode(r['?value']) for r in execute([[anchor,field(f),'?value']],['?value'])]
  else:raise ValueError('unsupported_question_kind')
  if kind=='target_definitions':
   targets=sorted({v[2] for v in values})
   if len(targets)>50:raise ValueError('bounded_target_limit')
   result=[]
   for target in targets:
    found=execute([[subject(sha,target),field('browse'),'?browse']],['?browse'])
    result.append({'target':target,'status':'defined_in_selected_file' if found else 'not_defined_in_selected_file','browse':[decode(r['?browse']) for r in found]})
   values=result
 return {'status':'completed','values':sorted(values,key=transport.canonical),'calls':calls}

KINDS=('browse','parent','references','target_definitions','alias','required_ia')
def run(paths,out):
 out=Path(out)
 if out.exists():raise ValueError('output_directory_already_exists')
 out.mkdir(parents=True);sources=[];datasets=[];alltriples=[]
 for i,path in enumerate(paths):
  try:
   data=json.loads(Path(path).read_text());facts=triples(data)
   sources.append({'index':i,'path':str(path),'status':'completed','sha256':data['sha256'],'triples':len(facts)})
   datasets.append(data);alltriples.extend(facts)
  except Exception as e:
   sources.append({'index':i,'path':str(path),'status':'source_failed','error':type(e).__name__+': '+str(e)});datasets.append(None)
 (out/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
 plan=[{'backend':name,'source_index':i,'question':kind} for name in ('sqlite_python','rdflib_offline') for i in range(len(paths)) for kind in KINDS]
 (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');rows=[];cleanups=[]
 for Store in (transport.SQLStore,transport.RDFStore):
  store=None;load_error=None
  try:
   store=Store();store.load(sorted(set(alltriples)))
  except Exception as e:load_error=type(e).__name__+': '+str(e)
  try:
   for p in [p for p in plan if p['backend']==Store.name]:
    data=datasets[p['source_index']];row=dict(p)
    try:
     if data is None:row.update(status='source_failed',values=[])
     elif load_error:row.update(status='backend_load_failed',error=load_error,values=[])
     else:row.update(query(store,data['sha256'],p['question']))
    except Exception as e:row.update(status='query_failed',error=type(e).__name__+': '+str(e),values=[])
    rows.append(row)
    with (out/'rows.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
  finally:
   try:
    if store is not None:store.cleanup()
    cleanups.append({'backend':Store.name,'status':'completed'})
   except Exception as e:cleanups.append({'backend':Store.name,'status':'cleanup_failed','error':str(e)})
 (out/'cleanup.json').write_text(json.dumps(cleanups,indent=2)+'\n')
 summary={'planned':len(plan),'emitted':len(rows),'statuses':{s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})},'scope':'Frozen partial projections coexisting, explicit serialized references, no inference/QA/compatibility/performance claim'}
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary

if __name__=='__main__':
 import sys
 print(run(sys.argv[1:3],sys.argv[3]))

```
## Plannedchecks
```python
import tempfile,json
from pathlib import Path
import runtime as r

def fixture():
 k=r.key(r.MT,5025);ext=r.key(r.IA,3004)
 return {'sha256':'a'*64,'models':[],'aliases':{'SignalColor':ext},'nodes':{k:{'browse':[r.MT,'old'],'parent':None,'references':[[r.key(r.transport.BASE,1),True,ext]]}}}
for Store in (r.transport.SQLStore,r.transport.RDFStore):
 a=fixture();b=fixture();b['sha256']='b'*64;b['nodes'][r.key(r.MT,5025)]['browse']=[r.MT,'new']
 s=Store();s.load(r.triples(a)+r.triples(b))
 assert r.query(s,a['sha256'],'browse')['values']==[[r.MT,'old']]
 assert r.query(s,b['sha256'],'browse')['values']==[[r.MT,'new']]
 assert r.query(s,'missing','browse')['status']=='snapshot_not_loaded'
 assert r.query(s,a['sha256'],'browse',r.IA,5025)['status']=='node_not_defined_in_selected_file'
 target=r.query(s,a['sha256'],'target_definitions')['values'][0]
 assert target['status']=='not_defined_in_selected_file' and target['browse']==[]
 s.cleanup()
with tempfile.TemporaryDirectory(dir='_workspace/manufacturing-continuation-20261107') as tmp:
 p=Path(tmp);(p/'good.json').write_text(json.dumps(fixture()));(p/'bad.json').write_text('{broken')
 summary=r.run([p/'good.json',p/'bad.json'],p/'out')
 assert summary['planned']==summary['emitted']==24 and summary['statuses']=={'completed':12,'source_failed':12}
print('two backends x five semantic controls; one-source failure preserves24planned/12failed')

```