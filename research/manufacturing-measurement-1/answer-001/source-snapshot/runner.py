"""Single-launch 18-slot extension of the existing $15/180 nonrefunded ledger."""
import json,sys,hashlib,fcntl,signal
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path('scripts').resolve()))
import run_source_semantics as base
import checker
ROOT=Path(__file__).resolve().parent
LEDGER=Path('_workspace/schema-management-20261106/campaign-budget.json')
DEADLINE='2026-11-07T23:12:55+00:00'
ARMS=('draft','self_review','shacl_review')

def plan(providers):
 slots=[{'id':f'measurement-answer-001|draft|{p["model"]}','model':p['model'],'arm':'draft'} for p in providers]
 for i,p in enumerate(providers):
  for arm in (ARMS[1:] if i%2==0 else ARMS[1:][::-1]):slots.append({'id':f'measurement-answer-001|{arm}|{p["model"]}','model':p['model'],'arm':arm})
 return slots

def messages(inp,arm,draft=None,report=None):
 body={k:inp[k] for k in ('question_id','question','evidence')}
 system=inp['system']
 if arm!='draft':
  system+='\n'+inp['review_instruction'];body['saved_draft']=draft
  if arm=='shacl_review':body['advisory_report']=report
 return [{'role':'system','content':system},{'role':'user','content':base.canonical(body).decode()}]

def assess(data,provider,bound,reserved):
 result=base.assess(data,provider,bound,reserved) # Reuse only billing/routing/usage and strict JSON structural parsing.
 result['status']='completed' if result['finish_reason']=='stop' and checker.structural(result['contract']) else 'output_failure'
 return result

def preflight():
 inp=base.strict((ROOT/'input.json').read_text());providers=base.strict((ROOT/'providers.json').read_text());slots=plan(providers)
 if len(providers)!=6 or len({p['model'] for p in providers})!=6 or len(slots)!=18:raise ValueError('universe')
 ledger=base.strict(LEDGER.read_text())
 if ledger['attempts']!=162 or len(ledger['reservations'])!=162 or any(x['state']!='resolved' for x in ledger['reservations']):raise ValueError('initial_ledger_state')
 if ledger['authorized_usd']!=15 or ledger['attempt_cap']!=180:raise ValueError('authorization_binding')
 amounts=[]
 for p in providers:
  e=p['endpoint']
  if e['status']!=0 or e['tag']!=p['slug'] or not {'max_tokens','reasoning','response_format'}<=set(e['supported_parameters']):raise ValueError('endpoint')
  if e['context_length']<base.INPUT_CAP+base.OUTPUT_CAP:raise ValueError('context_limit')
  if e.get('max_completion_tokens') is not None and e['max_completion_tokens']<base.OUTPUT_CAP:raise ValueError('output_limit')
  if any(x.get('min_prompt_tokens',0)<=base.INPUT_CAP for x in e['pricing'].get('overrides',[])):raise ValueError('unhandled_price_tier')
  a,b,c=base.prices(p);amounts.append(3*((a+b)*base.INPUT_CAP+c*base.OUTPUT_CAP))
  base.reserve(messages(inp,'draft'),p)
 if base.used(ledger)+sum(amounts)>base.USD_CAP:raise ValueError('worst_case_budget')
 return inp,providers,slots,{'new_attempt_cap':18,'existing_attempts':162,'worst_case_additional_reserved_usd':str(sum(amounts)),'existing_used_usd':str(base.used(ledger)),'input_byte_envelope_cap':base.INPUT_CAP,'output_token_cap':base.OUTPUT_CAP,'native_tokenizer_measured':False}

