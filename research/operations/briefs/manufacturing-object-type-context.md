Followup toimport-boundary992slots with0/248localclassquestionschanged. Newquestionfamilyasks allinheritedtypes ofevery original150UAObject/version=300questions×2sourcecontexts×2algorithms1200slots. Posthocconsumeddata; noheldout/noenginebenefit. AddIAcommonbothalgorithms not strongerreasoning. OriginalUAObjects modeldeclarationsnotplant equipment. RawXML/configlistomittedunverified, frozen300objectkeys fromprevioussnapshots. No changedoldoutputs. Controlsourcefailurefull1200. Review<=250words.

## check.py
```
import runtime as r
import json,copy
from pathlib import Path
p={'types':{('o','B'),('x','B')},'edges':{('B','A')},'closure':{('B','A')},'allclasses':{'A','B'}}
for arm in r.ARMS:assert r.memberships(p,arm,{'o'})=={'o':['A','B']}
cfg=json.loads(Path(__file__).with_name('config.json').read_text());cfg=copy.deepcopy(cfg)
for s in cfg['sources']:s['main']['path']='/missing'
x=r.run(cfg);assert x['planned']==len(x['rows'])==1200 and all(q['status']=='source_failed' for q in x['rows'])
print('all-type set originalobjectfilter andfull1200failure controls passed')

```

## runtime.py
```
"""All original150model objects per source, partial inherited type sets."""
import json
from pathlib import Path
import source_context as sc
from rdflib import Graph,RDF,RDFS,OWL
from owlrl import DeductiveClosure,OWLRL_Semantics
h=sc.h
ARMS=('python_transitive','owlrl_transitive')
def memberships(p,arm,objects):
 if arm=='python_transitive':
  return {o:sorted({t for x,t in p['types'] if x==o}|{b for x,t in p['types'] if x==o for a,b in p['closure'] if a==t}) for o in objects}
 if arm!='owlrl_transitive':raise ValueError('arm')
 g=Graph()
 for c in p['allclasses']:g.add((h.u(c),RDF.type,OWL.Class))
 for a,b in p['edges']:g.add((h.u(a),RDFS.subClassOf,h.u(b)))
 for o,t in p['types']:g.add((h.u(o),RDF.type,h.u(t)))
 DeductiveClosure(OWLRL_Semantics,axiomatic_triples=False,datatype_axioms=False).expand(g)
 return {o:sorted(c for c in p['allclasses'] if (h.u(o),RDF.type,h.u(c)) in g) for o in objects}
def run(cfg):
 plan=[{'source_index':q['source_index'],'object':q['object'],'mode':mode,'arm':arm} for q in cfg['questions'] for mode in sc.MODES for arm in ARMS];rows=[];metadata=[]
 for i,s in enumerate(cfg['sources']):
  objects={q['object'] for q in cfg['questions'] if q['source_index']==i}
  for mode in sc.MODES:
   answer={};error=None
   try:
    main=sc.read_source(s['main']);base=h.project(main)
    if objects!=base['objects'] or sum(q['source_index']==i for q in cfg['questions'])!=len(objects):raise ValueError('object_universe')
    p=h.project(main if mode=='isolated' else sc.combine(main,sc.read_source(s['ia'])))
    for arm in ARMS:
     try:answer[arm]=memberships(p,arm,objects)
     except Exception as e:answer[arm]={'error':f'{type(e).__name__}: {e}'}
    metadata.append({'source_index':i,'mode':mode,'defined_class_keys':sorted(p['defined_classes']),'remaining_boundary_keys':sorted(p['allclasses']-p['defined_classes'])})
   except Exception as e:error=f'{type(e).__name__}: {e}'
   for slot in [r for r in plan if r['source_index']==i and r['mode']==mode]:
    a=answer.get(slot['arm'],{})
    if error:rows.append({**slot,'status':'source_failed','types':[],'error':error})
    elif 'error' in a:rows.append({**slot,'status':'arm_failed','types':[],'error':a['error']})
    else:rows.append({**slot,'status':'completed','types':a[slot['object']]})
 return {'planned':len(plan),'rows':rows,'source_contexts':metadata,'limits':['Posthoc question-family expansion after local-class queries were insensitive to IA inclusion','Alloriginalobjects queried; no positive-case-onlyselection','Type sets limited to explicit projected graph and one IA file; externaldefinitionsstillmissing','This is additional source access, not a stronger reasoner or actual plant truth']}
if __name__=='__main__':
 import sys
 out=Path(sys.argv[2]);
 if out.exists():raise ValueError('existing_output')
 out.write_text(json.dumps(run(json.loads(Path(sys.argv[1]).read_text())),indent=2)+'\n')

```

