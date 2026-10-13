"""Protocol 0.5 development: real RDF/SHACL/code runs; optional bounded model smoke.

LPG is an in-memory reference representation, NOT a Cypher/Neo4j benchmark.
Reserved evaluation fixtures are rejected. All failures and attempted calls persist.
"""
import argparse
import hashlib
import json
import resource
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from rdflib import Graph, Literal, RDF, SH, URIRef

try:
    from scripts import run_gleif_pilot as old
except ModuleNotFoundError:
    import run_gleif_pilot as old

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'experiments/comparison'
EX, LEI = old.EX, old.LEI


def canonical(graph):
    return [{'id': f'F{i:03d}', 's': str(s), 'p': str(p),
             'o': str(o), 'kind': 'literal' if isinstance(o, Literal) else 'iri',
             'datatype': str(o.datatype) if isinstance(o, Literal) and o.datatype else None,
             'language': o.language if isinstance(o, Literal) else None}
            for i, (s, p, o) in enumerate(sorted(graph, key=lambda t: tuple(x.n3() for x in t)), 1)]


def lpg_reference(graph, subject):
    """Independent property/label/edge representation and bounded traversal."""
    nodes, edges = {}, []
    for s, p, o in graph:
        node = nodes.setdefault(str(s), {'labels': [], 'properties': {}})
        if p == RDF.type:
            node['labels'].append(str(o))
        elif isinstance(o, Literal):
            node['properties'].setdefault(str(p), []).append((str(o), o.datatype, o.language))
        else:
            edges.append((str(s), str(p), str(o)))
    selected = {str(subject)} | {o for s, p, o in edges if s == str(subject) and p == str(EX.directParent)}
    result = Graph()
    for key in selected:
        node = nodes.get(key, {'labels': [], 'properties': {}})
        for label in node['labels']:
            result.add((URIRef(key), RDF.type, URIRef(label)))
        for predicate, values in node['properties'].items():
            for value, datatype, language in values:
                result.add((URIRef(key), URIRef(predicate), Literal(value, datatype=datatype, lang=language)))
    for s, p, o in edges:
        if s in selected:
            result.add((URIRef(s), URIRef(p), URIRef(o)))
    return result


def build_case(dataset, item, variant):
    source = old.make_source(dataset, item)
    subject = LEI[item['lei']]
    if variant == 'source_relation_missing':
        source.remove((subject, EX.directParent, None))
    if variant == 'source_exception_missing':
        source.remove((subject, EX.exceptionReason, None))
    if variant in {'wrong_class', 'wrong_parent'}:
        other = next(e for lei, e in sorted(dataset['entities'].items()) if lei not in {item['lei'], item['parent']})
        source.remove((subject, EX.directParent, None))
        old.add_entity(source, other)
        source.add((subject, EX.directParent, LEI[other['lei']]))
        if variant == 'wrong_class':
            target = LEI[other['lei']]
            source.remove((target, RDF.type, EX.Entity))
            source.add((target, RDF.type, EX.Person))  # Explicit disjoint class in task contract.
    if variant == 'invalid_reason':
        source.set((subject, EX.exceptionReason, Literal('UNDEFINED_REASON')))
    return source


def omit(evidence, subject, variant):
    if variant == 'irrelevant_name_missing':
        evidence.remove((subject, EX.legalName, None))
    elif variant == 'retrieval_relation_missing':
        evidence.remove((subject, EX.directParent, None))
    elif variant == 'retrieval_exception_missing':
        evidence.remove((subject, EX.exceptionReason, None))
    elif variant == 'retrieval_type_missing':
        for parent in evidence.objects(subject, EX.directParent):
            evidence.remove((parent, RDF.type, None))
    return evidence


def code_judge(evidence, subject):
    parents = list(evidence.objects(subject, EX.directParent))
    reasons = list(evidence.objects(subject, EX.exceptionReason))
    if len(parents) > 1 or len(reasons) > 1 or (parents and reasons):
        return 'fail'
    if reasons:
        return 'pass' if reasons[0] in {Literal(x) for x in old.REASONS} else 'fail'
    if not parents:
        return 'unknown'
    types = set(evidence.objects(parents[0], RDF.type))
    if EX.Entity in types:
        return 'pass'
    return 'fail' if types else 'unknown'


def shacl_judge(evidence, subject, shapes, destination=None):
    conforms, report, issues, elapsed = old.inspect(evidence, shapes)
    if destination:
        report.serialize(destination / 'report.ttl', format='turtle')
    # Map only missing type class violations to unknown; retain every other violation.
    unknown = False
    for r in report.subjects(RDF.type, SH.ValidationResult):
        component, value = report.value(r, SH.sourceConstraintComponent), report.value(r, SH.value)
        if component == SH.ClassConstraintComponent and not list(evidence.objects(value, RDF.type)):
            unknown = True
        else:
            return 'fail', {'raw_conforms': conforms, 'issues': issues, 'validation_ms': elapsed}
    if not list(evidence.objects(subject, EX.directParent)) and not list(evidence.objects(subject, EX.exceptionReason)):
        unknown = True
    return ('unknown' if unknown else 'pass'), {'raw_conforms': conforms, 'issues': issues, 'validation_ms': elapsed}