def run():
 import httpx
 from dotenv import dotenv_values
 with (LEDGER.parent/'campaign.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  freeze=base.strict((ROOT/'freeze.json').read_text())
  for path,sha in freeze['hashes'].items():
   if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('frozen_file_changed')
  gate=base.strict((ROOT/'launch-gate.json').read_text())
  if gate.get('decision')!='ready' or gate['freeze_sha256']!=hashlib.sha256(base.canonical(freeze)).hexdigest():raise ValueError('review_gate')
  inp,providers,slots,estimate=preflight();provider_map={p['model']:p for p in providers}
  if datetime.now(timezone.utc)>=datetime.fromisoformat(DEADLINE):raise ValueError('deadline')
  key=dotenv_values('.env').get('OPENROUTER_API_KEY')
  if not key:raise ValueError('credential_missing')
  with (ROOT/'started.json').open('x') as f:json.dump({'at':datetime.now(timezone.utc).isoformat(),'deadline':DEADLINE},f)
  output=ROOT/'responses';output.mkdir(exist_ok=False)
  states=[{**s,'state':'not_attempted'} for s in slots];base.atomic(ROOT/'states.json',states);base.atomic(ROOT/'plan.json',slots);base.atomic(ROOT/'preflight.json',estimate)
  ledger=base.strict(LEDGER.read_text());drafts={};reports={};stop=None
  def alarm(*_):raise TimeoutError('transport_wall_timeout')
  signal.signal(signal.SIGALRM,alarm)
  with httpx.Client(timeout=base.TIMEOUT,transport=httpx.HTTPTransport(retries=0),follow_redirects=False) as client:
   for index,state in enumerate(states):
    if stop:state['reason']=stop;continue
    model,arm=state['model'],state['arm'];provider=provider_map[model];prefix=output/f'{index:03d}'
    try:
     if arm!='draft' and model not in drafts:raise ValueError('missing_original_draft')
     if arm=='shacl_review' and model not in reports:
      draft=drafts[model];report,g,rg=checker.report(draft['parsed_response'],inp['checker_context']);reports[model]=report
      base.atomic(prefix.with_suffix('.advisory.json'),report)
      if g is not None:g.serialize(destination=str(prefix.with_suffix('.data.ttl')),format='turtle');rg.serialize(destination=str(prefix.with_suffix('.report.ttl')),format='turtle')
     msg=messages(inp,arm,drafts.get(model),reports.get(model));bound,amount=base.reserve(msg,provider);request=base.payload(msg,provider)
     base.atomic(prefix.with_suffix('.request.json'),request)
     reservation=base.admit(ledger,state['id'],amount,datetime.now(timezone.utc),DEADLINE)
    except Exception as error:
     stop='precall_'+type(error).__name__;state.update(reason=stop,error=str(error));continue
    ledger['status']='active';base.atomic(LEDGER,ledger);state['state']='reserved';base.atomic(ROOT/'states.json',states)
    try:
     signal.alarm(base.TIMEOUT)
     try:
      raw=bytearray()
      with client.stream('POST','https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':'Bearer '+key},json=request) as response:
       reservation['http_status']=response.status_code
       for chunk in response.iter_bytes():
        if len(raw)+len(chunk)>2000000:raise ValueError('response_size')
        raw.extend(chunk)
      prefix.with_suffix('.raw.txt').write_bytes(raw)
     finally:signal.alarm(0)
     if reservation['http_status']!=200:raise ValueError('http_cost_unresolved')
     data=base.strict(raw);result=assess(data,provider,bound,amount);base.atomic(prefix.with_suffix('.result.json'),result)
     reservation.update(state='resolved',status=result['status'],reported_usd=result['reported_usd']);state['state']=result['status']
     if arm=='draft':drafts[model]={'completion_status':result['status'],'finish_reason':result['finish_reason'],'parsed_response':result['contract'],'visible_text':data['choices'][0]['message'].get('content')}
    except Exception as error:
     reservation.update(state='unresolved',error_type=type(error).__name__);state.update(state='execution_failure',error_type=type(error).__name__);stop='unresolved_attempt'
    ledger['reserved_nonrefunded_usd']=str(base.used(ledger));ledger['reported_cost_usd']=str(sum((base.Decimal(x.get('reported_usd','0')) for x in ledger['reservations']),base.Decimal(0)))
    base.atomic(LEDGER,ledger);base.atomic(ROOT/'states.json',states)
    print(json.dumps({'slot':index,'arm':arm,'state':state['state'],'campaign_attempts':ledger['attempts'],'budget_used':str(base.used(ledger))}),flush=True)
  ledger.update(status='stopped' if stop else 'phase_complete',stop_reason=stop);base.atomic(LEDGER,ledger);base.atomic(ROOT/'states.json',states)
if __name__=='__main__':
 if '--preflight' in sys.argv:print(json.dumps(preflight()[3],indent=2))
 else:run()
