"""Synthetic saved-output fixtures; no campaign artifacts or model calls."""
import fcntl
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from test_audit_nl2shacl_normalized_witnesses import bundle  # noqa: F401
import audit_nl2shacl_normalized_witnesses as evaluator
import render_nl2shacl_witness_report as viewer


@pytest.fixture
def saved(bundle):
    def make(source_list=False, **kwargs):
        args = bundle(**kwargs)
        if source_list:
            packet = json.loads(args['pairs'].read_text())
            args['pairs'].write_text(json.dumps(packet['pairs']))
            design = json.loads(args['design'].read_text())
            design['source_pairs_sha256'] = viewer.sha(args['pairs'])
            args['design'].write_text(json.dumps(design))
            raw = json.loads(args['raw_results'].read_text())
            for path in (args['pairs'], args['design']):
                raw['hashes'][str(path)] = viewer.sha(path)
            args['raw_results'].write_text(json.dumps(raw))
        evaluator.run(**{**args, 'pairs': None if source_list else args['pairs']})  # Synthetic fixture only.
        return dict(audit=args['audit'], inputs=args['inputs'], ledger=args['ledger'],
                    normalized=[args['output']], pairs=args['pairs'], output=args['output'].with_suffix('.html'))
    return make


def test_saved_parse_failure_and_normalized_success(saved):
    args = saved()
    before = {str(p): p.read_bytes() for p in args['normalized']}
    result = viewer.run(**args)
    row = result['rows'][0]['witness_result']
    assert row['raw_result']['counts']['unavailable'] == 1
    assert row['normalized_result']['counts']['agreement'] == 1
    assert result['rows'][1]['witness_result']['pipeline_status'] == 'unexecuted'
    assert 'ex:n a ex:C' in result['cases']['case']['probes'][0]['ttl']
    assert all(Path(p).read_bytes() == raw for p, raw in before.items())
    with pytest.raises(FileExistsError):
        viewer.run(**args)


def test_failed_and_unexecuted(saved):
    data = viewer.run(**saved(status='failed'))
    assert data['rows'][0]['witness_result']['normalized_result']['reason'] == 'terminal_provider_failure'
    assert data['rows'][1]['witness_result']['normalized_result'] is None


@pytest.mark.parametrize('target', ['inputs', 'ledger', 'audit', 'probe.ttl', 'design.json', 'processed.jsonl'])
def test_dependency_hash_mismatch(saved, target):
    args = saved()
    path = args[target] if target in args else args['audit'].parent / target
    path.write_bytes(path.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='[Hh]ash mismatch'):
        viewer.run(**args)
    assert not args['output'].exists()


@pytest.mark.parametrize('mutation', ['model', 'raw', 'expected', 'unexecuted'])
def test_row_binding(saved, mutation):
    args = saved()
    path = args['normalized'][0]
    data = json.loads(path.read_text())
    if mutation == 'model':
        data['rows'][0]['model'] = 'other'
    elif mutation == 'raw':
        data['rows'][0]['raw_result']['reason'] = 'forged'
    elif mutation == 'expected':
        data['rows'][0]['normalized_result']['witnesses'][0]['expected_reference_conforms'] = True
    else:
        data['rows'][1]['normalized_result'] = {}
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='mismatch'):
        viewer.run(**args)


def test_binary_dependency(saved):
    args = saved()
    binary = args['audit'].parent / 'dependency.bin'
    binary.write_bytes(b'\xff\x00\xfe')
    path = args['normalized'][0]
    data = json.loads(path.read_text())
    data['hashes'][str(binary)] = viewer.sha(binary)
    path.write_text(json.dumps(data))
    assert str(binary) in viewer.run(**args)['provenance']


def test_lock(saved):
    args = saved()
    with args['ledger'].with_suffix('.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='busy'):
            viewer.run(**args)


def test_inert_json_xss():
    malicious = '</script><img src=x onerror=alert(1)>\u2028&'
    html = viewer.render({'attack': malicious})
    assert malicious not in html
    assert '<img src=x' not in html
    assert '\\u003c/script\\u003e' in html
    payload = html.split('id="data">')[1].split('</script>')[0]
    assert json.loads(payload)['attack'] == malicious
    assert 'innerHTML' not in html
    assert "connect-src 'none'" in html
    assert 'id="probe"' in html and 'id="cards"' in html


@pytest.mark.parametrize('mutation', ['conforms_flip', 'conforms_nonboolean', 'status', 'outcome', 'pipeline', 'count_bool', 'count_missing', 'count_unknown', 'unavailable_boolean', 'result_status'])
def test_reject_inconsistent_saved_claims(saved, mutation):
    args = saved()
    path = args['normalized'][0]
    record = json.loads(path.read_text())
    row = record['rows'][0]
    result = row['normalized_result']
    witness = result['witnesses'][0]
    if mutation == 'conforms_flip':
        witness['conforms'] = not witness['conforms']
    elif mutation == 'conforms_nonboolean':
        witness['conforms'] = 0
    elif mutation == 'status':
        witness['status'] = 'invented'
    elif mutation == 'outcome':
        witness['outcome'] = 'invented'
    elif mutation == 'pipeline':
        row['pipeline_status'] = 'unavailable'
    elif mutation == 'count_bool':
        result['counts']['agreement'] = True
    elif mutation == 'count_missing':
        del result['counts']['unavailable']
    elif mutation == 'count_unknown':
        result['counts']['invented'] = 0
    elif mutation == 'unavailable_boolean':
        witness.update(status='unavailable', outcome='unavailable')
    else:
        result['status'] = 'invented'
    path.write_text(json.dumps(record))
    before = path.read_bytes()
    with pytest.raises(ValueError, match='mismatch'):
        viewer.run(**args)
    assert not args['output'].exists()
    assert path.read_bytes() == before


@pytest.mark.parametrize('source_list', [False, True])
def test_canonical_pairs_different_path(saved, source_list):
    args = saved(source_list=source_list)
    source = json.loads(args['pairs'].read_text())
    canonical = args['audit'].parent / 'canonical-pairs.json'
    canonical.write_text(json.dumps({'pairs': source if source_list else source['pairs']}))
    args['pairs'] = canonical
    result = viewer.run(**args)
    assert result['rows'][0]['requirement'] == 'question'
    assert str(canonical) in result['provenance']


def test_canonical_pair_mismatch(saved):
    args = saved(source_list=True)
    canonical = args['audit'].parent / 'canonical-pairs.json'
    canonical.write_text(json.dumps({'pairs': [{'id': 'case', 'en': 'different question'}]}))
    args['pairs'] = canonical
    with pytest.raises(ValueError, match='Pair content binding mismatch'):
        viewer.run(**args)
    assert not args['output'].exists()


def test_missing_metadata_is_not_unexecuted():
    assert "x===undefined?'미보고'" in viewer.HTML
