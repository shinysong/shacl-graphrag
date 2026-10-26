import copy
import pytest
from rule_workbench.core import new_project
from rule_workbench.linkage import table_digest
from rule_workbench.linkage_consistency import audit_field_consistency


def fixture():
    p = new_project()
    for name, cols, rows in [
        ('receipts', ['qi','item'], [{'qi':'Q1','item':'P1'}, {'qi':'Q2','item':'P2'}, {'qi':'Q3','item':'P3'}, {'qi':None,'item':'P4'}, {'qi':'Q5','item':'P5'}, {'qi':'Q6','item':'P6'}]),
        ('inspection', ['name','item'], [{'name':'Q1','item':'P1'}, {'name':'Q2','item':'OTHER'}, {'name':'Q3','item':None}, {'name':'Q6','item':'P6'}, {'name':'Q6','item':'P6'}])]:
        p['tables'].append(dict(id=name,name=name,columns=cols,rows=rows,source={'complete':True}))
    return p


def contract(p):
    return dict(id='receipt-inspection',source_table='receipts',source_column='qi',
                target_table='inspection',target_column='name',status='confirmed',
                source_digest=table_digest(p['tables'][0]),target_digest=table_digest(p['tables'][1]),
                equality_pairs=[{'source_column':'item','target_column':'item'}],equality_status='confirmed')


def test_separate_observed_conflict_missing_and_unlinked():
    p=fixture(); before=copy.deepcopy(p)
    r=audit_field_consistency(p,contract(p))
    assert [x['status'] for x in r['results']]==['agrees','violates_declared_equality','missing_evidence','not_evaluated','not_evaluated','not_evaluated']
    assert [x['reason'] for x in r['results'][3:]]==['missing_key','unmatched_in_snapshot','ambiguous']
    assert p==before


@pytest.mark.parametrize('flag',['truncated','redacted','data_omitted'])
def test_incomplete_reference_never_compared(flag):
    p=fixture(); p['tables'][1]['source'][flag]=True
    r=audit_field_consistency(p,contract(p))
    assert r['counts']=={'not_evaluated':6}


def test_stale_and_unreviewed():
    p=fixture(); c=contract(p);p['tables'][1]['rows'][0]['item']='CHANGED'
    assert audit_field_consistency(p,c)['counts']=={'not_evaluated':6}
    c=contract(p);c['equality_status']='draft'
    assert audit_field_consistency(p,c)['counts']=={'not_evaluated':6}


@pytest.mark.parametrize('a,b', [('001',1),(True,1),('P1','p1'),('P1',' P1')])
def test_no_implicit_coercion(a,b):
    p=fixture();p['tables'][0]['rows'][0]['item']=a;p['tables'][1]['rows'][0]['item']=b
    assert audit_field_consistency(p,contract(p))['results'][0]['status']=='violates_declared_equality'


def test_bad_mapping_rejected():
    p=fixture();c=contract(p);c['equality_pairs'][0]['target_column']='absent'
    with pytest.raises(ValueError):audit_field_consistency(p,c)


def test_violation_preserved_alongside_missing_field():
    p=fixture()
    for t in p['tables']:
        t['columns'].append('revision')
    c=contract(p);c['equality_pairs'].append({'source_column':'revision','target_column':'revision'})
    row=audit_field_consistency(p,c)['results'][1]
    assert row['status']=='violates_declared_equality'
    assert row['comparisons'][1]['status']=='missing_evidence'
