# Paid contract mapping diagnostic launch review
User newly authorized8h through2026-11-06T21:52:59Z and total experimentalOpenRouter cap$15. Main imposed180totalattempt cap, new shared ledger; no reuse historicalbudget. This phase exactly9questions×6models=54calls, one attempt per slot, noautomaticretry. No newAWS/DB. Six historical model identities rechecked via public endpoints today: Google3.8Flash/4Argon, OpenAI6Luna/6Astra, ClaudeSonnet5.5/Fable5.1. Actual IDs/routing names frozenconfig.
Primarymeasurement: Does model select correctoperation/target/scope? Shared deterministicexecutor then computes declaredresult. Human-authored contract reference uses originalsourceSQLite and is evaluatoronly. No freeform finalanswer or maintenanceefficacy claim. All9authored questions and5sourcefiles inspecteddevelopment, not freshheldout. Prior3395validcontract executions agree on status/refs/knowledge, not proof of natural interpretation. SHACL only checks contract structure/enums/targetmembership, not questionintent, and getsnogold. Valid-but-wrong contracts retained.
54slots stagger modelorder byquestion. Common2048outputtoken cap includes reasoning, mediumreasoning, JSONobject, same full projectedsource for eachmodel. Textonly no tools/search. Conservative inputenvelope bytes+4096 atmost21278, not exact native tokenizer. Maxnonrefunded reservation sum12.68609410<15 if all54 fail; actual successfuloutputs settle reportedcost, failures retain reservation. Runtime checks boundusage/model/provider/cost. Price routepinned, fallbackoff, paidHTTP non200/unresolvedcost stopswholephase. Sharedledger unresolvedreservations preventlatercalls. Oldledgeruntouched.
Protocol scoring beforecalls: all54slotsdenominator; responsefailure, invalidcontract, mappingerror, correctmapping, clarification and unknownscope separate. Q07 accepts valid nonclarify real_world contract yieldingunknown; Q08/Q09 requireclarify; others exact authoredcontract. Resultset agreement scored separately from mapping, emptyanswers donotmaskwrongintent. Checker pass withwrongmapping separatelyreported. Evaluator runtimeimports prohibited; referencehash boundonly. Questionsbelow noanswers. Main will not tune prompts or repairoutputs onobserved errors.
Execution gate requires native two independentreadyreviews, direct11unit tests and config/freeze hash. Pinnedsourcefiles and actualprovider metadata omittedfrompacket: remainunverifiedbyreview. Reviewer cancheck includedrequestlanguage, runnercode and budgettests. Keep reviewconcise~1500bytes, preserve blockers. Nootherreviews/secrets/evaluator-only/historicalQA.

