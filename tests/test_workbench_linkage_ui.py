import copy
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from rule_workbench.core import new_project
from rule_workbench.linkage import audit_relationship, table_digest
from rule_workbench.linkage_ui import export_linkage, inspect_linkage, parse_aliases


def fixture():
    project = new_project()
    for name, values in [('orders', ['A', 'OLD', None, 'X', 'D']), ('parts', ['A', 'B', 'D', 'D'])]:
        project['tables'].append({'id': name, 'name': name, 'columns': ['code'],
                                  'rows': [{'code': v} for v in values], 'source': {'kind': 'fixture'}})
    return project


SELECTION = dict(source_table='orders', source_column='code', target_table='parts', target_column='code')
ALIASES = [{'source_value': 'OLD', 'target_value': 'B', 'evidence': 'PRIVATE-EVIDENCE'}]


def test_inspection_does_not_mutate_input_or_approve_aliases():
    p = fixture(); before = copy.deepcopy(p)
    result = inspect_linkage(p, SELECTION, ALIASES, True, True)
    assert p == before
    assert result['report']['counts'] == dict(linked=1, candidate_only=1, missing_key=1,
                                             unmatched_in_snapshot=1, ambiguous=1)
    assert set(inspect_linkage(p, SELECTION, ALIASES)['report']['counts']) == {'not_reviewed'}


def test_redacted_download_omits_keys_and_alias_evidence():
    r = inspect_linkage(fixture(), SELECTION, ALIASES, True, True)
    payload = export_linkage(r)
    assert b'PRIVATE-EVIDENCE' not in payload and b'"OLD"' not in payload
    saved = json.loads(payload)
    assert all('value' not in x for x in saved['report']['results'])
    assert saved['report']['results'][1]['alias_candidates'] == [{'target_row': 2}]
    assert b'PRIVATE-EVIDENCE' in export_linkage(r, True)
    assert r['report']['results'][1]['value'] == 'OLD'


@pytest.mark.parametrize('text', ['{}', '[null]', '[{"source_value": [], "target_value": "B", "evidence": "x"}]',
                                  '[{"source_value": "a", "target_value": NaN, "evidence": "x"}]',
                                  '[{"source_value": "a", "target_value": "b", "evidence": ""}]'])
def test_invalid_alias_inputs_rejected(text):
    with pytest.raises(ValueError): parse_aliases(text)


def test_alias_size_limits():
    with pytest.raises(ValueError): parse_aliases(json.dumps(ALIASES * 101))
    with pytest.raises(ValueError): parse_aliases(' ' * 50_001)


def test_omitted_target_rows_remain_unknown_despite_scope_checkbox():
    p = fixture(); p['tables'][1]['source']['data_omitted'] = True
    result = inspect_linkage(p, SELECTION, [], True, True)
    assert result['report']['results'][0]['status'] == 'unknown_target_scope'


def test_dense_evidence_budget_fails_without_partial_result():
    p = fixture()
    p['tables'][0]['rows'] = [{'code': 'A'} for _ in range(5000)]
    p['tables'][1]['rows'] = [{'code': 'A'} for _ in range(11)]
    with pytest.raises(ValueError, match='50,000'):
        inspect_linkage(p, SELECTION, [], True, True)


def test_long_alias_evidence_cannot_expand_into_large_report():
    p = fixture()
    p['tables'][0]['rows'] = [{'code': 'OLD'} for _ in range(100)]
    p['tables'][1]['rows'] = [{'code': 'B'} for _ in range(100)]
    aliases = parse_aliases(json.dumps([{'source_value': 'OLD', 'target_value': 'B', 'evidence': 'x'*40_000}]))
    with pytest.raises(ValueError, match='2MB'):
        inspect_linkage(p, SELECTION, aliases, True, True)


def test_ui_review_scope_candidate_and_stale_results():
    at = AppTest.from_file(str(Path('apps/rule_workbench.py').resolve()), default_timeout=30).run()
    at.session_state['project'] = fixture(); at.run()
    assert not at.exception
    next(x for x in at.text_area if x.label == '별칭 후보 JSON 직접 입력').set_value(json.dumps(ALIASES)).run()
    next(b for b in at.button if b.label == '연결 검사 실행').click().run()
    assert set(at.session_state['linkage_result']['result']['report']['counts']) == {'not_reviewed'}
    next(c for c in at.checkbox if c.label.startswith('참조 자료가')).check()
    next(c for c in at.checkbox if c.label.startswith('선택한 두 열이')).check().run()
    assert any('이전 연결 결과는 숨겼습니다' in x.value for x in at.warning)
    next(b for b in at.button if b.label == '연결 검사 실행').click().run()
    assert at.session_state['linkage_result']['result']['report']['counts']['candidate_only'] == 1
    changed = copy.deepcopy(at.session_state['project']); changed['tables'][0]['rows'][0]['code'] = 'B'
    at.session_state['project'] = changed; at.run()
    assert not at.exception
    assert any('이전 연결 결과는 숨겼습니다' in x.value for x in at.warning)
    assert not next(c for c in at.checkbox if c.label.startswith('선택한 두 열이')).value


