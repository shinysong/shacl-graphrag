"""Run a bounded, exploratory GLEIF evidence-validation and real LLM QA pilot."""
import argparse
import hashlib
import json
import platform
import random
import re
import shutil
import subprocess
import time
import uuid
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import httpx
from dotenv import dotenv_values
from pyshacl import validate
from rdflib import RDF, SH, XSD, Graph, Literal, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'experiments/gleif'
EX = Namespace('https://example.org/gleif-pilot/')
LEI = Namespace('https://rdf.gleif.org/L1/L-')
REASONS = {'NO_LEI', 'NATURAL_PERSONS', 'NON_CONSOLIDATING', 'NO_KNOWN_PERSON', 'NON_PUBLIC'}
QUERY = '''PREFIX ex: <https://example.org/gleif-pilot/>
CONSTRUCT { ?subject ?p ?o . ?parent ?pp ?po . }
WHERE { ?subject ?p ?o . OPTIONAL { ?subject ex:directParent ?parent . ?parent ?pp ?po . } }'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def clone(graph):
    result = Graph()
    for triple in graph:
        result.add(triple)
    return result


def graph_text(graph):
    return '\n'.join(sorted(' '.join(x.n3() for x in triple) + ' .' for triple in graph)) + '\n'


def add_entity(graph, entity):
    subject = LEI[entity['lei']]
    graph.add((subject, RDF.type, EX.Entity))
    graph.add((subject, EX.lei, Literal(entity['lei'])))
    graph.add((subject, EX.legalName, Literal(entity['name'])))


def make_source(dataset, item):
    graph = Graph()
    subject = LEI[item['lei']]
    add_entity(graph, dataset['entities'][item['lei']])
    graph.add((subject, RDF.type, EX.QuerySubject))
    if item['kind'] == 'parent':
        add_entity(graph, dataset['entities'][item['parent']])
        graph.add((subject, EX.directParent, LEI[item['parent']]))
    else:
        graph.add((subject, EX.exceptionReason, Literal(item['reason'])))
    return graph


def retrieve(source, subject):
    return source.query(QUERY, initBindings={'subject': subject}).graph


def make_case(dataset, item, variant):
    source = make_source(dataset, item)
    subject = LEI[item['lei']]
    if variant == 'invalid_lei':
        source.set((LEI[item['parent']], EX.lei, Literal('INVALID-LEI')))
    elif variant == 'wrong_parent':
        # Use a real, different, fully described entity. No detectable type violation.
        other = next(e for lei, e in sorted(dataset['entities'].items())
                     if lei not in {item['lei'], item['parent']})
        source.remove((subject, EX.directParent, None))
        source.remove((LEI[item['parent']], None, None))
        add_entity(source, other)
        source.add((subject, EX.directParent, LEI[other['lei']]))
    elif variant == 'invalid_reason':
        source.set((subject, EX.exceptionReason, Literal('UNDEFINED_REASON')))
    evidence = retrieve(source, subject)
    if variant == 'missing_name':
        evidence.remove((subject, EX.legalName, None))
    elif variant == 'missing_relation':
        evidence.remove((subject, EX.directParent, None))
        evidence.remove((LEI[item['parent']], None, None))
    elif variant == 'missing_exception':
        evidence.remove((subject, EX.exceptionReason, None))
    return source, evidence


def inspect(graph, shapes):
    start = time.perf_counter()
    conforms, report, _ = validate(graph, shacl_graph=shapes, inference='none',
                                  abort_on_first=False, advanced=False, js=False)
    if not isinstance(report, Graph):
        raise RuntimeError('ValidationFailure')  # noqa: TRY004 - pySHACL failure sentinel
    issues = sorted({(str(report.value(r, SH.focusNode)),
                      str(report.value(r, SH.resultPath) or ''),
                      str(report.value(r, SH.sourceConstraintComponent)))
                     for r in report.subjects(RDF.type, SH.ValidationResult)})
    return bool(conforms), report, issues, (time.perf_counter() - start) * 1000


def python_conforms(graph):
    def one_string(values):
        return len(values) == 1 and isinstance(values[0], Literal) and values[0].language is None and values[0].datatype in (None, XSD.string)
    for node in graph.subjects(RDF.type, EX.Entity):
        leis, names = list(graph.objects(node, EX.lei)), list(graph.objects(node, EX.legalName))
        if not one_string(leis) or not re.fullmatch(r'[A-Z0-9]{18}[0-9]{2}', str(leis[0])):
            return False
        if not one_string(names) or not str(names[0]):
            return False
    for node in graph.subjects(RDF.type, EX.QuerySubject):
        parents, reasons = list(graph.objects(node, EX.directParent)), list(graph.objects(node, EX.exceptionReason))
        if (len(parents), len(reasons)) not in ((1, 0), (0, 1)):
            return False
        if parents and (parents[0], RDF.type, EX.Entity) not in graph:
            return False
        if reasons and reasons[0] not in {Literal(x) for x in REASONS}:
            return False
    return True


def repair(source, evidence, subject, issues):
    result = clone(evidence)
    for focus, path, _ in issues:
        node = URIRef(focus)
        if path:
            predicate = URIRef(path)
            result.remove((node, predicate, None))
            for triple in source.triples((node, predicate, None)):
                result.add(triple)
        else:
            # xone failure: retrieve both relation and reporting-exception paths.
            for predicate in (EX.directParent, EX.exceptionReason):
                result.remove((subject, predicate, None))
                for triple in source.triples((subject, predicate, None)):
                    result.add(triple)
            for parent in result.objects(subject, EX.directParent):
                for triple in source.triples((parent, None, None)):
                    result.add(triple)
    return result


def facts(graph):
    return {f'E{i:03d}': triple for i, triple in enumerate(sorted(graph, key=lambda t: tuple(x.n3() for x in t)), 1)}


def evidence_text(graph, condition):
    lines = []
    for key, (s, p, o) in facts(graph).items():
        if condition == 'R0':
            label = str(p).split('/')[-1].split('#')[-1]
            lines.append(f'[{key}] Entity {s} has {label} value {o!s}.')
        else:
            lines.append(f'[{key}] {s.n3()} {p.n3()} {o.n3()} .')
    return '\n'.join(lines)


def answer_support(answer, graph, subject):
    if answer.get('status') != 'answer':
        return False
    available = facts(graph)
    cited = answer.get('evidence_ids', [])
    if not cited or any(key not in available for key in cited):
        return False
    triples = {available[key] for key in cited}
    value = answer.get('value')
    if answer.get('kind') == 'exception':
        return (subject, EX.exceptionReason, Literal(value)) in triples
    if answer.get('kind') == 'parent':
        return any((subject, EX.directParent, parent) in triples and
                   (parent, EX.lei, Literal(value)) in triples
                   for parent in graph.objects(subject, EX.directParent))
    return False


class Gateway:
    def __init__(self, config, directory, *, prompt_path=None, answer_kinds=("parent", "exception")):
        env = dotenv_values(ROOT / '.env')
        key = env.get('OPENROUTER_API_KEY')
        if not key or key.startswith('your_'):
            raise RuntimeError('Missing OpenRouter credential')
        self.model = env.get('OPENROUTER_MODEL', 'openai/gpt-4o-mini')
        self.base = env.get('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').rstrip('/')
        if self.base != 'https://openrouter.ai/api/v1':
            raise ValueError('Pilot gateway must be official OpenRouter endpoint')
        self.client = httpx.Client(timeout=60, headers={'Authorization': 'Bearer ' + key})
        self.config, self.directory = config, directory
        self.calls, self.reserved, self.actual, self.missing_cost = 0, 0.0, 0.0, 0
        self.prompt = (prompt_path or FIX / 'prompt.txt').read_text()
        self.answer_kinds = set(answer_kinds)

    def generate(self, question, evidence, path):
        config = self.config
        content = question + '\n\nEvidence:\n' + evidence
        chars = len(self.prompt) + len(content)
        if chars > config['max_prompt_chars']:
            raise RuntimeError('PromptLimit')
        # UTF-8 bytes + overhead is a conservative token bound, price-capped server-side.
        prices = config['provider_max_price_per_million']
        upper = ((len((self.prompt + content).encode()) + 2048) * prices['prompt']
                 + config['max_completion_tokens'] * prices['completion']) / 1e6
        if self.calls >= config['max_llm_calls'] or self.reserved + upper > config['max_cost_usd']:
            raise RuntimeError('BudgetLimit')
        self.calls += 1
        self.reserved += upper  # Retain reservation even after failed requests.
        request = {'model': self.model, 'temperature': config['temperature'],
                   'max_tokens': config['max_completion_tokens'],
                   'response_format': {'type': 'json_object'},
                   'provider': {'max_price': prices, 'allow_fallbacks': False},
                   'usage': {'include': True},
                   'messages': [{'role': 'system', 'content': self.prompt}, {'role': 'user', 'content': content}]}
        write(path / 'request.json', request)
        started = time.perf_counter()
        response = self.client.post(self.base + '/chat/completions', json=request)
        elapsed = (time.perf_counter() - started) * 1000
        # Response only, never headers, request client or env/credential contents.
        (path / 'response.json').write_text(response.text)
        response.raise_for_status()
        raw = response.json()
        usage = raw.get('usage', {})
        if usage.get('cost') is None:
            self.missing_cost += 1
        else:
            self.actual += usage['cost']
        text = raw['choices'][0]['message']['content']
        answer = json.loads(text)
        if answer.get('status') not in {'answer', 'abstain'} or not isinstance(answer.get('evidence_ids'), list):
            raise ValueError('InvalidAnswerSchema')
        if not all(isinstance(x, str) for x in answer['evidence_ids']):
            raise ValueError('InvalidCitations')
        if answer['status'] == 'answer' and (answer.get('kind') not in self.answer_kinds or not isinstance(answer.get('value'), str)):
            raise ValueError('InvalidAnswerValue')
        return answer, {'model': raw.get('model'), 'provider': raw.get('provider'),
                        'generation_id': raw.get('id'), 'usage': usage, 'llm_ms': elapsed,
                        'finish_reason': raw['choices'][0].get('finish_reason')}


def aggregate(rows, conditions):
    result = {}
    for condition in conditions:
        group = [r for r in rows if r['condition'] == condition]
        answered = [r for r in group if r.get('answer', {}).get('status') == 'answer']
        correct = sum(r.get('correct', False) for r in group)
        result[condition] = {'total': len(group), 'answered': len(answered), 'correct': correct,
                             'accuracy_all': correct / len(group) if group else None,
                             'accuracy_answered': correct / len(answered) if answered else None,
                             'abstained': sum(r.get('answer', {}).get('status') == 'abstain' for r in group),
                             'errors': sum(r['status'] == 'error' for r in group),
                             'supported_answers': sum(r.get('supported', False) for r in group),
                             'retrieval_calls': sum(r.get('retrieval_calls', 0) for r in group),
                             'retrieved_triples': sum(r.get('retrieved_triples', 0) for r in group),
                             'validation_ms': sum(r.get('validation_ms', 0) for r in group),
                             'llm_calls': sum('llm' in r for r in group),
                             'prompt_tokens': sum(r.get('llm', {}).get('usage', {}).get('prompt_tokens', 0) for r in group),
                             'completion_tokens': sum(r.get('llm', {}).get('usage', {}).get('completion_tokens', 0) for r in group),
                             'cost_usd_reported': sum(r.get('llm', {}).get('usage', {}).get('cost', 0) or 0 for r in group),
                             'mean_total_ms': sum(r.get('total_ms', 0) for r in group) / len(group) if group else None}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--split', choices=['development', 'pilot'], default='pilot')
    parser.add_argument('--validate-only', action='store_true', help='No LLM; preserve functional check as a separate run')
    args = parser.parse_args()
    config = json.loads((FIX / 'config.json').read_text())
    dataset = json.loads(args.dataset.read_text())
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-gleif-' + uuid.uuid4().hex[:8]
    output = ROOT / 'runs' / run_id
    output.mkdir(parents=True)
    inputs = ['scripts/run_gleif_pilot.py', 'scripts/prepare_gleif.py', 'scripts/download_gleif.py',
              'experiments/gleif/shapes.ttl', 'experiments/gleif/config.json', 'experiments/gleif/prompt.txt',
              'docs/experiments/specification.md', 'uv.lock']
    hashes = {}
    for relative in inputs:
        path = ROOT / relative
        target = output / 'inputs' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        hashes[relative] = sha(path)
    shutil.copyfile(args.dataset, output / 'dataset.json')
    record = {'run_id': run_id, 'experiment': config['experiment'], 'protocol_version': config['protocol_version'],
              'started_at': datetime.now(UTC).isoformat(), 'status': 'running',
              'split': args.split, 'validate_only': args.validate_only,
              'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'working_tree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
              'sha256': hashes, 'dataset_sha256': sha(args.dataset), 'source_manifest': dataset['source_manifest'],
              'python': platform.python_version(), 'packages': {p: version(p) for p in ['rdflib', 'pyshacl', 'httpx']},
              'config': config, 'cases': [], 'rows': []}
    write(output / 'record.json', record)
    shapes = Graph().parse(FIX / 'shapes.ttl')
    cases = []
    for item in dataset['cohort']:
        if item['split'] != args.split:
            continue
        for variant in config[item['kind'] + '_variants']:
            case_id = item['lei'] + '-' + variant
            source, first = make_case(dataset, item, variant)
            case_path = output / case_id
            case_path.mkdir()
            source.serialize(case_path / 'source.ttl', format='turtle')
            first.serialize(case_path / 'first.ttl', format='turtle')
            conforms, report, issues, ms = inspect(first, shapes)
            report.serialize(case_path / 'initial-report.ttl', format='turtle')
            expected = variant in ('clean', 'wrong_parent')
            case = {'id': case_id, 'subject': item['lei'], 'variant': variant,
                    'kind': item['kind'], 'expected_conforms': expected, 'conforms': conforms,
                    'python_conforms': python_conforms(first), 'issues': issues,
                    'validation_ms': ms, 'first_sha256': hashlib.sha256(graph_text(first).encode()).hexdigest(),
                    'gold': {'kind': item['kind'], 'value': item.get('parent', item.get('reason'))}}
            record['cases'].append(case)
            cases.append((case, source, first))
    record['functional_matches'] = sum(c['expected_conforms'] == c['conforms'] for c in record['cases'])
    record['python_shacl_matches'] = sum(c['python_conforms'] == c['conforms'] for c in record['cases'])
    write(output / 'record.json', record)
    if not args.validate_only:
        gateway = Gateway(config, output)
        record['requested_model'] = gateway.model
        schedule = [(i, condition) for i in range(len(cases)) for condition in config['conditions']]
        random.Random(config['seed']).shuffle(schedule)
        for index, (i, condition) in enumerate(schedule):
            case, source, first = cases[i]
            subject = LEI[case['subject']]
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
                    permitted, report, issues, ms = inspect(evidence, shapes)
                    row['validation_ms'] += ms
                    report.serialize(path / 'report-0.ttl', format='turtle')
                    if condition == 'G2':
                        for attempt in range(config['max_retries']):
                            if permitted:
                                break
                            before = graph_text(evidence)
                            evidence = repair(source, evidence, subject, issues)
                            row['retrieval_calls'] += 1
                            # Actual returned graph snapshot size (not unique network bytes).
                            row['retrieved_triples'] += len(evidence)
                            permitted, report, issues, ms = inspect(evidence, shapes)
                            row['validation_ms'] += ms
                            report.serialize(path / f'report-{attempt + 1}.ttl', format='turtle')
                            if graph_text(evidence) == before:
                                break
                elif condition == 'P1':
                    vstart = time.perf_counter()
                    permitted = python_conforms(evidence)
                    row['validation_ms'] = (time.perf_counter() - vstart) * 1000
                elif condition == 'U2':
                    evidence = retrieve(source, subject)
                    row['retrieval_calls'] += 1
                    row['retrieved_triples'] += len(evidence)
                evidence.serialize(path / 'evidence.ttl', format='turtle')
                row['final_sha256'] = hashlib.sha256(graph_text(evidence).encode()).hexdigest()
                if not permitted:
                    answer = {'status': 'abstain', 'kind': None, 'value': None, 'evidence_ids': []}
                    row['abstention_reason'] = 'validation'
                else:
                    question = f'For legal entity LEI {case["subject"]}, provide its direct accounting-consolidation parent LEI, or its reported direct-parent exception code.'
                    answer, row['llm'] = gateway.generate(question, evidence_text(evidence, condition), path)
                row['answer'] = answer
                row['correct'] = answer.get('status') == 'answer' and answer.get('kind') == case['gold']['kind'] and answer.get('value') == case['gold']['value']
                row['supported'] = answer_support(answer, evidence, subject)
                row['status'] = 'completed'
            except Exception as exc:  # noqa: BLE001 - retain failed trials, never discard them
                row.update(status='error', error_type=type(exc).__name__, correct=False, supported=False)
                # Do not serialize exception messages which can include request internals.
            row['total_ms'] = (time.perf_counter() - started) * 1000
            record['rows'].append(row)
            record['budget'] = {'calls_attempted': gateway.calls, 'reserved_upper_usd': gateway.reserved,
                                'cost_usd_reported': gateway.actual, 'missing_cost_responses': gateway.missing_cost}
            write(path / 'result.json', row)
            write(output / 'record.json', record)
            print(json.dumps({'progress': f'{index+1}/{len(schedule)}', 'condition': condition, 'status': row['status'], 'cost': gateway.actual}), flush=True)
        gateway.client.close()
    record['metrics'] = aggregate(record['rows'], config['conditions'])
    record['status'] = 'completed_with_errors' if any(r['status'] == 'error' for r in record['rows']) else 'completed'
    if record['functional_matches'] != len(cases) or record['python_shacl_matches'] != len(cases):
        record['status'] = 'functional_mismatch'
    record['finished_at'] = datetime.now(UTC).isoformat()
    write(output / 'record.json', record)
    print(json.dumps({'run_id': run_id, 'status': record['status'], 'cases': len(cases),
                      'functional_matches': record['functional_matches'], 'metrics': record['metrics']}, indent=2))


if __name__ == '__main__':
    main()
