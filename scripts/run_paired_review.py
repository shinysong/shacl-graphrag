"""Single-launch, failure-nonrefunded-reservation paired review campaign. No gold imports."""
import argparse
import copy
import fcntl
import hashlib
import json
import os
import signal
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from scripts.postreview_messages_v3 import build_messages, validate_draft

ROOT = Path('_workspace/paired-campaign-20261104')
CAP = 162
MONEY = Decimal('10')
OUTPUT = 2048
INPUT_MAX = 32768
TRANSPORT_SECONDS = 180

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()

def sync_dir(p):
    fd=os.open(p, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)

def atomic(p, x):
    tmp = p.with_suffix(p.suffix + '.tmp')
    with tmp.open('wb') as f:
        f.write(canonical(x)); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)
    sync_dir(p.parent)

def strict(s):
    def pairs(items):
        d = {}
        for k,v in items:
            if k in d: raise ValueError('duplicate key')
            d[k] = v
        return d
    return json.loads(s, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))

def now(): return datetime.now(timezone.utc)

def prices(provider):
    p = provider['endpoint']['pricing']
    prompt = Decimal(p['prompt'])
    cache = max([Decimal('0')] + [Decimal(str(v)) for k,v in p.items() if k.startswith('input_cache_write')])
    completion = max(Decimal(p['completion']), Decimal(p.get('internal_reasoning', '0')))
    if any(not v.is_finite() or v < 0 for v in (prompt,cache,completion)): raise ValueError('price')
    if Decimal(str(p.get('request','0'))) != 0: raise ValueError('request surcharge')
    return prompt,cache,completion

def make_payload(messages, provider):
    prompt, _, completion = prices(provider)
    return {'model':provider['model'], 'messages':messages, 'max_tokens':OUTPUT,
            'reasoning':{'effort':'medium','exclude':True}, 'response_format':{'type':'json_object'},
            'provider':{'only':[provider['slug']], 'allow_fallbacks':False, 'require_parameters':True,
                        'max_price':{'prompt':float(prompt*1000000),'completion':float(completion*1000000)}}}

def reservation(messages, provider):
    # Conservative engineering envelope, NOT an exact native token count.
    # Text-only, no tools/schema request field. 4096 extra tokens for framing.
    bound = len(canonical(messages)) + 4096
    if bound > INPUT_MAX: raise ValueError('input_envelope')
    a,b,c = prices(provider)
    return bound, ((a+b)*bound+c*OUTPUT).quantize(Decimal('0.00000001'), rounding='ROUND_UP')

def budget_used(ledger):
    # Successful completed outputs settle at known actual cost; failures never refund.
    return sum((Decimal(a['reported_usd']) if a.get('state')=='resolved' and a.get('status')=='completed' else Decimal(a['reserved_usd']) for a in ledger['attempts']),Decimal(0))

def admit(ledger, slot, amount, instant, deadline):
    if (datetime.fromisoformat(deadline)-instant).total_seconds() <= TRANSPORT_SECONDS+30: raise ValueError('deadline')
    if len(ledger['attempts']) >= CAP: raise ValueError('attempt_cap')
    if any(a['slot_id']==slot for a in ledger['attempts']): raise ValueError('duplicate')
    if any(a['state']!='resolved' for a in ledger['attempts']): raise ValueError('unresolved_cost')
    if budget_used(ledger)+amount > MONEY: raise ValueError('budget')
    item = {'slot_id':slot,'state':'reserved','reserved_usd':str(amount),'reserved_at':instant.isoformat()}
    ledger['attempts'].append(item)
    return item

