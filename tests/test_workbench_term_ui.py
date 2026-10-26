import copy,json
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
import rule_workbench.term_ui as module
from rule_workbench.core import new_project

def fixture():
    p=new_project();p['tables'].append({'id':'t','name':'Table','columns':['id'],'rows':[{'id':'PRIVATE-ROW'}],'source':{}});return p

def test_column_binding_and_business_value_exclusion(monkeypatch):
    def lookup(a,b,req):
        assert req==[{'column_id':'["t", "id"]','term_name':'번호'}]
        return {'results':[{'request':req[0],'candidates':[],'approval_status':'unreviewed'}]}
    monkeypatch.setattr(module,'find_term_candidates',lookup)
    p=fixture();before=copy.deepcopy(p);r=module.inspect_column_term(p,b'a',b'b','t','id','번호')
    assert p==before and r['selected_column']=={'table_id':'t','column':'id'}
    assert 'PRIVATE-ROW' not in json.dumps(r)

@pytest.mark.parametrize('table,column',[('bad','id'),('t','bad')])
def test_invalid_column(table,column):
    with pytest.raises(ValueError):module.inspect_column_term(fixture(),b'',b'',table,column,'번호')

def test_real_app_requires_two_files():
    at=AppTest.from_file(str(Path('apps/rule_workbench.py').resolve()),default_timeout=30).run()
    assert not at.exception and any(t.label=='표준용어' for t in at.tabs)
    assert any('모두 올려주세요' in x.value for x in at.info)
    assert not any(b.label=='표준용어 후보 조회 실행' for b in at.button)

def test_render_stale_and_invalid_sources_hide_result(monkeypatch):
    def lookup(a,b,req):
        if a==b'bad':raise ValueError('bad source')
        return {'results':[{'candidates':[],'approval_status':'unreviewed'}] if req else []}
    monkeypatch.setattr(module,'find_term_candidates',lookup)
    code='''
import streamlit as st
from rule_workbench.term_ui import render_term_lookup
from rule_workbench.core import new_project
class Upload:
    def getvalue(self):return st.session_state.get('raw',b'ok')
from unittest.mock import patch
p=new_project();p['tables']=[{'id':'t','name':'T','columns':['id'],'rows':[{'id':'private'}],'source':{}}]
with patch.object(st,'file_uploader',lambda *a,**k: Upload()):
    render_term_lookup(p,0)
'''
    at=AppTest.from_string(code,default_timeout=30).run()
    at.text_input[0].set_value('번호').run();at.button[0].click().run()
    assert not at.exception and 'term_candidates_result' in at.session_state
    at.text_input[0].set_value('다름').run()
    assert any('이전 용어 후보를 숨겼습니다' in w.value for w in at.warning)
    at.session_state['raw']=b'bad';at.run()
    assert any('지원하는 원본과 다릅니다' in e.value for e in at.error)
    assert not at.button
