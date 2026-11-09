PosthocoriginalXML/BFSaudit of1200partialtypeoutputs; noruntimeimports/norepair. Query300originalmodelobjects isolated/oneIA×PythonOWL. RawXML/runtimeoutputs omittedunverified; codeandcontrols below notyetexecuted. All-sourcefail600slots unscorable; declaredmatrixchecked. Partialselectedtypesonly noOPCcompatibility/physicaltruth. Review<=220words.

## check.py
```
import audit as a,json,copy
from pathlib import Path
p=Path(__file__).parent.parent;cfg=json.loads((p/'config.json').read_text());x=json.loads((p/'observed.json').read_text());r=a.audit(cfg,x)
assert r['planned']==1200 and r['denominator_matches'] and r['source_object_universe_matches'] and all(v['status']=='scored' and v['equal'] for v in r['rows'])
y=copy.deepcopy(x);y['rows'][0]['types']=['invented'];r=a.audit(cfg,y);assert not r['rows'][0]['equal']
y=copy.deepcopy(x);y['rows'].pop();assert not a.audit(cfg,y)['denominator_matches']
y=copy.deepcopy(cfg);y['sources'][0]['main']['sha256']='0'*64;r=a.audit(y,x);assert sum(v['status']=='unscorable_source' for v in r['rows'])==600
print('1200originalXML/BFS matches; wrongtype/missingrow/badsource600unscorable controls passed')

```

## audit.py
```
"""Posthoc original XML/BFS audit, no runtime imports and no repairs."""
import json,re,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict,deque,Counter
NS='{http://opcfoundation.org/UA/2011/03/UANodeSet.xsd}';BASE='http://opcfoundation.org/UA/'
def key(uri,num):return json.dumps([uri,'i='+str(int(num))],separators=(',',':'))
def read(s):
 raw=Path(s['path']).read_bytes()
 if len(raw)>1000000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper() or hashlib.sha256(raw).hexdigest()!=s['sha256']:raise ValueError('source_boundary')
 root=ET.fromstring(raw);uris=[BASE]+[x.text for x in root.find(NS+'NamespaceUris')];aliases={x.attrib['Alias']:x.text.strip() for x in root.find(NS+'Aliases')}
 def resolve(text):
  seen=set()
  while text in aliases:
   if text in seen:raise ValueError('alias_cycle')
   seen.add(text);text=aliases[text]
  m=re.fullmatch(r'(?:ns=(\d+);)?i=(\d+)',text)
  if not m:raise ValueError('nonnumeric')
  return key(uris[int(m[1] or 0)],m[2])
 classes=set();objects=set();edges=set();types=set()
 for e in root:
  if e.tag not in (NS+'UAObject',NS+'UAObjectType'):continue
  ident=resolve(e.attrib['NodeId']);isclass=e.tag==NS+'UAObjectType';(classes if isclass else objects).add(ident)
  refs=e.find(NS+'References')
  if refs is None:continue
  for ref in refs:
   typ=resolve(ref.attrib['ReferenceType']);target=resolve(ref.text.strip());direction=ref.attrib.get('IsForward','true')
   if direction not in ('true','false','1','0'):raise ValueError('direction')
   forward=direction in ('true','1')
   if isclass and typ==key(BASE,45):edges.add((ident,target) if not forward else (target,ident))
   if not isclass and typ==key(BASE,40):
    if not forward:raise ValueError('unsupported_inverse_type')
    types.add((ident,target))
 return classes,objects,edges,types

def expected(main,extra=None):
 c,o,e,t=read(main)
 if extra is not None:
  cc,oo,ee,tt=read(extra)
  if c&cc or o&oo:raise ValueError('duplicate_definition')
  e|=ee;t|=tt
 parents=defaultdict(set);direct=defaultdict(set)
 for a,b in e:parents[a].add(b)
 for x,typ in t:direct[x].add(typ)
 answers={}
 for obj in o:
  visited=set();queue=deque(direct[obj])
  while queue:
   x=queue.popleft()
   if x in visited:continue
   visited.add(x);queue.extend(parents[x])
  answers[obj]=sorted(visited)
 return answers

def audit(cfg,observed):
 declared=[(q['source_index'],q['object'],mode,arm) for q in cfg['questions'] for mode in ('isolated','with_declared_ia_file') for arm in ('python_transitive','owlrl_transitive')]
 rows=observed['rows'];actual=[(r['source_index'],r['object'],r['mode'],r['arm']) for r in rows];denominator=Counter(actual)==Counter(declared) and len(set(declared))==len(declared) and observed['planned']==len(declared)
 refs={};errors={};universe=True
 for i,s in enumerate(cfg['sources']):
  for mode in ('isolated','with_declared_ia_file'):
   try:
    refs[i,mode]=expected(s['main'],None if mode=='isolated' else s['ia']);universe &= set(refs[i,mode])=={q['object'] for q in cfg['questions'] if q['source_index']==i}
   except Exception as e:errors[i,mode]=f'{type(e).__name__}: {e}'
 outcomes=[]
 for r in rows:
  k=r['source_index'],r['mode'];q={v:r[v] for v in ('source_index','object','mode','arm')}
  if k in errors:q.update(status='unscorable_source',error=errors[k])
  elif r['status']!='completed':q.update(status='unscorable_runtime')
  elif r['object'] not in refs.get(k,{}):q.update(status='outside_source_universe')
  else:q.update(status='scored',equal=r['types']==refs[k][r['object']])
  outcomes.append(q)
 return {'planned':len(declared),'denominator_matches':denominator,'source_object_universe_matches':universe,'rows':outcomes,'limits':['Independent XML parsing/BFS over selected files only, not full OPC semantics','Posthoc scorer never changes runtime values','Raw source hash failures leave outcomes unscorable']}
if __name__=='__main__':
 import sys
 Path(sys.argv[3]).write_text(json.dumps(audit(json.loads(Path(sys.argv[1]).read_text()),json.loads(Path(sys.argv[2]).read_text())),indent=2)+'\n')

```