def assess(data, provider, bound, amount):
    cost=Decimal(str(data.get('usage',{}).get('cost')))
    if not cost.is_finite() or cost<0 or cost>amount: raise ValueError('unresolved_or_excess_cost')
    u=data['usage']
    for key,limit in [('prompt_tokens',bound),('completion_tokens',OUTPUT)]:
        if type(u.get(key)) is not int or not 0<=u[key]<=limit: raise ValueError('usage_envelope')
    reasoning=u.get('completion_tokens_details',{}).get('reasoning_tokens',0)
    if reasoning is not None and (type(reasoning) is not int or not 0<=reasoning<=u['completion_tokens']): raise ValueError('reasoning_envelope')
    if data.get('model')!=provider['model'] or data.get('provider')!=provider['provider']: raise ValueError('route_mismatch')
    choice=data['choices'][0];result={'cost':str(cost),'usage':u,'finish_reason':choice.get('finish_reason'),'status':'output_failure','answer':None}
    if choice.get('finish_reason')!='stop':return result
    try:
        answer=strict(choice['message']['content']);validate_draft(answer)
        result.update(status='completed',answer=answer)
    except (ValueError,TypeError,KeyError):pass
    except Exception as e:
        from jsonschema import ValidationError
        if not isinstance(e,ValidationError):raise
    return result

def validate_config(config):
    if len(config['inputs'])!=9 or len(config['providers'])!=6 or len(config['slots'])!=CAP:raise ValueError('universe')
    if len({q['question_id'] for q in config['inputs']})!=9 or len({p['model'] for p in config['providers']})!=6:raise ValueError('duplicate identities')
    expected={(q['question_id'],p['model'],phase) for q in config['inputs'] for p in config['providers'] for phase in ['draft','self_review','report']}
    actual={(s['question_id'],s['model'],s['phase']) for s in config['slots']}
    if len(actual)!=CAP or len(expected)!=CAP or expected!=actual or len({s['slot_id'] for s in config['slots']})!=CAP:raise ValueError('slot universe')
    seen_drafts=set()
    for slot in config['slots']:
        pair=(slot['question_id'],slot['model'])
        expected_id='|'.join([slot['question_id'],slot['model'],slot['phase']])
        if slot['slot_id']!=expected_id or slot['state']!='not_attempted':raise ValueError('slot identity/state')
        if slot['phase']=='draft':
            if slot['dependency'] is not None:raise ValueError('draft dependency')
            seen_drafts.add(pair)
        elif pair not in seen_drafts or slot['dependency']!='|'.join([*pair,'draft']):raise ValueError('review order/dependency')
    for q in config['inputs']:
        if set(q)!={'question_id','question','context','representation'}:raise ValueError('runtime fields')
        build_messages(q['question'],q['context'],representation=q['representation'])
    for p in config['providers']:
        if not {'max_tokens','reasoning','response_format'}<=set(p['endpoint']['supported_parameters']):raise ValueError('unsupported parameters')
        if p['endpoint'].get('status')!=0 or p['endpoint'].get('tag')!=p['slug']:raise ValueError('endpoint tag/status')
        prices(p)
    return config

