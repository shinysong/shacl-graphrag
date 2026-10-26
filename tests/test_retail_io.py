import json
import pytest
from scripts.retail_io import build_packet,expected_keys,parse_output
from scripts.score_retail_decisions import score

def packet():
    return build_packet([{'row_id':'2','data':{'x':None}}],[{'id':'p','origin':'authored','meaning':'x required'}],[{'name':'x','description':'value','unwanted':'exclude'}])

def test_packet_stable_and_no_label():
    a=packet();assert a==packet();assert expected_keys(a)==[('2','p')]
    assert 'unwanted' not in a['common_input']['variables'][0]
    with pytest.raises(ValueError):build_packet([{'row_id':'2','data':{'x':1},'gold':'pass'}],a['common_input']['policies'],a['common_input']['variables'])

def test_changed_input_changes_hash():
    a=packet();r=a['common_input'];r['rows'][0]['data']['x']='new'
    assert build_packet(r['rows'],r['policies'],r['variables'])['input_sha256']!=a['input_sha256']

def test_wrong_but_valid_preserved():
    raw=json.dumps({'decisions':[{'row_id':'2','policy':'p','status':'pass'}]})
    r=parse_output(raw,[('2','p')]);assert r['schema_error'] is None and r['raw']==raw
    assert score([{'row_id':'2','policy':'p','status':'violation'}],r['predictions'])['overall']['false_pass_n']==1

def test_missing_not_schema_failure():
    r=parse_output('{"decisions":[]}',[('2','p')]);assert r['predictions']==[] and r['schema_error'] is None
    assert score([{'row_id':'2','policy':'p','status':'violation'}],r['predictions'])['overall']['missing_output_n']==1

@pytest.mark.parametrize('raw',['bad','```json\n{}\n```','{"decisions":[],"decisions":[]}','{"decisions":null}','{"decisions":[{"row_id":"2","policy":"p","status":"yes"}]}','{"decisions":[{"row_id":"3","policy":"p","status":"pass"}]}','{"decisions":[{"row_id":"2","policy":"p","status":"pass","reason":NaN}]}'])
def test_malformed_response_preserved_as_batch_failure(raw):
    r=parse_output(raw,[('2','p')]);assert r['raw']==raw and r['schema_error']
    assert r['predictions']==[{'row_id':'2','policy':'p','status':'error'}]

def test_duplicate_prediction():
    d={'row_id':'2','policy':'p','status':'pass'}
    assert parse_output(json.dumps({'decisions':[d,d]}),[('2','p')])['schema_error']

def test_partial_keeps_valid():
    raw=json.dumps({'decisions':[{'row_id':'2','policy':'p','status':'unknown'}]})
    r=parse_output(raw,[('2','p'),('3','p')]);assert r['missing_keys']==[['3','p']] and r['predictions'][0]['status']=='unknown'
