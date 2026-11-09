# Shared-draft advisory review follow-up
Newcampaign deadline2026-11-06T21:52:59UTC,180attempts/$15. Current126calls,actual2.122258550,nonrefunded2.780039390. Proposed36additionalcalls, maxreservation6.08330726;combined8.86334665<15,plannedtotal162. Same sixmodels/providers,output2048reasoninginclusive eachreview,mediumreasoning,inputengineeringbound bytes+4096 max17713,notnativetokenizer. No retries,newAWS,sourcefetch. Originalfailures retained; this newreviewstage never rewritesfirstoutputs.
Development/posthoc subset P01(scope-default),P02(absentdependencyentry),P03(entrypresentwithoutdependsOn),selectedAFTER observingP03errors inpriorphase. All18originalsource_only drafts retained,including2wrongvalid and1lengthfailure. Notconfirmatory orfreshheldout; repeatedinspectedquestions/modeltraces. Each of6models reviews its own3saveddrafts in2conditions. BOTHconditions get exactsame selectedsource, taskselector, fullpinnednormativefieldmetadata,originalvisibletext/parsedoutput/status, commonprompt. OnlySHACLcondition addscomputedreport fromthose inputs. Selfreview hasallpolicyinformation; no addedsourceorquestiongold inreport. Firststage draft isshared, notindependentlyreplicated, eachanalyticalarmhasoriginal2048+review2048outputbudget; commoninputcap32768eachstage, actualtokensneednotmatch. Newreportisno compulsoryveto; modelcanignoreorretainanswer.
Effectunderstudy incrementalcomputedreport beyond explicitpolicy+selfreview; NOT pureSHACLversusPython orRDF/DB advantage. Pythonmirror checkssamepolicy;17actualcompletechecks agreewithSHACL (2violations),1inputboundaryrejectionnotSHACLfail.32fixturepairs agree; unit testsobservedbycoordinator notindependentreviewer. Shapes use operational facts fromexactselectedevidence: task, declaredscope/default,dependencyentrypresence/count. Notnatural-language policyextraction, andwrongtaskcouldpass. ScopeDefault field copiedfrompinnedJSONschema; dependencyentryemptyinterpretation followsdeclaredoperationalpolicy. Invaliddraft report input_rejected suppliesnoreplacementlabel; bothmodels mayrecoverformat using sameevidence. No goldrepair. Standardinstructions commonworld-evidencecaveat. Reporter hasnoevaluatorimports, fetches ormodelcalls.
Frozenall36slots; bothreviewconditions requestedforall18drafts, notonlyerrors. Primaryclassificationagreement againstexistingpre-frozenauthoredreferences, full36denominator, separate formatfailure, wrongvalidcorrection, failed-draftrecovery, correct-draftharm,pairedresults. Explanationbasis preserved nottruth-scored. No modelrankings orhumanmaintenancethreshold. Costguards are cloneofpreviousreviewedrunner; strictclassification/basisstructurebeforecompleted; validwronglabelcompleted; failureskeepfullreservation, unknowncoststopswholephase. Newvalidator bindsinputIDcase|arm|modeland36exactslots, allpreviousledger retained. Omittedcode/provider/source/evaluatorfacts unverifiedbyreview. Concise~1500byte independentreview; nootherreviews/secrets/evaluatorgold/historyrawanswers.

