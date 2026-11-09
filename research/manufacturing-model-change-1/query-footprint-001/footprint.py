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