## Actual system message
Translate the user question into one supported query contract. Do not answer the question directly. Output exactly one JSON object with exactly three string fields: operation, target, scope. Use only the supplied source and language definition. Do not infer deployed software, vulnerability, safety, or hidden relationships.
Contract language:
- direct_dependencies: outgoing declared dependency edges from target.
- transitive_dependencies: all nodes reachable by outgoing declared edges, excluding target itself.
- direct_dependents: components with a declared outgoing edge to target.
- transitive_dependents: nodes that reach target along declared edges, excluding target itself.
- dependency_status: distinguish an explicit dependency entry with no children, a nonempty entry, and an absent dependency entry.
- clarify: question does not determine a unique target or relation/direction; target must be empty string.
For other operations target must be the exact bom-ref from source.components. scope is declared_document when asking what this document reports, or real_world when asking to establish actual complete deployment facts. The executor returns unknown for real_world; do not silently weaken a requested world claim into a document claim. For clarify use scope declared_document.
An absent dependency entry is unknown dependency information. A present entry with an empty dependsOn array explicitly reports no children. Even a complete traversal of the document does not establish deployment completeness. Selecting a syntactically valid contract does not establish that you interpreted the question correctly.
## Questions
Q01 laravel 문서에 기록된 symfony/http-kernel-5.4.16.0의 직접 의존 대상을 나열해 주세요. 그 대상이 다시 의존하는 항목은 제외합니다.
Q02 laravel symfony/http-kernel-5.4.16.0에서 의존 관계를 여러 단계 따라가 도달하는 구성요소를 모두 나열해 주세요. 이 문서에 기록된 관계만 대상으로 하고 시작 구성요소 자체는 제외합니다.
Q03 laravel symfony/event-dispatcher-5.4.9.0에 직접 의존한다고 기록된 구성요소는 무엇인가요? event-dispatcher가 사용하는 구성요소를 묻는 것은 아닙니다.
Q04 laravel 이 문서에서 symfony/event-dispatcher-5.4.9.0을 직접 또는 간접 의존하는 구성요소를 모두 찾아주세요. 잠재적 검토 후보를 찾는 질문이며 실제 장애 발생을 판정하는 것은 아닙니다.
Q05 laravel brick/math-0.9.3.0의 의존성 정보는 문서에 없나요, 아니면 의존 대상이 없다고 명시되어 있나요? 기록 상태를 구분해 주세요.
Q06 cern pkg:npm/puppeteer@1.19.0의 의존성 정보는 문서에 없나요, 아니면 의존 대상이 없다고 명시되어 있나요? 기록 상태를 구분해 주세요.
Q07 laravel symfony/http-kernel-5.4.16.0이 실제 운영 환경에서 직접·간접으로 사용하는 모든 구성요소를 빠짐없이 확정해 주세요. 문서 안에서 찾을 수 있는 항목만 나열하는 것으로 대체하지 마세요.
Q08 laravel symfony/http-kernel-5.4.16.0과 관련된 것들을 찾아주세요.
Q09 cern debug 패키지의 직접 의존 대상을 알려주세요.
## scripts/run_contract_mapping.py SHA256 3a3fcc61672b4b35b7a1a6113c06074c907367f9d84eee829819058a9da53441
```python
"""One-launch bounded OpenRouter contract-selection diagnostic; no gold imports."""
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
    return json.loads(value, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))

def atomic(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('wb') as handle:
        handle.write(canonical(value))
        handle.flush()
        os.fsync(handle.fileno())
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
    if any((not v.is_finite() or v < 0 for v in (a, b, c))) or Decimal(str(price.get('request', '0'))) != 0:
        raise ValueError('unsupported_pricing')
    return (a, b, c)

def reserve(messages, provider):
    bound = len(canonical(messages)) + 4096
    if bound > INPUT_CAP:
        raise ValueError('input_envelope')
    a, b, c = prices(provider)
    return (bound, ((a + b) * bound + c * OUTPUT_CAP).quantize(Decimal('.00000001'), rounding=ROUND_UP))

def payload(messages, provider):
    a, _, c = prices(provider)
    return {'model': provider['model'], 'messages': messages, 'max_tokens': OUTPUT_CAP, 'reasoning': {'effort': 'medium', 'exclude': True}, 'response_format': {'type': 'json_object'}, 'provider': {'only': [provider['slug']], 'allow_fallbacks': False, 'require_parameters': True, 'max_price': {'prompt': float(a * 1000000), 'completion': float(c * 1000000)}}}

def used(ledger):
    return sum((Decimal(r['reported_usd']) if r.get('state') == 'resolved' and r.get('status') == 'completed' else Decimal(r['reserved_usd']) for r in ledger['reservations']), Decimal('0'))

def admit(ledger, slot_id, amount, now, deadline):
    if len(ledger['reservations']) >= ATTEMPT_CAP or ledger['attempts'] != len(ledger['reservations']):
        raise ValueError('attempt_cap_or_ledger_mismatch')
    if any((r['state'] != 'resolved' for r in ledger['reservations'])):
        raise ValueError('unresolved_previous_attempt')
    if any((r['slot_id'] == slot_id for r in ledger['reservations'])):
        raise ValueError('duplicate_attempt')
    if used(ledger) + amount > USD_CAP:
        raise ValueError('budget_cap')
    if (datetime.fromisoformat(deadline) - now).total_seconds() <= TIMEOUT + 30:
        raise ValueError('deadline')
    row = {'slot_id': slot_id, 'state': 'reserved', 'reserved_usd': str(amount), 'reserved_at': now.isoformat()}
    ledger['reservations'].append(row)
    ledger['attempts'] += 1
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
    result = {'status': 'output_failure', 'reported_usd': str(cost), 'usage': usage, 'finish_reason': choice.get('finish_reason'), 'contract': None}
    if choice.get('finish_reason') == 'stop':
        try:
            contract = strict(choice['message']['content'])
            if isinstance(contract, dict):
                result.update(status='completed', contract=contract)
        except (ValueError, TypeError, KeyError):
            pass
    return result

def validate_config(config):
    if config['phase'] != 'mapping-001' or len(config['inputs']) != 9 or len(config['providers']) != 6:
        raise ValueError('frozen_universe')
    ids = {q['id'] for q in config['inputs']}
    models = {p['model'] for p in config['providers']}
    if len(ids) != 9 or len(models) != 6:
        raise ValueError('duplicate_universe')
    expected = {f'mapping-001|{q}|{m}' for q in ids for m in models}
    if len(config['slots']) != 54 or {s['id'] for s in config['slots']} != expected:
        raise ValueError('slot_universe')
    for slot in config['slots']:
        if slot['id'] != f'mapping-001|{slot['question_id']}|{slot['model']}':
            raise ValueError('slot_binding')
    for item in config['inputs']:
        if set(item) != {'id', 'messages', 'source_sha256'}:
            raise ValueError('runtime_input_fields')
        if any((set(m) != {'role', 'content'} or m['role'] not in ('system', 'user') or (not isinstance(m['content'], str)) for m in item['messages'])):
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
    with (ROOT / 'campaign.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        freeze = strict((folder / 'freeze.json').read_text())
        for path, checksum in freeze['hashes'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != checksum:
                raise ValueError('frozen_file_changed')
        gate = strict((folder / 'launch-gate.json').read_text())
        if gate.get('decision') != 'ready' or gate.get('freeze_sha256') != hashlib.sha256(canonical(freeze)).hexdigest():
            raise ValueError('review_gate')
        config = strict((folder / 'config.json').read_text())
        validate_config(config)
        ledger_path = ROOT / 'campaign-budget.json'
        ledger = strict(ledger_path.read_text())
        if ledger['authorized_usd'] != 15 or ledger['attempt_cap'] != ATTEMPT_CAP:
            raise ValueError('authorization_binding')
        key = dotenv_values('.env').get('OPENROUTER_API_KEY')
        if not key:
            raise ValueError('credential_missing')
        with (folder / 'started.json').open('x') as handle:
            json.dump({'started_at': datetime.now(timezone.utc).isoformat()}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        results = folder / 'responses'
        results.mkdir(exist_ok=False)
        providers = {p['model']: p for p in config['providers']}
        inputs = {q['id']: q for q in config['inputs']}
        states = []

        def alarm(*_):
            raise TimeoutError('transport_wall_timeout')
        signal.signal(signal.SIGALRM, alarm)
        stop = None
        with httpx.Client(timeout=TIMEOUT, transport=httpx.HTTPTransport(retries=0), follow_redirects=False) as client:
            for index, slot in enumerate(config['slots']):
                state = {**slot, 'state': 'not_attempted'}
                states.append(state)
                if stop:
                    state['reason'] = stop
                    continue
                item, provider = (inputs[slot['question_id']], providers[slot['model']])
                bound, amount = reserve(item['messages'], provider)
                request = payload(item['messages'], provider)
                prefix = results / f'{index:03d}'
                atomic(prefix.with_suffix('.request.json'), request)
                try:
                    reservation = admit(ledger, slot['id'], amount, datetime.now(timezone.utc), config['deadline'])
                except ValueError as error:
                    stop = str(error)
                    state['reason'] = stop
                    continue
                ledger['status'] = 'active'
                atomic(ledger_path, ledger)
                state['state'] = 'reserved'
                try:
                    signal.alarm(TIMEOUT)
                    try:
                        response = client.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': 'Bearer ' + key}, json=request)
                    finally:
                        signal.alarm(0)
                    with prefix.with_suffix('.raw.txt').open('wb') as handle:
                        handle.write(response.content)
                        handle.flush()
                        os.fsync(handle.fileno())
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
                atomic(ledger_path, ledger)
                atomic(folder / 'states.json', states)
                print(json.dumps({'slot': index, 'state': state['state'], 'attempts': ledger['attempts'], 'budget_used': str(used(ledger))}), flush=True)
        ledger.update(status='stopped' if stop else 'phase_complete', stop_reason=stop)
        atomic(ledger_path, ledger)
        atomic(folder / 'states.json', states)
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    run(parser.parse_args().folder)
```

