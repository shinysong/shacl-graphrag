import json,sys,hashlib
from pathlib import Path
run=Path(sys.argv[1]);refpath=Path('research/backend-reasoning-review-1/inference-contracts-001/evaluator-only.json');ref=json.loads(refpath.read_text())['expected'];rows=[json.loads(x) for x in (run/'results.jsonl').read_text().splitlines()];plan=json.loads((run/'plan.json').read_text());key=lambda r:(r['variant'],r['arm'],r['query_id']);assert len({key(r) for r in rows})==len(rows);assert {key(r) for r in rows}<={key(r) for r in plan}
checks=[]
for r in rows:
 expected=ref[r['variant']][r['query_id']];match=r['status']=='completed' and r.get('answer')==expected
 checks.append({'variant':r['variant'],'arm':r['arm'],'query_id':r['query_id'],'status':r['status'],'matches_current_reference':match})
summary={arm:{'observed':sum(r['arm']==arm for r in rows),'completed':sum(r['arm']==arm and r['status']=='completed' for r in rows),'matching_current_reference':sum(c['arm']==arm and c['matches_current_reference'] for c in checks)} for arm in sorted({r['arm'] for r in plan})}
result={'planned':len(plan),'observed':len(rows),'unobserved':len(plan)-len(rows),'by_arm':summary,'checks':checks,'reference_sha256':hashlib.sha256(refpath.read_bytes()).hexdigest(),'interpretation':'Current authored schema query membership; asserted ablation and stale snapshot intentionally can differ. Not external truth, human maintenance benefit or general OWL equivalence.'}
(run/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
assert len(rows)==len(plan)
assert all(c['matches_current_reference'] for c in checks if c['arm'] not in ('asserted','stale_base_rdfs'))
