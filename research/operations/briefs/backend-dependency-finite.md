# Finite dependency property check
Following actual640slot query-scope replay: correctscope10flags8mismatch2matching0miss,swapped10flags0mismatch10matching8miss,320reportpairsagree. This is separate softwareverification, not newrealdata/LLM benchmark. Exhaustivelyenumerate3symbols9possibleedges512directedgraphs(includingcycles/selfloops), types2entitieseach0/1of3types16assignments8192states; relation3optionalexplicitfacts8assignments4096states; total12288. Thiscoincidentalcount is NOT prior shared-semantics12288cohort. IndependentFloyd-Warshall matrix oracle computes membership, runtimefunction backward/forwarddependencyseparate. GroupbyexactcanonicaldependencyJSON (notjustSHA); check anygroup withdifferingoracleanswer retainscounterexample. No goldruntimecheck/answerrepair: thisentireprogram isofflinesoftwareverification onauthoredenumeration, notexperimentalLLMruntime. PositivecasecannotproveallRDF/OWL/completeness; boundtofiniteenumeration andexplicitSC/SP rules. NoDB/newpaidcalls. Fullplannedcountsavedbeforeloops, perstate results and allcounterexamples stored;interruption leavespartialrows/planneddenominator. Generatedprogramanddependencycopied. Importedcanonical/digest deterministic; TYPE/SC/SP RDFURIs, otherimportedbodiesomittedunverified. Reviewbeforeexplicitexecution. Endwindow10:31:23UTC unchanged.

FILE scripts/check_query_dependency.py
"""Finite model check of dependency fingerprints, not a factual benchmark.

Three symbols, all nine directed/self edges, two entities with zero/one type;
separately three optional relation facts. Independent Floyd-Warshall membership.
"""
import argparse
import itertools
import json
from pathlib import Path
from scripts.backend_query_scope import dependency
from scripts.backend_inference import TYPE, SC, SP
from scripts.backend_parity import canonical, digest

SYMBOLS = ('A', 'B', 'R')
EDGES = tuple(itertools.product(SYMBOLS, repeat=2))


def oracle(facts, edges, kind):
    index = {s: i for i, s in enumerate(SYMBOLS)}
    reach = [[i == j for j in range(3)] for i in range(3)]
    for a, b in edges:
        reach[index[a]][index[b]] = True
    for k in range(3):
        for i in range(3):
            for j in range(3):
                reach[i][j] = reach[i][j] or (reach[i][k] and reach[k][j])
    if kind == 'type':
        return sorted({s for s, p, o in facts if reach[index[o]][2]})
    return sorted({o for s, p, o in facts if s == 'x' and reach[index[p]][2]})


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    plan = {'type_states': 512 * 16, 'relation_states': 512 * 8, 'total': 12288,
            'scope': 'All directed graphs on three declared symbols; restricted supplied facts. No arbitrary RDF/OWL or missing-source guarantee.'}
    (output / 'plan.json').write_text(canonical(plan) + '\n')
    (output / 'runtime.py').write_bytes(Path(__file__).read_bytes())
    (output / 'dependency-runtime.py').write_bytes(Path('scripts/backend_query_scope.py').read_bytes())
    seen = {}
    observed = 0
    counterexamples = 0
    with (output / 'results.jsonl').open('a') as results, (output / 'counterexamples.jsonl').open('a') as failures:
        for kind in ('type', 'relation'):
            query = {'kind': kind, 'target': 'R'} | ({'start': 'x'} if kind == 'relation' else {})
            for mask in range(512):
                edges = [edge for i, edge in enumerate(EDGES) if mask & (1 << i)]
                assignments = itertools.product(range(4), repeat=2) if kind == 'type' else itertools.product(range(2), repeat=3)
                for assignment in assignments:
                    if kind == 'type':
                        facts = [(s, TYPE, SYMBOLS[t-1]) for s, t in zip(('x', 'y'), assignment) if t]
                    else:
                        options = [('x', 'A', 'y'), ('x', 'B', 'z'), ('other', 'A', 'y')]
                        facts = [fact for fact, present in zip(options, assignment) if present]
                    state = {'facts': facts, 'schema': [(a, SC if kind == 'type' else SP, b) for a, b in edges]}
                    selected = dependency(state, query)
                    # Compare exact serialized content, not hash equality alone.
                    key = canonical(selected)
                    answer = oracle(facts, edges, kind)
                    row = {'case_id': observed, 'kind': kind, 'schema_mask': mask, 'assignment': assignment,
                           'dependency_sha256': digest(selected), 'oracle_answer': answer}
                    if key in seen and seen[key]['oracle_answer'] != answer:
                        counterexamples += 1
                        failures.write(canonical({'first': seen[key], 'second': row, 'dependency': selected}) + '\n')
                        failures.flush()
                    seen.setdefault(key, row)
                    results.write(canonical(row) + '\n')
                    observed += 1
    result = {'planned': plan['total'], 'observed': observed, 'dependency_groups': len(seen),
              'same_dependency_different_answer': counterexamples,
              'scope': 'Finite verification of a conditional dependency property with a separate matrix algorithm; not empirical QA or general proof.'}
    (output / 'evaluation.json').write_text(canonical(result) + '\n')
    print(json.dumps(result, indent=2))
    if observed != plan['total'] or counterexamples:
        raise SystemExit(1)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    run(p.parse_args().output)

FILE scripts/backend_query_scope.py
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
