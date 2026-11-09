"""Posthoc original-XML audit of saved live rows; never changes answers."""
import json,hashlib,importlib.util
from pathlib import Path
from collections import Counter
PARSER=Path('research/manufacturing-model-change-1/subtype-offline-001/xml-audit-code/audit.py')
ARMS={'neo4j_cypher_paths','n10s_category','neptune_sparql_paths','neptune_external_owlrl'}
def audit(config,plan,rows,xmlpaths):
 if hashlib.sha256(PARSER.read_bytes()).hexdigest()!='208602c406bc6de0f7f9d9b7ea743042457ea9241f1e1ad0230e1f4ac51cdac5':raise ValueError('XML_parser_code_changed')
 spec=importlib.util.spec_from_file_location('xml_source',PARSER);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 identity=lambda r:(r['source_index'],r['kind'],r['target'],r['arm']);expected={};checks=[];domain=set()
 for i,path in enumerate(xmlpaths):
  try:
   sha,values,counts=module.source(path)
   if sha!=config['sources'][i]['original_xml_sha256']:raise ValueError('original_hash_mismatch')
   expected[i]=values;checks.append({'source_index':i,'status':'completed','sha256':sha,**counts})
   domain|={(i,k,t,a) for k,t,mode in values if mode=='closure' for a in ARMS}
  except Exception as e:checks.append({'source_index':i,'status':'source_unscorable','error':type(e).__name__+': '+str(e)})
 planids=list(map(identity,plan));rowids=list(map(identity,rows));denominator={'planned':len(plan),'emitted':len(rows),'unique_planned':len(set(planids)),'unique_emitted':len(set(rowids)),'same_identity_multiset':Counter(planids)==Counter(rowids),'expected_992':len(planids)==len(rowids)==len(set(planids))==len(set(rowids))==992,'source_domain_verified':len(expected)==2 and set(planids)==domain}
 result=[]
 for r in rows:
  supported=r['arm'] in ARMS and not (r['arm']=='n10s_category' and r['kind']=='ancestors');wanted=expected.get(r['source_index'],{}).get((r['kind'],r['target'],'closure'));scorable=supported and wanted is not None
  result.append({**{k:r[k] for k in ('source_index','kind','target','arm','status')},'supported_selected_adapter':supported,'scorable':scorable,'values_equal':r['values']==wanted if scorable and r['status']=='completed' else None})
 return {'denominator':denominator,'source_checks':checks,'rows':result,'limits':['Independent original XML/BFS implementation with same declared partial semantics','Unsupported n10s adapter rows not scored as completed or incorrect','Scorer does not alter saved results or load runtime gold','No external model definitions/full OPC inheritance/plant truth/QA']}
if __name__=='__main__':
 import sys
 c=json.loads(Path(sys.argv[1]).read_text());p=Path(sys.argv[2]);result=audit(c,json.loads((p/'plan.json').read_text()),[json.loads(l) for l in (p/'rows.jsonl').read_text().splitlines()],sys.argv[3:5]);Path(sys.argv[5]).write_text(json.dumps(result,indent=2)+'\n');print({'denominator':result['denominator'],'scorable':sum(r['scorable'] for r in result['rows']),'equal':sum(r['values_equal'] is True for r in result['rows'])})
