"""Compare question-relevant gating on the frozen YAGO cohort (protocol 0.4)."""
import argparse
import hashlib
import json
import platform
import random
import shutil
import subprocess
import time
import uuid
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

from pyshacl import validate
from rdflib import RDF, RDFS, SH, XSD, Graph, Literal, Namespace, URIRef
from run_gleif_pilot import Gateway, aggregate, clone, facts, graph_text, write

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'experiments/yago'
SC = Namespace('http://schema.org/')
QUERY = '''PREFIX schema: <http://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
CONSTRUCT { ?subject ?p ?o . ?place ?cp ?co . }
WHERE { ?subject ?p ?o . OPTIONAL {
 ?subject schema:birthPlace ?place . ?place ?cp ?co .
 FILTER (?cp IN (rdf:type, rdfs:label)) } }'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retrieve(source, subject):
    return source.query(QUERY, initBindings={'subject': subject}).graph


def make_case(data, cohort, item, variant):
    # Keep all selected entity descriptions in the case-specific source, but only
    # retrieve query subject + its current object descriptions. Gold never enters repair.
    source = clone(data)
    subject, place = URIRef(item['subject']), URIRef(item['place'])
    other_place = next(URIRef(x['place']) for x in cohort if x['place'] != item['place'])
    other_person = next(URIRef(x['subject']) for x in cohort if x['subject'] != item['subject'])
    if variant == 'duplicate_relation':
        source.add((subject, SC.birthPlace, other_place))
    elif variant in ('wrong_class', 'wrong_place'):
        source.set((subject, SC.birthPlace, other_person if variant == 'wrong_class' else other_place))
    elif variant == 'wrong_datatype':
        date = source.value(subject, SC.birthDate)
        source.set((subject, SC.birthDate, Literal(str(date), datatype=XSD.string)))
    if variant == 'source_missing_relation':
        source.remove((subject, SC.birthPlace, None))
    evidence = retrieve(source, subject)
    if variant == 'missing_label':
        evidence.remove((subject, RDFS.label, None))
    elif variant == 'missing_relation':
        evidence.remove((subject, SC.birthPlace, None))
        evidence.remove((place, None, None))
    elif variant == 'missing_target_type':
        evidence.remove((place, RDF.type, None))
    return source, evidence


def inspect(graph, shapes, taxonomy, subject):
    started = time.perf_counter()
    conforms, report, _ = validate(graph, shacl_graph=shapes, ont_graph=taxonomy,
                                  inference='none',
                                  abort_on_first=False, advanced=False, js=False)
    if not isinstance(report, Graph):
        raise RuntimeError('ValidationFailure')  # noqa: TRY004 - pySHACL sentinel
    # Filter results after evaluation: pySHACL focus_nodes also filters nested
    # literal shapes, which can silently bypass sh:or datatype validation.
    focus = {subject} | set(graph.objects(subject, SC.birthPlace))
    for root in list(report.subjects(RDF.type, SH.ValidationReport)):
        for result in list(report.objects(root, SH.result)):
            if report.value(result, SH.focusNode) not in focus:
                report.remove((root, SH.result, result))
    retained = {r for root in report.subjects(RDF.type, SH.ValidationReport)
                for r in report.objects(root, SH.result)}
    conforms = not retained
    for root in report.subjects(RDF.type, SH.ValidationReport):
        report.set((root, SH.conforms, Literal(conforms)))
    issues = sorted({(str(report.value(r, SH.focusNode)),
                      str(report.value(r, SH.resultPath) or ''),
                      str(report.value(r, SH.sourceConstraintComponent)),
                      str(report.value(r, SH.value) or ''))
                     for r in retained})
    return bool(conforms), report, issues, (time.perf_counter() - started) * 1000


def has_class(graph, taxonomy, node, expected):
    return any(cls == expected or expected in taxonomy.transitive_objects(cls, RDFS.subClassOf)
               for cls in graph.objects(node, RDF.type))


def python_conforms(graph, taxonomy, subject):
    """Equivalent checks for this restricted evidence profile, not all YAGO shapes."""
    focus = {subject} | set(graph.objects(subject, SC.birthPlace))
    for node in focus:
        if has_class(graph, taxonomy, node, SC.Thing):
            labels = list(graph.objects(node, RDFS.label))
            if not labels or any(not isinstance(x, Literal) or not x.language for x in labels):
                return False
            if len({x.language.lower() for x in labels}) != len(labels):
                return False
            types = list(graph.objects(node, RDF.type))
            if not types or any((cls, RDF.type, RDFS.Class) not in taxonomy for cls in types):
                return False
        if has_class(graph, taxonomy, node, SC.Person):
            places = list(graph.objects(node, SC.birthPlace))
            if len(places) > 1 or any(not has_class(graph, taxonomy, obj, SC.Place) for obj in places):
                return False
            dates = list(graph.objects(node, SC.birthDate))
            if len(dates) > 1 or any(not isinstance(d, Literal) or d.datatype not in
                                   {XSD.date, XSD.dateTime, XSD.gYear, XSD.gYearMonth} or d.ill_typed for d in dates):
                return False
    return True


def repair(source, evidence, issues):
    repaired = clone(evidence)
    for focus, path, component, value in issues:
        if not path:
            continue
        node, predicate = URIRef(focus), URIRef(path)
        repaired.remove((node, predicate, None))
        for triple in source.triples((node, predicate, None)):
            repaired.add(triple)
        # Range checking can fail because the object description was not retrieved.
        if component == str(SH.ClassConstraintComponent) and value.startswith('http'):
            target = URIRef(value)
            for prop in (RDF.type, RDFS.label):
                repaired.remove((target, prop, None))
                for triple in source.triples((target, prop, None)):
                    repaired.add(triple)
    return repaired


def render(graph, condition):
    lines = []
    for key, (s, p, o) in facts(graph).items():
        if condition == 'R0':
            lines.append(f'[{key}] {s} has {str(p).split("/")[-1].split("#")[-1]} value {o.n3()}.')
        else:
            lines.append(f'[{key}] {s.n3()} {p.n3()} {o.n3()} .')
    return '\n'.join(lines)


def supported(answer, graph, subject):
    if answer.get('status') != 'answer' or answer.get('kind') != 'birthPlace':
        return False
    mapping = facts(graph)
    citations = answer.get('evidence_ids', [])
    if not citations or any(c not in mapping for c in citations):
        return False
    return (subject, SC.birthPlace, URIRef(answer['value'])) in {mapping[c] for c in citations}



def relevant_issues(issues, subject):
    # A preregistered single-relation question contract, not an LLM classifier.
    return [i for i in issues if i[0] == str(subject) and i[1] == str(SC.birthPlace)]


def selective_gate(evidence, issues, subject, condition):
    blockers = relevant_issues(issues, subject) if condition != 'C2' else []
    complete = len(list(evidence.objects(subject, SC.birthPlace))) == 1
    return not blockers and (complete or condition == 'S1'), blockers, complete


def selective_repair(source, evidence, subject, blockers, complete):
    # Query only the available case-specific source. Never use evaluation gold.
    if not complete:
        return retrieve(source, subject)
    return repair(source, evidence, blockers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=('development', 'pilot'), default='pilot')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    config = json.loads((FIX / 'selective-config.json').read_text())
    manifest = json.loads((FIX / 'manifest.json').read_text())
    for name, checksum in manifest['sha256'].items():
        if sha(FIX / name) != checksum:
            raise ValueError(f'Input hash mismatch: {name}')
    if sha(FIX / 'schema.ttl') != manifest['source']['files']['schema']['turtle_sha256']:
        raise ValueError('Official schema modified')
    data, shapes, taxonomy = (Graph().parse(FIX / name) for name in ('data.ttl', 'schema.ttl', 'taxonomy.ttl'))
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-yago-selective-' + uuid.uuid4().hex[:8]
    output = ROOT / 'runs' / run_id
    output.mkdir(parents=True)
    paths = ['scripts/run_yago_selective.py', 'scripts/run_yago_pilot.py', 'scripts/prepare_yago.py', 'scripts/download_yago.py',
             'scripts/run_gleif_pilot.py', 'docs/experiments/specification.md', 'uv.lock']
    paths += [str(p.relative_to(ROOT)) for p in sorted(FIX.iterdir()) if p.is_file()]
    hashes = {}
    for name in paths:
        target = output / 'inputs' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        hashes[name] = sha(ROOT / name)
    record = {'run_id': run_id, 'experiment': config['experiment'], 'protocol_version': config['protocol_version'],
              'started_at': datetime.now(UTC).isoformat(), 'status': 'running', 'split': args.split,
              'validate_only': args.validate_only, 'config': config, 'source_manifest': manifest,
              'sha256': hashes, 'python': platform.python_version(),
              'packages': {x: version(x) for x in ('rdflib', 'pyshacl', 'httpx')},
              'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, cwd=ROOT).strip(),
              'working_tree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
              'cases': [], 'rows': []}
    write(output / 'record.json', record)
    cases = []
    for item in manifest['cohort']:
        if item['split'] != args.split:
            continue
        for variant in config['variants']:
            case_id = item['subject'].rsplit('/', 1)[-1] + '-' + variant
            path = output / case_id
            path.mkdir()
            subject = URIRef(item['subject'])
            source, evidence = make_case(data, manifest['cohort'], item, variant)
            source.serialize(path / 'source.ttl', format='turtle')
            evidence.serialize(path / 'first.ttl', format='turtle')
            conforms, report, issues, elapsed = inspect(evidence, shapes, taxonomy, subject)
            report.serialize(path / 'initial-report.ttl', format='turtle')
            case = {'id': case_id, 'subject': item['subject'], 'variant': variant,
                    'gold': {'kind': 'birthPlace', 'value': None if variant == 'source_missing_relation' else item['place']},
                    'source_answerable': variant in {'clean', 'missing_label', 'missing_relation', 'missing_target_type', 'wrong_datatype'},
                    'expected_conforms': variant in {'clean', 'missing_relation', 'wrong_place', 'source_missing_relation'},
                    'conforms': conforms, 'python_conforms': python_conforms(evidence, taxonomy, subject),
                    'issues': issues, 'validation_ms': elapsed,
                    'first_sha256': hashlib.sha256(graph_text(evidence).encode()).hexdigest()}
            record['cases'].append(case)
            cases.append((case, source, evidence))
    record['functional_matches'] = sum(c['expected_conforms'] == c['conforms'] for c in record['cases'])
    record['python_shacl_matches'] = sum(c['python_conforms'] == c['conforms'] for c in record['cases'])
    record['status'] = 'running'
    write(output / 'record.json', record)
    if record['functional_matches'] != len(cases) or record['python_shacl_matches'] != len(cases):
        record['status'] = 'functional_mismatch'
        write(output / 'record.json', record)
        print(json.dumps({'run_id': run_id, 'status': record['status'], 'cases': record['cases']}, indent=2))
        return
    if not args.validate_only:
        gateway = Gateway(config, output, prompt_path=FIX / 'prompt.txt', answer_kinds=('birthPlace',))
        record['requested_model'] = gateway.model
        schedule = [(i, condition) for i in range(len(cases)) for condition in config['conditions']]
        random.Random(config['seed']).shuffle(schedule)
        for index, (i, condition) in enumerate(schedule):
            case, source, first = cases[i]
            subject = URIRef(case['subject'])
            path = output / case['id'] / condition
            path.mkdir()
            row = {'case_id': case['id'], 'variant': case['variant'], 'condition': condition,
                   'status': 'running', 'first_sha256': case['first_sha256'],
                   'retrieval_calls': 1, 'retrieved_triples': len(first), 'validation_ms': 0.0}
            started = time.perf_counter()
            try:
                evidence = clone(first)
                permitted = True
                if condition in ('G1', 'G2'):
                    permitted, report, issues, ms = inspect(evidence, shapes, taxonomy, subject)
                    row['validation_ms'] += ms
                    report.serialize(path / 'report-0.ttl', format='turtle')
                    if condition == 'G2':
                        for attempt in range(config['max_retries']):
                            if permitted:
                                break
                            before = graph_text(evidence)
                            evidence = repair(source, evidence, issues)
                            row['retrieval_calls'] += 1
                            row['retrieved_triples'] += len(evidence)
                            permitted, report, issues, ms = inspect(evidence, shapes, taxonomy, subject)
                            row['validation_ms'] += ms
                            report.serialize(path / f'report-{attempt+1}.ttl', format='turtle')
                            if graph_text(evidence) == before:
                                break
                elif condition in ('S1', 'S2', 'C2'):
                    _, report, issues, ms = inspect(evidence, shapes, taxonomy, subject)
                    row['validation_ms'] += ms
                    report.serialize(path / 'report-0.ttl', format='turtle')
                    permitted, blockers, complete = selective_gate(evidence, issues, subject, condition)
                    row['initial_blockers'] = blockers
                    row['initial_complete'] = complete
                    row['nonblocking_issues'] = [i for i in issues if i not in blockers]
                    if condition in ('S2', 'C2'):
                        for attempt in range(config['max_retries']):
                            if permitted:
                                break
                            before = graph_text(evidence)
                            evidence = selective_repair(source, evidence, subject, blockers, complete)
                            row['retrieval_calls'] += 1
                            row['retrieved_triples'] += len(evidence)
                            _, report, issues, ms = inspect(evidence, shapes, taxonomy, subject)
                            row['validation_ms'] += ms
                            report.serialize(path / f'report-{attempt+1}.ttl', format='turtle')
                            permitted, blockers, complete = selective_gate(evidence, issues, subject, condition)
                            if graph_text(evidence) == before:
                                break
                    row['final_complete'] = complete
                    row['final_blockers'] = blockers
                elif condition == 'P1':
                    vstart = time.perf_counter()
                    permitted = python_conforms(evidence, taxonomy, subject)
                    row['validation_ms'] = (time.perf_counter() - vstart) * 1000
                elif condition == 'U2':
                    evidence = retrieve(source, subject)
                    row['retrieval_calls'] += 1
                    row['retrieved_triples'] += len(evidence)
                evidence.serialize(path / 'evidence.ttl', format='turtle')
                row['final_sha256'] = hashlib.sha256(graph_text(evidence).encode()).hexdigest()
                if permitted:
                    question = f'What is the birthPlace URI of {subject}?'
                    answer, row['llm'] = gateway.generate(question, render(evidence, condition), path)
                else:
                    answer = {'status': 'abstain', 'kind': None, 'value': None, 'evidence_ids': []}
                    row['abstention_reason'] = 'validation_or_incomplete' if condition in ('S1', 'S2', 'C2') else 'validation'
                row['answer'] = answer
                row['correct'] = answer.get('status') == 'answer' and answer.get('kind') == case['gold']['kind'] and answer.get('value') == case['gold']['value']
                row['supported'] = supported(answer, evidence, subject)
                row['unnecessary_abstention'] = case['source_answerable'] and answer.get('status') == 'abstain'
                row['unknown_source_abstention'] = case['variant'] == 'source_missing_relation' and answer.get('status') == 'abstain'
                row['status'] = 'completed'
            except Exception as exc:  # noqa: BLE001 - retain every failed trial
                row.update(status='error', error_type=type(exc).__name__, correct=False, supported=False)
            row['total_ms'] = (time.perf_counter() - started) * 1000
            record['rows'].append(row)
            record['budget'] = {'calls_attempted': gateway.calls, 'reserved_upper_usd': gateway.reserved,
                                'cost_usd_reported': gateway.actual, 'missing_cost_responses': gateway.missing_cost}
            write(path / 'result.json', row)
            write(output / 'record.json', record)
            print(json.dumps({'progress': f'{index+1}/{len(schedule)}', 'condition': condition,
                              'status': row['status'], 'cost': gateway.actual}), flush=True)
        gateway.client.close()
    record['metrics'] = aggregate(record['rows'], config['conditions'])
    for condition, metrics in record['metrics'].items():
        rows = [r for r in record['rows'] if r['condition'] == condition]
        metrics['unnecessary_abstentions'] = sum(r.get('unnecessary_abstention', False) for r in rows)
        metrics['unknown_source_abstentions'] = sum(r.get('unknown_source_abstention', False) for r in rows)
        metrics['wrong_answers'] = metrics['answered'] - metrics['correct']
    record['status'] = 'completed_with_errors' if any(r['status'] == 'error' for r in record['rows']) else 'completed'
    record['finished_at'] = datetime.now(UTC).isoformat()
    write(output / 'record.json', record)
    print(json.dumps({'run_id': run_id, 'status': record['status'], 'functional_matches': record['functional_matches'],
                      'metrics': record['metrics']}, indent=2))


if __name__ == '__main__':
    main()
