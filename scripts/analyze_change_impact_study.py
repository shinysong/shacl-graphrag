#!/usr/bin/env python3
"""Independent saved-artifact audit; never imported by runtime selection."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path

from rdflib import Graph, Namespace, RDF

NS = Namespace('urn:change-impact:')
DEPTHS, FANOUTS, SEEDS = (1, 2, 4, 8), (1, 3), (11, 23, 37, 53)
FAULTS = ('complete', 'missing_edge', 'stale_edge', 'wrong_relation', 'missing_mapping', 'bad_mapping')
FORMATS = ('json', 'csv', 'rdf')
ARMS = ('direct_only', 'untyped_transitive', 'typed_json', 'typed_rdf')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def decode_representation(record):
    value, fmt = record['representation'], record['format']
    if fmt == 'json':
        packet = json.loads(value)
    elif fmt == 'csv':
        packet = {r['key']: json.loads(r['json_value']) for r in csv.DictReader(io.StringIO(value['metadata']))}
        for k in ('nodes', 'edges'):
            packet[k] = list(csv.DictReader(io.StringIO(value[k])))
    else:
        g = Graph().parse(data=value, format='nt')
        packet = {str(p)[len(str(NS)):]: json.loads(str(o)) for p, o in g.predicate_objects(NS.packet)}
        for k in ('nodes', 'edges'):
            packet[k] = []
            for s in g.subjects(RDF.type, NS[k]):
                packet[k].append({str(p)[len(str(NS)):]: str(o) for p, o in g.predicate_objects(s) if p != RDF.type})
    for k in ('nodes', 'edges'):
        packet[k].sort(key=lambda n: n['id'])
    return packet


def closure(start, pairs, one_hop=False):
    reached = {start}
    while True:
        expanded = reached | {b for a, b in pairs if a in reached}
        if one_hop or expanded == reached:
            return expanded
        reached = expanded


def audit_runtime(packet, row):
    arm, out = row['arm'], row['output']
    arcs, missing = [], []
    for e in packet['edges']:
        if e['status'] != 'active':
            continue
        mode = packet['catalog'].get(e['relation'])
        if mode is None:
            missing.append(e['id'])
        if arm == 'untyped_transitive':
            arcs += [(e['source'], e['target'], e['id']), (e['target'], e['source'], e['id'])]
        elif mode in ('forward', 'inverse'):
            a, b = e['source'], e['target']
            arcs.append((b, a, e['id']) if mode == 'inverse' else (a, b, e['id']))
    reached = closure(packet['changed'], [(a, b) for a, b, _ in arcs], arm == 'direct_only')
    candidates = sorted(n['id'] for n in packet['nodes'] if n['kind'] == 'product' and n['id'] in reached and n['id'] != packet['changed'])
    assert candidates == out['candidates']
    assert [list(a) for a in sorted(arcs)] == out['eligible_edges']
    assert sorted(missing) == out['unmapped_edge_ids']
    reasons = []
    if not packet['coverage']['relations_complete']:
        reasons.append('declared_relation_incompleteness')
    if packet['coverage']['source_version'] != packet['coverage']['advertised_version']:
        reasons.append('stale_source')
    if missing:
        reasons.append('unmapped_active_relation')
    if arm in ('direct_only', 'untyped_transitive'):
        reasons.append('approximate_policy')
    assert reasons == out['uncertainty']
    assert out['status'] == ('partial/unknown' if reasons else 'complete')
    assert set(out['witnesses']) == set(candidates)
    for target, witness in out['witnesses'].items():
        positions = {packet['changed']}
        assert witness
        if arm == 'direct_only':
            assert len(witness) == 1
        for edge in witness:
            positions = {b for a, b, eid in arcs if eid == edge and a in positions}
            assert positions
        assert target in positions


def analyze(run, output):
    manifest = json.loads((run / 'manifest.json').read_text())
    assert manifest['protocol'] == 'change-impact-1' and manifest['status'] == 'complete'
    for name, h in manifest['artifact_hashes'].items():
        assert hashlib.sha256((run / name).read_bytes()).hexdigest() == h, name
    for name, h in manifest['source_hashes'].items():
        assert hashlib.sha256((run / 'source' / Path(name).name).read_bytes()).hexdigest() == h, name
    cases = load_rows(run / 'cases.jsonl')
    packets = load_rows(run / 'packets.jsonl')
    rows = load_rows(run / 'rows.jsonl')
    expected = {f'd{d}-f{f}-s{s}-{fault}' for d, f, s, fault in itertools.product(DEPTHS, FANOUTS, SEEDS, FAULTS)}
    cmap = {c['case_id']: c for c in cases}
    assert len(cases) == len(cmap) == 192 and set(cmap) == expected
    pmap = {(p['case_id'], p['format']): p for p in packets}
    assert len(packets) == len(pmap) == 576 and set(pmap) == set(itertools.product(expected, FORMATS))
    rmap = {(r['case_id'], r['format'], r['arm']): r for r in rows}
    assert len(rows) == len(rmap) == 2304 and set(rmap) == set(itertools.product(expected, FORMATS, ARMS))
    assert manifest['completed_rows'] == 2304 and manifest['completed_cases'] == 192
    for c in cases:
        reached = closure('changed', [(e['child'], e['parent']) for e in c['canonical_bom'] if e['status'] == 'active'])
        truth = sorted(n['id'] for n in c['canonical_nodes'] if n['kind'] == 'product' and n['id'] in reached)
        assert truth == c['truth']
        assert len(truth) == c['fanout']
    for key, p in pmap.items():
        assert decode_representation(p) == p['packet']
        assert digest(p['representation']) == p['representation_hash']
        assert digest(p['packet']) == p['graph_hash']
        assert digest(p['packet']['catalog']) == p['model_hash']
        assert p['packet'] == pmap[(key[0], 'json')]['packet']
        assert digest(p['packet']) == cmap[key[0]]['mutation']['after_packet_hash']
    groups = defaultdict(Counter)
    for r in rows:
        c, p = cmap[r['case_id']], pmap[(r['case_id'], r['format'])]
        assert r['graph_hash'] == p['graph_hash'] and r['model_hash'] == p['model_hash']
        audit_runtime(p['packet'], r)
        got, truth = set(r['output']['candidates']), set(c['truth'])
        complete = r['output']['status'] == 'complete'
        score = dict(exact=got == truth, false_positive=sorted(got - truth), false_negative=sorted(truth - got), complete_claim=complete, unsafe_complete_claim=complete and got != truth)
        assert r['evaluation'] == score
        for key in (r['arm'], r['arm'] + '/' + c['fault'], r['arm'] + '/depth-' + str(c['depth'])):
            # Headline aggregates only JSON to avoid counting serializations as new cases.
            if r['format'] != 'json':
                continue
            counter = groups[key]
            counter['cases'] += 1
            counter['exact'] += score['exact']
            counter['false_positive_targets'] += len(score['false_positive'])
            counter['false_negative_targets'] += len(score['false_negative'])
            counter['complete_claims'] += complete
            counter['unsafe_complete_claims'] += score['unsafe_complete_claim']
            counter['partial_or_unknown'] += not complete
    for cid in expected:
        for arm in ARMS:
            ref = rmap[(cid, 'json', arm)]
            for fmt in FORMATS:
                assert rmap[(cid, fmt, arm)]['output'] == ref['output']
        for fmt in FORMATS:
            assert rmap[(cid, fmt, 'typed_json')]['output'] == rmap[(cid, fmt, 'typed_rdf')]['output']
    output.mkdir(parents=True, exist_ok=False)
    summary = dict(run_id=run.name, protocol=manifest['protocol'], verification={'status': 'complete', 'cases': 192, 'packets': 576, 'rows': 2304, 'typed_pairs': 576, 'format_arm_groups': 768}, groups={k: dict(v) for k, v in sorted(groups.items())}, scope='Synthetic manufacturing potential-impact targeting; JSON-only aggregates, formats are paired controls; no approval or physical prediction.')
    samples = []
    for fault in FAULTS:
        cid = f'd4-f3-s11-{fault}'
        samples.append(dict(case=cmap[cid], packet=pmap[(cid, 'json')]['packet'], rows=[rmap[(cid, 'json', a)] for a in ARMS]))
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (output / 'samples.json').write_text(json.dumps(samples, indent=2) + '\n')
    print(json.dumps(summary))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    analyze(args.run, args.output)
