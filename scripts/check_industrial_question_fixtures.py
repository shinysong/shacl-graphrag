"""Offline artifact integrity checks, not a business accuracy experiment."""
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
repo = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(p.read_text())
manifest = read(root / 'manifest.json')
assert len(manifest['scenes']) == 24
for name, digest in manifest['bindings'].items():
    assert hashlib.sha256((repo / name).read_bytes()).hexdigest() == digest
assert hashlib.sha256((root / 'runtime/policy.json').read_bytes()).hexdigest() == manifest['runtime_policy_sha256']
families = {}
for entry in manifest['scenes']:
    sid = entry['scene_id']
    for name, digest in entry['files'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    packet = read(root / f'runtime/{sid}.json')
    lineage = read(root / f'scorer/{sid}-lineage.json')
    source = read(root / f'scorer/{sid}-source.json')
    expected = read(root / f'scorer/{sid}-expected.json')
    assert set(packet) == {'scene_id', 'policy_id', 'question', 'tables', 'coverage'}
    assert entry['runtime_records'] <= 100
    rows = sum(packet['tables'].values(), []) + packet['coverage']
    assert len({r['occurrence_id'] for r in rows}) == len(rows)
    assert len(packet['tables']['receipt']) == 1
    assert len(packet['tables']['product']) == len(expected['products']) == 4
    assert len(expected['links']) == 3
    f = lineage['family']
    families.setdefault(f, []).append(lineage['depth'])
    if f == 'ambiguous_order_line':
        orders = packet['tables']['order_line']
        assert len(orders) == 2 and orders[0]['id'] == orders[1]['id']
        assert orders[0]['occurrence_id'] != orders[1]['occurrence_id']
    if f == 'component_edge_omitted_projection':
        assert len(source['tables']['component_edge']) == len(packet['tables']['component_edge']) + 1
        assert len(lineage['omitted_from_projection']) == 1
        assert not lineage['removed_before_source']
    else:
        assert source['tables'] == packet['tables']
    if f == 'component_edge_missing_source':
        assert len(lineage['removed_before_source']) == 1
        assert not lineage['omitted_from_projection']
    serialized = json.dumps(packet)
    for forbidden in ('family', 'expected', 'injected_fault', 'constructed_paths', 'removed_before_source', 'omitted_from_projection'):
        assert forbidden not in serialized
assert len(families) == 12 and all(sorted(depths) == [1, 3] for depths in families.values())
assert len(list((root / 'runtime').glob('*.json'))) == 25
print(json.dumps({'integrity': 'passed', 'scenes': 24, 'arm_executions': 0}))