def extract(evidence, subject):
    parents = list(evidence.objects(subject, EX.directParent))
    reasons = list(evidence.objects(subject, EX.exceptionReason))
    if len(parents) == 1 and not reasons:
        identifiers = list(evidence.objects(parents[0], EX.lei))
        if len(identifiers) == 1:
            return {'status': 'answer', 'kind': 'parent', 'value': str(identifiers[0])}
    if len(reasons) == 1 and not parents:
        return {'status': 'answer', 'kind': 'exception', 'value': str(reasons[0])}
    return {'status': 'abstain', 'kind': None, 'value': None}


def model_judge(gateway, evidence, subject, destination):
    answer, metadata = gateway.generate(
        'Judge the direct-parent-or-reporting-exception evidence for subject ' + str(subject),
        json.dumps(canonical(evidence), ensure_ascii=False), destination)
    if answer['status'] != 'answer' or answer.get('value') not in {'pass', 'fail', 'unknown'}:
        raise ValueError('InvalidJudgement')
    checks = answer.get('checks', {})
    if set(checks) != {'cardinality', 'parent_type', 'exception_reason'}:
        raise ValueError('MissingJudgementChecks')
    if checks['cardinality'] not in {'pass', 'fail', 'unknown'} or any(
        checks[k] not in {'pass', 'fail', 'unknown', 'not_applicable'} for k in ['parent_type', 'exception_reason']):
        raise ValueError('InvalidJudgementChecks')
    composed = 'fail' if 'fail' in checks.values() else 'unknown' if 'unknown' in checks.values() else 'pass'
    if answer['value'] != composed:
        raise ValueError('InconsistentJudgementChecks')
    ids = {f['id'] for f in canonical(evidence)}
    if not set(answer['evidence_ids']) <= ids:
        raise ValueError('InvalidEvidenceReference')
    return answer['value'], {'response': answer, 'llm': metadata}


def run_condition(source, first, subject, condition, shapes, directory, gateway=None):
    """Runtime has no variant, original item, correctness label or evaluation gold."""
    start = time.perf_counter()
    evidence = old.clone(first)
    trace, retry, calls = [], 0, 0
    for attempt in range(2):
        step = directory / f'attempt-{attempt}'
        step.mkdir()
        old.write(step / 'evidence.json', canonical(evidence))
        if condition in {'none', 'refresh'}:
            judgement, detail = 'unchecked', {}
        elif condition == 'code':
            judgement, detail = code_judge(evidence, subject), {}
        elif condition == 'shacl':
            judgement, detail = shacl_judge(evidence, subject, shapes, step)
        elif condition == 'llm':
            calls += 1
            judgement, detail = model_judge(gateway, evidence, subject, step)
        else:
            raise ValueError('UnknownCondition')
        trace.append({'attempt': attempt, 'judgement': judgement, 'detail': detail})
        old.write(step / 'judgement.json', trace[-1])
        if attempt == 0 and (condition == 'refresh' or judgement == 'unknown'):
            evidence = old.retrieve(source, subject)
            retry += 1
            continue
        break
    answer = extract(evidence, subject) if judgement in {'pass', 'unchecked'} else {'status': 'abstain', 'kind': None, 'value': None}
    return {'status': 'ok', 'answer': answer, 'trace': trace, 'extra_retrievals': retry,
            'judge_calls': calls, 'runtime_ms': (time.perf_counter() - start) * 1000,
            'final_evidence_sha256': hashlib.sha256(old.graph_text(evidence).encode()).hexdigest()}


