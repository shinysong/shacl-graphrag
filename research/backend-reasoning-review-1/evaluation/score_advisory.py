import json,sys
from pathlib import Path
out=Path(sys.argv[1]);inputs=json.loads((out/'inputs.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()];plan=json.loads((out/'plan.json').read_text())
key=lambda r:(r['id'],r['policy']);assert len({key(r) for r in rows})==len(rows);assert {key(r) for r in rows}<={key(r) for r in plan}
lookup={key(r):r for r in rows};evaluation=json.loads(Path('research/backend-reasoning-review-1/updates-live-001/evaluation.json').read_text());reference={(x['event'],x['arm'],x['query_id']):x['matches_current_reference'] for x in evaluation['checks']}
summary={};checks=[]
for x in inputs:
    truth=reference[tuple(x['origin'][k] for k in ('event','arm','query_id'))]
    pair=[lookup.get((x['id'],p)) for p in ('python','shacl')]
    same=all(r and r['status']=='completed' for r in pair) and pair[0]['codes']==pair[1]['codes']
    checks.append({'id':x['id'],'cohort':x['cohort'],'policy_agreement':same,'source_query_set_matches_reference':truth})
    for policy,row in zip(('python','shacl'),pair):
        s=summary.setdefault(x['cohort']+'/'+policy,{'planned':0,'completed':0,'reports_requesting_review':0,'query_set_mismatch_with_review':0,'matching_query_set_with_review':0,'query_set_mismatch_without_review':0})
        s['planned']+=1
        if row and row['status']=='completed':
            s['completed']+=1;s['reports_requesting_review']+=row['review_requested']
            s['query_set_mismatch_with_review']+=not truth and row['review_requested']
            s['matching_query_set_with_review']+=truth and row['review_requested']
            s['query_set_mismatch_without_review']+=not truth and not row['review_requested']
            assert row['original_answer']==x['original_answer'] and row['answer_changed'] is False
result={'planned_checker_slots':len(plan),'observed_checker_slots':len(rows),'unobserved':len(plan)-len(rows),'policy_pairs':len(inputs),'agreeing_pairs':sum(x['policy_agreement'] for x in checks),'summary':summary,'checks':checks,'interpretation':'Offline replay, same metadata policy, no new answers or model calls. Version warning is not factual-error finding. Query-set matches use consumed authored reference; not external truth. Matching outputs flagged are review burden, not actual abstention because no veto. Authored metadata controls separate.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
assert len(rows)==len(plan) and all(x['policy_agreement'] for x in checks)
