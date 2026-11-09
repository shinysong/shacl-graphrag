# Paid contract mapping diagnostic launch review
User newly authorized8h through2026-11-06T21:52:59Z and total experimentalOpenRouter cap$15. Main imposed180totalattempt cap, new shared ledger; no reuse historicalbudget. This phase exactly9questions×6models=54calls, one attempt per slot, noautomaticretry. No newAWS/DB. Six historical model identities rechecked via public endpoints today: Google3.8Flash/4Argon, OpenAI6Luna/6Astra, ClaudeSonnet5.5/Fable5.1. Actual IDs/routing names frozenconfig.
Primarymeasurement: Does model select correctoperation/target/scope? Shared deterministicexecutor then computes declaredresult. Human-authored contract reference uses originalsourceSQLite and is evaluatoronly. No freeform finalanswer or maintenanceefficacy claim. All9authored questions and5sourcefiles inspecteddevelopment, not freshheldout. Prior3395validcontract executions agree on status/refs/knowledge, not proof of natural interpretation. SHACL only checks contract structure/enums/targetmembership, not questionintent, and getsnogold. Valid-but-wrong contracts retained.
54slots stagger modelorder byquestion. Common2048outputtoken cap includes reasoning, mediumreasoning, JSONobject, same full projectedsource for eachmodel. Textonly no tools/search. Conservative inputenvelope bytes+4096 atmost21278, not exact native tokenizer. Maxnonrefunded reservation sum12.68609410<15 if all54 fail; actual successfuloutputs settle reportedcost, failures retain reservation. Runtime checks boundusage/model/provider/cost. Price routepinned, fallbackoff, paidHTTP non200/unresolvedcost stopswholephase. Sharedledger unresolvedreservations preventlatercalls. Oldledgeruntouched.
Protocol scoring beforecalls: all54slotsdenominator; responsefailure, invalidcontract, mappingerror, correctmapping, clarification and unknownscope separate. ALL9 primarymapping requires exact three-field authoredcontract and validcontract, including Q07 operation AND target AND scope. Unknown/clarification behavior and resultagreement are separate secondarymetrics; wrongoperation/target cannot earn primarymapping credit. Priorjob methods blocker preserved; no calls occurred. Resultset agreement scored separately from mapping, emptyanswers donotmaskwrongintent. Checker pass withwrongmapping separatelyreported. Evaluator runtimeimports prohibited; referencehash boundonly. Questionsbelow noanswers. Main will not tune prompts or repairoutputs onobserved errors.
Execution gate requires native two independentreadyreviews, direct13unit tests and config/freeze hash. Pinnedsourcefiles and actualprovider metadata omittedfrompacket: remainunverifiedbyreview. Reviewer cancheck includedrequestlanguage, runnercode and budgettests. Keep reviewconcise~1500bytes, preserve blockers. Nootherreviews/secrets/evaluator-only/historicalQA.

## Runtime prompting
Frozen system message explicitly defines6supportedoperations, exactsource bom-ref selection, declared_document versusreal_world, and clarify usingemptytarget/document scope. It states missing dependencyentry unknown, presentempty entry declaredempty, documentclosure notworldcompleteness. No gold or reference output is in messages. Actualfullsource/modelmetadata omitted: reviewer unverified. Priorprompt unchanged after blockedscoringreview.
## Question scope
Q01–04 declared direct/transitive outgoing/reverse graph queries. Q05 explicit-empty dependency entry; Q06 absent dependency entry. Q07 explicitly requests actual-world complete transitive dependencies of a named target, not document-only enumeration. Q08 says related things with no direction. Q09 names debug without selecting among3versions. Allquestions are authored development, no independent expertvalidation; exact original questiontexts omitted, semantic labeling remains unverifiedbyreview.
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

# validate_config implementation omitted: main checks9uniquequestions,6providers,exact54slots, whitelistedmessagefields and supportedendpointparameters. Reviewer must mark omitted implementation unverified.

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