def test_comparison_export_and_unreviewed_boundary():
    p=fixture()
    for table in p['tables']:
        table['columns'].append('item')
        for row in table['rows']:row['item']='PRIVATE-ITEM'
    pairs=[{'source_column':'item','target_column':'item'}]
    result=inspect_linkage(p,SELECTION,ALIASES,True,True,pairs,False)
    assert result['consistency']['counts']=={'not_evaluated':5}
    result=inspect_linkage(p,SELECTION,ALIASES,True,True,pairs,True)
    assert result['consistency']['counts']=={'agrees':1,'not_evaluated':4}
    assert result['consistency']['results'][1]['reason']=='candidate_only'
    assert b'PRIVATE-ITEM' not in export_linkage(result)
    assert b'PRIVATE-ITEM' in export_linkage(result,True)
    assert 'linkage' not in result['consistency']
    assert result['consistency']['results'][0]['comparisons'][0]['source_value']=='PRIVATE-ITEM'


def test_ui_equality_review_and_selection_reset():
    at=AppTest.from_file(str(Path('apps/rule_workbench.py').resolve()),default_timeout=30).run()
    p=fixture()
    for table in p['tables']:
        table['columns'].append('item')
        for row in table['rows']:row['item']='P'
    at.session_state['project']=p;at.run()
    next(c for c in at.checkbox if c.label=='연결된 행의 값도 비교').check().run()
    next(c for c in at.checkbox if c.label.startswith('참조 자료가')).check()
    next(c for c in at.checkbox if c.label.startswith('선택한 두 열이')).check()
    next(c for c in at.checkbox if c.label=='선택한 값이 같아야 한다는 규칙을 검토했습니다').check().run()
    next(b for b in at.button if b.label=='연결 검사 실행').click().run()
    assert at.session_state['linkage_result']['result']['consistency']['counts']['agrees']==1
    next(c for c in at.selectbox if c.label=='비교할 원본 값 열').select('item').run()
    assert any('이전 연결 결과는 숨겼습니다' in w.value for w in at.warning)
    assert not next(c for c in at.checkbox if c.label=='선택한 값이 같아야 한다는 규칙을 검토했습니다').value
    assert not at.exception


def test_config_restore_resets_widgets_and_results():
    from rule_workbench.linkage_config import encode_linkage_config
    from rule_workbench.linkage_ui import restore_linkage_config
    p=fixture(); raw=encode_linkage_config(p,SELECTION,ALIASES)
    state={'linkage_result':{'old':True},'root_g0_confirmed':True}
    base=restore_linkage_config(state,p,'root',raw)
    assert base=='root_g1' and 'linkage_result' not in state
    assert state[base+'_source']=='orders'
    assert json.loads(state[base+'_aliases'])==ALIASES
    assert not state[base+'_equality_enabled']
    assert not any(k.startswith(base) and k.endswith(('_confirmed','_complete','_file')) for k in state)
    assert state['root_loaded_status']=='same_snapshot'
    assert restore_linkage_config(state,p,'root',raw)=='root_g2'
    p['tables'][0]['rows'][0]['code']='changed'
    restore_linkage_config(state,p,'root',raw)
    assert state['root_loaded_status']=='changed_snapshot'
    before=copy.deepcopy(state)
    with pytest.raises(ValueError): restore_linkage_config(state,p,'root',b'{}')
    assert state==before


def test_config_restore_app_widgets_are_unreviewed():
    from rule_workbench.core import fingerprint
    from rule_workbench.linkage_config import encode_linkage_config
    from rule_workbench.linkage_ui import restore_linkage_config
    at=AppTest.from_file(str(Path('apps/rule_workbench.py').resolve()),default_timeout=30).run()
    p=fixture();at.session_state['project']=p;at.run()
    source_widget=next(x for x in at.selectbox if x.label=='검사할 표')
    root=source_widget.key.rsplit('_g',1)[0]
    next(c for c in at.checkbox if c.label.startswith('참조 자료가')).check()
    next(c for c in at.checkbox if c.label.startswith('선택한 두 열이')).check().run()
    next(b for b in at.button if b.label=='연결 검사 실행').click().run()
    raw=encode_linkage_config(p,SELECTION,ALIASES,[{'source_column':'code','target_column':'code'}])
    restore_linkage_config(at.session_state,p,root,raw);at.run()
    assert not at.exception
    assert not next(c for c in at.checkbox if c.label.startswith('참조 자료가')).value
    assert not next(c for c in at.checkbox if c.label.startswith('선택한 두 열이')).value
    assert not next(c for c in at.checkbox if c.label.startswith('선택한 값이')).value
    assert next(c for c in at.checkbox if c.label=='연결된 행의 값도 비교').value
    assert next(x for x in at.text_area if x.label=='별칭 후보 JSON 직접 입력').value==json.dumps(ALIASES,ensure_ascii=False)
    assert any('다시 확인' in x.value for x in at.info)
    next(b for b in at.button if b.label=='연결 검사 실행').click().run()
    assert set(at.session_state['linkage_result']['result']['report']['counts'])=={'not_reviewed'}
