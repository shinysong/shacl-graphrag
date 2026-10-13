#!/usr/bin/env python3
"""Offline, synthetic positive OWL-RL subset; no truth, SHACL or LLM benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import signal
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import Graph, Namespace, OWL, RDF, RDFS, URIRef

EX = Namespace('urn:ontology-study:')
TYPE, SUBCLASS, SUBPROPERTY = map(str, (RDF.type, RDFS.subClassOf, RDFS.subPropertyOf))
INVERSE, TRANSITIVE, DISJOINT = map(str, (OWL.inverseOf, OWL.TransitiveProperty, OWL.disjointWith))
CHAIN, FIRST, REST, NIL = map(str, (OWL.propertyChainAxiom, RDF.first, RDF.rest, RDF.nil))
ARMS = ('asserted', 'json_rules', 'owlrl')
PROTOCOL = 'ontology-reasoning-offline-1'
Triple = tuple[str, str, str]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def term(name):
    return str(EX[name])


def fixture_suite():
    """Gold is returned separately and is never an argument to an inference function.

    Fanout is a spine with fanout-1 terminal siblings at every level, not a full
    exponential tree. Transfer changes only vocabulary and explicit mappings.
    """
    cases, expected = [], {}
    for depth in (1, 2, 4, 8):
        for fanout in (1, 3):
            for mapped in (False, True):
                for domain in ('manufacturing', 'catalog'):
                    for conflict in (False, True):
                        cid = f'g{len(cases):03d}'
                        def entity(i):
                            return term(f'{cid}:e{i:03d}')

                        def cls(i):
                            return term(f'{cid}:c{i:02d}')
                        raw = term(f'{domain}:sourceLink')
                        raw_class = term(f'{domain}:sourceClass')
                        direct, ancestor, descendant = map(term, ('directParent', 'ancestor', 'descendant'))
                        supply, location, country = map(term, ('suppliedBy', 'locatedIn', 'supplyCountry'))
                        raw_supply, raw_location = term(f'{domain}:provider'), term(f'{domain}:region')
                        list_a, list_b = term(f'{cid}:listA'), term(f'{cid}:listB')
                        forbidden = term('Forbidden')
                        schema = {(cls(i), SUBCLASS, cls(i + 1)) for i in range(depth)}
                        schema |= {(direct, SUBPROPERTY, ancestor), (ancestor, TYPE, TRANSITIVE),
                                   (ancestor, INVERSE, descendant), (cls(depth), DISJOINT, forbidden),
                                   (country, CHAIN, list_a), (list_a, FIRST, supply),
                                   (list_a, REST, list_b), (list_b, FIRST, location), (list_b, REST, NIL)}
                        if mapped:
                            schema |= {(raw, SUBPROPERTY, direct), (raw_class, SUBCLASS, cls(0)),
                                       (raw_supply, SUBPROPERTY, supply), (raw_location, SUBPROPERTY, location)}
                        facts = {(entity(0), TYPE, raw_class)}
                        for i in range(depth):
                            facts.add((entity(i), raw, entity(i + 1)))
                            for branch in range(1, fanout):
                                facts.add((entity(i), raw, entity(100 + i * fanout + branch)))
                        facts |= {(entity(500), raw_supply, entity(501)),
                                  (entity(501), raw_location, entity(502))}
                        if conflict:
                            facts |= {(entity(700), TYPE, cls(0)), (entity(700), TYPE, forbidden)}
                        queries = [
                            ('subclass', (entity(0), TYPE, cls(depth)), mapped),
                            ('transitive', (entity(0), ancestor, entity(depth)), mapped),
                            ('inverse', (entity(depth), descendant, entity(0)), mapped),
                            ('direct', (entity(0), direct, entity(depth)), mapped and depth == 1),
                            ('reverse', (entity(depth), ancestor, entity(0)), False),
                            ('inverse_direction', (entity(0), descendant, entity(depth)), False),
                            ('asserted', (entity(0), raw, entity(1)), True),
                            ('unrelated', (entity(900), TYPE, cls(depth)), False),
                            ('property_chain', (entity(500), country, entity(502)), mapped),
                            ('chain_reverse', (entity(502), country, entity(500)), False),
                        ]
                        cases.append({'id': cid, 'schema': sorted(schema), 'facts': sorted(facts),
                                      'queries': [{'id': f'{cid}:q{i:02d}', 'triple': q}
                                                  for i, (_, q, _) in enumerate(queries)]})
                        for i, (kind, _, entailed) in enumerate(queries):
                            expected[f'{cid}:q{i:02d}'] = {
                                'membership': 'entailed' if entailed else 'unknown',
                                'conflict': conflict, 'query_kind': kind, 'depth': depth,
                                'fanout': fanout, 'mapped': mapped, 'domain': domain}
    return cases, expected


def property_chains(schema):
    """Read finite RDF lists; reject malformed/cyclic lists instead of guessing."""
    schema = set(map(tuple, schema))
    result = []
    for prop, predicate, head in sorted(schema):
        if predicate != CHAIN:
            continue
        seen, members, support = set(), [], [(prop, predicate, head)]
        while head != NIL:
            if head in seen:
                raise ValueError('Cyclic property-chain RDF list')
            seen.add(head)
            first = sorted(t for t in schema if t[0] == head and t[1] == FIRST)
            rest = sorted(t for t in schema if t[0] == head and t[1] == REST)
            if len(first) != 1 or len(rest) != 1:
                raise ValueError('Malformed property-chain RDF list')
            members.append(first[0][2])
            support.extend((first[0], rest[0]))
            head = rest[0][2]
        if len(members) != 2:
            raise ValueError('This restricted engine supports length-two chains only')
        result.append((prop, members, support))
    return result


def json_closure(schema, facts):
    """Vocabulary-independent positive forward chaining over the declared subset.

    Proofs record the first deterministic derivation, not a globally smallest proof.
    Schema is fixed; generated query instances do not use metamodeling axioms.
    """
    schema = set(map(tuple, schema))
    known = schema | set(map(tuple, facts))
    proofs = {t: {'rule': 'asserted', 'premises': []} for t in known}
    chains = property_chains(schema)
    while True:
        before = len(known)
        snapshot = sorted(known)
        by_predicate = {}
        for triple in snapshot:
            by_predicate.setdefault(triple[1], []).append(triple)

        def add(triple, rule, premises):
            if triple not in known:
                known.add(triple)
                proofs[triple] = {'rule': rule, 'premises': list(premises)}

        for axiom in sorted(schema):
            left, predicate, right = axiom
            if predicate == SUBCLASS:
                for t in by_predicate.get(TYPE, []):
                    if t[2] == left:
                        add((t[0], TYPE, right), 'subclass', (t, axiom))
            elif predicate == SUBPROPERTY:
                for t in by_predicate.get(left, []):
                    add((t[0], right, t[2]), 'subproperty', (t, axiom))
            elif predicate == INVERSE:
                for source, target in ((left, right), (right, left)):
                    for t in by_predicate.get(source, []):
                        add((t[2], target, t[0]), 'inverse', (t, axiom))
            elif predicate == TYPE and right == TRANSITIVE:
                for a in by_predicate.get(left, []):
                    for b in by_predicate.get(left, []):
                        if a[2] == b[0]:
                            add((a[0], left, b[2]), 'transitive', (a, b, axiom))
        for prop, members, support in chains:
            for a in by_predicate.get(members[0], []):
                for b in by_predicate.get(members[1], []):
                    if a[2] == b[0]:
                        add((a[0], prop, b[2]), 'property_chain', [a, b, *support])
        if len(known) == before:
            return known, proofs


def proof_support(query, proofs):
    """A compact reachable proof DAG, with explicit asserted schema/fact leaves."""
    visited = set()
    def visit(triple):
        if triple in visited or triple not in proofs:
            return
        visited.add(triple)
        for premise in proofs[triple]['premises']:
            visit(premise)
    visit(tuple(query))
    return [{'triple': t, **proofs[t]} for t in sorted(visited)]


def conflicts(triples, schema):
    known = set(map(tuple, triples))
    result = []
    for left, predicate, right in sorted(map(tuple, schema)):
        if predicate == DISJOINT:
            for subject, p, obj in sorted(known):
                if p == TYPE and obj == left and (subject, TYPE, right) in known:
                    result.append({'entity': subject, 'classes': [left, right]})
    return result


def infer(schema, facts, arm):
    """No evaluator, query labels, case factors, or expected answers are accepted."""
    start = time.perf_counter()
    proofs, diagnostics = {}, []
    if arm == 'owlrl':
        graph = Graph()
        for triple in [*schema, *facts]:
            graph.add(tuple(URIRef(t) for t in triple))
        DeductiveClosure(OWLRL_Semantics).expand(graph)
        triples = {tuple(map(str, t)) for t in graph}
        diagnostics = sorted(str(o) for _, p, o in graph if str(p) == 'http://www.daml.org/2002/03/agents/agent-ont#error')
        serialized = graph.serialize(format='nt')
    elif arm in ('json_rules', 'asserted'):
        triples = set(map(tuple, [*schema, *facts]))
        if arm == 'json_rules':
            triples, proofs = json_closure(schema, facts)
        graph = Graph()
        for triple in triples:
            graph.add(tuple(URIRef(t) for t in triple))
        serialized = graph.serialize(format='nt')
    else:
        raise ValueError(f'Unknown arm: {arm}')
    elapsed = (time.perf_counter() - start) * 1000
    return {'triples': triples, 'proofs': proofs, 'diagnostics': diagnostics,
            'conflicts': conflicts(triples, schema), 'elapsed_ms': elapsed, 'ntriples': serialized}


def answer(query, result):
    triple = tuple(query)
    return {'membership': 'entailed' if triple in result['triples'] else 'unknown',
            'entailed_query_triples': [triple] if triple in result['triples'] else [],
            'conflict': bool(result['conflicts']), 'conflict_details': result['conflicts'],
            'owlrl_diagnostics': result['diagnostics'],
            'proof': proof_support(triple, result['proofs'])}


def evaluate(prediction, expected):
    return {'membership_agreement': prediction['membership'] == expected['membership'],
            'conflict_agreement': prediction['conflict'] == expected['conflict']}


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def run(output):
    """Explicit fresh output directory; persist intent before doing inference."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    cases, expected = fixture_suite()
    planned = [{'id': f'{q["id"]}:{arm}', 'case_id': c['id'], 'query_id': q['id'],
                'arm': arm, 'status': 'not_executed'}
               for c in cases for arm in ARMS for q in c['queries']]
    metadata = {'protocol': PROTOCOL, 'status': 'running', 'planned_rows': len(planned),
                'started_at': datetime.now(timezone.utc).isoformat(), 'completed_rows': 0,
                'input_sha256': digest(cases), 'evaluator_sha256': digest(expected),
                'schema_sha256': {c['id']: digest(c['schema']) for c in cases},
                'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'versions': {p: version(p) for p in ('rdflib', 'owlrl')},
                'python': platform.python_version(),
                'membership_scope': 'positive-rule closure membership, not classical entailment on inconsistent graphs',
                'comparison_scope': 'same explicit ontology semantics in JSON and OWL-RL; asserted lookup is an ablation',
                'fanout_scope': 'spine with fanout-1 terminal siblings at each depth',
                'timing_scope': 'single graph closure and serialization; descriptive only',
                'conflict_scope': 'disjoint-class witnesses; not full DL consistency',
                'proof_scope': 'first derivation support, not globally minimal'}
    write_json(output / 'status.json', metadata)
    write_json(output / 'inputs.json', cases)
    write_json(output / 'evaluator.json', expected)
    write_json(output / 'planned.json', planned)
    position = {row['id']: row for row in planned}
    active = None
    try:
        with (output / 'rows.jsonl').open('x') as stream:
            for case in cases:
                for arm in ARMS:
                    active = {'case_id': case['id'], 'arm': arm}
                    result = infer(case['schema'], case['facts'], arm)
                    artifact = f'{case["id"]}-{arm}.nt'
                    (output / artifact).write_text(result['ntriples'])
                    for query in case['queries']:
                        row_id = f'{query["id"]}:{arm}'
                        prediction = answer(query['triple'], result)
                        row = {**position[row_id], 'status': 'ok', 'query': query['triple'],
                               'prediction': prediction, 'scores': evaluate(prediction, expected[query['id']]),
                               'factors': expected[query['id']], 'closure_artifact': artifact,
                               'closure_ms_shared': result['elapsed_ms'],
                               'closure_triple_count': len(result['triples'])}
                        stream.write(json.dumps(row) + '\n')
                        stream.flush()
                        position[row_id]['status'] = 'ok'
                        metadata['completed_rows'] += 1
                    write_json(output / 'planned.json', planned)
                    write_json(output / 'status.json', metadata)
        metadata['status'] = 'completed'
    except BaseException as exc:
        metadata.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                        failure={'type': type(exc).__name__, 'message': str(exc), 'active': active})
        raise
    finally:
        metadata['finished_at'] = datetime.now(timezone.utc).isoformat()
        write_json(output / 'planned.json', planned)
        write_json(output / 'status.json', metadata)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='Fresh directory, e.g. runs/<UTC timestamp>-ontology; never overwritten')
    args = parser.parse_args()
    def interrupt(signum, frame):
        raise KeyboardInterrupt(f'Signal {signum}')
    signal.signal(signal.SIGTERM, interrupt)
    print(json.dumps(run(args.output), indent=2))


if __name__ == '__main__':
    main()