## hierarchy.py
```
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

## source_context.py
```
"""Frozen MachineTool query universe, explicit one-IA-file augmentation; offline only."""
import json,hashlib,copy
from pathlib import Path
import source_projection as sp
import hierarchy as h
MODES=('isolated','with_declared_ia_file');ARMS=('python_transitive','owlrl_transitive')
def read_source(s):
 if hashlib.sha256(Path(s['path']).read_bytes()).hexdigest()!=s['sha256']:raise ValueError('source_hash')
 return sp.parse(s['path'])
def combine(main,extra):
 required=[r for m in main['models'] for r in m['required'] if r['ModelUri']=='http://opcfoundation.org/UA/IA/'];provided=[m['attributes'] for m in extra['models'] if m['attributes']['ModelUri']=='http://opcfoundation.org/UA/IA/']
 if len(required)!=1 or len(provided)!=1 or any(required[0].get(k)!=provided[0].get(k) for k in ('ModelUri','Version','PublicationDate')):raise ValueError('selected_exact_metadata_binding')
 # Exact selection is reproducibility policy, not general minimum-version compatibility.
 if set(main['nodes'])&set(extra['nodes']):raise ValueError('duplicate_definition_outside_contract')
 d=copy.deepcopy(main);d['nodes'].update(extra['nodes']);return d

def run(cfg):
 plan=[{'source_index':i,'mode':mode,'arm':arm,'kind':q['kind'],'target':q['target']} for i,s in enumerate(cfg['sources']) for mode in MODES for arm in ARMS for q in cfg['questions'] if q['source_index']==i]
 rows=[];metadata=[]
 for i,s in enumerate(cfg['sources']):
  qs=[q for q in cfg['questions'] if q['source_index']==i]
  for mode in MODES:
   values={};error=None
   try:
    main=read_source(s['main']);base=h.project(main);expected={(c,k) for c in base['defined_classes'] for k in ('ancestors','model_object_members')}
    if {(q['target'],q['kind']) for q in qs}!=expected or len(qs)!=len(expected):raise ValueError('question_matrix')
    d=main if mode=='isolated' else combine(main,read_source(s['ia']))
    projected=h.project(d)
    metadata.append({'source_index':i,'mode':mode,'status':'completed','original_object_universe':len(base['objects']),'loaded_defined_classes':len(projected['defined_classes']),'remaining_boundary':sorted(projected['allclasses']-projected['defined_classes'])})
    for arm in ARMS:
     try:
      answer=h.outputs(projected,arm);values[arm]={}
      for q in qs:
       v=answer[q['kind'],q['target']]
       if q['kind']=='model_object_members':v=sorted(set(v)&base['objects'])
       values[arm][q['kind'],q['target']]=v
     except Exception as e:values[arm]={'error':f'{type(e).__name__}: {e}'}
   except Exception as e:error=f'{type(e).__name__}: {e}';metadata.append({'source_index':i,'mode':mode,'status':'source_failed','error':error})
   for slot in [r for r in plan if r['source_index']==i and r['mode']==mode]:
    a=values.get(slot['arm'],{})
    if error:rows.append({**slot,'status':'source_failed','values':[],'error':error})
    elif 'error' in a:rows.append({**slot,'status':'arm_failed','values':[],'error':a['error']})
    else:rows.append({**slot,'status':'completed','values':a[slot['kind'],slot['target']]})
 return {'planned':len(plan),'plan':plan,'rows':rows,'sources':metadata,'scope':'Two existing consumed MachineTool files, adding only selected IA definitions; original MachineTool object universe retained; not complete imports or compatibility, no DB/LLM/performance claim'}
if __name__=='__main__':
 import sys
 cfg=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);
 if out.exists():raise ValueError('existing_output')
 out.write_text(json.dumps(run(cfg),indent=2)+'\n')

```

## source_projection.py
```
"""Bounded numeric NodeId definition projection; not an OPC UA implementation."""
import hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
BASE='http://opcfoundation.org/UA/'
NS={'u':'http://opcfoundation.org/UA/2011/03/UANodeSet.xsd'}

