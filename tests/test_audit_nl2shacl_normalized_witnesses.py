"""Synthetic fixtures only; never read campaign outputs or invoke a paid client."""
import fcntl
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_nl2shacl_normalized_witnesses as normalized
import audit_nl2shacl_witnesses as original
from render_nl2shacl_tier_report import digest, sha

PREFIX = '@prefix ex: <urn:test:> . @prefix sh: <http://www.w3.org/ns/shacl#> . '
SHAPE = PREFIX + 'ex:S a sh:NodeShape ; sh:targetClass ex:C ; sh:property [ sh:path ex:p ; sh:minCount 1 ] .'


@pytest.fixture
def bundle(tmp_path):
    def build(raw=None, cleaned=SHAPE, status='completed', classification='formatting'):
        raw = '```turtle\n' + SHAPE + '\n```' if raw is None else raw
        def write(name, value):
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value if isinstance(value, str) else json.dumps(value))
            return path
        ref = write('source/dataset/ref.ttl', SHAPE)
        manifest = write('source/source-hashes.json', {'dataset/ref.ttl': sha(ref)})
        pairs = write('pairs.json', {'pairs': [{'id': 'case', 'en': 'question'}]})
        probe = write('probe.ttl', PREFIX + 'ex:n a ex:C .')
        design = write('design.json', dict(case_id='case', reference_path=str(ref), reference_sha256=sha(ref),
            source_pairs_path=str(pairs), source_pairs_sha256=sha(pairs), validation_options=normalized.OPTIONS,
            witnesses=[dict(id='missing', data_path=str(probe), sha256=sha(probe), expected_reference_conforms=False)], limits=['Synthetic fixture.']))
        prompt = dict(model='fixture', id='case', language='en', system_prompt='system', user_prompt='question')
        inputs = write('inputs.json', [prompt, dict(prompt, model='unexecuted')])
        usage = {'cost': 0}
        raw_path = write('generation/call-0000/output.ttl', raw)
        response = write('generation/call-0000/response.json', dict(model='fixture', provider='fixture', usage=usage,
            choices=[dict(message={'content': raw}, finish_reason='length' if classification=='truncation' else 'stop')]))
        request = write('generation/call-0000/request.json', dict(model='fixture', messages=[dict(role='system', content='system'),dict(role='user', content='question')]))
        reservation = {k: prompt[k] for k in ('model','id','language')}
        reservation.update(status=status, input_sha256=digest(prompt), reported_usd=0 if status=='completed' else None, upper_usd=1)
        ledger = write('ledger.json', dict(attempts=1, reservations=[reservation], output=str(tmp_path/'generation')))
        processed = write('processed.jsonl', dict(id='case-en', output_shacl=cleaned, reference_shacl=SHAPE))
        row = dict(reservation, reservation_index=0, raw_sha256=sha(raw_path), cleaned_sha256=original.sha(cleaned.encode()), reference_sha256=sha(ref),
                   meta={'status': 'meta_conformant' if raw==SHAPE else 'parse_failure'}, usage=usage, provider='fixture', response_model='fixture',
                   finish_reason='length' if classification=='truncation' else 'stop', classification=classification)
        if status=='failed':
            row['meta']={'status':'not_evaluated'}
        audit = write('audit.json', dict(ledger=str(ledger), hashes={str(p):sha(p) for p in [ledger,raw_path,response,request,processed,manifest]},
                    source_hashes={'dataset/ref.ttl':sha(ref)}, rows=[row], upstream_runs=[dict(model='fixture', processed_input=str(processed))]))
        raw_results = tmp_path/'raw-results.json'
        original.run(audit, design, raw_results)
        return dict(audit=audit, inputs=inputs, ledger=ledger, design=design, raw_results=raw_results, output=tmp_path/'normalized.json', pairs=pairs)
    return build


def test_fence_success_and_partial_campaign(bundle):
    args = bundle()
    before = args['raw_results'].read_bytes()
    result = normalized.run(**args)
    assert result['denominators'] == dict(planned=2, attempted=1, completed=1, failed=0, unexecuted=1, witnesses_per_attempt=1)
    assert result['summary']['raw']['unavailable']==1
    assert result['summary']['normalized']['agreement']==1
    assert result['rows'][0]['postprocessing_change']=='outer_fence_removal_only_ignoring_boundary_whitespace'
    assert result['rows'][1]['normalized_result'] is None
    assert args['raw_results'].read_bytes()==before
    with pytest.raises(FileExistsError):
        normalized.run(**args)


