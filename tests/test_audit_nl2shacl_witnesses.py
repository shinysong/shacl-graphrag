"""Authored offline fixtures only: never inspect campaign model outputs."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_nl2shacl_witnesses as audit

PREFIX = '@prefix ex: <urn:test:> . @prefix sh: <http://www.w3.org/ns/shacl#> . '
STRICT = PREFIX + 'ex:S a sh:NodeShape ; sh:targetClass ex:C ; sh:property [ sh:path ex:p ; sh:minCount 1 ; sh:maxCount 1 ] .'
WEAK = STRICT.replace('sh:minCount 1', 'sh:minCount 0')
WRONG = STRICT.replace('sh:path ex:p', 'sh:path ex:q')
OPTIONS = {'inference': 'none', 'advanced': False, 'meta_shacl': True, 'do_owl_imports': False,
           'abort_on_first': False, 'allow_infos': False, 'allow_warnings': False}


@pytest.fixture
def bundle(tmp_path):
    def write(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        return path
    reference = write('reference.ttl', STRICT)
    pairs = write('pairs.json', [])
    probes = []
    for name, body, expected in [('absent', 'ex:n a ex:C .', False), ('one', 'ex:n a ex:C ; ex:p ex:v .', True)]:
        path = write(name + '.ttl', PREFIX + body)
        probes.append({'id': name, 'data_path': str(path), 'sha256': audit.sha(path.read_bytes()),
                       'expected_reference_conforms': expected})
    design = {'case_id': 'test-1', 'reference_path': str(reference), 'reference_sha256': audit.sha(reference.read_bytes()),
              'source_pairs_path': str(pairs), 'source_pairs_sha256': audit.sha(pairs.read_bytes()),
              'witnesses': probes, 'validation_options': OPTIONS, 'limits': ['Finite witness data, not proof.']}
    inp = {'model': 'fixture', 'id': 'test-1', 'language': 'en', 'system_prompt': 's', 'user_prompt': 'u'}
    request = {'model': 'fixture', 'messages': [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'u'}]}
    write('generation/call-0000/request.json', request)
    raw = write('generation/call-0000/output.ttl', STRICT)
    response = write('generation/call-0000/response.json', {'choices': [{'message': {'content': STRICT}}]})
    reservation = {k: inp[k] for k in ('model', 'id', 'language')}
    reservation.update(status='completed', reported_usd=0, input_sha256=audit.canonical_digest(inp))
    ledger = write('ledger.json', {'attempts': 1, 'output': str(tmp_path/'generation'), 'reservations': [reservation]})
    row = {**reservation, 'reservation_index': 0, 'raw_sha256': audit.sha(raw.read_bytes()),
           'reference_sha256': design['reference_sha256'], 'meta': {'status': 'meta_conformant'}}
    record = {'ledger': str(ledger), 'hashes': {str(p): audit.sha(p.read_bytes()) for p in (ledger, raw, response)}, 'rows': [row]}
    return {'audit': write('audit.json', record), 'design': write('design.json', design), 'output': tmp_path/'result.json',
            'write': write, 'record': record, 'design_record': design, 'raw': raw, 'ledger': ledger}


def run(bundle):
    return audit.run(bundle['audit'], bundle['design'], bundle['output'])


def test_matching_and_finite_counts(bundle):
    result = run(bundle)
    assert result['summary'] == {'agreement': 2, 'underconstraint_observed': 0, 'overconstraint_observed': 0, 'unavailable': 0}
    assert result['rows'][0]['result']['interpretation'] == 'no_counterexample_among_frozen_witnesses'
    assert result['rows'][0]['result']['raw_graph_isomorphic']
    with pytest.raises(FileExistsError):
        run(bundle)


@pytest.mark.parametrize('shape,under,over', [(WEAK, 1, 0), (WRONG, 0, 1)])
def test_nonmatching(shape, under, over):
    probes = [{'id': 'absent', 'ttl': PREFIX+'ex:n a ex:C .', 'expected_reference_conforms': False},
              {'id': 'one', 'ttl': PREFIX+'ex:n a ex:C ; ex:p ex:v .', 'expected_reference_conforms': True}]
    result = audit.account(audit.worker({'shape': shape, 'reference': STRICT, 'witnesses': probes, 'options': OPTIONS}), probes)
    assert result['counts']['underconstraint_observed'] == under
    assert result['counts']['overconstraint_observed'] == over
    assert sum(result['counts'].values()) == 2


@pytest.mark.parametrize('status', ['parse_failure', 'invalid_shape', 'runtime_exception'])
def test_audit_meta_unavailable(bundle, status):
    bundle['record']['rows'][0]['meta']['status'] = status
    bundle['write']('audit.json', bundle['record'])
    result = run(bundle)
    assert result['summary']['unavailable'] == 2
    assert result['summary']['underconstraint_observed'] == 0


@pytest.mark.parametrize('shape,reason', [('not turtle', 'parse_failure'), (STRICT.replace('sh:minCount 1', 'sh:minCount "bad"'), 'invalid_shape')])
def test_worker_parse_meta_failures(shape, reason):
    result = audit.worker({'shape': shape})
    assert result['status'] == 'unavailable'
    assert result['reason'] == reason


@pytest.mark.parametrize('target', ['raw', 'ledger'])
def test_hash_mismatch(bundle, target):
    bundle[target].write_text(bundle[target].read_text()+'\n')
    with pytest.raises(ValueError, match='Hash mismatch'):
        run(bundle)
    assert not bundle['output'].exists()


def test_witness_hash_mismatch(bundle):
    Path(bundle['design_record']['witnesses'][0]['data_path']).write_text('changed')
    with pytest.raises(ValueError, match='Hash mismatch'):
        run(bundle)


def test_reference_expectation_mismatch(bundle):
    bundle['design_record']['witnesses'][0]['expected_reference_conforms'] = True
    bundle['write']('design.json', bundle['design_record'])
    with pytest.raises(ValueError, match='Reference witness expectation'):
        run(bundle)


def test_input_request_mismatch(bundle):
    bundle['write']('generation/call-0000/request.json', {'model': 'fixture', 'messages': [{'role': 'system', 'content': 'changed'}, {'role': 'user', 'content': 'u'}]})
    with pytest.raises(ValueError, match='Request input hash mismatch'):
        run(bundle)


def test_unresolved_reservation(bundle):
    ledger = json.loads(bundle['ledger'].read_text())
    ledger['reservations'][0]['reported_usd'] = None
    bundle['ledger'].write_text(json.dumps(ledger))
    bundle['record']['hashes'][str(bundle['ledger'])] = audit.sha(bundle['ledger'].read_bytes())
    bundle['write']('audit.json', bundle['record'])
    with pytest.raises(ValueError, match='Unresolved reservation'):
        run(bundle)


def test_timeout_unavailable():
    import subprocess
    with patch.object(audit.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixture', 1)):
        result = audit.execute({}, 1)
    result = audit.account(result, [{'id': 'x', 'expected_reference_conforms': True}])
    assert result['counts']['unavailable'] == 1


def test_terminal_failed_unknown_cost_unavailable(bundle):
    ledger = json.loads(bundle['ledger'].read_text())
    ledger['reservations'][0].update(status='failed', reported_usd=None)
    bundle['ledger'].write_text(json.dumps(ledger))
    bundle['record']['hashes'][str(bundle['ledger'])] = audit.sha(bundle['ledger'].read_bytes())
    bundle['record']['rows'][0].update(status='failed', meta={'status': 'not_evaluated'})
    bundle['write']('audit.json', bundle['record'])
    result = run(bundle)
    assert result['summary']['unavailable'] == 2
    assert result['terminal_failed_unknown_cost'] == 1
