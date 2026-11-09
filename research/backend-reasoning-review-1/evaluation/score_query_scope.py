import json,sys
from pathlib import Path
out=Path(sys.argv[1]);plan=json.loads((out/'plan.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()];inputs=json.loads((out/'inputs.json').read_text());expected={(x['row_index'],x['policy']):x for x in inputs}
key=lambda r:(r['row_index'],r['policy'],r['checker']);assert len({key(r) for r in rows})==len(rows);assert {key(r) for r in rows}<={key(r) for r in plan}
parent=Path('research/backend-reasoning-review-1/updates-live-001');ev=json.loads((parent/'evaluation.json').read_text());ref={(x['event'],x['arm'],x['query_id']):x['matches_current_reference'] for x in ev['checks']}
lookup={key(r):r for r in rows};summary={};pairs=[]
for p in plan:
    row=lookup.get(key(p));s=summary.setdefault(p['policy']+'/'+p['checker'],{'planned':0,'completed':0,'review_flags':0,'mismatch_with_review':0,'matching_with_review':0,'mismatch_without_review':0});s['planned']+=1
    if row and row['status']=='completed':
        x=expected[(p['row_index'],p['policy'])];assert row['original_answer']==x['original_answer'] and not row['answer_changed']
        matches=ref[tuple(row['origin'][k] for k in ('event','arm','query_id'))];flag=row['review_requested']
        s['completed']+=1;s['review_flags']+=flag;s['mismatch_with_review']+=not matches and flag;s['matching_with_review']+=matches and flag;s['mismatch_without_review']+=not matches and not flag
for i,p in expected:
    a,b=[lookup.get((i,p,c)) for c in ('python','shacl')];pairs.append(bool(a and b and a['status']==b['status']=='completed' and a['codes']==b['codes']))
result={'planned_checker_slots':len(plan),'observed':len(rows),'pairs':len(pairs),'agreeing_pairs':sum(pairs),'summary':summary,'interpretation':'Derived replay on same160controlledbackendoutputs. Typed query dependency on complete controlled snapshots supplied, not learnedNLunderstanding or sourcecompleteness discovery. Metadataonly/noLLM/veto/repair. Correctflags quantify proxyreviewburden, not actual labor orabstention.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert len(rows)==len(plan) and all(pairs)