def test_invalid_shape_independent_meta(bundle):
    invalid=SHAPE.replace('sh:minCount 1', 'sh:minCount "bad"')
    result=normalized.run(**bundle(cleaned=invalid))
    row=result['rows'][0]
    assert row['normalized_result']['reason']=='invalid_shape'
    assert result['summary']['normalized']['unavailable']==1
    assert row['postprocessing_change']=='original_postprocessing_change'


def test_true_truncation_remains_unavailable(bundle):
    truncated=SHAPE[:-15]
    result=normalized.run(**bundle(raw=truncated,cleaned=truncated,classification='truncation'))
    assert result['rows'][0]['audit_classification']=='truncation'
    assert result['rows'][0]['finish_reason']=='length'
    assert result['summary']['normalized']['unavailable']==1


def test_terminal_unknown_failure_and_unexecuted_separate(bundle):
    result=normalized.run(**bundle(status='failed'))
    assert result['denominators']['failed']==1
    assert result['denominators']['unexecuted']==1
    assert result['rows'][0]['pipeline_status']=='terminal_provider_failure'
    assert result['summary']['normalized']['unavailable']==1


@pytest.mark.parametrize('target',['audit','design','ledger','processed','reference','raw_results'])
def test_hash_tamper(bundle,target):
    args=bundle()
    if target in ('processed','reference'):
        path=args['audit'].parent / ('processed.jsonl' if target=='processed' else 'source/dataset/ref.ttl')
    else:
        path=args[target]
    if target=='raw_results':
        doc=json.loads(path.read_text()); doc['hashes'][str(args['design'])]='0'*64
        path.write_text(json.dumps(doc))
    else:
        path.write_text(path.read_text()+'\n')
    with pytest.raises(ValueError,match='[Hh]ash mismatch'):
        normalized.run(**args)
    assert not args['output'].exists()


def test_ledger_busy(bundle):
    args=bundle()
    with args['ledger'].with_suffix('.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(ValueError,match='busy'):
            normalized.run(**args)


def test_change_class_is_conservative():
    assert normalized.change_class('```turtle\nx\n```','x') .startswith('outer_fence')
    assert normalized.change_class('```turtle\nx\n```','y')=='original_postprocessing_change'
    assert normalized.change_class('prose\n```turtle\nx\n```','x')=='original_postprocessing_change'
    assert normalized.change_class('x ','x')=='original_postprocessing_change'


def test_counterexample_saved_without_repair(bundle):
    weak=SHAPE.replace('sh:minCount 1', 'sh:minCount 0')
    result=normalized.run(**bundle(cleaned=weak))
    assert result['summary']['normalized']['underconstraint_observed']==1
    assert result['counterexamples'][0]['normalized']['conforms'] is True
    assert result['counterexamples'][0]['raw']['outcome']=='unavailable'


def test_timeout_loses_partial_progress(bundle,monkeypatch):
    args=bundle()
    execute=normalized.execute
    calls=[]
    def limited(payload,timeout):
        calls.append(payload)
        if len(calls)==1:
            return execute(payload,timeout)
        return {'status':'unavailable','reason':'candidate_timeout'}
    monkeypatch.setattr(normalized,'execute',limited)
    result=normalized.run(**args)
    assert result['summary']['normalized']['unavailable']==1
    assert result['rows'][0]['normalized_result']['reason']=='candidate_timeout'


def test_binary_source_manifest_artifact(bundle):
    args=bundle()
    binary=args['audit'].parent/'source/dataset/binary.bin'
    binary.write_bytes(bytes([0xff,0xfe,0,0x80]))
    manifest=binary.parent.parent/'source-hashes.json'
    pins=json.loads(manifest.read_text())
    pins['dataset/binary.bin']=sha(binary)
    manifest.write_text(json.dumps(pins))
    audit=json.loads(args['audit'].read_text())
    audit['source_hashes']=pins
    audit['hashes'][str(manifest)]=sha(manifest)
    args['audit'].write_text(json.dumps(audit))
    raw=json.loads(args['raw_results'].read_text())
    raw['hashes'][str(manifest)]=sha(manifest)
    raw['hashes'][str(args['audit'])]=sha(args['audit'])
    args['raw_results'].write_text(json.dumps(raw))
    result=normalized.run(**args)
    assert result['summary']['normalized']['agreement']==1
    assert result['hashes'][str(binary.resolve())]==sha(binary)
