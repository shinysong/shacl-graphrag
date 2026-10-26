import copy,json
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
import rule_workbench.domain_ui as module
from rule_workbench.core import new_project

def fixture():
    p=new_project()
    p['tables'].append({'id':'orders','name':'Orders','columns':['id'],
                        'rows':[{'id':'PRIVATE-BUSINESS-VALUE'}],'source':{}})
    return p

def test_selected_column_provenance_and_no_business_rows(monkeypatch):
    def lookup(raw,requests):
        assert requests==[{'column_id':'["orders", "id"]','domain_name':'번호C9','declared_type':'CHAR'}]
        return {'results':[{'request':requests[0],'approval_status':'unreviewed','candidates':[]}]}
    monkeypatch.setattr(module,'find_domain_candidates',lookup)
    p=fixture();before=copy.deepcopy(p)
    r=module.inspect_column_domain(p,b'fixture','orders','id','번호C9','CHAR')
    assert p==before
    assert r['selected_column']=={'table_id':'orders','column':'id'}
    assert 'PRIVATE-BUSINESS-VALUE' not in json.dumps(r)
    assert r['project_fingerprint']

@pytest.mark.parametrize('table,column',[('absent','id'),('orders','missing')])
def test_invalid_column_rejected(table,column):
    with pytest.raises(ValueError):module.inspect_column_domain(fixture(),b'',table,column,'번호C9')

def test_panel_requires_uploaded_dictionary():
    at=AppTest.from_file(str(Path('apps/rule_workbench.py').resolve()),default_timeout=30).run()
    assert not at.exception
    assert any(t.label=='표준도메인' for t in at.tabs)
    assert any('공식 CSV 원본을 올려주세요' in x.value for x in at.info)
    assert not any(b.label=='표준도메인 후보 조회 실행' for b in at.button)
