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