def parse(path):
 raw=Path(path).read_bytes()
 if len(raw)>1000000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('unsupported_xml')
 root=ET.fromstring(raw)
 if root.tag!='{'+NS['u']+'}UANodeSet':raise ValueError('wrong_root')
 uris=[BASE]+[e.text for e in root.find('u:NamespaceUris',NS)]
 if any(not u for u in uris) or len(set(uris))!=len(uris):raise ValueError('invalid_namespaces')
 aliases={}
 for e in root.find('u:Aliases',NS):
  key=e.attrib['Alias']
  if key in aliases:raise ValueError('duplicate_alias')
  aliases[key]=(e.text or '').strip()
 def resolve(value,seen=()):
  if value in aliases:
   if value in seen:raise ValueError('alias_cycle')
   return resolve(aliases[value],seen+(value,))
  match=re.fullmatch(r'(?:ns=(\d+);)?i=(\d+)',value)
  if not match:raise ValueError('unsupported_nodeid:'+value)
  index=int(match[1] or 0)
  if index>=len(uris):raise ValueError('unknown_namespace')
  return json.dumps([uris[index],'i='+str(int(match[2]))],separators=(',',':'))
 def browse(value):
  match=re.fullmatch(r'(\d+):(.*)',value)
  index=int(match[1]) if match else 0;name=match[2] if match else value
  if index>=len(uris):raise ValueError('unknown_browse_namespace')
  return [uris[index],name]
 models=[{'attributes':m.attrib,'required':[r.attrib for r in m]} for m in root.find('u:Models',NS)]
 nodes={}
 for e in root:
  if not e.tag.rsplit('}',1)[-1].startswith('UA'):continue
  key=resolve(e.attrib['NodeId'])
  if key in nodes:raise ValueError('duplicate_nodeid')
  refs=[];rawrefs=[]
  container=e.find('u:References',NS)
  if container is not None:
   for r in container:
    forward=r.get('IsForward','true')
    if forward not in ('true','false','1','0'):raise ValueError('invalid_direction')
    target=(r.text or '').strip();typ=r.attrib['ReferenceType']
    refs.append([resolve(typ),forward in ('true','1'),resolve(target)])
    rawrefs.append([typ,forward in ('true','1'),target])
  nodes[key]={'key':key,'raw_nodeid':e.attrib['NodeId'],'class':e.tag.rsplit('}',1)[-1],
   'browse':browse(e.attrib['BrowseName']),'raw_browse':e.attrib['BrowseName'],
   'parent':resolve(e.attrib['ParentNodeId']) if 'ParentNodeId' in e.attrib else None,
   'datatype':resolve(e.attrib['DataType']) if 'DataType' in e.attrib else None,
   'references':sorted(refs),'raw_references':sorted(rawrefs)}
 return {'sha256':hashlib.sha256(raw).hexdigest(),'models':models,'namespaces':uris,
         'aliases':{a:resolve(a) for a in aliases},'raw_aliases':aliases,'nodes':nodes,
         'scope':'Numeric NodeId, node class, qualified BrowseName, explicit ParentNodeId/DataType and references only; other attributes/values/descriptions omitted; imports not loaded'}

def compare(a,b):
 common=set(a['nodes'])&set(b['nodes']);changes=[]
 for key in sorted(common):
  old=a['nodes'][key];new=b['nodes'][key]
  fields=[f for f in ('class','browse','parent','datatype','references') if old[f]!=new[f]]
  if fields:changes.append({'key':key,'changed_projected_fields':fields,'before':old,'after':new})
 return {'common_node_keys':len(common),'added_keys':sorted(set(b['nodes'])-set(a['nodes'])),'removed_keys':sorted(set(a['nodes'])-set(b['nodes'])),
         'changed_definitions':changes,'alias_raw_index_is_not_identity':[
          {'alias':name,'resolved_identity':a['aliases'][name]} for name in sorted(set(a['aliases'])&set(b['aliases']))
          if a['aliases'][name]==b['aliases'][name] and a['raw_aliases'][name]!=b['raw_aliases'][name]],
         'limits':['Projection changes only, not complete semantic differences','Same key is a lookup locator, not proof of unchanged meaning','Source versions are real published model snapshots, not deployed plant history','No operational compatibility or defect judgment']}

```
