"""Local relationship review panel; never invokes a model or approves aliases."""
from __future__ import annotations

import copy
import hashlib
import json
import math

from .core import fingerprint
from .linkage import audit_relationship, table_digest
from .linkage_consistency import audit_field_consistency

LABELS = {'linked': '연결됨', 'candidate_only': '별칭 후보', 'ambiguous': '중복으로 모호함',
          'missing_key': '키 누락', 'unmatched_in_snapshot': '현재 자료에서 찾지 못함',
          'unknown_target_scope': '참조 범위 확인 불가', 'not_reviewed': '연결 미검토',
          'stale_mapping': '검토 후 자료 변경'}


def parse_aliases(text):
    if len(text.encode()) > 50_000:
        raise ValueError('별칭 후보는 50KB 이하로 입력하세요.')
    rows = json.loads(text or '[]')
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError('별칭 후보는 최대 100개인 JSON 목록이어야 합니다.')
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'source_value', 'target_value', 'evidence'}:
            raise ValueError('별칭에는 source_value, target_value, evidence가 필요합니다.')
        if not isinstance(row['evidence'], str) or not row['evidence'].strip():
            raise ValueError('별칭의 근거를 입력하세요.')
        for field in ['source_value', 'target_value']:
            value = row[field]
            if (type(value) not in (str, int, float, bool)
                    or isinstance(value, str) and not value.strip()
                    or isinstance(value, float) and not math.isfinite(value)):
                raise ValueError('별칭 키는 비어 있지 않은 문자열 또는 유한한 스칼라 값이어야 합니다.')
    return rows


def inspect_linkage(project, selection, aliases, complete=False, confirmed=False,
                    equality_pairs=None, equality_confirmed=False):
    audited = copy.deepcopy(project)
    tables = {t['id']: t for t in audited['tables']}
    source, target = tables[selection['source_table']], tables[selection['target_table']]
    target['source']['complete'] = complete
    contract = {**selection, 'id': 'interactive-linkage',
                'status': 'confirmed' if confirmed else 'draft',
                'source_digest': table_digest(source), 'target_digest': table_digest(target)}
    result = {'schema_version': 1, 'project_fingerprint': fingerprint(project),
            'contract': contract, 'report': audit_relationship(audited, contract, aliases),
            'notice': 'Declared column mapping and scope; not semantic identity, business approval or alias approval.'}

    if equality_pairs:
        equality_contract = {**contract, 'equality_pairs': equality_pairs,
                             'equality_status': 'confirmed' if equality_confirmed else 'draft'}
        comparison = audit_field_consistency(audited, equality_contract, aliases)
        comparison.pop('linkage')  # Existing report already provides linkage evidence.
        result['consistency'] = comparison
    return result


def export_linkage(result, include_values=False):
    saved = copy.deepcopy(result)
    saved['includes_keys_and_alias_evidence'] = include_values
    if not include_values:
        for row in saved['report']['results']:
            row.pop('value', None)
            for candidate in row['alias_candidates']:
                candidate.pop('evidence', None)
        for row in saved.get('consistency', {}).get('results', []):
            for comparison in row['comparisons']:
                comparison.pop('source_value', None)
                comparison.pop('target_value', None)
    saved['includes_comparison_values'] = include_values
    return json.dumps(saved, ensure_ascii=False, indent=2, allow_nan=False).encode()


def restore_linkage_config(state, project, root, raw):
    """Validate before state changes; use a fresh widget namespace on every load."""
    from .linkage_config import decode_linkage_config
    loaded = decode_linkage_config(project, raw)
    generation = (state[root+'_generation'] if root+'_generation' in state else 0) + 1
    base = root + '_g' + str(generation)
    config = loaded['config']; selection = config['selection']
    source = selection['source_table']; target = selection['target_table']
    values = {base+'_source': source, base+'_target_'+source: target,
              base+'_sc_'+source: selection['source_column'],
              base+'_tc_'+target: selection['target_column'],
              base+'_aliases': json.dumps(config['aliases'], ensure_ascii=False),
              base+'_equality_enabled': bool(config['equality_pairs'])}
    if config['equality_pairs']:
        pair = config['equality_pairs'][0]
        values.update({base+'_es_'+source: pair['source_column'],
                       base+'_et_'+target: pair['target_column']})
    for key, value in values.items():
        state[key] = value
    state[root+'_generation'] = generation
    state[root+'_loaded_status'] = loaded['snapshot_status']
    if 'linkage_result' in state:
        del state['linkage_result']
    return base


