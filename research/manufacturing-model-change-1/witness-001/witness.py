"""Posthoc selected-source witnesses, not answer repair or full dependencies."""
import json,hashlib
from pathlib import Path
from collections import deque,defaultdict

def index(d):
 base='http://opcfoundation.org/UA/';key=lambda n:json.dumps([base,'i='+str(n)],separators=(',',':'))
 nodes=d['nodes'];classes={k for k,v in nodes.items() if v['class']=='UAObjectType'};objects={k for k,v in nodes.items() if v['class']=='UAObject'};edges=defaultdict(list)
 for k in sorted(classes|objects):
  for i,(kind,forward,target) in enumerate(nodes[k]['references']):
   if k in classes and kind==key(45):
    a,b=(target,k) if forward else (k,target);rel='subtype'
   elif k in objects and kind==key(40) and forward:a,b,rel=k,target,'type'
   else:continue
   edges[a].append({'subject':a,'relation':rel,'object':b,'projected_node':k,'projected_reference_index':i,'stored_reference':[kind,forward,target]})
 for k in edges:edges[k].sort(key=lambda r:json.dumps(r,sort_keys=True))
 return classes,objects,edges

def path(edges,start,end,kind):
 # Membership requires exactly one initial type edge; ancestry only subtype edges.
 pending=deque([(start,False,[])]);seen={(start,False)}
 while pending:
  node,typed,proof=pending.popleft()
  if node==end and proof and (kind=='ancestors' or typed):return proof
  for e in edges.get(node,[]):
   if kind=='ancestors' and e['relation']!='subtype':continue
   if kind=='model_object_members' and ((not typed and e['relation']!='type') or (typed and e['relation']!='subtype')):continue
   nexttyped=typed or e['relation']=='type';state=(e['object'],nexttyped)
   if state in seen:continue
   seen.add(state);pending.append((e['object'],nexttyped,proof+[e]))
 return None

def reachable_boundary(classes,edges,starts):
 pending=list(starts);seen=set();boundary=set()
 while pending:
  k=pending.pop()
  if k in seen:continue
  seen.add(k)
  if k not in classes:boundary.add(k)
  pending.extend(e['object'] for e in edges.get(k,[]) if e['relation']=='subtype')
 return sorted(boundary)

def build(config,rows):
 sources={};errors={};receipts=[]
 for i,s in enumerate(config['sources']):
  try:
   raw=Path(s['path']).read_bytes()
   if hashlib.sha256(raw).hexdigest()!=s['projection_sha256']:raise ValueError('projection_hash_mismatch')
   d=json.loads(raw)
   if d['sha256']!=s['original_xml_sha256']:raise ValueError('source_hash_metadata_mismatch')
   sources[i]=(d,index(d));receipts.append({'source_index':i,'status':'loaded','projection_sha256':s['projection_sha256'],'original_xml_sha256':s['original_xml_sha256']})
  except Exception as e:errors[i]=str(e);receipts.append({'source_index':i,'status':'unavailable','error':str(e)})
 reports=[]
 for row in rows:
  r={k:row[k] for k in ('source_index','kind','target','arm','status')};r['answers']=[]
  if row['source_index'] not in sources:r.update(witness_status='source_unavailable',error=errors.get(row['source_index'],'unknown_source_index'));reports.append(r);continue
  d,(classes,objects,edges)=sources[row['source_index']]
  if row['kind'] not in ('ancestors','model_object_members') or row['target'] not in classes:r['witness_status']='question_outside_contract';reports.append(r);continue
  if row['status']!='completed':r['witness_status']='runtime_not_completed';reports.append(r);continue
  for value in row['values']:
   start,end=(row['target'],value) if row['kind']=='ancestors' else (value,row['target'])
   proof=path(edges,start,end,row['kind']) if row['kind']=='ancestors' or value in objects else None
   r['answers'].append({'value':value,'one_support_path':proof,'supported_in_selected_projection':proof is not None})
  starts=[row['target']] if row['kind']=='ancestors' else [e['object'] for o in objects for e in edges.get(o,[]) if e['relation']=='type']
  r['unloaded_definition_boundary']=reachable_boundary(classes,edges,starts)
  r['witness_status']='all_returned_values_supported' if all(a['supported_in_selected_projection'] for a in r['answers']) else 'unsupported_returned_value'
  r['negative_or_global_completeness']='not_certified';reports.append(r)
 return {'sources':receipts,'reports':reports,'limits':['One selected support path per returned positive value, not all derivations','Membership boundary conservatively traverses all declared object types','Empty answers have vacuous positive support, not completeness proof','Original XML hash is recorded metadata; independent XML audit separate','No runtime repair, scoring gold, external truth or LLM improvement']}
if __name__=='__main__':
 import sys
 cfg=json.loads(Path(sys.argv[1]).read_text());rows=[json.loads(l) for l in Path(sys.argv[2]).read_text().splitlines()];result=build(cfg,rows);Path(sys.argv[3]).write_text(json.dumps(result,indent=2)+'\n');print({'rows':len(result['reports']),'answers':sum(len(r['answers']) for r in result['reports'])})
