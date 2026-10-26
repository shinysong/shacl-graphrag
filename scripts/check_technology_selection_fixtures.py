"""Offline fixture integrity checker; does not import builder or runtime arms."""
import argparse
import copy
import hashlib
import heapq
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def shortest(edges, root):
    # Heap on (path length, occurrence sequence): independent of builder's
    # topological construction DP and future runtime sorted BFS.
    frontier, paths = [(0, (), root)], {}
    while frontier:
        distance, sequence, node = heapq.heappop(frontier)
        if node in paths:
            continue
        paths[node] = list(sequence)
        for edge in edges:
            if edge['active'] and edge['component_item'] == node:
                heapq.heappush(frontier, (distance + 1, sequence + (edge['occurrence_id'],), edge['parent_item']))
    return paths


def check(folder):
    manifest = json.loads((folder / 'manifest.json').read_text())
    assert manifest['case_count'] == 22 and len(manifest['files']) == 88
    for name, value in manifest['bindings'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value, name
    for name, value in manifest['files'].items():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == value, name
    cases = json.loads((ROOT / 'research/technology-selection/cases-v1.json').read_text())
    runs = json.loads((ROOT / 'research/technology-selection/runs-v1.json').read_text())
    assert len(runs) == 198 and len({r['attempt_id'] for r in runs}) == 198
    assert {(r['case_id'], r['arm'], r['repeat']) for r in runs} == {
        (c['case_id'], arm, repeat) for c in cases
        for arm in ('python_indexed', 'sqlite_recursive', 'rdf_owl_shacl') for repeat in range(3)}
    for spec in cases:
        cid = spec['case_id']
        runtime = json.loads((folder / 'runtime' / (cid + '.json')).read_text())
        assert set(runtime) == {'packet', 'updates'}
        p = runtime['packet']
        assert set(p) == {'scene_id', 'policy_id', 'tables', 'question', 'coverage'}
        assert p == json.loads((folder / 'scorer' / (cid + '-source.json')).read_text())
        line = json.loads((folder / 'scorer' / (cid + '-lineage.json')).read_text())
        refs = json.loads((folder / 'scorer' / (cid + '-expected.json')).read_text())
        assert line['manifest_case'] == spec
        t = p['tables']
        assert set(t) == {'receipt', 'order_line', 'inspection', 'certificate', 'component_edge', 'product'}
        assert all(len(t[name]) == 1 for name in ('receipt', 'order_line', 'inspection', 'certificate'))
        assert len(t['product']) == 4
        all_rows = sum(t.values(), []) + p['coverage']
        assert len({row['occurrence_id'] for row in all_rows}) == len(all_rows)
        for rows in t.values():
            assert len({r['id'] for r in rows}) == len(rows)
        receipt, order, inspection, cert = [t[k][0] for k in ('receipt', 'order_line', 'inspection', 'certificate')]
        assert p['question'] == dict(receipt_id=receipt['id'], target_item=receipt['part'], target_revision='R1',
                                     certificate_id=cert['id'], as_of='2026-10-21')
        assert receipt['order_line_id'] == order['id'] and receipt['inspection_id'] == inspection['id']
        assert receipt['certificate_id'] == cert['id'] and inspection['receipt_id'] == receipt['id']
        for row in (order, inspection, cert):
            assert all(row[k] == receipt[k] for k in ('part', 'revision', 'facility'))
        assert type(receipt['quantity']) is int and receipt['quantity'] == 5
        assert type(order['remaining_quantity']) is int and order['remaining_quantity'] == 10
        assert receipt['uom'] == order['uom'] == 'Nos'
        assert receipt['received_at'] == '2026-09-15' and inspection['status'] == 'Accepted'
        assert cert['status'] == 'Active' and cert['valid_from'] == '2026-01-01' and cert['expires'] == '2026-10-01'
        assert len(p['coverage']) == 1 and p['coverage'][0]['table'] == 'component_edge'
        assert p['coverage'][0]['complete'] is True
        edges, roles = t['component_edge'], line['product_roles']
        assert len(edges) == spec['edges'] and set(roles) == {'X', 'E', 'F', 'U'}
        assert {r['id'] for r in t['product']} == set(roles.values())
        for role, pid in roles.items():
            row = next(r for r in t['product'] if r['id'] == pid)
            assert row['revision'] == 'R1' and row['requires_current_certificate'] is (role != 'E')
            assert (row['facility'] == receipt['facility']) == (role != 'F')
        assert all(e['active'] is True and e['component_revision'] == e['parent_revision'] == 'R1' for e in edges)
        paths = shortest(edges, p['question']['target_item'])
        assert len(paths) == spec['reachable_nodes'] == line['reachable_nodes_including_root']
        relevant = [e for e in edges if e['component_item'] in paths]
        unrelated = [e for e in edges if e['component_item'] not in paths]
        assert len(relevant) == spec['reachable_edges'] == line['reachable_edges']
        assert len(unrelated) == spec['unrelated_edges'] == line['unrelated_edges']
        assert len({e[k] for e in unrelated for k in ('component_item', 'parent_item')}) == 2 * len(unrelated)
        assert all(e['parent_item'] not in paths and e['parent_item'] not in roles.values() for e in unrelated)
        assert all(len(paths[roles[r]]) == spec['depth'] for r in ('X', 'E', 'F')) and roles['U'] not in paths
        levels = [[n for n, path in paths.items() if len(path) == level]
                  for level in range(spec['depth'] + 1)]
        assert len(levels[0]) == 1 and len(levels[-1]) == 3
        assert all(len(level) == spec['width'] for level in levels[1:-1])
        assert {(e['component_item'], e['parent_item']) for e in relevant} == {
            (a, b) for left, right in zip(levels, levels[1:]) for a in left for b in right}
        assert runtime['updates'] == {'E': dict(operation='deactivate_incoming', product_id=roles['X'], revision='R1'),
                                      'C': dict(operation='set_certificate_expiry', certificate_id=cert['id'], expires='2026-11-01')}
        changed = copy.deepcopy(edges)
        for e in changed:
            if e['parent_item'] == roles['X']:
                e['active'] = False
        assert sum(not e['active'] for e in changed) == (1 if spec['depth'] == 1 else spec['width'])
        after = shortest(changed, p['question']['target_item'])
        for phase in ('baseline', 'E', 'C'):
            ref = refs[phase]
            assert set(ref) == {'scene_id', 'receipt_id', 'receipt', 'links', 'impact_graph_completeness',
                                'violated_checks', 'unknown_checks', 'products'}
            assert ref['scene_id'] == cid and ref['receipt_id'] == receipt['id'] and ref['receipt'] == 'accept'
            assert ref['links'] == {k: 'resolved' for k in ('order_line', 'inspection', 'certificate')}
            assert ref['impact_graph_completeness'] == 'complete' and ref['violated_checks'] == ref['unknown_checks'] == []
            phase_paths = after if phase == 'E' else paths
            expected = []
            for role, pid in roles.items():
                present = pid in phase_paths
                expected.append(dict(id=pid, revision='R1', candidate='yes' if present else 'no',
                                     recheck='required' if role == 'X' and phase == 'baseline' else 'not_required',
                                     witness=phase_paths.get(pid, [])))
            assert ref['products'] == sorted(expected, key=lambda r: (r['id'], r['revision']))
    print(json.dumps({'fixture_integrity': 'passed', 'cases': len(cases), 'planned_worker_slots': len(runs),
                      'reference_phases_checked': 66, 'arm_executions': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    check(parser.parse_args().folder)
