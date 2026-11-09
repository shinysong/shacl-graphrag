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
