# Offline ontology reasoning review packet

The user asks to broaden beyond SHACL and investigate ontology meaning, explicit reasoning and reuse. This is an OFFLINE synthetic implementation and experiment protocol review; no OpenRouter calls, no new infrastructure. Existing paid-call stop remains. Output is not a medical/financial truth or LLM benchmark.

Planned design:64 graph instances = depths1/2/4/8 x spine fanout1/3 x vocabulary mapping absent/present x two vocabulary namespaces x clean/disjoint-class-conflict. Ten triple-membership queries per graph, three arms,1920 rows. Same graphs reused across query types; not640 independent domains. Fanout means terminal siblings, not exponential tree. Two vocabulary namespaces are structural renamings, NOT independent real domain validation.

Arms: asserted exact membership ablation; generic JSON positive-rule closure; owlrl actual OWLRL_Semantics closure. JSON and OWL-RL receive IDENTICAL explicit ontology semantics, so this is a tool/implementation comparison, not ontology vs no ontology. No predetermined advantage expected between equal-expressivity arms. Missing mapping/absent facts give unknown, never false. Supported subset: subclass membership, subproperty, inverse, transitive, length2 property chain. DirectParent is subproperty of transitive Ancestor; DirectParent itself is NOT transitive. Property chains derive product supplyCountry from suppliedBy/locatedIn. Reverse/unrelated queries test over-inference. Schema and facts only enter infer; evaluator separate. All identifiers opaque URNs. No NLP mapping or SPARQL generation.

Conflict condition places one entity in a subclass of a class disjoint with its other asserted class; all arms record disjoint-type witnesses separately, OWL arm additionally stores native owlrl error diagnostics. On inconsistent graphs membership means operational positive-rule closure membership, NOT full classical OWL entailment. Do not claim general DL consistency or truth verification. Same-as/restrictions/negation/temporal policies not tested. JSON fixed schema supports only stated subset; OWL closure includes additional standard vocabulary triples not compared as full closure equality.

Per graph/arm closure serialization and latency stored once and shared by10query rows (do not sum as10 independent timings). All planned row IDs/statuses persisted before reasoning; rows flushed; failed active graph/arm and unfinished planned rows retained. Full closures are actual local artifacts. JSON proof DAG first deterministic derivation, not globally minimal, must not attribute it to OWL native proofs. Strict fresh output dir. Signal handler preserves interruption. No API budgets affected.

Unit tests implemented but NOT RUN: entire finite fixture query agreement with independently specified expectations, missing mappings/directions/direct-vs-transitive, cycles, proof input leaves, conflict diagnostics without operational explosion, malformed chains, output refusal/failure retention, evaluator boundary. Registered check: unit-tests only. Main must run new actual suite separately AFTER passing gates and record raw outputs before reporting results. No benchmark numbers yet. Full fixture generator/evaluator and tests omitted from packet; mark those unverified, do not invent defects. Root statically inspected those source files. Source hash freeze will cover both files. Current daily role cap may prevent synthesis/checks; do not bypass. Ready means protocol review ready, not executed result.

Below are exact runtime inference/recording source excerpts; fixture generation is omitted.

```python
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

```