def render_linkage(project, epoch):
    import streamlit as st

    st.subheader('표 사이 연결 검토')
    st.caption('키가 같은 행, 별칭 후보, 중복, 누락을 구분합니다. 연결됨은 같은 실물이나 업무 규칙 통과를 뜻하지 않습니다.')
    if len(project['tables']) < 2:
        st.info('데이터 연결에서 비교할 표를 두 개 이상 추가하세요.')
        return
    tables = {t['id']: t for t in project['tables']}
    ids = list(tables); root = f'link_{epoch}_{fingerprint(project)[:16]}'
    with st.expander('연결 설정 불러오기'):
        st.caption('연결 설정 JSON 전용입니다. 검사 결과나 프로젝트 백업과 다릅니다. 불러오면 검토 확인·참조 범위·이전 결과를 초기화합니다.')
        config_file = st.file_uploader('연결 설정 JSON', type=['json'], max_upload_size=1, key=root+'_config_file')
        if st.button('설정 불러오기', disabled=config_file is None, key=root+'_load_config'):
            try:
                restore_linkage_config(st.session_state, project, root, config_file.getvalue())
            except ValueError:
                st.error('설정을 읽지 못했습니다. 100KB 이하의 연결 설정 파일과 표·열 이름을 확인하세요.')
                return
            st.rerun()
    status = st.session_state.get(root+'_loaded_status')
    if status == 'changed_snapshot':
        st.warning('저장 당시와 현재 표의 데이터 또는 출처 정보가 다릅니다. 값이 바뀌었다는 뜻으로 단정하지 말고 열 선택과 참조 범위를 다시 검토하세요.')
    elif status:
        st.info('저장 당시와 현재 표의 데이터·출처 정보가 일치합니다. 검토 확인과 참조 범위는 다시 확인해야 합니다.')
    base = root + '_g' + str(st.session_state.get(root+'_generation', 0))
    source_id = st.selectbox('검사할 표', ids, format_func=lambda k: tables[k]['name'], key=base+'_source')
    target_id = st.selectbox('참조할 표', [k for k in ids if k != source_id],
                             format_func=lambda k: tables[k]['name'], key=base+'_target_'+source_id)
    source_col = st.selectbox('검사할 키 열', tables[source_id]['columns'], key=base+'_sc_'+source_id)
    target_col = st.selectbox('참조할 키 열', tables[target_id]['columns'], key=base+'_tc_'+target_id)
    selection = dict(source_table=source_id, target_table=target_id,
                     source_column=source_col, target_column=target_col)
    with st.expander('별칭 후보와 근거 입력'):
        st.caption('source_value, target_value, evidence를 가진 JSON 목록입니다. 업로드한 파일이 있으면 직접 입력보다 우선합니다. 후보를 자동 승인하지 않습니다.')
        uploaded = st.file_uploader('별칭 후보 JSON', type=['json'], max_upload_size=1, key=base+'_file')
        if base+'_aliases' not in st.session_state:
            st.session_state[base+'_aliases'] = '[]'
        text = st.text_area('별칭 후보 JSON 직접 입력', key=base+'_aliases')
    try:
        aliases = parse_aliases(uploaded.getvalue().decode('utf-8-sig') if uploaded else text)
    except (ValueError, UnicodeError) as exc:
        st.error('별칭 후보를 읽지 못했습니다. JSON 형식과 최대 100개·50KB 제한을 확인하세요.')
        return  # Never expose a previous result while new candidate input is invalid.
    equality_pairs = []
    enabled = st.checkbox('연결된 행의 값도 비교', key=base+'_equality_enabled')
    if enabled:
        st.caption('같아야 하는 열 한 쌍을 선택합니다. 형식·대소문자·공백을 자동 변환하지 않으며, 값 일치가 검사 합격을 뜻하지 않습니다. 빈 값은 근거 부족입니다.')
        ec_source = st.selectbox('비교할 원본 값 열', tables[source_id]['columns'], key=base+'_es_'+source_id)
        ec_target = st.selectbox('비교할 참조 값 열', tables[target_id]['columns'], key=base+'_et_'+target_id)
        equality_pairs = [{'source_column': ec_source, 'target_column': ec_target}]
    from .linkage_config import encode_linkage_config
    st.caption('설정에는 표·열 이름과 별칭 값·근거가 포함됩니다. 원본 행, 문서, 검토 승인은 저장하지 않습니다.')
    try:
        payload = encode_linkage_config(project, selection, aliases, equality_pairs)
        st.download_button('연결 설정 JSON 다운로드', payload, file_name='linkage-config.json',
                           mime='application/json', key=base+'_config_download')
    except ValueError:
        st.error('현재 설정을 저장할 수 없습니다. 설정 파일 크기와 입력을 확인하세요.')
    config = json.dumps({'selection': selection, 'aliases': aliases, 'equality_pairs': equality_pairs}, sort_keys=True, ensure_ascii=False)
    context = base + hashlib.sha256(config.encode()).hexdigest()[:16]
    complete = st.checkbox('참조 자료가 이번 검사 범위를 모두 포함함을 확인했습니다', key=context+'_complete')
    confirmed = st.checkbox('선택한 두 열이 같은 식별자를 나타내는지 검토했습니다', key=context+'_confirmed')
    if any(tables[target_id]['source'].get(k) for k in ['truncated', 'redacted', 'data_omitted']):
        st.info('참조 자료가 잘렸거나 원본 행이 제외되어 있어, 확인을 선택해도 참조 범위는 미확인으로 처리합니다.')
    equality_confirmed = st.checkbox('선택한 값이 같아야 한다는 규칙을 검토했습니다', key=context+'_equality_confirmed') if enabled else False
    binding = (context, complete, confirmed, equality_confirmed)
    if st.button('연결 검사 실행', key=base+'_run'):
        try:
            result = inspect_linkage(project, selection, aliases, complete, confirmed, equality_pairs, equality_confirmed)
            st.session_state['linkage_result'] = {'binding': binding, 'result': result}
        except ValueError as exc:
            st.session_state.pop('linkage_result', None)
            st.error(str(exc))
    stored = st.session_state.get('linkage_result')
    if not stored:
        return
    if stored['binding'] != binding:
        st.warning('입력이나 검토 상태가 바뀌어 이전 연결 결과는 숨겼습니다. 다시 실행하세요.')
        return
    report = stored['result']['report']
    st.write(f"검사 대상: 가져온 {report['denominator']:,}행")
    if report['source_truncated'] or report['source_redacted']:
        st.warning('검사할 자료도 일부만 제공됐습니다. 전체 원본의 연결률로 해석하지 마세요.')
    st.dataframe([{'연결 상태': LABELS[k], '행 수': v} for k, v in report['counts'].items()], hide_index=True)
    st.dataframe([{'원본 행': r['source_row'], '키': str(r['value']), '상태': LABELS[r['status']],
                   '정확히 일치한 참조 행': str(r['exact_target_rows']),
                   '별칭 후보와 근거': json.dumps(r['alias_candidates'], ensure_ascii=False)}
                  for r in report['results']], hide_index=True)
    consistency = stored['result'].get('consistency')
    if consistency:
        names = {'agrees': '선택한 값 일치', 'violates_declared_equality': '선언한 일치 규칙 위반',
                 'missing_evidence': '비교할 값 누락', 'not_evaluated': '비교 보류'}
        st.subheader('연결된 행의 값 비교')
        st.dataframe([{'비교 결과': names[k], '행 수': v} for k, v in consistency['counts'].items()], hide_index=True)
        reasons = {**LABELS, 'equality_not_reviewed': '값 비교 규칙 미검토',
                   'reviewed_exact_equality': '검토한 값 일치 규칙 적용'}
        st.dataframe([{'원본 행': r['source_row'], '결과': names[r['status']],
                       '사유': reasons.get(r['reason'], r['reason']),
                       '비교 근거': json.dumps(r['comparisons'], ensure_ascii=False)}
                      for r in consistency['results']], hide_index=True)
    include = st.checkbox('내보내기에 원본 키·비교 값·별칭 근거 포함', key=context+'_export_values')
    st.caption('연결 검사 결과는 별도 JSON으로 저장합니다. 프로젝트 JSON에는 포함되지 않습니다. 기본 내보내기는 키·비교 값·별칭 근거 문구를 제외하지만 표·열 이름과 행 번호는 포함합니다.')
    st.download_button('연결 결과 JSON 다운로드', export_linkage(stored['result'], include),
                       file_name='linkage-report.json', mime='application/json', key=context+'_download')