def prepare(root=ROOT):
    config=validate_config(strict((root/'config.json').read_text()))
    paths=[Path(__file__),Path('uv.lock')]+list(Path('scripts').glob('postreview*.py'))+[Path('scripts/post_answer_review.py'),root/'config.json',root/'evaluation-protocol.json',root/'evaluation-reference.json']
    freeze={'hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'config_sha256':digest(config),'max_attempts':CAP,'max_usd':str(MONEY),'failed_reservations_nonrefunded':True,'completed_successes_settle_at_actual':True}
    f=root/'freeze.json'
    if f.exists() and strict(f.read_text())!=freeze:raise ValueError('freeze changed')
    atomic(f,freeze)
    return freeze

def execute(config, root, transport, clock=now):
    validate_config(config)
    ledger={'attempts':[],'max_attempts':CAP,'max_usd':str(MONEY),'slots':copy.deepcopy(config['slots']),'stop_reason':None}
    lp=root/'campaign-budget.json'
    # Durable exclusive marker means crashes never silently replay an attempt.
    with lp.open('x') as f:json.dump(ledger,f);f.flush();os.fsync(f.fileno())
    sync_dir(root)
    out=root/'responses';out.mkdir(exist_ok=False);sync_dir(root)
    drafts={};providers={p['model']:p for p in config['providers']};inputs={q['question_id']:q for q in config['inputs']}
    for idx,s in enumerate(ledger['slots']):
        if ledger['stop_reason']:
            s.update(state='not_attempted',reason=ledger['stop_reason']);continue
        q=inputs[s['question_id']];p=providers[s['model']];pair=(s['question_id'],s['model']);phase=s['phase']
        if phase!='draft' and pair not in drafts:
            s.update(state='dependency_not_run',reason='no_valid_original_draft');atomic(lp,ledger);continue
        try:
            draft=copy.deepcopy(drafts.get(pair))
            built=build_messages(q['question'],q['context'],phase,draft,q['representation'])
            bound,amount=reservation(built['messages'],p)
            payload=make_payload(built['messages'],p)
        except Exception as e:
            s.update(state='input_failure',error_type=type(e).__name__);atomic(lp,ledger);continue
        prefix=out/f'{idx:03d}'
        atomic(prefix.with_suffix('.request.json'),payload)
        atomic(prefix.with_suffix('.binding.json'),{'slot_id':s['slot_id'],'original_draft_sha256':digest(draft) if draft is not None else None,'context_sha256':digest(q['context']),'representation':q['representation'],'message_sha256':digest(built['messages']),'input_envelope':bound,'reserved_usd':str(amount)})
        if built['review_artifact'] is not None:atomic(prefix.with_suffix('.report.json'),built['review_artifact'])
        try:item=admit(ledger,s['slot_id'],amount,clock(),config['deadline'])
        except ValueError as e:
            ledger['stop_reason']=str(e);s.update(state='not_attempted',reason=str(e));atomic(lp,ledger);continue
        s['state']='reserved';atomic(lp,ledger)
        try:
            status,body=transport(payload)
            with prefix.with_suffix('.raw.txt').open('wb') as f:f.write(body);f.flush();os.fsync(f.fileno())
            item['http_status']=status
            if status!=200:raise ValueError('http_cost_unresolved')
            result=assess(strict(body),p,bound,amount)
            atomic(prefix.with_suffix('.result.json'),result)
            item.update(state='resolved',reported_usd=result['cost'],status=result['status'],finished_at=clock().isoformat())
            s['state']=result['status']
            if phase=='draft' and result['status']=='completed':drafts[pair]=copy.deepcopy(result['answer'])
        except Exception as e:
            item.update(state='unresolved',error_type=type(e).__name__);s['state']='execution_failure';ledger['stop_reason']='unresolved_attempt'
        atomic(lp,ledger)
        print(json.dumps({'slot':idx,'state':s['state'],'attempts':len(ledger['attempts']),'budget_used':str(budget_used(ledger))}),flush=True)
    atomic(lp,ledger)
    return ledger

def run(root=ROOT):
    import httpx
    from dotenv import dotenv_values
    freeze=strict((root/'freeze.json').read_text())
    for p,h in freeze['hashes'].items():
        if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h:raise ValueError('frozen bytes changed')
    config=strict((root/'config.json').read_text())
    if digest(config)!=freeze['config_sha256']:raise ValueError('config changed')
    # Operator records successful independent review and tests, bound to freeze.
    gate=strict((root/'launch-gate.json').read_text())
    if gate.get('freeze_sha256')!=digest(freeze) or gate.get('decision')!='ready':raise ValueError('launch gate')
    key=dotenv_values('.env').get('OPENROUTER_API_KEY')
    if not key:raise ValueError('credential missing')
    def alarm(*_):raise TimeoutError('wall timeout')
    signal.signal(signal.SIGALRM,alarm)
    with httpx.Client(timeout=TRANSPORT_SECONDS,transport=httpx.HTTPTransport(retries=0),follow_redirects=False) as client:
        def transport(payload):
            signal.alarm(TRANSPORT_SECONDS)
            try:
                r=client.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':'Bearer '+key},json=payload)
                return r.status_code,r.content
            finally:signal.alarm(0)
        return execute(config,root,transport)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','run']);args=ap.parse_args()
    with (ROOT/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        prepare() if args.mode=='prepare' else run()
