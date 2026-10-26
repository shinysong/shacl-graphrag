import copy
import pytest
import rule_workbench.domain_candidates as module

@pytest.fixture
def dictionary(monkeypatch):
    rows=[{'공통표준도메인명':'번호C9','데이터타입':'CHAR','단위':''},
          {'공통표준도메인명':'번호C9','데이터타입':'VARCHAR','단위':''},
          {'공통표준도메인명':'날짜','데이터타입':'DATETIME','단위':''}]
    # Unit lookup stub only; actual pin verified by real-source replay separately.
    monkeypatch.setattr(module,'profile',lambda raw:({}, {'tables':[{'rows':rows}]}))
    return rows

def test_duplicates_retained_despite_type_agreement(dictionary):
    request=[{'column_id':'orders.id','domain_name':'번호C9','declared_type':'CHAR'}]
    before=copy.deepcopy(dictionary)
    r=module.find_domain_candidates(b'unit-fixture',request)['results'][0]
    assert r['status']=='ambiguous_name' and r['approval_status']=='unreviewed'
    assert [x['type_comparison'] for x in r['candidates']]==['exact_string_agreement','different_string']
    assert len({c['snapshot_row_id'] for c in r['candidates']})==2
    assert dictionary==before

def test_missing_single_and_no_coercion(dictionary):
    req=[{'column_id':'a','domain_name':'날짜'},
         {'column_id':'b','domain_name':' 번호C9'},
         {'column_id':'c','domain_name':'번호C9','declared_type':'char'}]
    r=module.find_domain_candidates(b'x',req)['results']
    assert [x['status'] for x in r]==['single_candidate','not_found_in_snapshot','ambiguous_name']
    assert r[0]['candidates'][0]['type_comparison']=='not_supplied'
    assert all(c['type_comparison']=='different_string' for c in r[2]['candidates'])
    assert all(x['approval_status']=='unreviewed' for x in r)

@pytest.mark.parametrize('req',[{},[{}],[{'column_id':'x','domain_name':''}],
    [{'column_id':'x','domain_name':'날짜','declared_type':None}],
    [{'column_id':'x','domain_name':'날짜','extra':1}],
    [{'column_id':'x','domain_name':'날짜'}]*2,
    [{'column_id':str(i),'domain_name':'날짜'} for i in range(1001)]])
def test_invalid_requests(dictionary,req):
    with pytest.raises(ValueError):module.find_domain_candidates(b'x',req)

def test_actual_pin_is_not_optional():
    with pytest.raises(ValueError,match='pinned'):module.find_domain_candidates(b'fake',[])

def test_returned_fields_do_not_mutate_dictionary(dictionary):
    r=module.find_domain_candidates(b'x',[{'column_id':'a','domain_name':'날짜'}])
    r['results'][0]['candidates'][0]['official_fields']['단위']='changed'
    assert dictionary[2]['단위']==''
