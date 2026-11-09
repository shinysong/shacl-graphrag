"""Posthoc version comparison on consumed authored inputs, never runtime repair."""
import json, sys
from pathlib import Path
from scripts.check_backend_evidence import coverage
out=Path(sys.argv[1]); inputs=json.loads((out/'inputs.json').read_text());plan=json.loads((out/'plan.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()];coverage(plan,rows,('id','checker'))
lookup={(r['id'],r['checker']):r for r in rows};old=Path('research/backend-reasoning-review-1/advisory-replay-001');oldrows=[json.loads(x) for x in (old/'results.jsonl').read_text().splitlines()];oldlookup={(r['id'],r['policy']):r for r in oldrows}
pairs=[];unchanged=0
for x in inputs:
 a,b=[lookup[(x['id'],c)] for c in ('python','shacl')];both=a['status']==b['status']=='completed';reject=a['status']==b['status']=='input_rejected' and a['error']==b['error'];agree=both and a['codes']==b['codes'];pairs.append({'id':x['id'],'completed_pair':both,'code_agreement':agree,'shared_rejection':reject})
 for r in (a,b):
  assert r['answer_changed'] is False
  if 'original_answer' in x:assert r['original_answer']==x['original_answer'] and r['original_status']==x['original_status']
 if x['parent_run']=='advisory-replay-001':
  unchanged+=all(r['status']=='completed' and r['codes']==oldlookup[(x['parent_id'],r['checker'])]['codes'] for r in (a,b))
result={'planned':len(plan),'observed':len(rows),'completed':sum(r['status']=='completed' for r in rows),'input_rejected':sum(r['status']=='input_rejected' for r in rows),'checker_failures':sum(r['status']=='checker_failure' for r in rows),'pairs':len(pairs),'completed_pairs':sum(p['completed_pair'] for p in pairs),'agreeing_completed_pairs':sum(p['code_agreement'] for p in pairs),'shared_rejected_pairs':sum(p['shared_rejection'] for p in pairs),'unchanged_old_pairs':unchanged,'checks':pairs,'scope':'Post-observation contract revision on consumed inputs, no general arbitraryinput parity or QA efficacy; shared input rejections not SHACL conformance.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
assert all(p['code_agreement'] or p['shared_rejection'] for p in pairs)
