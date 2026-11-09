# Selected-source additions and query read dependencies
Manufacturing main objective. Natural published schema release, not plant history. Same consumed2MachineTool snapshots;124old-source typedqueries. Preliminary inspection of prior outputs foundone changed membershipquery (ObligationType addsmodelobjecti5068) while oldpositiveproofsunchanged. This is posthoc explanatory diagnostic, NOTfreshheldout, complexitythreshold, natural-language extraction or benchmark. Compare whole selected graph change; deliberately incomplete previouspositivepaths-only; adjacencybucketreads including emptybuckets. Complete old/newselectedsnapshots supplied equally. Flags use changedbuckets/oldreads/triples; new answer recomputation is posthoc changed label only, never repairs answers. No DB/APIcall/QA. Raw XML parser/preprojection not re-reviewed; selected projector shown. Controlsplannednotrun; sourcefailure denominator124planned. Review <=200words.

## footprint.py
```python
"""Selected-source cache invalidation diagnostic. No answer repair or gold input."""
import json,hashlib
from pathlib import Path

def indexes(p):
 b={}
 def add(kind,key,value):b.setdefault((kind,key),set()).add(value)
 for child,parent in p['edges']:
  add('parents',child,parent);add('children',parent,child)
 for obj,typ in p['types']:add('members',typ,obj)
 return b

def query(b,kind,target):
 reads=set();proof=set()
 def read(k):reads.add(k);return b.get(k,set())
 if kind=='ancestors':
  pending=[target];visited=set();answer=set()
  while pending:
   node=pending.pop()
   if node in visited:continue
   visited.add(node)
   for parent in read(('parents',node)):
    if parent==target:raise ValueError('unsupported_cycle')
    proof.add(('subtype',node,parent));answer.add(parent);pending.append(parent)
 elif kind=='model_object_members':
  pending=[target];visited=set();answer=set()
  while pending:
   node=pending.pop()
   if node in visited:continue
   visited.add(node)
   for obj in read(('members',node)):answer.add(obj)
   pending.extend(read(('children',node)))
  # Preserve a set of positive supporting paths for every returned member.
  # This is a deliberately incomplete invalidation baseline, not an optimal cache.
  for obj in sorted(answer):
   for typ in sorted(visited):
    if obj not in b.get(('members',typ),set()):continue
    queue=[(typ,[])];seen=set()
    while queue:
     node,path=queue.pop(0)
     if node in seen:continue
     seen.add(node)
     if node==target:proof.add(('type',obj,typ));proof.update(path);break
     queue.extend((parent,path+[('subtype',node,parent)]) for parent in sorted(b.get(('parents',node),set())))
 else:raise ValueError('unsupported_kind')
 return sorted(answer),reads,proof

def triples(p):return {('subtype',a,b) for a,b in p['edges']}|{('type',a,b) for a,b in p['types']}
def compare(old,new,questions):
 a=indexes(old);b=indexes(new);changed={k for k in a.keys()|b.keys() if a.get(k,set())!=b.get(k,set())};whole=triples(old)!=triples(new);rows=[]
 for q in questions:
  values,reads,proof=query(a,q['kind'],q['target']);newvalues,_,_=query(b,q['kind'],q['target'])
  rows.append({**q,'old_values':values,'new_values':newvalues,'changed':values!=newvalues,'flags':{'whole_selected_graph':whole,'previous_positive_paths_only':bool(proof-triples(new)),'query_adjacency_buckets':bool(reads&changed)},'old_read_buckets':[list(x) for x in sorted(reads)],'changed_read_buckets':[list(x) for x in sorted(reads&changed)],'old_positive_path_triples':[list(x) for x in sorted(proof)]})
 return {'rows':rows,'changed_buckets':[list(k) for k in sorted(changed)],'policies':{pol:{'queries':len(rows),'changed':sum(r['changed'] for r in rows),'flagged':sum(r['flags'][pol] for r in rows),'missed_changed':sum(r['changed'] and not r['flags'][pol] for r in rows),'unchanged_flagged':sum(not r['changed'] and r['flags'][pol] for r in rows)} for pol in ('whole_selected_graph','previous_positive_paths_only','query_adjacency_buckets')},'limits':['Complete selected snapshots and manually typed queries; not natural-language extraction','Positive-path-only is a deliberately incomplete invalidation baseline','Bucket metadata captures empty adjacency reads as well as positive values','No cache refresh, measured labor, DB requests saved, minimality or SHACL-specific effect','Original source imports remain excluded; published model objects are not physical equipment']}

```

