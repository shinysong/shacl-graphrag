"""One-launch bounded source-semantics metadata diagnostic; no gold imports."""
import argparse
import fcntl
import hashlib
import json
import os
import signal
from datetime import datetime, timezone
from decimal import Decimal, ROUND_UP
from pathlib import Path

ROOT = Path('_workspace/schema-management-20261106')
OUTPUT_CAP = 2048
INPUT_CAP = 32768
TIMEOUT = 180
USD_CAP = Decimal('15')
ATTEMPT_CAP = 180


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(value):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))


def atomic(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('wb') as handle:
        handle.write(canonical(value)); handle.flush(); os.fsync(handle.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def prices(provider):
    price = provider['endpoint']['pricing']
    a = Decimal(price['prompt'])
    b = max([Decimal('0')] + [Decimal(str(v)) for k, v in price.items() if k.startswith('input_cache_write')])
    c = max(Decimal(price['completion']), Decimal(price.get('internal_reasoning', '0')))
    if any(not v.is_finite() or v < 0 for v in (a, b, c)) or Decimal(str(price.get('request', '0'))) != 0:
        raise ValueError('unsupported_pricing')
    return a, b, c


def reserve(messages, provider):
    bound = len(canonical(messages)) + 4096  # Conservative text envelope, not a native tokenizer measurement.
    if bound > INPUT_CAP:
        raise ValueError('input_envelope')
    a, b, c = prices(provider)
    return bound, ((a+b)*bound+c*OUTPUT_CAP).quantize(Decimal('.00000001'), rounding=ROUND_UP)


def payload(messages, provider):
    a, _, c = prices(provider)
    return {'model': provider['model'], 'messages': messages, 'max_tokens': OUTPUT_CAP,
            'reasoning': {'effort': 'medium', 'exclude': True}, 'response_format': {'type': 'json_object'},
            'provider': {'only': [provider['slug']], 'allow_fallbacks': False, 'require_parameters': True,
                         'max_price': {'prompt': float(a*1000000), 'completion': float(c*1000000)}}}


def used(ledger):
    return sum((Decimal(r['reported_usd']) if r.get('state') == 'resolved' and r.get('status') == 'completed'
                else Decimal(r['reserved_usd']) for r in ledger['reservations']), Decimal('0'))


def admit(ledger, slot_id, amount, now, deadline):
    if len(ledger['reservations']) >= ATTEMPT_CAP or ledger['attempts'] != len(ledger['reservations']):
        raise ValueError('attempt_cap_or_ledger_mismatch')
    if any(r['state'] != 'resolved' for r in ledger['reservations']):
        raise ValueError('unresolved_previous_attempt')
    if any(r['slot_id'] == slot_id for r in ledger['reservations']):
        raise ValueError('duplicate_attempt')
    if used(ledger) + amount > USD_CAP:
        raise ValueError('budget_cap')
    if (datetime.fromisoformat(deadline) - now).total_seconds() <= TIMEOUT+30:
        raise ValueError('deadline')
    row = {'slot_id': slot_id, 'state': 'reserved', 'reserved_usd': str(amount), 'reserved_at': now.isoformat()}
    ledger['reservations'].append(row); ledger['attempts'] += 1
    return row


def assess(data, provider, bound, reserved):
    usage = data.get('usage', {})
    cost = Decimal(str(usage.get('cost')))
    if not cost.is_finite() or cost < 0 or cost > reserved:
        raise ValueError('unresolved_or_excess_cost')
    for field, cap in [('prompt_tokens', bound), ('completion_tokens', OUTPUT_CAP)]:
        if type(usage.get(field)) is not int or not 0 <= usage[field] <= cap:
            raise ValueError('usage_envelope')
    reasoning = usage.get('completion_tokens_details', {}).get('reasoning_tokens', 0)
    if reasoning is not None and (type(reasoning) is not int or not 0 <= reasoning <= usage['completion_tokens']):
        raise ValueError('reasoning_envelope')
    if data.get('model') != provider['model'] or data.get('provider') != provider['provider']:
        raise ValueError('route_mismatch')
    choice = data['choices'][0]
    result = {'status': 'output_failure', 'reported_usd': str(cost), 'usage': usage,
              'finish_reason': choice.get('finish_reason'), 'contract': None}
    if choice.get('finish_reason') == 'stop':
        try:
            contract = strict(choice['message']['content'])
            # Structural validity only. Valid-but-wrong classifications remain completed outcomes.
            if isinstance(contract, dict):
                result['contract'] = contract
            if (isinstance(contract, dict) and set(contract) == {'classification', 'basis'}
                    and isinstance(contract['classification'], str)
                    and contract['classification'] in {'required', 'optional', 'excluded', 'explicit_empty',
                        'reported_nonempty', 'unknown', 'established', 'not_established'}
                    and isinstance(contract['basis'], str) and bool(contract['basis'].strip())):
                result.update(status='completed', contract=contract)
        except (ValueError, TypeError, KeyError):
            pass
    return result


def validate_config(config):
    if config['phase'] != 'semantics-001' or len(config['inputs']) != 12 or len(config['providers']) != 6:
        raise ValueError('frozen_universe')
    ids = {q['id'] for q in config['inputs']}; models = {p['model'] for p in config['providers']}
    if len(ids) != 12 or len(models) != 6:
        raise ValueError('duplicate_universe')
    expected = {f'semantics-001|{q}|{m}' for q in ids for m in models}
    if len(config['slots']) != 72 or {s['id'] for s in config['slots']} != expected:
        raise ValueError('slot_universe')
    for slot in config['slots']:
        if slot['id'] != f"semantics-001|{slot['question_id']}|{slot['model']}":
            raise ValueError('slot_binding')
    for item in config['inputs']:
        if set(item) != {'id', 'messages', 'source_sha256'}:
            raise ValueError('runtime_input_fields')
        if any(set(m) != {'role', 'content'} or m['role'] not in ('system', 'user') or not isinstance(m['content'], str) for m in item['messages']):
            raise ValueError('message_contract')
    for provider in config['providers']:
        endpoint = provider['endpoint']
        if endpoint.get('status') != 0 or endpoint.get('tag') != provider['slug']:
            raise ValueError('endpoint_status')
        if not {'max_tokens', 'reasoning', 'response_format'} <= set(endpoint['supported_parameters']):
            raise ValueError('endpoint_parameters')
        for item in config['inputs']:
            reserve(item['messages'], provider)


def run(folder):
    import httpx
    from dotenv import dotenv_values
    with (ROOT/'campaign.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        freeze = strict((folder/'freeze.json').read_text())
        for path, checksum in freeze['hashes'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != checksum:
                raise ValueError('frozen_file_changed')
        gate = strict((folder/'launch-gate.json').read_text())
        if gate.get('decision') != 'ready' or gate.get('freeze_sha256') != hashlib.sha256(canonical(freeze)).hexdigest():
            raise ValueError('review_gate')
        config = strict((folder/'config.json').read_text()); validate_config(config)
        ledger_path = ROOT/'campaign-budget.json'; ledger = strict(ledger_path.read_text())
        if ledger['authorized_usd'] != 15 or ledger['attempt_cap'] != ATTEMPT_CAP:
            raise ValueError('authorization_binding')
        key = dotenv_values('.env').get('OPENROUTER_API_KEY')
        if not key:
            raise ValueError('credential_missing')
        # Exclusive marker prevents accidental restart/retry after interruption.
        with (folder/'started.json').open('x') as handle:
            json.dump({'started_at': datetime.now(timezone.utc).isoformat()}, handle); handle.flush(); os.fsync(handle.fileno())
        results = folder/'responses'; results.mkdir(exist_ok=False)
        providers = {p['model']: p for p in config['providers']}; inputs = {q['id']: q for q in config['inputs']}
        states = []
        def alarm(*_):
            raise TimeoutError('transport_wall_timeout')
        signal.signal(signal.SIGALRM, alarm)
        stop = None
        with httpx.Client(timeout=TIMEOUT, transport=httpx.HTTPTransport(retries=0), follow_redirects=False) as client:
            for index, slot in enumerate(config['slots']):
                state = {**slot, 'state': 'not_attempted'}; states.append(state)
                if stop:
                    state['reason'] = stop; continue
                item, provider = inputs[slot['question_id']], providers[slot['model']]
                bound, amount = reserve(item['messages'], provider)
                request = payload(item['messages'], provider); prefix = results/f'{index:03d}'
                atomic(prefix.with_suffix('.request.json'), request)
                try:
                    reservation = admit(ledger, slot['id'], amount, datetime.now(timezone.utc), config['deadline'])
                except ValueError as error:
                    stop = str(error); state['reason'] = stop; continue
                ledger['status'] = 'active'; atomic(ledger_path, ledger)
                state['state'] = 'reserved'
                try:
                    signal.alarm(TIMEOUT)
                    try:
                        response = client.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': 'Bearer '+key}, json=request)
                    finally:
                        signal.alarm(0)
                    with prefix.with_suffix('.raw.txt').open('wb') as handle:
                        handle.write(response.content); handle.flush(); os.fsync(handle.fileno())
                    reservation['http_status'] = response.status_code
                    if response.status_code != 200:
                        raise ValueError('http_cost_unresolved')
                    result = assess(strict(response.content), provider, bound, amount)
                    atomic(prefix.with_suffix('.result.json'), result)
                    reservation.update(state='resolved', status=result['status'], reported_usd=result['reported_usd'])
                    state['state'] = result['status']
                except Exception as error:
                    reservation.update(state='unresolved', error_type=type(error).__name__)
                    state.update(state='execution_failure', error_type=type(error).__name__)
                    stop = 'unresolved_attempt'
                ledger['reserved_nonrefunded_usd'] = str(used(ledger))
                ledger['reported_cost_usd'] = str(sum((Decimal(r.get('reported_usd', '0')) for r in ledger['reservations']), Decimal('0')))
                atomic(ledger_path, ledger); atomic(folder/'states.json', states)
                print(json.dumps({'slot': index, 'state': state['state'], 'attempts': ledger['attempts'], 'budget_used': str(used(ledger))}), flush=True)
        ledger.update(status='stopped' if stop else 'phase_complete', stop_reason=stop)
        atomic(ledger_path, ledger); atomic(folder/'states.json', states)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('folder', type=Path)
    run(parser.parse_args().folder)
