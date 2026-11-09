# Saved result demo builder followup
Fix previous review warning. Scope saved artifacts only; no DB/model execution. CurrentScope now labels savedrun basename only, neveractualexecutionfromcounts. Validate full expectedbackend/question matrix18or36 plusuniqueness. Create ignoredoutputdirectory. Full template, imports anddata omitted/unverified. Existing reviewed template unchanged. Plan checks: expected36 and18 rebuild; mutated36unexpectedbackend rejects; duplicatepair rejects; browserall36selections,etc. No clean-checkout full experiment claim. Command from repo root: PYTHONPATH=. uv run --locked python research/manufacturing-answer-trace-1/demo-001/build.py research/manufacturing-answer-trace-1/manufacturing-v2-20261107-001. Browser command requires uv run --locked --with playwright python research/manufacturing-answer-trace-1/demo-001/check.py. Allsourceartifactsrequired, no externalservices.
```python
import json,datetime as dt,sys
from pathlib import Path
from scripts.manufacturing_evidence_cards import package
from scripts.manufacturing_obligation_coverage import coverage
root=Path('research/manufacturing-answer-trace-1')
run=Path(sys.argv[1]) if len(sys.argv)>1 else root/'projection-offline-001'
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()]
old=[r for r in rows(Path('research/backend-reasoning-review-1/live-001/results.jsonl')) if r['case_id']!='BGP_REUSE']
current=rows(run/'results.jsonl');contracts=json.loads((root/'coverage-design-001/contracts.json').read_text())
assert len(old)==36 and len(current) in (18,36)
assert len({(r['backend'],r['case_id']) for r in current})==len(current)
expected_backends={'sqlite_python','rdflib_offline'} if len(current)==18 else {'sqlite_python','rdflib_offline','neo4j_cypher','neptune_sparql'}
expected={(backend,'Q'+str(i)) for backend in expected_backends for i in range(1,10)}
if {(r['backend'],r['case_id']) for r in current}!=expected:raise ValueError('unexpected_backend_question_matrix')
q=json.loads(Path('research/backend-reasoning-review-1/design-001/question-map.json').read_text())['types']
cards=[package(r) for r in current];cov=[coverage(r,contracts['questions'][r['case_id']]) for r in current]
d={'questions':q,'old':old,'current':current,'cards':cards,'contracts':contracts,'oldCoverage':[coverage(r,contracts['questions'][r['case_id']]) for r in old],
'currentCoverage':cov,'adapters':rows(root/'replay-001/results.jsonl'),'queries':json.loads((root/'projection-v2/runtime-queries.json').read_text()),
'currentScope':'저장된 후속 결과: '+run.name,'builtAt':dt.datetime.now(dt.timezone.utc).isoformat()}
d['identityResults']=json.loads(Path('research/manufacturing-identity-1/run-001/results.json').read_text())
d['identityFields']=json.loads(Path('research/manufacturing-identity-1/run-001/identity-fields.json').read_text())
modelroot=Path('research/manufacturing-model-change-1/projection-001')
d['modelComparison']=json.loads((modelroot/'comparison.json').read_text())
d['modelSnapshots']=[{k:v for k,v in json.loads((modelroot/f'snapshot-{i}.json').read_text()).items() if k!='nodes'} for i in (0,1)]
impactroot=Path('research/manufacturing-model-change-1/read-scope-001')
d['impactSummary']=json.loads((impactroot/'summary.json').read_text())
impactrows=json.loads((impactroot/'rows.json').read_text())
categories=[('다른 노드만 바뀐 경우',lambda r:not r['answer_changed'] and not r['flags']['node_projected_fields']),('같은 노드의 다른 필드가 바뀐 경우',lambda r:not r['answer_changed'] and r['flags']['node_projected_fields']),('질문이 읽는 값이 바뀐 경우',lambda r:r['answer_changed'] and r['before']['status']=='defined' and r['after']['status']=='defined'),('새 파일에 정의가 추가된 경우',lambda r:r['before']['status']!='defined' and r['after']['status']=='defined'),('새 파일에서 정의가 빠진 경우',lambda r:r['before']['status']=='defined' and r['after']['status']!='defined')]
d['scopeExamples']=[{'label':label,'row':next(r for r in impactrows if pred(r))} for label,pred in categories]
workspace=Path('_workspace/manufacturing-continuation-20261107');workspace.mkdir(parents=True,exist_ok=True);(workspace/'demo-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
html=(Path(__file__).with_name('template.html')).read_text().replace('__DATA__',json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
Path('docs/experiments/seminar/manufacturing-trace.html').write_text(html)
print({'current_slots':len(current),'html_bytes':len(html.encode()),'path':'docs/experiments/seminar/manufacturing-trace.html'})

```