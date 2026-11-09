# Posthoc manufacturing hierarchy XML audit

Offline follow-up only; no runtime repair or new calls. Original two pinned MachineTool XMLs under1MB each; source XMLs and exact actual run are omitted/unverified by this packet. New independent ElementTree parser + BFS compares selected original XML answers to saved asserted/Python/OWL-RL results. Same declared partial ObjectType/UAObject positive semantics, no imports or full OPC inheritance. Plan744 slots248dependent development queries. Verify denominator separately and preserve unscorable source slots. Malformed row JSON is a whole-audit exception, not partial recovery. Controls below planned not executed.

```python
"""Posthoc selected hierarchy audit from original XML, no runtime imports/repair."""
import json,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
NS='{http://opcfoundation.org/UA/2011/03/UANodeSet.xsd}'
BASE='http://opcfoundation.org/UA/'
def key(uri,number):return json.dumps([uri,'i='+str(number)],separators=(',',':'))
def source(path):
 raw=Path(path).read_bytes()
 if len(raw)>1000000 or b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:raise ValueError('unsupported_XML')
 root=ET.fromstring(raw);uris=[BASE]+[n.text for n in root.find(NS+'NamespaceUris')];aliases={a.get('Alias'):a.text for a in root.find(NS+'Aliases')}
 def resolve(text):
  seen=set();text=text.strip()
  while text in aliases:
   if text in seen:raise ValueError('alias_cycle')
   seen.add(text);text=aliases[text]
  parts=dict(piece.split('=',1) for piece in text.split(';'))
  if set(parts)-{'ns','i'} or 'i' not in parts:raise ValueError('unsupported_NodeId')
  return key(uris[int(parts.get('ns',0))],int(parts['i']))
 nodes={}
 for n in root:
  if 'NodeId' not in n.attrib:continue
  k=resolve(n.attrib['NodeId'])
  if k in nodes:raise ValueError('duplicate_NodeId')
  nodes[k]=n
 classes={k for k,n in nodes.items() if n.tag==NS+'UAObjectType'};objects={k for k,n in nodes.items() if n.tag==NS+'UAObject'};parents={};types={}
 for k in classes|objects:
  for ref in nodes[k].find(NS+'References'):
   rel=resolve(ref.attrib['ReferenceType']);target=resolve(ref.text)
   direction=ref.get('IsForward','true')
   if direction not in ('true','false','1','0'):raise ValueError('invalid_direction')
   forward=direction in ('true','1')
   if k in classes and rel==key(BASE,45):
    child,parent=(target,k) if forward else (k,target);parents.setdefault(child,set()).add(parent)
   if k in objects and rel==key(BASE,40):
    if not forward:raise ValueError('unsupported_inverse_type')
    types.setdefault(k,set()).add(target)
 def ancestors(node):
  reached=set();pending=list(parents.get(node,set()))
  while pending:
   item=pending.pop()
   if item==node:raise ValueError('cycle')
   if item in reached:continue
   reached.add(item);pending.extend(parents.get(item,set()))
  return reached
 expected={}
 for c in classes:
  expected['ancestors',c,'asserted']=sorted(parents.get(c,set()))
  expected['ancestors',c,'closure']=sorted(ancestors(c))
  expected['model_object_members',c,'asserted']=sorted(o for o in objects if c in types.get(o,set()))
  expected['model_object_members',c,'closure']=sorted(o for o in objects if any(c==t or c in ancestors(t) for t in types.get(o,set())))
 return hashlib.sha256(raw).hexdigest(),expected,{'defined_classes':len(classes),'objects':len(objects),'direct_edges':sum(map(len,parents.values())),'asserted_types':sum(map(len,types.values()))}

def audit(run,xmlpaths):
 run=Path(run);config=json.loads((run/'config.json').read_text());plan=json.loads((run/'plan.json').read_text());rows=[json.loads(line) for line in (run/'rows.jsonl').read_text().splitlines()]
 identity=lambda r:(r['source_index'],r['kind'],r['target'],r['arm'])
 denominator={'planned':len(plan),'emitted':len(rows),'unique_planned':len({identity(r) for r in plan}),'unique_emitted':len({identity(r) for r in rows}),'same_identity_multiset':Counter(map(identity,plan))==Counter(map(identity,rows))}
 expected={};checks=[]
 for i,p in enumerate(xmlpaths):
  try:
   sha,values,counts=source(p)
   if sha!=config['sources'][i]['original_xml_sha256']:raise ValueError('original_hash_mismatch')
   expected[i]=values;checks.append({'source_index':i,'status':'completed','sha256':sha,**counts})
  except Exception as e:checks.append({'source_index':i,'status':'source_unscorable','error':type(e).__name__+': '+str(e)})
 scored=[]
 for row in rows:
  arm='asserted' if row['arm']=='asserted' else 'closure' if row['arm'] in ('python_transitive','owlrl_transitive') else None
  wanted=expected.get(row['source_index'],{}).get((row['kind'],row['target'],arm));scorable=wanted is not None
  scored.append({**{k:row[k] for k in ('source_index','kind','target','arm','status')},'scorable':scorable,'values_equal':row['values']==wanted if scorable and row['status']=='completed' else None})
 return {'denominator':denominator,'source_checks':checks,'rows':scored,'limits':['Selected ObjectType positive ancestry and model-object membership only','Independent XML/BFS implementation, same manually declared semantics','No runtime imports or repairs; not full XML projection certification','No external imports or complete OPC inheritance; not plant truth or QA']}
if __name__=='__main__':
 import sys
 result=audit(sys.argv[1],sys.argv[2:4]);Path(sys.argv[4]).write_text(json.dumps(result,indent=2)+'\n');print({'denominator':result['denominator'],'scorable':sum(r['scorable'] for r in result['rows']),'equal':sum(r['values_equal'] is True for r in result['rows'])})

```
## Planned controls
```python
import json,tempfile,shutil
from pathlib import Path
import audit
RUN=Path('research/manufacturing-model-change-1/subtype-offline-001')
XML=sorted(Path('research/manufacturing-model-change-1/projection-001/sources').glob('*.xml'))
base=audit.audit(RUN,XML)
assert base['denominator']['same_identity_multiset'] and all(r['values_equal'] for r in base['rows'])
with tempfile.TemporaryDirectory(dir='_workspace/manufacturing-continuation-20261107/subtype-xml') as tmp:
 p=Path(tmp)
 for f in ('config.json','plan.json','rows.jsonl'):shutil.copyfile(RUN/f,p/f)
 rows=[json.loads(l) for l in (p/'rows.jsonl').read_text().splitlines()];rows[0]['values']=['wrong']
 (p/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 changed=audit.audit(p,XML);assert sum(r['values_equal'] is False for r in changed['rows'])==1
 rows.append(rows[0]);(p/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 assert not audit.audit(p,XML)['denominator']['same_identity_multiset']
missing=audit.audit(RUN,[Path('missing-original.xml'),XML[1]])
assert len(missing['rows'])==744 and sum(r['scorable'] for r in missing['rows'])==372
with tempfile.TemporaryDirectory(dir='_workspace/manufacturing-continuation-20261107/subtype-xml') as tmp:
 p=Path(tmp)
 for f in ('config.json','plan.json','rows.jsonl'):shutil.copyfile(RUN/f,p/f)
 c=json.loads((p/'config.json').read_text());c['sources'][0]['original_xml_sha256']='0'*64;(p/'config.json').write_text(json.dumps(c))
 assert sum(r['scorable'] for r in audit.audit(p,XML)['rows'])==372
print('baseline equality, wrong answer, duplicate row, missing XML, hash mismatch controls pass')

```
