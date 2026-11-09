import json,sys,hashlib
from pathlib import Path
run=Path(sys.argv[1]);reference=Path('research/backend-reasoning-review-1/contracts-001/evaluator-only.json')
ref=json.loads(reference.read_text());planned=json.loads((run/'plan.json').read_text());rows=[json.loads(x) for x in (run/'results.jsonl').read_text().splitlines()]
key=lambda x:(x['backend'],x['case_id'])
assert len({key(r) for r in rows})==len(rows)
assert {key(r) for r in rows}<={key(r) for r in planned}
checks=[]
for r in rows:
 if r['case_id'] in ref['unsupported']:
  match=r['status']=='unsupported'
 else:match=r['status']=='completed' and sorted(r.get('bindings',[]),key=lambda x:json.dumps(x,sort_keys=True))==sorted(ref['expected'][r['case_id']],key=lambda x:json.dumps(x,sort_keys=True))
 checks.append({'backend':r['backend'],'case_id':r['case_id'],'status':r['status'],'declared_contract_match':match})
result={'planned':len(planned),'observed':len(rows),'unobserved':len(planned)-len(rows),'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),'counts':{s:sum(r['status']==s for r in rows) for s in sorted({r['status'] for r in rows})},'checks':checks,'matching':sum(c['declared_contract_match'] for c in checks),'scope':'Manually frozen development binding references; no natural-language QA accuracy or independent domain truth.'}
(run/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
if result['matching']!=len(planned):raise SystemExit(1)
