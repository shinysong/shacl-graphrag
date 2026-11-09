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
