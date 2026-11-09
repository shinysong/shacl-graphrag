"""Bounded, single-launch OpenRouter experiment. No evaluation-reference imports."""
import argparse
import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path('_workspace/answer-campaign-20261103')
INPUT = Path('research/answer-evidence-1/answer-inputs-001/episodes.jsonl')
SCHEMA = Path('research/answer-evidence-1/answer-schema-v1.json')
DEADLINE = '2026-11-03T21:13:15+00:00'
MODEL = 'openai/gpt-4o-mini'
CAP = 72
RESERVE = Decimal('0.01')

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def sha(b):
    return hashlib.sha256(b).hexdigest()

def atomic(path, obj):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('wb') as f:
        f.write(canonical(obj)); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def now():
    return datetime.now(timezone.utc).isoformat()

def strict(s):
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d: raise ValueError('duplicate JSON key')
            d[k] = v
        return d
    return json.loads(s, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def load_inputs():
    rows = [strict(s) for s in INPUT.read_text().splitlines()]
    if len(rows) != CAP or len({r['episode_id'] for r in rows}) != CAP: raise ValueError('universe')
    by = {(r['question_id'], r['arm']): r for r in rows}
    if len(by) != CAP or any(sum(r['arm'] == a for r in rows) != 24 for a in 'BCD'): raise ValueError('arms')
    for r in rows:
        if r['status'] != 'prepared_not_admitted' or sha(canonical(r['messages'])) != r['message_sha256']: raise ValueError('input binding')
        if len(canonical(r['messages'])) + 4096 > 16384: raise ValueError('byte admission bound')
        body = strict(r['messages'][1]['content'])
        if set(body) != {'question', 'evidence', 'validation'}: raise ValueError('runtime fields')
        if r['arm'] in 'BC' and body['validation'] is not None: raise ValueError('report leak')
        if r['arm'] == 'D':
            c = strict(by[r['question_id'], 'C']['messages'][1]['content'])
            if body['evidence'] != c['evidence'] or body['question'] != c['question']: raise ValueError('CD mismatch')
    return rows

def payload(row):
    return dict(model=MODEL, messages=row['messages'], temperature=0, seed=20261103,
                max_tokens=2048, response_format={'type':'json_object'},
                provider={'only':['openai'], 'allow_fallbacks':False, 'require_parameters':True,
                          'max_price':{'prompt':0.15, 'completion':0.6}})

def reserve(ledger, episode_id, instant):
    if datetime.fromisoformat(instant) >= datetime.fromisoformat(DEADLINE): raise ValueError('deadline')
    if len(ledger['attempts']) >= CAP or any(a['episode_id'] == episode_id for a in ledger['attempts']): raise ValueError('attempt cap or duplicate')
    if any(a['state'] != 'resolved' for a in ledger['attempts']): raise ValueError('unresolved prior attempt')
    amount = sum((Decimal(a['reserved_usd']) for a in ledger['attempts']), Decimal(0)) + RESERVE
    if amount > Decimal('1'): raise ValueError('cost cap')
    item = dict(episode_id=episode_id, reserved_at=instant, reserved_usd=str(RESERVE), state='reserved', reported_usd=None)
    ledger['attempts'].append(item)
    return item

def assess(data, schema):
    import jsonschema
    usage = data.get('usage', {})
    cost = Decimal(str(usage.get('cost')))
    if not cost.is_finite() or cost < 0 or cost > RESERVE: raise ValueError('unresolved or excess cost')
    if data.get('provider') != 'OpenAI' or data.get('model') != MODEL: raise ValueError('provider/model mismatch')
    if not isinstance(usage.get('prompt_tokens'), int) or not isinstance(usage.get('completion_tokens'), int): raise ValueError('missing token usage')
    if not 0 <= usage['prompt_tokens'] <= 16384 or not 0 <= usage['completion_tokens'] <= 2048: raise ValueError('token bound')
    choice = data['choices'][0]
    result = dict(reported_usd=str(cost), usage=usage, status='schema_error', answer=None)
    if choice.get('finish_reason') == 'length': result['status'] = 'truncated'; return result
    if choice.get('finish_reason') != 'stop': result['status'] = 'provider_failure'; return result
    try:
        answer = strict(choice['message']['content'])
        jsonschema.validate(answer, schema)
        result.update(status='completed', answer=answer)
    except (ValueError, TypeError, KeyError, jsonschema.ValidationError): pass
    return result

def preflight():
    import tiktoken
    rows = load_inputs()
    enc = tiktoken.get_encoding('o200k_base')
    tokens = [3 + sum(3 + sum(len(enc.encode(v)) for v in m.values()) for m in r['messages']) for r in rows]
    if max(tokens) + 512 > 16384: raise ValueError('token admission')
    frozen = dict(model=MODEL, deadline=DEADLINE, max_attempts=CAP, max_usd='1', reservation_per_attempt=str(RESERVE),
                  input_cap=16384, output_cap=2048, tokenizer='tiktoken==0.12.0/o200k_base',
                  chat_token_estimates=tokens, token_count_is_estimate=True,
                  hashes={str(p):sha(p.read_bytes()) for p in [INPUT, SCHEMA, Path(__file__), ROOT/'protocol.json']},
                  episode_order=[r['episode_id'] for r in rows], payload_settings={k:v for k,v in payload(rows[0]).items() if k!='messages'})
    p=ROOT/'freeze.json'
    if p.exists():
        if strict(p.read_text()) != frozen: raise ValueError('freeze changed')
    else: atomic(p, frozen)
    print(json.dumps(dict(prepared=len(rows), min_tokens=min(tokens), max_tokens=max(tokens), paid_calls=0)))

def run():
    import httpx
    from dotenv import dotenv_values
    frozen = strict((ROOT/'freeze.json').read_text())
    for p,h in frozen['hashes'].items():
        if sha(Path(p).read_bytes()) != h: raise ValueError('frozen hash changed')
    rows = load_inputs()
    if [r['episode_id'] for r in rows] != frozen['episode_order']: raise ValueError('order changed')
    key = dotenv_values('.env').get('OPENROUTER_API_KEY')
    if not key: raise ValueError('missing credential')
    schema = strict(SCHEMA.read_text())
    ledger_path=ROOT/'campaign-budget.json'
    # Exclusive launch marker: interruption never silently resumes or replays a call.
    with ledger_path.open('x') as f:
        json.dump(dict(attempts=[], max_attempts=CAP, max_usd='1'), f); f.flush(); os.fsync(f.fileno())
    ledger = strict(ledger_path.read_text())
    (ROOT/'responses').mkdir(exist_ok=False)
    with httpx.Client(timeout=45, transport=httpx.HTTPTransport(retries=0), follow_redirects=False) as client:
        for row in rows:
            item=reserve(ledger,row['episode_id'],now())
            atomic(ledger_path,ledger)
            out=ROOT/'responses'/row['episode_id']
            atomic(out.with_suffix('.request.json'),payload(row))
            try:
                response=client.post('https://openrouter.ai/api/v1/chat/completions',headers={'Authorization':'Bearer '+key},json=payload(row))
                out.with_suffix('.raw.txt').write_bytes(response.content)
                item['http_status']=response.status_code
                if response.status_code != 200: raise ValueError('HTTP failure; billing unresolved')
                result=assess(strict(response.text),schema)
                atomic(out.with_suffix('.result.json'),result)
                item.update(state='resolved',reported_usd=result['reported_usd'],status=result['status'],finished_at=now())
            except Exception as exc:
                item.update(state='unresolved', error_type=type(exc).__name__, finished_at=now())
                atomic(ledger_path,ledger)
                print(json.dumps({'stopped':row['episode_id'],'error_type':type(exc).__name__}),flush=True)
                raise SystemExit(2)
            atomic(ledger_path,ledger)
            print(json.dumps({'episode':row['episode_id'],'status':item['status'],'attempts':len(ledger['attempts']),
                              'reported_usd':str(sum(Decimal(a['reported_usd']) for a in ledger['attempts']))}),flush=True)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=['preflight','run']); args=parser.parse_args()
    ROOT.mkdir(exist_ok=True,parents=True)
    with (ROOT/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        preflight() if args.mode=='preflight' else run()
