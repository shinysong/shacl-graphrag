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
