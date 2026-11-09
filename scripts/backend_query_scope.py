"""Query-conditioned dependency fingerprints on complete controlled snapshots.

Only explicit subtype/subproperty queries are supported. This is a supplied
operational preprocessor, not NL interpretation, source discovery or SHACL logic.
"""
import argparse
import json
from pathlib import Path
from rdflib import Graph
from scripts.backend_advisory import python_report, shacl_report
from scripts.backend_parity import canonical, digest
from scripts.backend_inference import TYPE, SC, SP
from scripts.backend_updates import input_digest

SWAPPED = {'I1_superclass': 'I1_unrelated', 'I1_unrelated': 'I1_superclass',
           'I2_forward': 'I2_reverse', 'I2_reverse': 'I2_forward'}


def dependency(state, query):
    kind = query['kind']
    if kind not in ('type', 'relation'):
        raise ValueError('unsupported query kind')
    predicate = SC if kind == 'type' else SP
    edges = {(s, o) for s, p, o in state['schema'] if p == predicate}
    backwards = {query['target']}
    while True:
        expanded = backwards | {s for s, o in edges if o in backwards}
        if expanded == backwards:
            break
        backwards = expanded
    if kind == 'type':
        facts = {(s, p, o) for s, p, o in state['facts'] if p == TYPE and o in backwards}
        starts = {o for s, p, o in facts}
    else:
        facts = {(s, p, o) for s, p, o in state['facts'] if s == query['start'] and p in backwards}
        starts = {p for s, p, o in facts}
    forward = starts
    while True:
        expanded = forward | {o for s, o in edges if s in forward and o in backwards}
        if expanded == forward:
            break
        forward = expanded
    schema = {(s, predicate, o) for s, o in edges if s in forward and o in backwards}
    return {'query': query, 'facts': sorted(facts), 'schema': sorted(schema)}


def run(parent, shapes_path, output):
    output.mkdir(parents=True, exist_ok=False)
    saved = [json.loads(x) for x in (parent / 'results.jsonl').read_text().splitlines()]
    states = json.loads((parent / 'states.json').read_text())
    queries = {q['id']: q for q in json.loads((parent / 'queries.json').read_text())}
    snapshots = {input_digest(s): s for s in states}
    policies = ('declared_query', 'swapped_query_control')
    plan = [{'row_index': i, 'policy': p, 'checker': c} for i in range(len(saved)) for p in policies for c in ('python', 'shacl')]
    (output / 'plan.json').write_text(canonical(plan) + '\n')
    (output / 'runtime.py').write_bytes(Path(__file__).read_bytes())
    (output / 'shapes.ttl').write_bytes(shapes_path.read_bytes())
    inputs = []
    for i, row in enumerate(saved):
        for policy in policies:
            query = queries[row['query_id'] if policy == 'declared_query' else SWAPPED[row['query_id']]]
            current = dependency(snapshots[row['current_input_hash']], query)
            used = dependency(snapshots[row['used_input_hash']], query)
            inputs.append({'row_index': i, 'policy': policy, 'family': 'query_dependency', 'declared_query': query,
                           'origin': {k: row[k] for k in ('event', 'arm', 'query_id')},
                           'original_answer': row['answer'], 'original_status': row['status'],
                           'metadata': {'used_input_hash': digest(used), 'current_input_hash': digest(current)},
                           'used_dependency': used, 'current_dependency': current})
    (output / 'inputs.json').write_text(canonical(inputs) + '\n')
    shapes = Graph().parse(shapes_path, format='turtle')
    with (output / 'results.jsonl').open('a') as handle:
        for i, item in enumerate(inputs):
            for checker in ('python', 'shacl'):
                row = {k: v for k, v in item.items() if k not in ('used_dependency', 'current_dependency')}
                row.update(checker=checker, answer_changed=False, decision='advisory_only_no_veto')
                try:
                    if checker == 'python':
                        codes = python_report(item['metadata'])
                    else:
                        result = shacl_report(item['metadata'], shapes)
                        codes = result['codes']
                        row['conforms'] = result['conforms']
                        (output / f'{i}-report.ttl').write_text(result['validation_graph'])
                    row.update(status='completed', codes=codes, review_requested=bool(codes))
                except Exception as error:
                    row.update(status='checker_failure', error=f'{type(error).__name__}: {error}')
                handle.write(canonical(row) + '\n')
                handle.flush()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--shapes', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    run(a.parent, a.shapes, a.output)
