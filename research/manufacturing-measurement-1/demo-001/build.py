"""Offline replay builder; reads saved artifacts only, never calls a model or DB."""
import json,hashlib
from pathlib import Path
from decimal import Decimal
ARMS={'draft','self_review','shacl_review'}
def bundle(run):
 run=Path(run);plan=json.loads((run/'plan.json').read_text());states=json.loads((run/'states.json').read_text());providers=json.loads((run/'providers.json').read_text());models=[p['model'] for p in providers]
 expected={(m,a) for m in models for a in ARMS}
 if len(models)!=6 or len(set(models))!=6 or len(plan)!=18 or len(states)!=18 or {(r['model'],r['arm']) for r in plan}!=expected:raise ValueError('plan_universe')
 rows=[]
 for i,(slot,state) in enumerate(zip(plan,states)):
  if any(slot[k]!=state.get(k) for k in ('id','model','arm')):raise ValueError('state_binding')
  row={k:state[k] for k in ('id','model','arm','state')};prefix=run/'responses'/f'{i:03d}'
  if prefix.with_suffix('.request.json').exists():
   req=json.loads(prefix.with_suffix('.request.json').read_text())
   if req['model']!=slot['model']:raise ValueError('request_binding')
  if prefix.with_suffix('.result.json').exists():
   r=json.loads(prefix.with_suffix('.result.json').read_text());raw=json.loads(prefix.with_suffix('.raw.txt').read_text())
   if raw['model']!=slot['model'] or r['status']!=state['state']:raise ValueError('response_binding')
   row.update(visible_text=raw['choices'][0]['message'].get('content'),reported_usd=r['reported_usd'],finish_reason=r['finish_reason'])
  if prefix.with_suffix('.advisory.json').exists():row['advisory']=json.loads(prefix.with_suffix('.advisory.json').read_text())
  rows.append(row)
 diagnosis=json.loads(Path('research/manufacturing-measurement-1/diagnostic-001/diagnostic.json').read_text())
 return {'models':models,'rows':rows,'diagnostic':diagnosis,'summary':{'planned':18,'states':{s:sum(r['state']==s for r in rows) for s in sorted({r['state'] for r in rows})},'reported_cost_usd':str(sum((Decimal(r.get('reported_usd','0')) for r in rows),Decimal(0))),'source_run':str(run),'source_plan_sha256':hashlib.sha256((run/'plan.json').read_bytes()).hexdigest(),'native_tokenizer_measured':False,'four_field_score_is_not_whole_answer_truth':True}}
def build(run,out):
 data=bundle(run);template=Path(__file__).with_name('template.html').read_text()
 if template.count('__BUNDLE__')!=1:raise ValueError('template_marker')
 encoded=json.dumps(data,ensure_ascii=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
 out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(template.replace('__BUNDLE__',encoded));return data
if __name__=='__main__':
 import sys
 print(build(sys.argv[1],sys.argv[2])['summary'])
