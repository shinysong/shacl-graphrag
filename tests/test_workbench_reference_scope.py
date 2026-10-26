"""Snapshot membership is not proof of absence from a partial reference source."""
import copy
import pytest
from rule_workbench.core import demo_project, run_checks
from rule_workbench.exports import export_json, import_json

@pytest.mark.parametrize('flag',['truncated','redacted','data_omitted'])
@pytest.mark.parametrize('roundtrip',[False,True])
def test_partial_reference_absence_unknown_but_observed_membership_passes(flag,roundtrip):
    p=demo_project();p['rules']=[p['rules'][2]]
    p['tables'][1]['source'][flag]=True
    before=copy.deepcopy(p)
    checked=import_json(export_json(p,True)) if roundtrip else p
    result=run_checks(checked)
    assert {x['row']:x['status'] for x in result['results']}=={1:'pass',2:'pass',3:'unknown',4:'unknown'}
    assert result['counts']['violation']==0
    assert p==before

@pytest.mark.parametrize('flag',[None,'redacted'])
def test_no_loss_flag_retains_snapshot_absence_violation(flag):
    p=demo_project();p['rules']=[p['rules'][2]]
    if flag:p['tables'][1]['source'][flag]=False
    result=run_checks(p)
    assert {x['row']:x['status'] for x in result['results']}=={1:'pass',2:'pass',3:'violation',4:'unknown'}
