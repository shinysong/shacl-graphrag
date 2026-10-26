"""Portable, versioned workspaces and inspection reports; no database credentials."""
import copy
import csv
import io
import json
import zipfile
from datetime import datetime, timezone

from openpyxl import Workbook

from .core import fingerprint, validate_project


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')


def _source(source):
    allowed = {'kind', 'file', 'sheet', 'table', 'sha256', 'truncated', 'redacted', 'data_omitted', 'page', 'line', 'quote', 'row_count', 'loaded_rows', 'total_rows', 'retrieved_at'}
    return {k: v for k, v in source.items() if k in allowed}


def export_json(project, include_data=False):
    validate_project(project)
    p = {'schema_version': 1, 'name': project['name'], 'tables': [], 'rules': [], 'documents': []}
    for table in project['tables']:
        t = {k: copy.deepcopy(table[k]) for k in ['id', 'name', 'columns']}
        t['source'] = _source(table['source'])
        t['rows'] = copy.deepcopy(table['rows']) if include_data else []
        if not include_data:
            t['source']['data_omitted'] = True
            t['source']['loaded_rows'] = len(table['rows'])
        p['tables'].append(t)
    for rule in project['rules']:
        r = {k: copy.deepcopy(rule[k]) for k in ['id', 'text', 'status', 'table', 'column', 'kind', 'params']}
        if 'llm' in rule:
            r['llm'] = copy.deepcopy(rule['llm'])
        r['source'] = _source(rule['source']); p['rules'].append(r)
    for doc in project['documents']:
        p['documents'].append({'name': doc['name'], 'segments': copy.deepcopy(doc['segments']) if include_data else [], 'content_omitted': not include_data})
    return _json(p)


def import_json(payload):
    if len(payload) > 20 * 1024 * 1024:
        raise ValueError('작업 파일은 최대 20MB입니다.')
    try:
        p = json.loads(payload.decode('utf-8-sig'))
        validate_project(p)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise ValueError('작업 JSON 형식 오류: ' + str(exc)) from None
    # Normalize portable keys and discard unrelated input fields, including connection strings.
    return json.loads(export_json(p, include_data=True))


def fresh_result(project, result):
    if result is not None and result.get('fingerprint') != fingerprint(project):
        raise ValueError('규칙 또는 데이터가 변경되었습니다. 다시 검사한 뒤 결과를 내보내세요.')
    return result


def _cell(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        # Spreadsheet formula evaluation must never execute imported document text.
        if value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')):
            value = "'" + value
        value = ''.join(ch for ch in value if ord(ch) >= 32 or ch in '\t\n\r')
        return value[:32767]
    return value


def _rule_rows(project):
    names = {t['id']: t['name'] for t in project['tables']}
    return [[r['id'], r['text'], r['status'], names.get(r['table'], r['table']), r['column'], r['kind'], r['params'], _source(r['source']), r.get('llm', {})] for r in project['rules']]


def export_excel(project, result=None):
    validate_project(project); fresh_result(project, result)
    book = Workbook(); sheet = book.active; sheet.title = '규칙'
    sheet.append(['규칙 ID', '요구사항', '검토 상태', '테이블', '열', '종류', '매개변수', '원문 출처', 'LLM 제안 이력'])
    for row in _rule_rows(project): sheet.append([_cell(c) for c in row])
    if result is not None:
        sheet = book.create_sheet('검사 결과')
        sheet.append(['규칙 ID', '테이블 ID', '데이터 행', '상태', '판정 근거', '데이터 출처', '규칙 출처'])
        for row in result['results']:
            sheet.append([_cell(row.get(k)) for k in ['rule_id', 'table', 'row', 'status', 'message', 'source', 'rule_source']])
    for sheet in book:
        sheet.freeze_panes = 'A2'; sheet.auto_filter.ref = sheet.dimensions
        for col in 'ABCDEFGH': sheet.column_dimensions[col].width = 24
    output = io.BytesIO(); book.save(output); return output.getvalue()


def export_bundle(project, result=None, include_data=False):
    validate_project(project); fresh_result(project, result)
    portable = json.loads(export_json(project, include_data))
    manifest = {'format': 'rule-workbench', 'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
                'source_fingerprint': fingerprint(project), 'includes_data': include_data,
                'has_current_result': result is not None,
                'scope': 'SHACL targets this snapshot only. Unknown/unmapped rows are recorded outside SHACL; the shapes alone do not represent full coverage.'}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json', _json(manifest)); z.writestr('project.json', _json(portable))
        z.writestr('rules.json', _json(portable['rules']))
        z.writestr('mappings.json', _json([{'rule_id': r['id'], 'table': r['table'], 'column': r['column'], 'kind': r['kind'], 'params': r['params']} for r in portable['rules']]))
        z.writestr('review.xlsx', export_excel(project, result))
        if result is not None:
            z.writestr('shapes.ttl', result['shapes_ttl'])
            if include_data: z.writestr('data.ttl', result['data_ttl'])
            fields = ['rule_id', 'rule_text', 'table', 'row', 'status', 'message', 'source', 'rule_source']
            s = io.StringIO(); writer = csv.DictWriter(s, fieldnames=fields); writer.writeheader()
            for row in result['results']: writer.writerow({k: _cell(row.get(k)) for k in fields})
            z.writestr('results.csv', s.getvalue().encode('utf-8-sig'))
            z.writestr('coverage.json', _json({'counts': result['counts'], 'scope': result['scope']}))
    return stream.getvalue()
