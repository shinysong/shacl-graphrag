import json
from copy import deepcopy
from pathlib import Path
from rdflib import Literal,URIRef
from scripts.manufacturing_answer_adapter import adapt

POLICY=json.loads(Path('research/manufacturing-answer-trace-1/design-001/policy.json').read_text())

def val(x):return Literal(json.dumps(x)).n3()
def row(q,bindings):return {'case_id':q,'backend':'fixture','status':'completed','bindings':bindings}

def test_partial_operands_do_not_repair_or_discard_supported_part():
    r=adapt(row('Q3',[{'?v1':val(450)}]),POLICY)
    assert r['claims']['first_nominal_current']['value']==450
    assert r['claims']['second_minus_first']['state']=='missing_operand'
    assert r['status']=='partial'

def test_declared_universe_and_duplicates():
    a={'?s':val('PP6:12'),'?x':val(239),'?label':val('Porosity')}
    b={'?s':val('PP6:2'),'?x':val(106),'?label':val('Metallic inclusion')}
    missing=adapt(row('Q4',[a]),POLICY)
    assert missing['claims']['observed_matching_rows']['value']==['PP6:12']
    assert missing['claims']['count']['state']=='incomplete_candidates'
    full=adapt(row('Q4',[a,a,b,{'?s':val('PP7:9'),'?x':val(150),'?label':val('Porosity')}]),POLICY)
    assert full['claims']['count']['value']==1
    assert full['duplicate_bindings_removed']==1 and full['irrelevant_rows_ignored']==1

def test_absence_failure_unsupported_separate():
    empty=adapt(row('Q8',[]),POLICY)
    assert empty['empty_binding_origin']=='undetermined'
    assert all(x['value'] is None for x in empty['claims'].values())
    failed=row('Q8',[]);failed['status']='timeout'
    assert adapt(failed,POLICY)['status']=='upstream_failure'
    q7=row('Q7',[]);q7['status']='unsupported'
    assert adapt(q7,POLICY)['status']=='unsupported'

def test_missing_role_policy_keeps_values():
    p=deepcopy(POLICY);p.pop('Q5')
    result=adapt(row('Q5',[{'?mm':val(106),'?sample':val(66244),'?nominal':val(450)}]),p)
    assert result['claims']['position']['value']==106
    assert result['claims']['field_roles']['state']=='policy_missing'
    assert result['claims']['actual_measured_current']['value'] is None


def test_wrong_workbook_same_label_does_not_establish_applicability():
    r=adapt(row('Q6',[{'?d':val('PP7:defect_code:4'),'?same':val('PP7'),'?other':val('PP7')}]),POLICY)
    assert r['claims']['linked_dictionary_applicable']['value'] is False
    inconsistent=adapt(row('Q6',[{'?d':val('PP7:defect_code:4'),'?same':val('PP6'),'?other':val('PP7')}]),POLICY)
    assert inconsistent['claims']['applicable_sources']['state']=='source_identity_conflict'
