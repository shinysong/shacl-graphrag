"""Build authored performance fixtures, never execute an experimental arm.

Runtime contains operational facts and update commands only. Scorer references
use construction-time dynamic programming, not a runtime implementation.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'research/technology-selection'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_case(spec):
    cid, depth, width = spec['case_id'], spec['depth'], spec['width']
    rng = random.Random(spec['seed'])
    layers = [['root']] + [[f'l{i}n{n}' for n in range(width)]
                           for i in range(1, depth)] + [['X', 'E', 'F']]
    pairs = [(a, b) for previous, following in zip(layers, layers[1:])
             for a in previous for b in following]
    reachable_count = len(pairs)
    pairs.extend((f'u{i}a', f'u{i}b') for i in range(spec['edges'] - reachable_count))
    names = sorted({n for pair in pairs for n in pair} | {'U'})
    permutation = [f'n{i:05d}' for i in range(len(names))]
    rng.shuffle(permutation)
    nodes = dict(zip(names, permutation))

    def ident(label):
        return hashlib.sha256((cid + ':' + label).encode()).hexdigest()[:24]

    def row(label, **fields):
        return dict(occurrence_id=ident('occ:' + label), **fields)

    rid, oid, iid, certid = [ident(k) for k in ('receipt', 'order', 'inspection', 'certificate')]
    facility, other_facility = ident('facility'), ident('other-facility')
    scope = dict(part=nodes['root'], revision='R1', facility=facility)
    tables = dict(
        receipt=[row('receipt', id=rid, **scope, order_line_id=oid,
                     inspection_id=iid, certificate_id=certid, quantity=5,
                     uom='Nos', received_at='2026-09-15')],
        order_line=[row('order', id=oid, **scope, remaining_quantity=10, uom='Nos')],
        inspection=[row('inspection', id=iid, **scope, receipt_id=rid, status='Accepted')],
        certificate=[row('certificate', id=certid, **scope, valid_from='2026-01-01',
                         expires='2026-10-01', status='Active')],
        product=[row('product:' + role, id=nodes[role], revision='R1',
                     facility=other_facility if role == 'F' else facility,
                     requires_current_certificate=role != 'E') for role in ('X', 'E', 'F', 'U')],
        component_edge=[])
    # IDs are assigned before row shuffling; reference DP relies on construction
    # order of the DAG, not on the order later supplied to any arm.
    best = {'root': []}
    for index, (a, b) in enumerate(pairs):
        edge = row(f'edge:{index}', id=ident(f'edge:{index}'), component_item=nodes[a],
                   component_revision='R1', parent_item=nodes[b], parent_revision='R1', active=True)
        tables['component_edge'].append(edge)
        if a in best:
            path = best[a] + [edge['occurrence_id']]
            if b not in best or (len(path), path) < (len(best[b]), best[b]):
                best[b] = path
    for rows in tables.values():
        rng.shuffle(rows)
    packet = dict(scene_id=cid, policy_id='technology-selection-1', tables=tables,
                  question=dict(receipt_id=rid, target_item=nodes['root'], target_revision='R1',
                                certificate_id=certid, as_of='2026-10-21'),
                  coverage=[row('coverage', table='component_edge', complete=True)])
    updates = {
        'E': {'operation': 'deactivate_incoming', 'product_id': nodes['X'], 'revision': 'R1'},
        'C': {'operation': 'set_certificate_expiry', 'certificate_id': certid, 'expires': '2026-11-01'},
    }
    # These literal decisions follow the authored policy. They are not imported
    # from runtime code. A separate raw-graph checker validates path references.
    base = dict(scene_id=cid, receipt_id=rid, receipt='accept',
                links={k: 'resolved' for k in ('order_line', 'inspection', 'certificate')},
                impact_graph_completeness='complete', violated_checks=[], unknown_checks=[],
                products=sorted([dict(id=nodes[role], revision='R1',
                                     candidate='no' if role == 'U' else 'yes',
                                     recheck='required' if role == 'X' else 'not_required',
                                     witness=best.get(role, [])) for role in ('X', 'E', 'F', 'U')],
                                key=lambda r: (r['id'], r['revision'])))
    edge_update, cert_update = copy.deepcopy(base), copy.deepcopy(base)
    for product in edge_update['products']:
        if product['id'] == nodes['X']:
            product.update(candidate='no', recheck='not_required', witness=[])
    for product in cert_update['products']:
        product['recheck'] = 'not_required'
    lineage = dict(origin='study_authored_records', policy_origin='study_authored_policy',
                   manifest_case=spec, root=nodes['root'], product_roles={k: nodes[k] for k in ('X', 'E', 'F', 'U')},
                   reachable_nodes_including_root=len(best), reachable_edges=reachable_count,
                   unrelated_edges=len(pairs) - reachable_count,
                   note='Identity/row-order sensitivity, not independent operational or domain samples.')
    return packet, updates, {'baseline': base, 'E': edge_update, 'C': cert_update}, lineage


def build(output):
    output.mkdir(parents=True, exist_ok=False)
    for name in ('runtime', 'scorer'):
        (output / name).mkdir()
    freeze = json.loads((ROOT / '_workspace/technology-selection/protocol-1/freeze.json').read_text())
    for name, expected in freeze['hashes'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('protocol design changed after review: ' + name)
    cases = json.loads((STUDY / 'cases-v1.json').read_text())
    files = {}
    for spec in cases:
        packet, updates, expected, lineage = make_case(spec)
        cid = spec['case_id']
        artifacts = {f'runtime/{cid}.json': {'packet': packet, 'updates': updates},
                     f'scorer/{cid}-expected.json': expected,
                     f'scorer/{cid}-lineage.json': lineage,
                     f'scorer/{cid}-source.json': packet}
        for name, value in artifacts.items():
            (output / name).write_text(encoded(value))
            files[name] = digest(output / name)
    bindings = dict(freeze['hashes'])
    for path in (Path(__file__), ROOT / 'scripts/check_technology_selection_fixtures.py',
                 ROOT / 'research/technology-selection/io-v1.json', ROOT / 'uv.lock'):
        bindings[str(path.relative_to(ROOT))] = digest(path)
    manifest = dict(study_id='technology-selection-1', case_count=len(cases),
                    worker_attempts=198, origin='study_authored_records', files=files, bindings=bindings,
                    reference_method='Literal policy decisions plus construction-order DAG path DP; separately checked from raw graph.',
                    limitations=['No arm executed', 'No real company records', 'No independent expert truth labels',
                                 'Performance fixtures are complete/valid; semantic failure fixtures are separate future checks'])
    (output / 'manifest.json').write_text(encoded(manifest))
    print(json.dumps({'cases': len(cases), 'files': len(files), 'arm_executions': 0, 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
