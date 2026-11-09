# Six-case source semantics metadata diagnostic
New8h deadline21:52:59UTC, totalcampaign$15/180attempts. Prior54calls complete:53valid mappingoutputs correct,1formatfailure; actualcharge1.474826350, nonrefundedused2.124156350. Newphase72calls =6authoredcases×6models×2conditions, oneattempt/slot, total126calls ifcomplete. Maxadditionalreservations9.29087211; total11.41502846<15. Samecostguard/noautomaticretry/unresolvedhalts, one-time launchmarker and filehashreviewgate. Sixproviders refreshed publicmetadata today,pricesunchanged; actualprovider metadata omittedunverifiedbyreview. Same2048reasoning-inclusiveoutputcap,mediumreasoning,no tools orsearch, priorstandardknowledge allowed. Allcases inspecteddevelopment, some reuseprevioussources, notfreshheldout.
Intervention ONLY access to pinned standard metadata: source_only versus source_plus_schema (actual version's component.scope and dependency definitions copied). Botharms receive identicalsourceprojection, suppliedtaskselector,outputschema and commonwarning archivedexamples do not verifycurrentinstallation. Addednormativemetadata is deliberately unequal informationaccess; no claim sameinformation or pureSHACL/RDF/DBadvantage. No SHACL runtime here. Source-only canusepriorstandardknowledge, not forcedabstention.6cases across4distinctions, not6independentdomains. Scope-default cases occur in1.2and1.4, dependencyabsence andexplicit-emptycases reuseearlierinspectedtargets. Common sourceprojection copies selectedcomponentwhole; dependencyquestions receivefull dependencyfield ifpresent and originalfieldpresence. Scope questions omitunrelateddependenciesexplicitly, not sourceloss.
Primary exactclassification against frozenauthoredreference, all72denominator and36pairs; preserveformaterrors, validwronglabels, explanations. Basistext structuralvalidationonly, nottruthscoring. SamepolicyPython gets suppliedtask+samepublishedsemantics; agreement verifiesdeclaredpolicy implementation, notNLunderstanding. No runtimegoldrepair/retry. Cases and policyreference main verified; no independentdomainexpertlabels. Querydirection not measuredhere.
Fullrunner largely identicalpreviousreviewedbudgetrunner; below include guards/paidloop, omitted configvalidator andhelpers are unverifiedbyreview. Changedphase semantics-001,12inputIDs(question+arm),6providers,72exactslots. Main validatedall12projections/hashbindings andnew2unit tests (18total). Review readiness beforecalls; concise~1500bytes; nootherreviews/secrets/evaluatorgold.

## Case questions (no gold)
[{"id": "P01", "source_id": "laravel", "question_type": "consumer_scope", "question": "이 구성요소의 scope 필드가 없습니다. 이 버전의 CycloneDX 문서를 소비하는 도구가 적용해야 하는 scope 값을 판정해 주세요. 실제 설치 여부를 묻는 것은 아닙니다."}, {"id": "P02", "source_id": "cern", "question_type": "dependency_knowledge", "question": "이 구성요소의 의존성 기록 상태를 판정해 주세요. 문서가 의존 대상이 없다고 명시한 것인가요, 아니면 알 수 없는 것인가요?"}, {"id": "P03", "source_id": "laravel", "question_type": "dependency_knowledge", "question": "이 구성요소를 가리키는 dependency 항목에는 dependsOn 필드가 없습니다. 문서가 의존 대상이 없다고 명시한 것인가요, 아니면 알 수 없는 것인가요?"}, {"id": "P04", "source_id": "proton", "question_type": "consumer_scope", "question": "문서 소비 도구가 이 구성요소에 적용해야 하는 scope 값을 판정해 주세요. 실제 설치 여부를 묻는 것은 아닙니다."}, {"id": "P05", "source_id": "cern", "question_type": "consumer_scope", "question": "이 구성요소의 scope 필드가 없습니다. 이 버전의 CycloneDX 문서를 소비하는 도구가 적용해야 하는 scope 값을 판정해 주세요. 실제 설치 여부를 묻는 것은 아닙니다."}, {"id": "P06", "source_id": "proton", "question_type": "external_claim", "question": "이 구성요소의 scope가 required라고 적혀 있다는 사실만으로 고객의 현재 운영 장비에 실제 설치되어 있다고 확정할 수 있나요?"}]
## Standard metadata (oneversion shown,1.2samefieldsemantics,originalbytespinned)
{
 "scope": {
  "type": "string",
  "enum": [
   "required",
   "optional",
   "excluded"
  ],
  "title": "Component Scope",
  "description": "Specifies the scope of the component. If scope is not specified, 'required' scope SHOULD be assumed by the consumer of the BOM.",
  "default": "required"
 },
 "dependency": {
  "type": "object",
  "title": "Dependency",
  "description": "Defines the direct dependencies of a component. Components that do not have their own dependencies MUST be declared as empty elements within the graph. Components that are not represented in the dependency graph MAY have unknown dependencies. It is RECOMMENDED that implementations assume this to be opaque and not an indicator of a component being dependency-free.",
  "required": [
   "ref"
  ],
  "additionalProperties": false,
  "properties": {
   "ref": {
    "$ref": "#/definitions/refType",
    "title": "Reference",
    "description": "References a component by the components bom-ref attribute"
   },
   "dependsOn": {
    "type": "array",
    "uniqueItems": true,
    "additionalItems": false,
    "items": {
     "$ref": "#/definitions/refType"
    },
    "title": "Depends On",
    "description": "The bom-ref identifiers of the components that are dependencies of this dependency object."
   }
  }
 }
}
## scripts/source_semantics.py
```python
"""Declared field semantics and posthoc classification scoring; no LLM client."""
import argparse
import hashlib
import json
from pathlib import Path
VALUES = {'required', 'optional', 'excluded', 'explicit_empty', 'reported_nonempty', 'unknown', 'established', 'not_established'}

def classify(document, ref, task, schema):
    nodes = [c for c in document['components'] if c['bom-ref'] == ref]
    if len(nodes) != 1:
        raise ValueError('ambiguous_component')
    if task == 'consumer_scope':
        return nodes[0].get('scope', schema['definitions']['component']['properties']['scope'].get('default', 'unknown'))
    if task == 'dependency_knowledge':
        entries = [e for e in document.get('dependencies', []) if e['ref'] == ref]
        if len(entries) > 1:
            raise ValueError('duplicate_dependency_entry')
        if not entries:
            return 'unknown'
        return 'reported_nonempty' if entries[0].get('dependsOn', []) else 'explicit_empty'
    if task == 'external_claim':
        return 'not_established'
    raise ValueError('unsupported_task')

def valid_response(value):
    return isinstance(value, dict) and set(value) == {'classification', 'basis'} and isinstance(value['classification'], str) and (value['classification'] in VALUES) and isinstance(value['basis'], str) and bool(value['basis'].strip())

def evaluate(folder, catalog, out):
    config = json.loads((folder / 'config.json').read_text())
    questions = {q['id']: q for q in json.loads((catalog / 'questions.json').read_text())}
    gold = {q['id']: q for q in json.loads((catalog / 'evaluator-only.json').read_text())}
    baselines = {}
    for qid, q in questions.items():
        raw = Path(q['source_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != q['source_sha256']:
            raise ValueError('source_changed')
        doc = json.loads(raw)
        schema_path = Path(q['source_path']).parent / ('schema14.json' if doc['specVersion'] == '1.4' else 'schema12.json')
        node = doc['components'][int(q['source_component_pointer'].split('/')[-1])]
        baseline = classify(doc, node['bom-ref'], q['question_type'], json.loads(schema_path.read_text()))
        if baseline != gold[qid]['expected_classification']:
            raise ValueError('declared_policy_reference_disagreement')
        baselines[qid] = baseline
    rows = []
    for index, slot in enumerate(config['slots']):
        qid, arm = slot['question_id'].split('|')
        row = {**slot, 'case': qid, 'arm': arm, 'state': 'not_completed', 'response_valid': False, 'correct': False}
        path = folder / 'responses' / f'{index:03d}.result.json'
        if path.exists():
            result = json.loads(path.read_text())
            row['state'] = result['status']
            answer = result.get('contract')
            row['answer'] = answer
            row['response_valid'] = result['status'] == 'completed' and valid_response(answer)
            row['correct'] = row['response_valid'] and answer['classification'] == gold[qid]['expected_classification']
        rows.append(row)
    paired = []
    for qid in questions:
        for provider in config['providers']:
            pair = {r['arm']: r for r in rows if r['case'] == qid and r['model'] == provider['model']}
            paired.append({'case': qid, 'model': provider['model'], 'source_only_correct': pair['source_only']['correct'], 'source_plus_schema_correct': pair['source_plus_schema']['correct'], 'both_valid': all((r['response_valid'] for r in pair.values()))})
    out.write_text(json.dumps({'planned': len(rows), 'rows': rows, 'pairs': paired, 'supplied_task_python_baseline': baselines, 'arm_counts': {a: {'planned': sum((r['arm'] == a for r in rows)), 'valid': sum((r['arm'] == a and r['response_valid'] for r in rows)), 'correct': sum((r['arm'] == a and r['correct'] for r in rows))} for a in ['source_only', 'source_plus_schema']}, 'limits': 'Authored consumed development; normative metadata access treatment, not SHACL or storage effect. Basis text retained but not scored for correctness; no external expert validation or blind intent extraction.'}, ensure_ascii=False, indent=2) + '\n')
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    p.add_argument('catalog', type=Path)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    evaluate(a.folder, a.catalog, a.out)
```

## tests/test_source_semantics.py
```python
import unittest
from scripts.source_semantics import classify, valid_response

class SourceSemantics(unittest.TestCase):

    def test_missing_fields_have_distinct_meanings(self):
        doc = {'components': [{'bom-ref': 'x'}]}
        schema = {'definitions': {'component': {'properties': {'scope': {'default': 'required'}}}}}
        self.assertEqual(classify(doc, 'x', 'consumer_scope', schema), 'required')
        self.assertEqual(classify(doc, 'x', 'dependency_knowledge', schema), 'unknown')
        doc['dependencies'] = [{'ref': 'x'}]
        self.assertEqual(classify(doc, 'x', 'dependency_knowledge', schema), 'explicit_empty')
        doc['components'][0]['scope'] = 'optional'
        self.assertEqual(classify(doc, 'x', 'consumer_scope', schema), 'optional')
        self.assertEqual(classify(doc, 'x', 'external_claim', schema), 'not_established')

    def test_response_boundary_does_not_assess_explanation_truth(self):
        self.assertTrue(valid_response({'classification': 'required', 'basis': 'Unsupported explanation can pass this structure check.'}))
        self.assertFalse(valid_response({'classification': [], 'basis': 'x'}))
        self.assertFalse(valid_response({'classification': 'required', 'basis': ' '}))
```

## Runner selectedfunctions
```python
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
```
ConstantROOT samecampaign;cap15/180;TIMEOUT180;OUTPUT_CAP2048. reserve usesserializedmessagebytes+4096,inputcap32768, conservativeprompt+cachewrite andmaxreasoning/completionprice. atomicfsync+rename. payload JSONobject,provideronly/fallbackfalse/maxprice. Sharedhelpercode omittedunverified.
