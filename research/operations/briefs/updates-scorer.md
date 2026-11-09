import json,sys,hashlib
from pathlib import Path
out=Path(sys.argv[1]);reference=Path('research/backend-reasoning-review-1/inference-contracts-001/evaluator-only.json')
ref=json.loads(reference.read_text())['expected']
mapping={'initial':'two_supports','delete_primary':'remove_primary','delete_alternate':'remove_both_annotation_supports','restore_paths':'two_supports','delete_fact':'remove_source_edge','restore_fact':'two_supports','delete_schema':'missing_schema','restore_schema':'two_supports'}
plan=json.loads((out/'plan.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()] if (out/'results.jsonl').exists() else []
key=lambda r:(r['event'],r['arm'],r['query_id'])
assert len({key(x) for x in plan})==len(plan)
assert len({key(x) for x in rows})==len(rows)
assert {key(x) for x in rows}<={key(x) for x in plan}
checks=[];byarm={}
for p in plan:
    found=[r for r in rows if key(r)==key(p)]
    row=found[0] if found else {**p,'status':'not_observed'}
    expected=ref[mapping[p['event']]][p['query_id']]
    matched=row['status']=='completed' and row['answer']==expected
    checks.append({**p,'status':row['status'],'matches_current_reference':matched})
    counts=byarm.setdefault(p['arm'],{'planned':0,'completed':0,'matching_current_reference':0})
    counts['planned']+=1;counts['completed']+=row['status']=='completed';counts['matching_current_reference']+=matched
result={'planned':len(plan),'observed':len(rows),'unobserved':len(plan)-len(rows),'by_arm':byarm,'checks':checks,'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),'event_mapping':mapping,'interpretation':'Repeated quiescent authoredchanges on consumed development source IDs, not independent samples, benchmark, LLM answers or fullOWL reasoner comparison.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
assert all(c['completed']==c['planned'] for c in byarm.values())
assert all(c['matching_current_reference']==c['planned'] for a,c in byarm.items() if a not in ('stale_offline','neptune_stale'))
