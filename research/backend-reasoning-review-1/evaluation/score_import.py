import json,sys
from pathlib import Path
out=Path(sys.argv[1]);plan=json.loads((out/'plan.json').read_text());cases={c['id']:c for c in json.loads((out/'cases.json').read_text())}
rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()] if (out/'results.jsonl').exists() else []
key=lambda x:(x['case'],x['operation'])
assert len({key(x) for x in rows})==len(rows)
assert {key(x) for x in rows}<={key(x) for x in plan}
ref=json.loads(Path('research/backend-reasoning-review-1/inference-contracts-001/evaluator-only.json').read_text())['expected']
checks=[]
for p in plan:
    row=next((r for r in rows if key(r)==key(p)),{**p,'status':'not_observed'})
    check={**p,'status':row['status']}
    if row['status']=='completed':
        if p['operation'].endswith('roundtrip'):
            expected={tuple(t) for t in cases[p['case']]['triples']};observed={tuple(t) for t in row['triples']}
            check.update(input_triples=len(expected),output_triples=len(observed),missing=sorted(expected-observed),extra=sorted(observed-expected),exact_terms=expected==observed)
        else:
            variant='missing_schema' if p['case']=='hierarchy-missing-schema' else 'base'
            check['matches_current_reference']=row['answer']==ref[variant][p['operation']]
    checks.append(check)
result={'planned':len(plan),'observed':len(rows),'completed':sum(r['status']=='completed' for r in rows),'unobserved':len(plan)-len(rows),'checks':checks,'interpretation':'Small configured RDF-to-LPG import/export diagnostic. Exact URI/literal-term comparison for this bundle only, no general invertibility/performance/QA claim. Authored fixtures separate from source projection.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({**{k:v for k,v in result.items() if k!='checks'},'checks':[{k:v for k,v in c.items() if k not in ('missing','extra')} for c in checks]},indent=2))
