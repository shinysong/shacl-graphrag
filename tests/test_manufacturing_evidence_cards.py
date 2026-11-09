from scripts.manufacturing_evidence_cards import card,package
from rdflib import Literal
import json
import pytest


def fixture():
    return {'archive_path':'test.xlsx','sheet':'settings','sha256':'a'*64,'coupon':'PP6',
            'header_rows':[{'cells':[{'cell':'A1','value':'setting group'},{'cell':'B1','value':'parent'}]},
                           {'cells':[{'cell':'A2','value':None},{'cell':'B2','value':'Idc (A)'}]}],
            'cells':[{'cell':'A3','value':None,'data_type':'n','formula':None,'cached_value':None},
                     {'cell':'B3','value':'=1+1','data_type':'f','formula':'=1+1','cached_value':2}]}


def test_null_formula_and_two_header_rows_retained():
    c=card(fixture())
    assert c['header_rows']==fixture()['header_rows']
    assert c['cells'][0]['value'] is None
    assert c['cells'][0]['header']['cell']=='A1'
    assert c['cells'][1]['value']=='=1+1' and c['cells'][1]['cached_value']==2
    assert c['cells'][1]['header']['value']=='Idc (A)'


def test_identical_payload_deduplication_and_invalid_payload_preserved():
    v=Literal(json.dumps(fixture())).n3()
    saved={'backend':'fixture','case_id':'Q3','status':'completed','bindings':[{'?a_payload':v,'?b_payload':v}]}
    r=package(saved)
    assert r['status']=='completed' and len(r['cards'])==1
    assert r['bindings'][0]['?a_payload']['card_index']==r['bindings'][0]['?b_payload']['card_index']
    saved['bindings'].append({'?bad_payload':Literal('{}').n3()})
    failed=package(saved)
    assert failed['status']=='projection_failure' and len(failed['cards'])==1


@pytest.mark.parametrize('blank',['','  \t'])
def test_blank_headers_preserve_previous_header_and_original_rows(blank):
    p=fixture();p['header_rows'][1]['cells'][0]['value']=blank
    result=card(p)
    assert result['cells'][0]['header']=={'cell':'A1','value':'setting group'}
    assert result['header_rows']==p['header_rows']


@pytest.mark.parametrize('field',['value','data_type','formula','cached_value'])
def test_missing_cell_field_is_failure_not_null(field):
    p=fixture();del p['cells'][0][field]
    saved={'backend':'fixture','case_id':'Q1','status':'completed',
           'bindings':[{'?row_payload':Literal(json.dumps(p)).n3()}]}
    assert package(saved)['status']=='projection_failure'