## run.py
```python
import json,hashlib,importlib.util
from pathlib import Path
import footprint
SOURCE_MODULE=Path('research/manufacturing-model-change-1/subtype-offline-001/runtime.py')
def run(config,out):
 cfg=json.loads(Path(config).read_text());questions=[{k:q[k] for k in ('kind','target')} for q in cfg['questions'] if q['source_index']==0];out=Path(out);out.mkdir(parents=True,exist_ok=False)
 if len(questions)!=124 or len({(q['kind'],q['target']) for q in questions})!=124:raise ValueError('question_contract')
 (out/'plan.json').write_text(json.dumps(questions,indent=2)+'\n')
 try:
  if hashlib.sha256(SOURCE_MODULE.read_bytes()).hexdigest()!='2b9f2ecad50b32c491bc9c113f7e9f6f6c9a612248e67a60d3b5dc91c5aad110':raise ValueError('projector_code_hash')
  spec=importlib.util.spec_from_file_location('hierarchy',SOURCE_MODULE);h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h);projections=[]
  for s in cfg['sources']:
   raw=Path(s['path']).read_bytes()
   if hashlib.sha256(raw).hexdigest()!=s['projection_sha256']:raise ValueError('projection_hash')
   data=json.loads(raw)
   if data['sha256']!=s['original_xml_sha256']:raise ValueError('original_hash_metadata')
   projections.append(h.project(data))
  if len(projections)!=2 or projections[0]['defined_classes']!=projections[1]['defined_classes']:raise ValueError('changed_query_domain_unsupported')
  if {(q['kind'],q['target']) for q in questions}!={(kind,c) for c in projections[0]['defined_classes'] for kind in ('ancestors','model_object_members')}:raise ValueError('question_domain')
  result=footprint.compare(*projections,questions)
  for r in result['rows']:r['status']='completed'
 except Exception as e:result={'rows':[{**q,'status':'source_or_execution_failed','error':type(e).__name__+': '+str(e)} for q in questions],'fatal':str(e)}
 (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 import sys
 r=run(sys.argv[1],sys.argv[2]);print({k:v for k,v in r.items() if k not in ('rows','changed_buckets')})

```

## check.py
```python
from footprint import compare

def p(edges=(),types=()):return {'edges':set(edges),'types':set(types)}
def run(a,b,kind='model_object_members',target='A'):return compare(a,b,[{'kind':kind,'target':target}])['rows'][0]
r=run(p(types=[('old','A')]),p(types=[('old','A'),('new','A')]));assert r['changed'] and not r['flags']['previous_positive_paths_only'] and r['flags']['query_adjacency_buckets']
r=run(p(),p(types=[('new','A')]));assert r['old_values']==[] and r['flags']['query_adjacency_buckets']
r=run(p(types=[('old','B')]),p(edges=[('B','A')],types=[('old','B')]));assert r['flags']['query_adjacency_buckets'] and r['new_values']==['old']
r=run(p(types=[('old','A')]),p());assert r['flags']['previous_positive_paths_only'] and r['flags']['query_adjacency_buckets']
r=run(p(types=[('old','A')]),p(types=[('old','A'),('other','Z')]));assert not r['changed'] and not r['flags']['query_adjacency_buckets'] and r['flags']['whole_selected_graph']
r=run(p(edges=[('A','B')]),p(edges=[('A','B'),('B','C')]),'ancestors');assert r['flags']['query_adjacency_buckets'] and not r['flags']['previous_positive_paths_only']
print('six addition/empty/edge/deletion/unrelated/ancestor controls passed')

```

## Previously verified partial projector (rest of module omitted, hash pinned)
```python
"""Bounded OPC declared ObjectType hierarchy projection, not full OPC semantics."""
import json,hashlib
from pathlib import Path
from urllib.parse import quote
from rdflib import Graph,URIRef,RDF,RDFS,OWL
from owlrl import DeductiveClosure,OWLRL_Semantics
BASE='http://opcfoundation.org/UA/'
def standard(number):return json.dumps([BASE,'i='+str(number)],separators=(',',':'))
def u(k):return URIRef('urn:opc-partial:'+quote(k,safe=''))
def project(d):
 nodes=d['nodes'];classes={k for k,v in nodes.items() if v['class']=='UAObjectType'};objects={k for k,v in nodes.items() if v['class']=='UAObject'};edges=set();types=set()
 for k in classes:
  for typ,forward,target in nodes[k]['references']:
   if typ==standard(45):
    child,parent=(target,k) if forward else (k,target)
    for x in (child,parent):
     if x in nodes and x not in classes:raise ValueError('non_object_type_subtype')
    edges.add((child,parent))
 for k in objects:
  for typ,forward,target in nodes[k]['references']:
   if typ==standard(40):
    if not forward:raise ValueError('unsupported_inverse_type_assertion')
    if target in nodes and target not in classes:raise ValueError('non_object_type_definition')
    types.add((k,target))
 allclasses=classes|{k for e in edges for k in e}|{t for _,t in types}
 closure=set(edges)
 while True:
  more={(a,c) for a,b in closure for x,c in closure if b==x}-closure
  if not more:break
  closure|=more
 if any(a==b for a,b in closure):raise ValueError('cyclic_hierarchy_outside_contract')
 return {'defined_classes':classes,'objects':objects,'allclasses':allclasses,'edges':edges,'types':types,'closure':closure}


```
