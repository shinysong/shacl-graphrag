import pytest
from scripts.retail_artifact_outcomes import intake_for_keys
from scripts.score_retail_decisions import score

KEYS=[('r1','p'),('r2','p')]
@pytest.mark.parametrize('kind,raw',[('python',b'def broken('),('turtle',b'<urn:s>'),('python',b''),('turtle',b'x'*65537)])
def test_failures_keep_denominator(kind,raw):
    out=intake_for_keys(raw,kind,KEYS,'attempt1')
    assert out['ready_for_scoring'] and out['state']=='terminal_intake_failure'
    assert out['failure_stage'] and not out['intake']['executed']
    refs=[{'row_id':'r1','policy':'p','status':'violation'},{'row_id':'r2','policy':'p','status':'pass'}]
    metrics=score(refs,out['predictions'])['overall']
    assert metrics['n']==2 and metrics['violation_fn']==1 and metrics['coverage_all']==0
    assert metrics['missing_output_n']==0 and metrics['runtime_error_n']==2

@pytest.mark.parametrize('kind,raw',[('python',b'raise RuntimeError()'),('turtle',b'# valid but no shapes')])
def test_parse_success_is_pending_not_success(kind,raw):
    out=intake_for_keys(raw,kind,KEYS,'attempt1')
    assert not out['ready_for_scoring'] and out['predictions']==[]
    assert out['state']=='pending_execution' and out['failure_stage'] is None

def test_failure_scope_is_declared_batch_only():
    out=intake_for_keys(b'','python',[KEYS[0]],'batch1')
    assert out['predictions']==[{'row_id':'r1','policy':'p','status':'error'}]
    assert out['declared_keys']==[['r1','p']]

@pytest.mark.parametrize('keys',[[],[('r1','p'),('r1','p')],[('','p')],[('r1',)]])
def test_invalid_keys(keys):
    with pytest.raises(ValueError):intake_for_keys(b'','python',keys,'a')
