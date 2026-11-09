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
