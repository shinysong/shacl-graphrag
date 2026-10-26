import csv,hashlib,io,json
import pytest
import rule_workbench.term_candidates as module
import rule_workbench.domain_candidates as domain

@pytest.fixture
def source(tmp_path,monkeypatch):
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=module.HEADERS);writer.writeheader()
    for marker in ('','변경'):
        row={h:'' for h in module.HEADERS};row.update({'공통표준용어명':'번호용어','공통표준도메인명':'번호C9','개정구분명(폐기 또는 변경)':marker,'용어 이음동의어 목록':'별칭'})
        writer.writerow(row)
    raw=stream.getvalue().encode('utf-8-sig');pin=tmp_path/'pin.json'
    pin.write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'expected_rows':2}))
    monkeypatch.setattr(module,'PIN',pin)
    monkeypatch.setattr(domain,'profile',lambda raw:({}, {'tables':[{'rows':[{'공통표준도메인명':'번호C9','데이터타입':t} for t in ('CHAR','VARCHAR')]}]}))
    return raw

def test_nested_ambiguity_revisions_and_raw_names(source):
    req=[{'column_id':str(i),'term_name':name} for i,name in enumerate(['번호용어',' 번호용어','별칭'])]
    r=module.find_term_candidates(source,b'domain-unit-stub',req)
    assert [x['status'] for x in r['results']]==['ambiguous_name','not_found_in_snapshot','not_found_in_snapshot']
    c=r['results'][0]['candidates'];assert len(c)==2
    assert [x['official_fields']['개정구분명(폐기 또는 변경)'] for x in c]==['','변경']
    assert len({x['snapshot_row_id'] for x in c})==2
    assert all(x['domain_lookup']['status']=='ambiguous_name' and len(x['domain_lookup']['candidates'])==2 for x in c)
    assert all(x['approval_status']=='unreviewed' for x in r['results'])

def test_term_pin_rejects_modified_bytes(source):
    with pytest.raises(ValueError,match='pinned'):module.find_term_candidates(source+b' ',b'x',[])

@pytest.mark.parametrize('requests',[{},[{}],[{'column_id':'x','term_name':''}], [{'column_id':'x','term_name':'a','extra':1}], [{'column_id':'x','term_name':'a'}]*2, [{'column_id':str(i),'term_name':'a'} for i in range(101)]])
def test_request_contract_rejected(source,requests):
    with pytest.raises(ValueError):module.find_term_candidates(source,b'x',requests)
