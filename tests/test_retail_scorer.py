import pytest
from scripts.score_retail_decisions import score

def rows(statuses,policy='p'):
    return [{'row_id':str(i),'policy':policy,'status':s} for i,s in enumerate(statuses)]

@pytest.mark.parametrize('prediction', ['pass','violation','unknown','error',None])
def test_violation_denominator_retains_every_outcome(prediction):
    r=score(rows(['violation']), [] if prediction is None else rows([prediction]))['overall']
    assert r['violation_tp']==int(prediction=='violation')
    assert r['violation_fn']==int(prediction!='violation')
    assert r['violation_recall_known_refs']==int(prediction=='violation')
    assert r['missing_output_n']==int(prediction is None)
    assert r['runtime_error_n']==int(prediction=='error')

@pytest.mark.parametrize('prediction', ['pass','violation','unknown','error',None])
def test_unknown_reference_not_binary_gold(prediction):
    r=score(rows(['unknown']),[] if prediction is None else rows([prediction]))['overall']
    assert r['violation_precision_known_refs'] is None
    assert r['violation_recall_known_refs'] is None
    assert r['selective_error_known_refs'] is None
    assert r['unsupported_decision_unknown_refs_n']==int(prediction in ('pass','violation'))

def test_hand_computed_mixed_case():
    r=score(rows(['violation','violation','violation','pass','pass','unknown']),rows(['violation','unknown','error','violation','pass','pass']))['overall']
    assert (r['violation_tp'],r['violation_fp'],r['violation_fn'])==(1,1,2)
    assert r['violation_precision_known_refs']==.5
    assert r['violation_recall_known_refs']==pytest.approx(1/3)
    assert r['violation_f1_known_refs']==.4
    assert r['coverage_all']==pytest.approx(4/6)
    assert r['coverage_known_refs']==.6
    assert r['selective_error_known_refs']==pytest.approx(1/3)
    assert r['unnecessary_abstention_known_refs_n']==1
    assert r['unsupported_decision_unknown_refs_rate']==1

def test_all_abstain_not_perfect():
    r=score(rows(['violation','pass']),rows(['unknown','unknown']))['overall']
    assert r['coverage_all']==0 and r['violation_recall_known_refs']==0
    assert r['selective_error_known_refs'] is None

def test_empty_not_perfect():
    r=score([],[])['overall']
    assert r['n']==0 and r['coverage_all'] is None and r['violation_f1_known_refs'] is None

def test_reordering_and_policy_isolation():
    refs=rows(['violation'],'a')+rows(['pass'],'b');preds=rows(['pass'],'a')+rows(['pass'],'b')
    r=score(refs,list(reversed(preds)))
    assert r==score(list(reversed(refs)),preds)
    assert r['by_policy']['a']['false_pass_n']==1 and r['by_policy']['b']['false_pass_n']==0

@pytest.mark.parametrize('ref,pred',[(rows(['pass'])*2,[]),(rows(['pass']),rows(['pass'])*2),(rows(['pass']),rows(['wrong'])),(rows(['error']),[]),([],rows(['pass'])),([{'row_id':1,'policy':'p','status':'pass'}],[])])
def test_invalid_inputs_rejected(ref,pred):
    with pytest.raises(ValueError): score(ref,pred)