## scripts/source_semantics_report.py
```python
"""Advisory validation of a saved draft against declared selected-source policy.

No source fetches, evaluator references, model calls, or repair operations.
"""
from rdflib import Graph, Namespace, Literal, RDF, BNode
from rdflib.namespace import SH, XSD
from pyshacl import validate
EX = Namespace('https://example.org/shacl-study/source-semantics/')

def valid_response(value):
    return isinstance(value, dict) and set(value) == {'classification', 'basis'} and isinstance(value['classification'], str) and (value['classification'] in {'required', 'optional', 'excluded', 'explicit_empty', 'reported_nonempty', 'unknown', 'established', 'not_established'}) and isinstance(value['basis'], str) and bool(value['basis'].strip())

def make_report(evidence, task, metadata, draft):
    if not valid_response(draft):
        return {'status': 'input_rejected', 'conforms': None, 'python_conforms': None, 'codes': ['response_structure'], 'action': 'Review output format using supplied source and policy; no replacement answer supplied.'}
    if task not in ('consumer_scope', 'dependency_knowledge'):
        return {'status': 'unknown', 'conforms': None, 'python_conforms': None, 'codes': ['unsupported_task']}
    component = evidence['component']
    ref = component['bom-ref']
    if task == 'dependency_knowledge' and evidence['source_field_presence']['dependencies'] and ('dependencies' not in evidence):
        return {'status': 'unknown', 'conforms': None, 'python_conforms': None, 'codes': ['projection_missing_dependency_field']}
    entries = [e for e in evidence.get('dependencies', []) if e['ref'] == ref]
    if len(entries) > 1:
        return {'status': 'unknown', 'conforms': None, 'python_conforms': None, 'codes': ['duplicate_source_entry']}
    if task == 'consumer_scope':
        expected = component.get('scope', metadata['scope']['default'])
    else:
        expected = 'unknown' if not entries else 'reported_nonempty' if entries[0].get('dependsOn', []) else 'explicit_empty'
    python_conforms = draft['classification'] == expected
    data, shapes = (Graph(), Graph())
    node = EX.review
    shape = EX.PolicyShape
    data.add((node, RDF.type, EX.Review))
    for name, value in [('task', task), ('classification', draft['classification']), ('scopeDefault', metadata['scope']['default'])]:
        data.add((node, EX[name], Literal(value, datatype=XSD.string)))
    if 'scope' in component:
        data.add((node, EX.declaredScope, Literal(component['scope'], datatype=XSD.string)))
    data.add((node, EX.hasDependencyEntry, Literal(bool(entries))))
    data.add((node, EX.dependencyCount, Literal(len(entries[0].get('dependsOn', [])) if entries else 0)))
    shapes.add((shape, RDF.type, SH.NodeShape))
    shapes.add((shape, SH.targetClass, EX.Review))
    queries = [('consumer_scope_policy', 'SELECT $this WHERE {\n      $this ex:task ?task; ex:classification ?actual; ex:scopeDefault ?fallback.\n      FILTER(STR(?task) = "consumer_scope")\n      OPTIONAL { $this ex:declaredScope ?declared }\n      BIND(COALESCE(?declared,?fallback) AS ?expected)\n      FILTER(STR(?actual) != STR(?expected))\n    }'), ('dependency_entry_policy', 'SELECT $this WHERE {\n      $this ex:task ?task; ex:classification ?actual;\n        ex:hasDependencyEntry ?present; ex:dependencyCount ?count.\n      FILTER(STR(?task) = "dependency_knowledge")\n      BIND(IF(!?present,"unknown",IF(?count = 0,"explicit_empty","reported_nonempty")) AS ?expected)\n      FILTER(STR(?actual) != STR(?expected))\n    }')]
    for code, query in queries:
        constraint = BNode()
        shapes.add((shape, SH.sparql, constraint))
        shapes.add((constraint, SH.select, Literal('PREFIX ex: <' + str(EX) + '>\n' + query)))
        shapes.add((constraint, SH.message, Literal(code)))
    conforms, report, _ = validate(data, shacl_graph=shapes, inference='none', advanced=False)
    codes = sorted({str(m) for m in report.objects(None, SH.resultMessage)})
    return {'status': 'completed', 'conforms': bool(conforms), 'python_conforms': python_conforms, 'codes': codes, 'policy_source_sha256': metadata['source_sha256'], 'component_pointer': evidence['source_component_pointer'], 'limits': 'Conformance to supplied task and declared source-field policy, not correct question interpretation, explanation truth or real deployment truth.', 'action': 'Consider these findings; you may revise or retain the draft. No compulsory veto.', 'data_turtle': data.serialize(format='turtle'), 'shapes_turtle': shapes.serialize(format='turtle')}
```

