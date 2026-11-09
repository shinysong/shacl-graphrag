# Imported frozen helper, only below functions called
```python
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


```