## tests/test_contract_mapping_budget.py SHA256 8fa45e8cd160f0ed925aca2d04b082bb0e419187ba08b2cd4d9482abc72d5b32
```python
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from scripts.run_contract_mapping import admit, used, assess, strict

class Budget(unittest.TestCase):

    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.deadline = (self.now + timedelta(hours=1)).isoformat()
        self.ledger = {'reservations': [], 'attempts': 0}

    def test_failure_reservation_never_refunded(self):
        r = admit(self.ledger, 'one', Decimal('2'), self.now, self.deadline)
        r.update(state='resolved', status='output_failure', reported_usd='.01')
        self.assertEqual(used(self.ledger), Decimal('2'))
        with self.assertRaisesRegex(ValueError, 'budget_cap'):
            admit(self.ledger, 'two', Decimal('14'), self.now, self.deadline)

    def test_unresolved_duplicate_deadline(self):
        r = admit(self.ledger, 'one', Decimal('.1'), self.now, self.deadline)
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            admit(self.ledger, 'two', Decimal('.1'), self.now, self.deadline)
        r.update(state='resolved', status='completed', reported_usd='.01')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            admit(self.ledger, 'one', Decimal('.1'), self.now, self.deadline)
        with self.assertRaisesRegex(ValueError, 'deadline'):
            admit(self.ledger, 'two', Decimal('.1'), self.now, self.now.isoformat())

    def test_wrong_contract_remains_outcome(self):
        data = {'model': 'm', 'provider': 'p', 'usage': {'cost': 0.01, 'prompt_tokens': 20, 'completion_tokens': 10}, 'choices': [{'finish_reason': 'stop', 'message': {'content': '{"operation":"wrong","target":"wrong","scope":"wrong"}'}}]}
        result = assess(data, {'model': 'm', 'provider': 'p'}, 100, Decimal('.1'))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['contract']['operation'], 'wrong')
        data['model'] = 'other'
        with self.assertRaisesRegex(ValueError, 'route_mismatch'):
            assess(data, {'model': 'm', 'provider': 'p'}, 100, Decimal('.1'))

    def test_duplicate_json_and_nonfinite_rejected(self):
        for value in ['{"a":1,"a":2}', '{"a":NaN}']:
            with self.assertRaises(ValueError):
                strict(value)
if __name__ == '__main__':
    unittest.main()
```