## scripts/score_semantics_review.py
```python
"""Posthoc review comparison; supplied classifications are evaluation-only."""
import argparse
import json
from pathlib import Path

def evaluate(folder, evaluator, out):
    config = json.loads((folder / 'config.json').read_text())
    expected = {q['id']: q['expected_classification'] for q in json.loads(evaluator.read_text())}
    inputs = {q['id']: json.loads(q['messages'][1]['content']) for q in config['inputs']}
    rows = []
    for index, slot in enumerate(config['slots']):
        qid, arm, model = slot['question_id'].split('|')
        if model != slot['model']:
            raise ValueError('model_binding')
        draft = inputs[slot['question_id']]['saved_draft']
        before_correct = draft['completion_status'] == 'completed' and draft['parsed_response']['classification'] == expected[qid]
        row = {**slot, 'case': qid, 'arm': arm, 'state': 'not_completed', 'correct': False, 'draft_correct': before_correct, 'draft_status': draft['completion_status']}
        path = folder / 'responses' / f'{index:03d}.result.json'
        if path.exists():
            result = json.loads(path.read_text())
            row['state'] = result['status']
            row['answer'] = result.get('contract')
            row['correct'] = result['status'] == 'completed' and result['contract']['classification'] == expected[qid]
        rows.append(row)
    counts = {a: {'planned': sum((r['arm'] == a for r in rows)), 'completed': sum((r['arm'] == a and r['state'] == 'completed' for r in rows)), 'correct': sum((r['arm'] == a and r['correct'] for r in rows)), 'correct_draft_harmed': sum((r['arm'] == a and r['draft_correct'] and (not r['correct']) for r in rows)), 'wrong_valid_draft_corrected': sum((r['arm'] == a and r['draft_status'] == 'completed' and (not r['draft_correct']) and r['correct'] for r in rows)), 'failed_draft_to_correct': sum((r['arm'] == a and r['draft_status'] != 'completed' and r['correct'] for r in rows))} for a in ('self_review', 'shacl_review')}
    pairs = []
    for qid in ('P01', 'P02', 'P03'):
        for p in config['providers']:
            rr = {r['arm']: r for r in rows if r['case'] == qid and r['model'] == p['model']}
            pairs.append({'case': qid, 'model': p['model'], 'self_correct': rr['self_review']['correct'], 'shacl_correct': rr['shacl_review']['correct']})
    out.write_text(json.dumps({'planned': len(rows), 'arm_counts': counts, 'pairs': pairs, 'rows': rows, 'limits': 'Posthoc three-case development subset selected after P03 errors. Both conditions receive same source and normative policy, share original draft, common additional2048outputcap. No independent draft replicas, explanationtruth, externaltruth or maintenanceeffort measurement.'}, ensure_ascii=False, indent=2) + '\n')
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('folder', type=Path)
    p.add_argument('evaluator', type=Path)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    evaluate(a.folder, a.evaluator, a.out)
```

## Paidrunner guards (otherhelpers/loop omittedunverified; samepreviousdurablelock/fsync/non200halt/180salarm/noHTTP retry pattern)
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
                result['contract'] = contract
            if isinstance(contract, dict) and set(contract) == {'classification', 'basis'} and isinstance(contract['classification'], str) and (contract['classification'] in {'required', 'optional', 'excluded', 'explicit_empty', 'reported_nonempty', 'unknown', 'established', 'not_established'}) and isinstance(contract['basis'], str) and bool(contract['basis'].strip()):
                result.update(status='completed', contract=contract)
        except (ValueError, TypeError, KeyError):
            pass
    return result
def validate_config(config):
    if config['phase'] != 'review-001' or len(config['inputs']) != 36 or len(config['providers']) != 6:
        raise ValueError('frozen_universe')
    ids = {q['id'] for q in config['inputs']}
    models = {p['model'] for p in config['providers']}
    if len(ids) != 36 or len(models) != 6:
        raise ValueError('duplicate_universe')
    expected_ids = {f'{q}|{arm}|{m}' for q in ('P01', 'P02', 'P03') for arm in ('self_review', 'shacl_review') for m in models}
    if ids != expected_ids:
        raise ValueError('paired_input_universe')
    expected = {f'review-001|{q}|{q.split(chr(124))[2]}' for q in ids}
    if len(config['slots']) != 36 or {s['id'] for s in config['slots']} != expected:
        raise ValueError('slot_universe')
    for slot in config['slots']:
        if slot['id'] != f'review-001|{slot['question_id']}|{slot['model']}':
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
```
