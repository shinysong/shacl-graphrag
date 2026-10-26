"""Explicit term lookup, without semantic mapping or automatic approval."""
import hashlib
import json
from .core import fingerprint, validate_project
from .term_candidates import find_term_candidates


def inspect_column_term(project, terms, domains, table_id, column, term_name):
    validate_project(project)
    table=next((t for t in project['tables'] if t['id']==table_id),None)
    if table is None or column not in table['columns']:raise ValueError('Select an existing column.')
    result=find_term_candidates(terms,domains,[{'column_id':json.dumps([table_id,column],ensure_ascii=False),'term_name':term_name}])
    result['project_fingerprint']=fingerprint(project)
    result['selected_column']={'table_id':table_id,'column':column}
    return result


def render_term_lookup(project,epoch):
    import streamlit as st
    st.subheader('표준용어와 도메인 후보 조회')
    st.caption('용어 이름을 직접 입력합니다. 용어가 하나여도 도메인 후보는 여러 개일 수 있습니다. 자동 매핑·승인·규칙 생성은 하지 않습니다.')
    st.markdown('[공식 용어 CSV](https://www.data.go.kr/data/15156379/fileData.do) · [공식 도메인 CSV](https://www.data.go.kr/data/15156442/fileData.do) · 2025년 11월 8차')
    terms=st.file_uploader('공식 공통표준용어 CSV',type=['csv'],max_upload_size=4,key=f'term_csv_{epoch}')
    domains=st.file_uploader('용어 연결용 공통표준도메인 CSV',type=['csv'],max_upload_size=1,key=f'term_domain_csv_{epoch}')
    if terms is None or domains is None:
        st.info('용어와 도메인 CSV 원본을 모두 올려주세요. 검증한 8차 파일만 지원합니다.');return
    term_raw=terms.getvalue();domain_raw=domains.getvalue()
    try:find_term_candidates(term_raw,domain_raw,[])
    except ValueError:
        st.error('지원하는 원본과 다릅니다. 용어·도메인 파일의 버전과 내용을 확인하세요.');return
    if not project['tables']:
        st.info('데이터 연결에서 검토할 컬럼이 있는 표를 추가하세요.');return
    tables={t['id']:t for t in project['tables']};base=f'term_{epoch}_{fingerprint(project)}'
    table=st.selectbox('용어를 검토할 표',list(tables),format_func=lambda k:tables[k]['name'],key=base+'_table')
    column=st.selectbox('용어를 검토할 컬럼',tables[table]['columns'],key=base+'_column_'+table)
    name=st.text_input('조회할 표준용어 이름',max_chars=1000,key=base+'_name')
    st.caption('공백까지 정확히 일치하는 이름을 조회합니다. 동의어·약어·개정 이력은 원문만 보여주며 해석하거나 후보를 제거하지 않습니다.')
    binding=(base,hashlib.sha256(term_raw).hexdigest(),hashlib.sha256(domain_raw).hexdigest(),table,column,name)
    if st.button('표준용어 후보 조회 실행',key=base+'_run'):
        try:st.session_state['term_candidates_result']={'binding':binding,'result':inspect_column_term(project,term_raw,domain_raw,table,column,name)}
        except ValueError:
            st.session_state.pop('term_candidates_result',None);st.error('표·컬럼과 비어 있지 않은 용어 이름을 확인하세요.')
    stored=st.session_state.get('term_candidates_result')
    if not stored:return
    if stored['binding']!=binding:
        st.warning('입력이나 데이터가 바뀌어 이전 용어 후보를 숨겼습니다. 다시 조회하세요.');return
    result=stored['result'];row=result['results'][0]
    st.write(f"용어 후보 {len(row['candidates'])}개 · 미검토")
    if not row['candidates']:st.info('이 원본에서 정확히 일치하는 용어 이름을 찾지 못했습니다.')
    for candidate in row['candidates']:
        st.write(f"용어 원본 레코드 {candidate['source_record']}")
        st.dataframe([candidate['official_fields']],hide_index=True)
        linked=candidate['domain_lookup']['candidates']
        st.write(f'연결된 도메인 후보 {len(linked)}개 · 미검토')
        if linked:st.dataframe([{'원본 레코드':c['source_record'],**c['official_fields']} for c in linked],hide_index=True)
        else:st.info('이 도메인 원본에서 일치하는 이름을 찾지 못했습니다.')
    st.caption('다운로드에는 표·컬럼 이름, 조회 이름, 공식 후보·출처 해시가 포함됩니다. 업무 데이터 행 값은 포함하지 않습니다. 프로젝트 백업이나 승인된 규칙 파일이 아닙니다.')
    st.download_button('표준용어 후보 JSON 다운로드',json.dumps(result,ensure_ascii=False,indent=2).encode(),file_name='term-candidates.json',mime='application/json',key=base+'_download')
