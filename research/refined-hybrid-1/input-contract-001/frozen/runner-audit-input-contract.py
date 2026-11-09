import hashlib,json,shutil,importlib.metadata
from pathlib import Path
from tokenizers import Tokenizer
from scripts.graphrag_input_contract import prepare_bundle,account_bundle,ARMS
from scripts.graphrag_check import canonical_bytes
paths={'questions':'research/graphrag-evidence-1/development-questions.json',
'A1':'research/vector-refinement-1/run-001/A1.jsonl',
'B':'research/refined-hybrid-1/retrieval-001/retrieval.jsonl',
'C':'research/refined-hybrid-1/relation-001/C.jsonl',
'E':'research/refined-hybrid-1/relation-001/E.jsonl',
'D':'research/refined-hybrid-1/shacl-binding-001/results.jsonl',
'code':'scripts/graphrag_input_contract.py','parser':'scripts/graphrag_check.py','tests':'tests/test_graphrag_input_contract.py',
'tokenizer':'_workspace/graphrag-cycle3/sources/e5-tokenizer.json','runner':__file__}
hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths.values()}
out=Path('research/refined-hybrid-1/input-contract-001');out.mkdir(exist_ok=False)
rows=[];summary={'status':'failed','planned_questions':24,'planned_arm_inputs':120,'generation_executed':False,'generator_ready':False,'accounting':'pinned E5 on complete serialized proposed messages, not provider chat framing'}
try:
 assert importlib.metadata.version('tokenizers')=='0.22.1'
 t=Tokenizer.from_file(paths['tokenizer']);t.no_padding();t.no_truncation()
 questions=json.loads(Path(paths['questions']).read_text())['questions'];assert len(questions)==24
 inputs={a:[json.loads(x) for x in Path(paths[a]).read_text().splitlines()] for a in ARMS}
 qids=[q['question_id'] for q in questions];assert len(set(qids))==24
 for a,items in inputs.items():assert [x['question_id'] for x in items]==qids
 (out/'frozen').mkdir()
 for key,p in paths.items():shutil.copyfile(p,out/'frozen'/(key+'-'+Path(p).name))
 (out/'manifest.json').write_text(json.dumps({'paths':paths,'hashes':hashes,'tokenizers':'0.22.1','token_cap':4096,'byte_cap':64000},indent=2))
 for i,q in enumerate(questions):
  row={'question_id':q['question_id'],'status':'error'}
  try:
   d=inputs['D'][i];assert d['status']=='ok' and d['evidence']==inputs['C'][i]
   r=d['report'];assert r['parity'] and r['results']==r['python_results']
   report={k:v for k,v in r.items() if k not in ('parity','python_results')}
   envelopes={a:(d['evidence'] if a=='D' else inputs[a][i]) for a in ARMS}
   messages=prepare_bundle(q,envelopes,report)
   result=account_bundle(messages,lambda text:len(t.encode(text).ids))
   for a in ARMS:
    raw=canonical_bytes(messages[a]);p=out/(q['question_id']+'.'+a+'.messages.json');p.write_bytes(raw)
    assert hashlib.sha256(p.read_bytes()).hexdigest()==result['arms'][a]['sha256']
   row.update(status='ok',accounting=result)
  except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
  rows.append(row);(out/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 for p,h in hashes.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
 good=[r for r in rows if r['status']=='ok']
 summary.update(status='completed' if len(good)==24 else 'partial_failure',ok_questions=len(good),failed_questions=24-len(good),
  all_arms_within_cap=sum(r['accounting']['all_arms_within_accounting_cap'] for r in good),
  arms={a:{'within_cap':sum(r['accounting']['arms'][a]['within_accounting_cap'] for r in good),
           'over_cap':sum(not r['accounting']['arms'][a]['within_accounting_cap'] for r in good),
           'max_tokens':max((r['accounting']['arms'][a]['tokens'] for r in good),default=None)} for a in ARMS})
except Exception as exc:summary['error']=f'{type(exc).__name__}: {exc}';raise
finally:
 summary.update(processed_questions=len(rows),unprocessed_questions=24-len(rows))
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
