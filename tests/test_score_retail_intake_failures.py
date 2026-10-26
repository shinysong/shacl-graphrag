import copy
import pytest
from scripts.retail_artifact_outcomes import intake_for_keys
from scripts.score_retail_intake_failures import score_intake_failures
REFS=[{'row_id':'a','policy':'p','status':'violation'},{'row_id':'b','policy':'p','status':'pass'}]
KEYS=[('a','p'),('b','p')]

def failure():return intake_for_keys(b'broken (','python',KEYS,'one')

def test_stage_counts_and_denominator():
    result=score_intake_failures(REFS,[failure()])
    assert result['failure_attempts_by_stage']=={'artifact_parse_error':1}
    assert result['affected_keys_by_stage']=={'artifact_parse_error':2}
    assert result['actual_execution_attempts']==0
    assert result['metrics']['overall']['n']==2 and result['metrics']['overall']['violation_fn']==1

def test_separate_batch_failures():
    outcomes=[intake_for_keys(b'','python',[key],str(i)) for i,key in enumerate(KEYS)]
    result=score_intake_failures(REFS,outcomes)
    assert result['failure_attempts_by_stage']=={'generation_empty_or_truncated':2}

def test_pending_rejected():
    with pytest.raises(ValueError):score_intake_failures(REFS,[intake_for_keys(b'x=1','python',KEYS,'one')])

@pytest.mark.parametrize('mutation',['readiness','stage','executed','missing_prediction','pass_prediction','duplicate_key'])
def test_inconsistent_outcomes_rejected(mutation):
    out=copy.deepcopy(failure())
    if mutation=='readiness':out['ready_for_scoring']=False
    elif mutation=='stage':out['failure_stage']='execution_exception'
    elif mutation=='executed':out['intake']['executed']=True
    elif mutation=='missing_prediction':out['predictions'].pop()
    elif mutation=='pass_prediction':out['predictions'][0]['status']='pass'
    elif mutation=='duplicate_key':out['declared_keys'].append(out['declared_keys'][0])
    with pytest.raises(ValueError):score_intake_failures(REFS,[out])

def test_scope_and_overlap_rejected():
    with pytest.raises(ValueError):score_intake_failures(REFS[:1],[failure()])
    with pytest.raises(ValueError):score_intake_failures(REFS,[failure(),failure()])
    with pytest.raises(ValueError):score_intake_failures(REFS,[])
