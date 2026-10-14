#!/usr/bin/env python3
"""Bounded change-impact-1 representation controls; no API or database calls.

Fanout is the number of independent depth-d branches sharing only their root.
Untyped traversal is undirected active-edge connectivity. Typed arms use the
published catalog, including wrong entries. A status is a conditional coverage
claim, never assurance of externally true semantics.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import random
import shutil
import time
from collections import deque
from pathlib import Path

from rdflib import RDF, Graph, Literal, Namespace, URIRef

PROTOCOL = 'change-impact-1'
DEPTHS = (1, 2, 4, 8)
FANOUTS = (1, 3)
SEEDS = (11, 23, 37, 53)
FAULTS = ('complete', 'missing_edge', 'stale_edge', 'wrong_relation', 'missing_mapping', 'bad_mapping')
FORMATS = ('json', 'csv', 'rdf')
ARMS = ('direct_only', 'untyped_transitive', 'typed_json', 'typed_rdf')
NS = Namespace('urn:change-impact:')
CATALOG = {'partOf': 'forward', 'usedIn': 'forward', 'contains': 'inverse', 'associatedWith': 'ignore'}
EXPECTED_CASES = len(DEPTHS)*len(FANOUTS)*len(SEEDS)*len(FAULTS)
EXPECTED_ROWS = EXPECTED_CASES*len(FORMATS)*len(ARMS)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def normalize(packet):
    """Canonicalize ordering; reject duplicate identifiers rather than collapsing."""
    p = copy.deepcopy(packet)
    for key in ('nodes', 'edges'):
        ids = [row['id'] for row in p[key]]
        if len(ids) != len(set(ids)):
            raise ValueError(f'duplicate {key} identifiers')
        p[key].sort(key=lambda row: row['id'])
    ids = {n['id'] for n in p['nodes']}
    if p['changed'] not in ids:
        raise ValueError('changed node absent')
    for edge in p['edges']:
        if edge['source'] not in ids or edge['target'] not in ids:
            raise ValueError('dangling endpoint')
        if edge['status'] not in ('active', 'retired'):
            raise ValueError('invalid edge status')
    if not set(p['catalog'].values()) <= {'forward', 'inverse', 'ignore'}:
        raise ValueError('invalid catalog entry')
    return p


def make_case(depth, fanout, seed, fault):
    """Build evaluator BOM first, then independently mutate a source-only packet."""
    if depth not in DEPTHS or fanout not in FANOUTS or seed not in SEEDS or fault not in FAULTS:
        raise ValueError('outside declared matrix')
    rng = random.Random(seed * 1000 + depth * 10 + fanout)
    nodes = [{'id': 'changed', 'kind': 'component'}]
    bom, edges = [], []
    targets = rng.sample(range(100, 999), fanout)
    for branch in range(fanout):
        prev = 'changed'
        for level in range(1, depth + 1):
            node = f'p{targets[branch]}' if level == depth else f'a{branch}_{level}_{rng.randrange(10000)}'
            nodes.append({'id': node, 'kind': 'product' if level == depth else 'assembly'})
            edge_id = f'b{branch}_{level}'
            bom.append({'id': edge_id, 'child': prev, 'parent': node, 'status': 'active'})
            relation = rng.choice(('partOf', 'usedIn', 'contains'))
            src, dst = (node, prev) if relation == 'contains' else (prev, node)
            edges.append({'id': edge_id, 'source': src, 'target': dst, 'relation': relation, 'status': 'active'})
            prev = node
    for node in ('unrelated', 'retired_product', 'old_product'):
        nodes.append({'id': node, 'kind': 'product'})
    edges.extend([
        {'id': 'noise', 'source': 'changed', 'target': 'unrelated', 'relation': 'associatedWith', 'status': 'active'},
        {'id': 'retired', 'source': 'changed', 'target': 'retired_product', 'relation': 'partOf', 'status': 'retired'},
    ])
    bom.append({'id': 'retired', 'child': 'changed', 'parent': 'retired_product', 'status': 'retired'})
    original = normalize({'changed': 'changed', 'nodes': nodes, 'edges': edges, 'catalog': CATALOG,
                              'coverage': {'relations_complete': True, 'source_version': 'v2', 'advertised_version': 'v2'}})
    packet = copy.deepcopy(original)
    selected = next(e for e in packet['edges'] if e['id'] == 'b0_1')
    before = copy.deepcopy(packet)
    if fault == 'missing_edge':
        packet['edges'].remove(selected)
        packet['coverage']['relations_complete'] = False
    elif fault == 'stale_edge':
        # The old source asserts the branch's first edge to a former product.
        if selected['relation'] == 'contains':
            selected['source'] = 'old_product'
        else:
            selected['target'] = 'old_product'
        packet['coverage']['source_version'] = 'v1'
    elif fault == 'wrong_relation':
        selected['relation'] = 'associatedWith'
    elif fault == 'missing_mapping':
        del packet['catalog'][selected['relation']]
    elif fault == 'bad_mapping':
        packet['catalog']['associatedWith'] = 'forward'
    packet = normalize(packet)
    # Evaluator truth uses only independent child/parent BOM, never source catalog.
    reachable = {'changed'}
    while True:
        expanded = reachable | {e['parent'] for e in bom if e['status'] == 'active' and e['child'] in reachable}
        if expanded == reachable:
            break
        reachable = expanded
    truth = sorted(n['id'] for n in nodes if n['kind'] == 'product' and n['id'] in reachable)
    case_id = f'd{depth}-f{fanout}-s{seed}-{fault}'
    case = {'case_id': case_id, 'depth': depth, 'fanout': fanout, 'seed': seed, 'fault': fault,
                'canonical_bom': bom, 'canonical_nodes': nodes, 'truth': truth,
                'mutation': {'before_packet_hash': digest(before), 'after_packet_hash': digest(packet),
                          'selected_edge_id': selected['id'], 'kind': fault},
                'original_packet': original}
    return case, packet


def encode(packet, fmt):
    p = normalize(packet)
    if fmt == 'json':
        return canonical(p)
    if fmt == 'csv':
        tables = {}
        for key in ('nodes', 'edges'):
            out = io.StringIO(newline='')
            writer = csv.DictWriter(out, fieldnames=sorted(p[key][0]) if p[key] else ['id'])
            writer.writeheader()
            writer.writerows(p[key])
            tables[key] = out.getvalue()
        # Metadata is a two-column table with JSON-valued cells, preserving types.
        out = io.StringIO(newline='')
        writer = csv.writer(out)
        writer.writerow(['key', 'json_value'])
        for key in sorted(set(p) - {'nodes', 'edges'}):
            writer.writerow([key, canonical(p[key])])
        tables['metadata'] = out.getvalue()
        return tables
    if fmt == 'rdf':
        graph = Graph()
        for kind in ('nodes', 'edges'):
            for index, record in enumerate(p[kind]):
                subject = URIRef(f'{NS}{kind}/{index}')
                graph.add((subject, RDF.type, NS[kind]))
                for key, value in record.items():
                    graph.add((subject, NS[key], Literal(value)))
        for key in sorted(set(p) - {'nodes', 'edges'}):
            graph.add((NS.packet, NS[key], Literal(canonical(p[key]))))
        return '\n'.join(sorted(graph.serialize(format='nt').splitlines())) + '\n'
    raise ValueError(fmt)


def decode(serialized, fmt):
    if fmt == 'json':
        packet = json.loads(serialized)
    elif fmt == 'csv':
        packet = {key: list(csv.DictReader(io.StringIO(serialized[key]))) for key in ('nodes', 'edges')}
        packet.update({r['key']: json.loads(r['json_value']) for r in csv.DictReader(io.StringIO(serialized['metadata']))})
    elif fmt == 'rdf':
        graph = Graph().parse(data=serialized, format='nt')
        packet = {key: [] for key in ('nodes', 'edges')}
        for kind in packet:
            for subject in graph.subjects(RDF.type, NS[kind]):
                packet[kind].append({str(pred).removeprefix(str(NS)): str(obj)
                                     for pred, obj in graph.predicate_objects(subject) if pred != RDF.type})
        packet.update({str(pred).removeprefix(str(NS)): json.loads(str(obj))
                       for pred, obj in graph.predicate_objects(NS.packet)})
    else:
        raise ValueError(fmt)
    return normalize(packet)


def eligible_edges(packet, untyped=False):
    arcs, unmapped = [], []
    for e in packet['edges']:
        if e['status'] != 'active':
            continue
        mode = packet['catalog'].get(e['relation'])
        if mode is None:
            unmapped.append(e['id'])
        if untyped:
            arcs.extend([(e['source'], e['target'], e['id']), (e['target'], e['source'], e['id'])])
        elif mode == 'forward':
            arcs.append((e['source'], e['target'], e['id']))
        elif mode == 'inverse':
            arcs.append((e['target'], e['source'], e['id']))
    return sorted(arcs), sorted(unmapped)


def traverse(start, arcs, direct=False):
    adjacency = {}
    for source, target, edge in arcs:
        adjacency.setdefault(source, []).append((target, edge))
    paths = {start: []}
    queue = deque([start])
    while queue:
        source = queue.popleft()
        if direct and paths[source]:
            continue
        for target, edge in adjacency.get(source, []):
            if target not in paths:
                paths[target] = paths[source] + [edge]
                queue.append(target)
    return paths


def select(packet, arm):
    """Runtime receives no case, fault label, canonical BOM, or evaluator truth."""
    if arm not in ARMS:
        raise ValueError(arm)
    p = normalize(packet)
    arcs, unmapped = eligible_edges(p, untyped=arm == 'untyped_transitive')
    paths = traverse(p['changed'], arcs, direct=arm == 'direct_only')
    products = {n['id'] for n in p['nodes'] if n['kind'] == 'product'}
    candidates = sorted((set(paths) - {p['changed']}) & products)
    if arm == 'typed_rdf':
        graph = Graph()
        ids = {n['id']: URIRef(f'{NS}entity/{i}') for i, n in enumerate(p['nodes'])}
        reverse = {v: k for k, v in ids.items()}
        for src, dst, _ in arcs:
            graph.add((ids[src], NS.eligible, ids[dst]))
        for product in products:
            graph.add((ids[product], RDF.type, NS.Product))
        results = graph.query('SELECT DISTINCT ?target WHERE { ?start <urn:change-impact:eligible>+ ?target . ?target a <urn:change-impact:Product> . FILTER(?target != ?start) }', initBindings={'start': ids[p['changed']]})
        candidates = sorted(reverse[row.target] for row in results)
        if candidates != sorted((set(paths) - {p['changed']}) & products):
            raise AssertionError('SPARQL/path witness disagreement')
    reasons = []
    if not p['coverage']['relations_complete']:
        reasons.append('declared_relation_incompleteness')
    if p['coverage']['source_version'] != p['coverage']['advertised_version']:
        reasons.append('stale_source')
    if unmapped:
        reasons.append('unmapped_active_relation')
    if arm in ('direct_only', 'untyped_transitive'):
        reasons.append('approximate_policy')
    return {'candidates': candidates, 'witnesses': {c: paths[c] for c in candidates},
                'status': 'partial/unknown' if reasons else 'complete', 'uncertainty': reasons,
                'unmapped_edge_ids': unmapped, 'eligible_edges': [list(a) for a in arcs]}


def score(output, truth):
    actual, expected = set(output['candidates']), set(truth)
    exact = actual == expected
    return {'exact': exact, 'false_positive': sorted(actual - expected), 'false_negative': sorted(expected - actual),
                'complete_claim': output['status'] == 'complete',
                'unsafe_complete_claim': output['status'] == 'complete' and not exact}


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    archive = output / 'source'
    archive.mkdir()
    root = Path(__file__).resolve().parents[1]
    source_hashes = {}
    for name in ('scripts/run_change_impact_study.py', 'scripts/analyze_change_impact_study.py', 'tests/test_change_impact_study.py'):
        source = root / name
        if source.exists():
            shutil.copyfile(source, archive / source.name)
            source_hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {'protocol': PROTOCOL, 'status': 'running', 'expected_cases': EXPECTED_CASES, 'expected_rows': EXPECTED_ROWS,
                    'completed_cases': 0, 'completed_rows': 0, 'formats': FORMATS, 'arms': ARMS, 'depths': DEPTHS,
                    'fanouts': FANOUTS, 'seeds': SEEDS, 'faults': FAULTS, 'source_hashes': source_hashes,
                    'model_hash': digest(CATALOG), 'model_kind': 'published typed relation catalog; no learned model',
                    'fanout_definition': 'independent depth-d branches sharing only changed root',
                    'budget_seconds': 300, 'paid_api_calls': 0}
    start = time.monotonic()
    write_json(output / 'manifest.json', manifest)
    try:
        with (output / 'cases.jsonl').open('w') as cases, (output / 'packets.jsonl').open('w') as packets, (output / 'rows.jsonl').open('w') as rows:
            for depth in DEPTHS:
                for fanout in FANOUTS:
                    for seed in SEEDS:
                        for fault in FAULTS:
                            if time.monotonic() - start > 300:
                                raise TimeoutError('declared 300-second runtime budget exceeded')
                            case, packet = make_case(depth, fanout, seed, fault)
                            cases.write(canonical(case) + '\n')
                            cases.flush()
                            for fmt in FORMATS:
                                representation = encode(packet, fmt)
                                normalized = decode(representation, fmt)
                                if normalized != packet:
                                    raise AssertionError('lossless representation parity failed')
                                packet_record = {'case_id': case['case_id'], 'format': fmt, 'packet': normalized,
                                                     'representation': representation, 'graph_hash': digest(normalized),
                                                     'representation_hash': digest(representation), 'model_hash': digest(normalized['catalog'])}
                                packets.write(canonical(packet_record) + '\n')
                                packets.flush()
                                for arm in ARMS:
                                    actual = select(normalized, arm)
                                    row = {'case_id': case['case_id'], 'format': fmt, 'arm': arm, 'output': actual,
                                               'graph_hash': digest(normalized), 'model_hash': digest(normalized['catalog']),
                                               'evaluation': score(actual, case['truth'])}
                                    rows.write(canonical(row) + '\n')
                                    rows.flush()
                                    manifest['completed_rows'] += 1
                            manifest['completed_cases'] += 1
                            write_json(output / 'manifest.json', manifest)
        manifest['status'] = 'complete'
    except BaseException as exc:
        manifest['status'] = 'partial'
        manifest['failure'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        manifest['elapsed_seconds'] = time.monotonic() - start
        manifest['artifact_hashes'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in output.glob('*.jsonl')}
        write_json(output / 'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(canonical(run(args.output)))


if __name__ == '__main__':
    main()