def summarize(rows):
    result = {}
    for condition in sorted({r['condition'] for r in rows}):
        group = [r for r in rows if r['condition'] == condition]
        eligible = sum(r['source_answerable'] for r in group)
        result[condition] = {'total': len(group), 'correct': sum(r.get('correct', False) for r in group),
                            'wrong': sum(r.get('wrong', False) for r in group),
                            'abstained': sum(r.get('answer', {}).get('status') == 'abstain' for r in group),
                            'errors': sum(r['status'] == 'error' for r in group),
                            'unnecessary_abstentions': sum(r.get('unnecessary_abstention', False) for r in group),
                            'source_answerable': eligible,
                            'extra_retrievals': sum(r.get('extra_retrievals', 0) for r in group)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('development', type=Path)
    parser.add_argument('--model-smoke', action='store_true', help='Only first new development subject of each stratum; max24 calls/$0.10')
    args = parser.parse_args()
    dataset = json.loads(args.development.read_text())
    if not dataset.get('cohort') or any(x['split'] != 'development' for x in dataset['cohort']):
        raise ValueError('DevelopmentOnly: reserved/evaluation data are not executable')
    config = json.loads((FIX / 'config.json').read_text())
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-gleif-comparison-' + uuid.uuid4().hex[:8]
    output = ROOT / 'runs' / run_id
    output.mkdir(parents=True)
    files = ['scripts/run_gleif_comparison.py', 'scripts/run_gleif_pilot.py', 'scripts/prepare_gleif_comparison.py',
             'experiments/comparison/config.json', 'experiments/comparison/shapes.ttl', 'experiments/comparison/judge-prompt.txt', 'uv.lock']
    hashes = {}
    for name in files:
        path = ROOT / name
        dest = output / 'inputs' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        hashes[name] = old.sha(path)
    shutil.copyfile(args.development, output / 'development.json')
    record = {'run_id': run_id, 'status': 'running', 'protocol': config['protocol_version'],
              'scope': 'development model smoke' if args.model_smoke else 'development deterministic comparison',
              'dataset_sha256': old.sha(args.development), 'inputs_sha256': hashes, 'config': config,
              'lpg_scope': 'in-memory property/label/edge traversal; no Cypher or graph-engine benchmark',
              'rows': [], 'cases': [], 'source_manifest': dataset.get('source_manifest')}
    old.write(output / 'record.json', record)
    shapes = Graph().parse(FIX / 'shapes.ttl')
    gateway = None
    if args.model_smoke:
        gateway = old.Gateway(config, output, prompt_path=FIX / 'judge-prompt.txt', answer_kinds=('judgement',))
        if gateway.model != config['model']:
            raise ValueError('ConfiguredModelMismatch')
        ledger = output / 'budget.json'
        original_generate = gateway.generate
        def durable_generate(question, evidence, destination):
            # Persist reservation before network transmission via local client wrapper below.
            try:
                return original_generate(question, evidence, destination)
            finally:
                old.write(ledger, {'calls': gateway.calls, 'reserved_usd': gateway.reserved,
                                  'reported_usd': gateway.actual, 'missing_cost': gateway.missing_cost})
        original_post = gateway.client.post
        def recorded_post(*a, **kw):
            old.write(ledger, {'calls': gateway.calls, 'reserved_usd': gateway.reserved,
                              'reported_usd': gateway.actual, 'missing_cost': gateway.missing_cost})
            return original_post(*a, **kw)
        gateway.client.post = recorded_post
        gateway.generate = durable_generate
    cohort = dataset['cohort']
    if args.model_smoke:
        cohort = [next(x for x in cohort if x['kind'] == kind) for kind in ('parent', 'exception')]
    try:
        for item in cohort:
            subject = LEI[item['lei']]
            for variant in config[item['kind'] + '_variants']:
                start = time.perf_counter()
                source = build_case(dataset, item, variant)
                first = omit(old.retrieve(source, subject), subject, variant)
                reference = omit(lpg_reference(source, subject), subject, variant)
                parity = canonical(first) == canonical(reference)
                if not parity:
                    raise ValueError('RepresentationMismatch')
                initial_ms = (time.perf_counter() - start) * 1000
                case_id = item['lei'] + '-' + variant
                case_path = output / case_id
                case_path.mkdir()
                source.serialize(case_path / 'source.ttl', format='turtle')
                old.write(case_path / 'first-evidence.json', canonical(first))
                # Evaluator-only information; runtime gets only source/evidence/subject.
                gold = {'kind': item['kind'], 'value': item.get('parent', item.get('reason'))}
                answerable = variant not in {'source_relation_missing', 'source_exception_missing', 'wrong_class', 'wrong_parent', 'invalid_reason'}
                case = {'case_id': case_id, 'variant': variant, 'kind': item['kind'], 'gold': gold,
                        'source_answerable': answerable, 'representation_equal': parity,
                        'initial_preparation_ms': initial_ms}
                record['cases'].append(case)
                conditions = ['llm'] if args.model_smoke else config['conditions']
                for condition in conditions:
                    path = case_path / condition
                    path.mkdir()
                    try:
                        result = run_condition(source, first, subject, condition, shapes, path, gateway)
                        answer = result['answer']
                        result['correct'] = answer['status'] == 'answer' and all(answer[k] == gold[k] for k in ('kind', 'value'))
                        result['wrong'] = answer['status'] == 'answer' and not result['correct']
                        result['unnecessary_abstention'] = answer['status'] == 'abstain' and answerable
                    except Exception as exc:
                        result = {'status': 'error', 'error_type': type(exc).__name__}
                    result.update(case_id=case_id, condition=condition, source_answerable=answerable)
                    record['rows'].append(result)
                    old.write(path / 'result.json', result)
                    old.write(output / 'record.json', record)
        record['status'] = 'completed_with_errors' if any(r['status'] == 'error' for r in record['rows']) else 'completed'
    except Exception as exc:
        record['status'] = 'failed'
        record['error_type'] = type(exc).__name__
        raise
    finally:
        record['summary'] = summarize(record['rows'])
        record['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if gateway:
            record['budget'] = {'calls': gateway.calls, 'reserved_usd': gateway.reserved,
                                'reported_usd': gateway.actual, 'missing_cost': gateway.missing_cost}
            gateway.client.close()
        old.write(output / 'record.json', record)
    print(json.dumps({'run_id': run_id, 'status': record['status'], 'cases': len(record['cases']),
                      'summary': record['summary'], 'budget': record.get('budget'),
                      'peak_rss_kib': record['peak_rss_kib']}, indent=2))


if __name__ == '__main__':
    main()
