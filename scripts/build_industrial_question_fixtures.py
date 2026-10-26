"""Author 24 controlled scenes; never run arms or derive labels from runtime code."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'research/industrial-questions/protocol-v1.json'
EXPECTATIONS = ROOT / 'research/industrial-questions/expectations-v1.json'


def opaque(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def encode(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def scene(index, depth, family):
    """Family is construction-only and must not be returned in runtime packet."""
    sid = opaque(f'industrial-questions-1:{index}')
    def ident(label):
        return opaque(sid + ':' + label)
    def row(label, **values):
        return dict(occurrence_id=ident('occ:' + label), **values)
    part, facility, other = ident('part'), ident('facility'), ident('other-facility')
    rid, oid, iid, cid = [ident(k) for k in ('receipt', 'order', 'inspection', 'certificate')]
    product_ids = [ident('product:' + str(i)) for i in range(4)]
    tables = {
        'receipt': [row('receipt', id=rid, part=part, revision='R1', facility=facility,
                        order_line_id=oid, inspection_id=iid, certificate_id=cid,
                        quantity='5', uom='Nos', received_at='2026-09-15')],
        'order_line': [row('order', id=oid, part=part, revision='R1', facility=facility,
                           remaining_quantity='10', uom='Nos')],
        'inspection': [row('inspection', id=iid, receipt_id=rid, part=part,
                           revision='R1', facility=facility, status='Accepted')],
        'certificate': [row('certificate', id=cid, part=part, revision='R1', facility=facility,
                            valid_from='2026-01-01', expires='2026-10-01', status='Active')],
        'component_edge': [],
        'product': [row('product:' + str(i), id=pid, revision='R1',
                        facility=other if i == 3 else facility,
                        requires_current_certificate=i != 1)
                    for i, pid in enumerate(product_ids)],
    }
    paths = {}
    # Three independent branches; product 2 is deliberately unrelated.
    for product_index in (0, 1, 3):
        nodes = [part] + [ident(f'node:{product_index}:{d}') for d in range(depth - 1)]
        nodes += [product_ids[product_index]]
        paths[product_index] = []
        for d, (a, b) in enumerate(zip(nodes, nodes[1:])):
            edge = row(f'edge:{product_index}:{d}', id=ident(f'edge:{product_index}:{d}'),
                       component_item=a, component_revision='R1', parent_item=b,
                       parent_revision='R1', active=True)
            tables['component_edge'].append(edge)
            paths[product_index].append(edge['occurrence_id'])
    coverage = [row('coverage:' + name, table=name, complete=True) for name in tables]
    def incomplete(name):
        next(c for c in coverage if c['table'] == name)['complete'] = False
    removed_source = []
    if family == 'unexpired_now':
        tables['certificate'][0]['expires'] = '2026-12-01'
    elif family == 'expires_exactly_as_of':
        tables['certificate'][0]['expires'] = '2026-10-21'
    elif family == 'expired_before_receipt':
        tables['certificate'][0]['expires'] = '2026-09-01'
    elif family == 'rejected_inspection':
        tables['inspection'][0]['status'] = 'Rejected'
    elif family == 'over_remaining_quantity':
        tables['receipt'][0]['quantity'] = '11'
    elif family == 'missing_inspection_source':
        removed_source.append(tables['inspection'].pop())
        incomplete('inspection')
    elif family == 'ambiguous_order_line':
        duplicate = copy.deepcopy(tables['order_line'][0])
        duplicate['occurrence_id'] = ident('occ:second-order')
        tables['order_line'].append(duplicate)
    elif family == 'missing_certificate_expiry':
        del tables['certificate'][0]['expires']
    elif family == 'component_edge_missing_source':
        removed_source.append(tables['component_edge'].pop(0))
        incomplete('component_edge')
    elif family == 'certificate_wrong_revision':
        tables['certificate'][0]['revision'] = 'R2'
    elif family not in ('complete_expired_now_valid_at_receipt', 'component_edge_omitted_projection'):
        raise ValueError(family)
    source = copy.deepcopy({'tables': tables, 'coverage': coverage})
    omitted_projection = []
    if family == 'component_edge_omitted_projection':
        omitted_projection.append(tables['component_edge'].pop(0))
        incomplete('component_edge')
    packet = {
        'scene_id': sid, 'policy_id': 'industrial-questions-1',
        'question': dict(receipt_id=rid, target_item=part, target_revision='R1',
                         certificate_id=cid, as_of='2026-10-21'),
        'tables': tables, 'coverage': coverage,
    }
    lineage = dict(scene_id=sid, family=family, depth=depth,
                   origin='study_authored_record', policy_origin='study_authored_policy',
                   product_roles=product_ids, constructed_paths=paths,
                   removed_before_source=removed_source, omitted_from_projection=omitted_projection)
    return packet, source, lineage


def build(output):
    # Never overwrite a consumed attempt. Partial failures remain on disk.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'runtime').mkdir()
    (output / 'scorer').mkdir()
    policy = json.loads(POLICY.read_text())
    expected = json.loads(EXPECTATIONS.read_text())
    assert set(expected) == set(policy['cases']['families'])
    manifest = {'origin': 'study_authored_record', 'scenes': [], 'bindings': {},
                'planned_denominators': {'receipt': 24, 'links': 72, 'candidate': 96,
                                        'recheck': 96, 'impact_graph_completeness': 24}}
    bindings = [POLICY, EXPECTATIONS, Path(__file__), ROOT / 'uv.lock',
                ROOT / 'research/industrial-questions/io-contract-v1.json',
                ROOT / 'research/sources/erpnext-procurement.json']
    for folder in ('source-acquisition-1', 'source-examples-1'):
        directory = ROOT / '_workspace/industrial-questions-v1' / folder
        manifests = ['manifest.json'] + (['certification-manifest.json'] if folder == 'source-acquisition-1'
                                       else ['child-doc-manifest.json'])
        for name in manifests:
            mp = directory / name
            bindings.append(mp)
            for record in json.loads(mp.read_text())['records']:
                if record['status'] != 'saved':
                    continue
                original = directory / record.get('saved_as', 'child-doctype.raw')
                # Acquisition byte integrity only, not authentication of source truth.
                assert hashlib.sha256(original.read_bytes()).hexdigest() == record['sha256']
                bindings.append(original)
    for path in bindings:
        manifest['bindings'][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / 'runtime/policy.json').write_text(encode({
        key: policy[key] for key in ('id', 'time', 'identity', 'receipt_policy',
                                    'impact_policy', 'runtime_contract', 'shared_dates')}))
    index = 0
    for family in policy['cases']['families']:
        for depth in (1, 3):
            packet, source, lineage = scene(index, depth, family)
            index += 1
            sid = packet['scene_id']
            expectation = copy.deepcopy(expected[family])
            expectation['scene_id'] = sid
            expectation['receipt_id'] = packet['question']['receipt_id']
            expectation['products'] = [dict(id=pid, revision='R1', candidate=candidate, recheck=recheck)
                                       for pid, candidate, recheck in zip(lineage['product_roles'],
                                                expectation.pop('candidates'), expectation.pop('rechecks'))]
            files = {f'runtime/{sid}.json': packet, f'scorer/{sid}-source.json': source,
                     f'scorer/{sid}-lineage.json': lineage, f'scorer/{sid}-expected.json': expectation}
            for name, content in files.items():
                (output / name).write_text(encode(content))
            manifest['scenes'].append({'scene_id': sid,
                'runtime_records': sum(map(len, packet['tables'].values())) + len(packet['coverage']),
                'files': {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in files}})
    manifest['runtime_policy_sha256'] = hashlib.sha256((output / 'runtime/policy.json').read_bytes()).hexdigest()
    (output / 'manifest.json').write_text(encode(manifest))
    print(json.dumps({'scenes': index, 'output': str(output), 'arm_executions': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
