# Actual published manufacturing subtype projection
Two frozen MachineTool source snapshots previouslyinspected. Each62UAObjectTypes; queries2kinds x62types x2versions =248dependentqueries x3arms =744slots. Armsassertedlookup, samepolicyPythontransitiveclosure, actualowlrl7.6.2. Notfreshheldout. Questionsaskknownancestorsandmodelobjectmembership, notequipmentoperation. Source HasSubtypei45 direction normalizedtochild->parent; onlyUAObjectTypehierarchy. HasTypeDefinitioni40 onUAObjects mappedtordf:type. OtherOPCinheritance/overrides/attributesnotimplemented. Externalmodeldefinitionsnotloaded; namedexternalboundarytypesdonotimplytheirfullancestorsknown. Officialhttps://reference.opcfoundation.org/specs/OPC-10000-3/7.10 and/6.3 describeHasSubtypeandObjectTypeinheritance; thisexplicitexperimentalRDFSprojectionisonlyapartialview,notcompleteOPCUAconformance. No SHACL/Neptune/Neo4j/LLMcall. Positiveclosure membership vsassertedablation; noRDFsuperiority. Independentruntime sourceXMLfieldcheck for earlierquestionsdoesnotverifyeveryhierarchyedge; rawsourceoriginals availablebutomittedthispacket/unverified. Freezeprojectionfilehashesandrawsourcehashbeforeexecution. Questionsfixedpriorrun; sourcefailuresretainedalldependent slots. Cycleoutsidecontract rejectedfor allarms beforeclosure. Runtimefilewrites canfaildurability. Plannedcontrolschain,membership,boundary,unrelated,edge removal,cycle; sourcefailurecontroltamperoneprojectionpathkeepingfull744matrix. No humanlabor/performance/operationaltruth claims.
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

def outputs(p,arm):
 if arm=='asserted':anc=p['edges'];types=p['types']
 elif arm=='python_transitive':
  anc=p['closure'];types=p['types']|{(s,parent) for s,t in p['types'] for child,parent in anc if child==t}
 elif arm=='owlrl_transitive':
  g=Graph()
  for c in p['allclasses']:g.add((u(c),RDF.type,OWL.Class))
  for child,parent in p['edges']:g.add((u(child),RDFS.subClassOf,u(parent)))
  for obj,c in p['types']:g.add((u(obj),RDF.type,u(c)))
  DeductiveClosure(OWLRL_Semantics,axiomatic_triples=False,datatype_axioms=False).expand(g)
  anc={(a,b) for a in p['allclasses'] for b in p['allclasses'] if a!=b and (u(a),RDFS.subClassOf,u(b)) in g}
  types={(obj,c) for obj in p['objects'] for c in p['allclasses'] if (u(obj),RDF.type,u(c)) in g}
 else:raise ValueError('unknown_arm')
 return {(kind,c):sorted(b for a,b in anc if a==c) if kind=='ancestors' else sorted(obj for obj,t in types if t==c) for c in p['defined_classes'] for kind in ('ancestors','model_object_members')}

def run(config,out):
 config=json.loads(Path(config).read_text());out=Path(out)
 if out.exists():raise ValueError('existing_output')
 out.mkdir(parents=True);plan=[{'source_index':q['source_index'],'kind':q['kind'],'target':q['target'],'arm':arm} for q in config['questions'] for arm in ('asserted','python_transitive','owlrl_transitive')]
 (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');rows=[];sources=[]
 for i,source in enumerate(config['sources']):
  p=None
  try:
   raw=Path(source['path']).read_bytes()
   if hashlib.sha256(raw).hexdigest()!=source['projection_sha256']:raise ValueError('projection_hash_changed')
   d=json.loads(raw)
   if d['sha256']!=source['original_xml_sha256']:raise ValueError('source_hash_changed')
   p=project(d);sources.append({'source_index':i,'status':'completed','defined_classes':len(p['defined_classes']),'objects':len(p['objects']),'direct_subtype_edges':len(p['edges']),'asserted_object_types':len(p['types']),'import_boundary_keys':sorted(p['allclasses']-p['defined_classes'])})
  except Exception as e:sources.append({'source_index':i,'status':'source_failed','error':type(e).__name__+': '+str(e)})
  for arm in ('asserted','python_transitive','owlrl_transitive'):
   answers=None;error=None
   if p is not None:
    try:answers=outputs(p,arm)
    except Exception as e:error=type(e).__name__+': '+str(e)
   for item in [q for q in plan if q['source_index']==i and q['arm']==arm]:
    row=dict(item)
    if p is None:row.update(status='source_failed',values=[])
    elif error:row.update(status='arm_failed',error=error,values=[])
    elif (item['kind'],item['target']) not in answers:row.update(status='question_outside_contract',values=[])
    else:row.update(status='completed',values=answers[item['kind'],item['target']])
    rows.append(row)
    with (out/'rows.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 (out/'sources.json').write_text(json.dumps(sources,indent=2)+'\n')
 summary={'planned':len(plan),'emitted':len(rows),'statuses':{s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})},'limits':['Partial ObjectType hierarchy and model-object membership projection only','Not complete OPC attribute or InstanceDeclaration inheritance','External model definitions absent; partial ancestor graph','Model objects are schema declarations, not operating plant equipment','No QA/performance/SHACL superiority claim; selected dependent development queries']}
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
if __name__=='__main__':
 import sys
 print(run(sys.argv[1],sys.argv[2]))

```
## Checks
```python
import runtime as r

def fixture():
 return {'nodes':{'A':{'class':'UAObjectType','references':[[r.standard(45),False,'B']]},'B':{'class':'UAObjectType','references':[[r.standard(45),False,'External']]},'Other':{'class':'UAObjectType','references':[]},'obj':{'class':'UAObject','references':[[r.standard(40),True,'A']]}}}
d=fixture();p=r.project(d);a=r.outputs(p,'asserted');b=r.outputs(p,'python_transitive');c=r.outputs(p,'owlrl_transitive')
assert b==c and a!=b and b['ancestors','A']==['B','External'] and b['model_object_members','B']==['obj'] and b['model_object_members','Other']==[]
d['nodes']['A']['references']=[];p=r.project(d);assert r.outputs(p,'python_transitive')==r.outputs(p,'owlrl_transitive');assert r.outputs(p,'python_transitive')['model_object_members','B']==[]
d=fixture();d['nodes']['B']['references']=[[r.standard(45),False,'A']]
try:r.project(d)
except ValueError:pass
else:raise AssertionError('cycle_not_rejected')
print('chain/membership/boundary/unrelated/removal parity; cycle rejected outside contract')

```