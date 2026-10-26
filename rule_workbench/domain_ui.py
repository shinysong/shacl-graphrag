"""Local explicit-domain lookup panel; no automatic selection or rule changes."""
import hashlib
import json
from .core import fingerprint, validate_project
from .domain_candidates import find_domain_candidates


def inspect_column_domain(project, raw, table_id, column, domain_name, declared_type=''):
    validate_project(project)
    table = next((t for t in project['tables'] if t['id'] == table_id), None)
    if table is None or column not in table['columns']:
        raise ValueError('Select an existing table and column.')
    request = {'column_id': json.dumps([table_id, column], ensure_ascii=False),
               'domain_name': domain_name}
    if declared_type:
        request['declared_type'] = declared_type
    report = find_domain_candidates(raw, [request])
    report['project_fingerprint'] = fingerprint(project)
    report['selected_column'] = {'table_id': table_id, 'column': column}
    return report


def render_domain_lookup(project, epoch):
    import streamlit as st
    st.subheader('표준도메인 후보 조회')
    st.caption('선택한 컬럼에 적용할 도메인 이름을 직접 입력합니다. 컬럼 의미를 자동 해석하거나 후보를 승인하지 않습니다.')
    st.markdown('[공식 CSV 받기 · 2025년 11월 8차](https://www.data.go.kr/data/15156442/fileData.do)')
    uploaded = st.file_uploader('공식 공통표준도메인 CSV', type=['csv'], max_upload_size=1, key=f'domain_csv_{epoch}')
    if not uploaded:
        st.info('공식 CSV 원본을 올려주세요. 이번 버전은 검증한 8차 원본 파일만 지원합니다.')
        return
    raw = uploaded.getvalue()
    try:
        find_domain_candidates(raw, [])  # Verify exact snapshot before exposing controls or old results.
    except ValueError:
        st.error('지원하는 원본 CSV와 파일 내용이 다릅니다. 엑셀로 다시 저장한 파일이나 다른 버전은 사용할 수 없습니다.')
        return
    if not project['tables']:
        st.info('데이터 연결에서 조회할 컬럼이 있는 표를 먼저 추가하세요.')
        return
    tables = {t['id']: t for t in project['tables']}
    base = f'domain_{epoch}_{fingerprint(project)}'
    table_id = st.selectbox('표준을 검토할 표', list(tables), format_func=lambda k: tables[k]['name'], key=base+'_table')
    column = st.selectbox('표준을 검토할 컬럼', tables[table_id]['columns'], key=base+'_column_'+table_id)
    domain_name = st.text_input('조회할 도메인 이름', key=base+'_name')
    declared_type = st.text_input('현재 컬럼의 데이터 타입 (선택)', key=base+'_type')
    st.caption('이름·타입의 공백과 대소문자를 그대로 비교합니다. 타입이 일치해도 다른 후보는 숨기지 않습니다.')
    binding = (base, hashlib.sha256(raw).hexdigest(), table_id, column, domain_name, declared_type)
    if st.button('표준도메인 후보 조회 실행', key=base+'_run'):
        try:
            result = inspect_column_domain(project, raw, table_id, column, domain_name, declared_type)
            st.session_state['domain_candidates_result'] = {'binding': binding, 'result': result}
        except ValueError:
            st.session_state.pop('domain_candidates_result', None)
            st.error('표·컬럼과 비어 있지 않은 도메인 이름, 데이터 타입을 확인하세요.')
    stored = st.session_state.get('domain_candidates_result')
    if not stored:
        return
    if stored['binding'] != binding:
        st.warning('조회 입력이나 데이터가 바뀌어 이전 후보를 숨겼습니다. 다시 조회하세요.')
        return
    result = stored['result']; row = result['results'][0]
    status = {'single_candidate': '후보 1개 · 미검토', 'ambiguous_name': '같은 이름의 후보 여러 개 · 미검토',
              'not_found_in_snapshot': '이 원본에서 정확히 일치하는 이름 없음'}
    st.write(status[row['status']])
    type_labels = {'not_supplied': '타입 미입력', 'exact_string_agreement': '타입 문자열 일치',
                   'different_string': '타입 문자열 다름'}
    if row['candidates']:
        st.dataframe([{'원본 레코드': c['source_record'], '타입 비교': type_labels[c['type_comparison']],
                       **c['official_fields']} for c in row['candidates']], hide_index=True)
    st.caption('다운로드에는 선택한 표·컬럼 이름, 입력한 도메인·타입, 공식 사전의 후보와 출처가 포함됩니다. 업무 데이터 행 값은 포함하지 않습니다. 후보를 선택하거나 검사 규칙을 만들지는 않습니다.')
    st.download_button('표준도메인 후보 JSON 다운로드', json.dumps(result, ensure_ascii=False, indent=2).encode(),
                       file_name='domain-candidates.json', mime='application/json', key=base+'_download')