Budget unit tests omitted from this packet; main observed4 passing, reviewer unverified.
## New posthoc scorer and regression tests
Evaluator-only references are not included. Primary exactcontract and componentagreement independent of resultagreement. Regression explicitly preserves valid wrongtarget/wrongoperation yielding sameunknownoutput as mappingerrors. All54 slots remain denominator.

### scripts/score_contract_mapping.py
```python
"""Posthoc-only scoring. Never imported by the paid request runner."""
import argparse
import hashlib
import json
from pathlib import Path
from scripts.sbom_contracts import read_document, contract_errors, shacl_contract_errors, execute
from scripts.sbom_reference import reference, compare

def score(contract, authored, output, expected, valid):
    fields = {key: isinstance(contract, dict) and contract.get(key) == authored[key] for key in ('operation', 'target', 'scope')}
    exact = valid and contract == authored
    return {'field_agreement': fields, 'mapping_correct': exact, 'result_agreement': valid and (not compare(output, expected)), 'valid_but_wrong_mapping': valid and (not exact), 'unknown_scope_behavior': output.get('status') == 'unknown_world_scope', 'clarification_behavior': output.get('status') == 'needs_clarification'}

def evaluate(folder, evaluator, destination):
    config = json.loads((folder / 'config.json').read_text())
    gold = {q['id']: q for q in json.loads(evaluator.read_text())}
    rows = []
    for index, slot in enumerate(config['slots']):
        q = gold[slot['question_id']]
        if hashlib.sha256(Path(q['source_path']).read_bytes()).hexdigest() != q['source_sha256']:
            raise ValueError('source_changed')
        expected = reference(q['source_path'], q['authored_contract'])
        if expected != q['reference'] or q['mapping_scoring'] != 'exact_contract':
            raise ValueError('reference_or_scoring_changed')
        path = folder / 'responses' / f'{index:03d}.result.json'
        row = {**slot, 'state': 'no_completed_output', 'mapping_correct': False, 'result_agreement': False, 'valid_but_wrong_mapping': False}
        if path.exists():
            response = json.loads(path.read_text())
            row['state'] = response['status']
            contract = response.get('contract')
            if response['status'] == 'completed':
                snapshot = read_document(q['source_path'])
                errors = contract_errors(contract, snapshot)
                output = execute(contract, snapshot)
                row.update(contract=contract, contract_errors=errors, output=output, shacl=shacl_contract_errors(contract, snapshot))
                row.update(score(contract, q['authored_contract'], output, expected, not errors))
        rows.append(row)
    result = {'planned': len(rows), 'completed_outputs': sum((r['state'] == 'completed' for r in rows)), **{k: sum((r[k] for r in rows)) for k in ('mapping_correct', 'result_agreement', 'valid_but_wrong_mapping')}, 'rows': rows, 'limits': 'Authored development contracts; matching output is not matching interpretation or external truth.'}
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    p.add_argument('evaluator', type=Path)
    p.add_argument('destination', type=Path)
    a = p.parse_args()
    evaluate(a.folder, a.evaluator, a.destination)
```

### tests/test_contract_mapping_score.py
```python
import unittest
from scripts.score_contract_mapping import score

class MappingScore(unittest.TestCase):

    def test_unknown_does_not_mask_wrong_target_or_operation(self):
        expected = {'operation': 'transitive_dependencies', 'target': 'A', 'scope': 'real_world'}
        output = {'status': 'unknown_world_scope', 'refs': []}
        for key, value in [('operation', 'direct_dependents'), ('target', 'B')]:
            result = score({**expected, key: value}, expected, output, output, True)
            self.assertFalse(result['mapping_correct'])
            self.assertTrue(result['result_agreement'])
            self.assertTrue(result['valid_but_wrong_mapping'])

    def test_exact_and_invalid_are_separate(self):
        expected = {'operation': 'clarify', 'target': '', 'scope': 'declared_document'}
        output = {'status': 'needs_clarification', 'refs': []}
        self.assertTrue(score(expected, expected, output, output, True)['mapping_correct'])
        self.assertFalse(score({**expected, 'extra': 'x'}, expected, output, output, False)['mapping_correct'])
```
