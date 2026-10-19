"""Small, explicit rule workbench. Inspection results are not business approvals."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from rdflib import BNode, Graph, Literal, Namespace, RDF, SH, URIRef, XSD
from rdflib.collection import Collection
from pyshacl import validate

BASE = 'urn:rule-workbench:'
KINDS = {'required', 'range', 'allowed', 'date_order', 'reference'}


def new_project(name='규칙 검토 작업'):
    return {'schema_version': 1, 'name': name, 'tables': [], 'rules': [], 'documents': []}


def _text(value, label, limit=100000):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'{label}: 문자열 또는 길이를 확인하세요.')


def validate_project(project):
    if not isinstance(project, dict) or project.get('schema_version') != 1:
        raise ValueError('지원하는 작업 형식은 schema_version 1입니다.')
    _text(project.get('name'), '작업 이름', 500)
    for key, cap in [('tables', 50), ('rules', 100), ('documents', 100)]:
        if not isinstance(project.get(key), list) or len(project[key]) > cap:
            raise ValueError(f'{key}: 최대 {cap}개까지 지원합니다.')
    ids = set()
    for table in project['tables']:
        if not isinstance(table, dict):
            raise ValueError('테이블 형식 오류')
        _text(table.get('id'), '테이블 ID', 200)
        _text(table.get('name'), '테이블 이름', 500)
        if not table['id'] or table['id'] in ids:
            raise ValueError('테이블 ID는 비어 있지 않고 고유해야 합니다.')
        ids.add(table['id'])
        cols = table.get('columns')
        if not isinstance(cols, list) or not 1 <= len(cols) <= 200:
            raise ValueError('테이블은 1~200개 열이어야 합니다.')
        for col in cols:
            _text(col, '열 이름', 500)
        if len(set(cols)) != len(cols) or any(not c for c in cols):
            raise ValueError('빈 열 이름 또는 중복 열 이름이 있습니다.')
        rows = table.get('rows')
        if not isinstance(rows, list) or len(rows) > 5000:
            raise ValueError('테이블은 최대 5,000개 행까지 지원합니다.')
        for row in rows:
            if not isinstance(row, dict) or set(row) - set(cols):
                raise ValueError('행과 열의 연결이 올바르지 않습니다.')
            for val in row.values():
                if val is not None and not isinstance(val, (str, int, float, bool)):
                    raise ValueError('셀에는 문자열·숫자·불리언·null만 사용할 수 있습니다.')
                if isinstance(val, float) and not math.isfinite(val):
                    raise ValueError('NaN과 무한대는 셀 값으로 사용할 수 없습니다.')
                if isinstance(val, str) and len(val) > 100000:
                    raise ValueError('셀 문자열이 너무 깁니다.')
        if not isinstance(table.get('source'), dict):
            raise ValueError('테이블 출처가 필요합니다.')
    if sum(len(t['rows']) * len(t['columns']) for t in project['tables']) > 1_000_000:
        raise ValueError('작업 전체는 최대 1,000,000개 셀까지 지원합니다.')
    ids = set()
    for rule in project['rules']:
        if not isinstance(rule, dict):
            raise ValueError('규칙 형식 오류')
        for key in ['id', 'text', 'table', 'column', 'kind', 'status']:
            _text(rule.get(key), f'규칙 {key}')
        if not rule['id'] or rule['id'] in ids:
            raise ValueError('규칙 ID는 비어 있지 않고 고유해야 합니다.')
        ids.add(rule['id'])
        if rule['status'] not in {'draft', 'confirmed'}:
            raise ValueError('규칙 상태는 draft 또는 confirmed입니다.')
        if not isinstance(rule.get('params'), dict) or not isinstance(rule.get('source'), dict):
            raise ValueError('규칙 params와 source 객체가 필요합니다.')
        params = rule['params']
        if 'llm' in rule:
            metadata = rule['llm']
            fields = {'model', 'request_id', 'rationale', 'questions', 'source_verified'}
            if not isinstance(metadata, dict) or set(metadata) != fields:
                raise ValueError('LLM 출처 메타데이터 형식 오류')
            for field in ['model', 'request_id', 'rationale']:
                _text(metadata[field], 'LLM ' + field)
            if not isinstance(metadata['questions'], list) or any(not isinstance(q, str) for q in metadata['questions']):
                raise ValueError('LLM 확인 사항은 문자열 목록이어야 합니다.')
            if type(metadata['source_verified']) is not bool:
                raise ValueError('LLM 인용 확인 상태는 불리언이어야 합니다.')
        if rule['kind'] == 'allowed' and 'values' in params:
            if not isinstance(params['values'], list) or len(params['values']) > 1000 or any(not isinstance(v, str) for v in params['values']):
                raise ValueError('허용값 params.values는 문자열 목록이어야 합니다.')
        if rule['kind'] == 'range':
            for bound in ['min', 'max']:
                if params.get(bound) is not None:
                    _number(params[bound])
        for key in ['other_column', 'target_table', 'target_column']:
            if key in params and not isinstance(params[key], str):
                raise ValueError(f'규칙 params.{key}는 문자열이어야 합니다.')
    for doc in project['documents']:
        if not isinstance(doc, dict):
            raise ValueError('문서 형식 오류')
        _text(doc.get('name'), '문서 이름', 500)
        if not isinstance(doc.get('segments'), list) or len(doc['segments']) > 2000:
            raise ValueError('문서는 최대 2,000개 구간까지 지원합니다.')
        for segment in doc['segments']:
            if not isinstance(segment, dict):
                raise ValueError('문서 구간 형식 오류')
            _text(segment.get('text'), '문서 텍스트', 200000)
    # Also reject nested non-JSON values, NaN and excessive imported workspaces.
    try:
        size = len(json.dumps(project, ensure_ascii=False, allow_nan=False).encode())
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError('올바른 JSON 작업 파일이 아닙니다.') from exc
    if size > 20 * 1024 * 1024:
        raise ValueError('작업 파일은 최대 20MB입니다.')
    return project


def fingerprint(project):
    validate_project(project)
    return hashlib.sha256(json.dumps(project, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _uri(*parts):
    return URIRef(BASE + ':'.join(quote(str(p), safe='') for p in parts))


def _missing(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _number(value):
    if isinstance(value, bool):
        raise ValueError('불리언은 숫자가 아닙니다.')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('숫자 형식을 확인하세요.') from None
    if not result.is_finite():
        raise ValueError('유한한 숫자가 필요합니다.')
    return result


def _date(value):
    if isinstance(value, str) and value.endswith('T00:00:00') and len(value) == 19:
        value = value[:10]  # Excel date cells arrive as midnight datetimes.
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError('날짜는 YYYY-MM-DD 형식이어야 합니다.')
    return date.fromisoformat(value)


def _configuration(rule, tables):
    if rule['status'] != 'confirmed':
        return '검토 전 규칙입니다. 연결과 조건을 확인한 뒤 확정하세요.'
    if rule['kind'] not in KINDS:
        return '이 규칙 종류는 아직 실행을 지원하지 않습니다.'
    table = tables.get(rule['table'])
    if table is None or rule['column'] not in table['columns']:
        return '데이터 테이블 또는 열 연결이 필요합니다.'
    p = rule['params']
    try:
        if rule['kind'] == 'range':
            low, high = p.get('min'), p.get('max')
            if low is None and high is None:
                return '숫자 범위의 하한 또는 상한이 필요합니다.'
            if low is not None: _number(low)
            if high is not None: _number(high)
            if low is not None and high is not None and _number(low) > _number(high):
                return '하한이 상한보다 큽니다.'
        if rule['kind'] == 'allowed':
            vals = p.get('values')
            if not isinstance(vals, list) or not vals or len(vals) > 1000 or any(not isinstance(v, str) for v in vals):
                return '허용값은 1~1,000개 문자열 목록이어야 합니다.'
        if rule['kind'] == 'date_order' and p.get('other_column') not in table['columns']:
            return '비교할 날짜 열을 연결하세요.'
        if rule['kind'] == 'reference':
            target = tables.get(p.get('target_table'))
            if target is None or p.get('target_column') not in target['columns']:
                return '참조 테이블과 열을 연결하세요.'
    except (ValueError, TypeError):
        return '규칙 매개변수 형식을 확인하세요.'
    return None


def run_checks(project):
    validate_project(project)
    tables = {t['id']: t for t in project['tables']}
    projected_checks = sum(max(1, len(tables.get(r['table'], {}).get('rows', []))) for r in project['rules'])
    if projected_checks > 20000:
        raise ValueError('한 번에 최대 20,000개 규칙×행 검사까지 지원합니다. 표 또는 규칙을 나누세요.')
    all_data, all_shapes = Graph(), Graph()
    for g in (all_data, all_shapes):
        g.bind('sh', SH); g.bind('xsd', XSD); g.bind('wb', Namespace(BASE))
    results = []
    for rule in project['rules']:
        table = tables.get(rule['table'])
        error = _configuration(rule, tables)
        def record(row, status, message):
            results.append({'rule_id': rule['id'], 'rule_text': rule['text'], 'table': rule['table'], 'row': row,
                            'status': status, 'message': message,
                            'source': copy.deepcopy(table['source']) if table else {},
                            'rule_source': copy.deepcopy(rule['source'])})
        if error:
            record(None, 'unknown', error); continue
        if table['source'].get('data_omitted') and not table['rows']:
            record(None, 'unknown', '원본 행이 제외된 작업 파일입니다. 데이터를 다시 연결하세요.'); continue
        if not table['rows']:
            record(None, 'not_applicable', '검사할 행이 없습니다. 통과로 계산하지 않습니다.'); continue
        data, shapes = Graph(), Graph()
        shape, prop, value_path, other_path = (_uri('rule', rule['id'], suffix) for suffix in ['shape', 'property', 'value', 'other'])
        shapes.add((shape, RDF.type, SH.NodeShape)); shapes.add((shape, SH.property, prop))
        shapes.add((prop, SH.path, value_path)); shapes.add((prop, SH.message, Literal(rule['text'])))
        p, kind = rule['params'], rule['kind']
        allowed = None
        if kind == 'required':
            shapes.add((prop, SH.minCount, Literal(1)))
        elif kind == 'range':
            shapes.add((prop, SH.datatype, XSD.decimal))
            for key, pred in [('min', SH.minInclusive), ('max', SH.maxInclusive)]:
                if p.get(key) is not None: shapes.add((prop, pred, Literal(_number(p[key]), datatype=XSD.decimal)))
        elif kind == 'date_order':
            shapes.add((prop, SH.datatype, XSD.date)); shapes.add((prop, SH.lessThanOrEquals, other_path))
        else:
            if kind == 'allowed':
                allowed = set(p['values'])
            else:
                target = tables[p['target_table']]
                allowed = {str(r.get(p['target_column'])) for r in target['rows'] if not _missing(r.get(p['target_column']))}
            if kind == 'reference':
                ref_class = _uri('rule', rule['id'], 'referenceClass')
                shapes.add((prop, SH['class'], ref_class))
                for entry in allowed:
                    entry_node = _uri('referenceValue', hashlib.sha256(entry.encode()).hexdigest())
                    data.add((entry_node, RDF.type, ref_class))
                    data.add((entry_node, _uri('value'), Literal(entry)))
            else:
                head = BNode() if allowed else RDF.nil
                if allowed: Collection(shapes, head, [Literal(v) for v in sorted(allowed)])
                shapes.add((prop, SH['in'], head))
        eligible = {}
        for number, row in enumerate(table['rows'], 1):
            value = row.get(rule['column']); node = _uri('table', table['id'], 'row', number)
            if kind != 'required' and _missing(value):
                record(number, 'unknown', '검사에 필요한 값이 없습니다.'); continue
            if kind == 'reference' and str(value) not in allowed and (target['source'].get('truncated') or target['source'].get('data_omitted')):
                record(number, 'unknown', '참조 데이터가 일부만 있어 값의 부재를 확정할 수 없습니다.'); continue
            try:
                if kind == 'range': literal = Literal(_number(value), datatype=XSD.decimal)
                elif kind == 'date_order':
                    literal = Literal(_date(value), datatype=XSD.date)
                    other = row.get(p['other_column'])
                    if _missing(other): raise ValueError('비교 날짜가 없습니다.')
                    data.add((node, other_path, Literal(_date(other), datatype=XSD.date)))
                elif kind == 'reference':
                    literal = _uri('referenceValue', hashlib.sha256(str(value).encode()).hexdigest())
                else: literal = Literal(str(value))
            except (ValueError, TypeError):
                record(number, 'unknown', '숫자 또는 날짜 형식이 맞지 않거나 비교 값이 없습니다.'); continue
            if not _missing(value): data.add((node, value_path, literal))
            data.add((node, _uri('sourceRow'), Literal(number)))
            shapes.add((shape, SH.targetNode, node)); eligible[node] = number
        if not eligible:
            continue
        try:
            _, report, _ = validate(data_graph=data, shacl_graph=shapes, meta_shacl=True, inference='none', do_owl_imports=False)
            if not isinstance(report, Graph): raise ValueError('검증기가 보고서를 반환하지 않았습니다.')
            violations = {}
            for result in report.subjects(RDF.type, SH.ValidationResult):
                node = report.value(result, SH.focusNode)
                component = report.value(result, SH.sourceConstraintComponent)
                violations.setdefault(node, []).append(str(component).rsplit('#', 1)[-1])
            for node, number in eligible.items():
                if node in violations:
                    record(number, 'violation', '조건 위반: ' + ', '.join(sorted(set(violations[node]))))
                else:
                    record(number, 'pass', '확인한 조건을 충족합니다. 업무 승인 판정은 아닙니다.')
            all_data += data; all_shapes += shapes
        except Exception:
            for number in eligible.values(): record(number, 'unknown', '검사 실행에 실패했습니다. 통과로 처리하지 않습니다.')
    counts = {key: 0 for key in ['pass', 'violation', 'unknown', 'not_applicable']}
    counts.update(Counter(r['status'] for r in results))
    return {'fingerprint': fingerprint(project), 'created_at': datetime.now(timezone.utc).isoformat(), 'engine': 'pySHACL',
            'results': results, 'counts': counts, 'data_ttl': all_data.serialize(format='turtle'),
            'shapes_ttl': all_shapes.serialize(format='turtle'),
            'scope': 'Snapshot checks only. Shapes target eligible snapshot rows; missing or invalid values are reported separately as unknown. No business approval or full-source completeness claim.'}


def demo_project():
    p = new_project('공급업체 규칙 검토 예제')
    p['tables'] = [
        {'id': 'suppliers', 'name': '공급업체', 'columns': ['업체코드', '납품일', '인증만료일', '금액'],
         'rows': [{'업체코드': 'A01', '납품일': '2026-10-17', '인증만료일': '2026-12-31', '금액': '100'},
                  {'업체코드': 'A02', '납품일': '2026-10-17', '인증만료일': '2026-10-16', '금액': '200'},
                  {'업체코드': 'A03', '납품일': '2026-10-17', '인증만료일': None, '금액': '300'},
                  {'업체코드': None, '납품일': '2026-10-17', '인증만료일': '2026-10-17', '금액': '400'}],
         'source': {'kind': 'demo', 'file': '공급업체.csv', 'truncated': False}},
        {'id': 'registry', 'name': '등록업체', 'columns': ['업체코드'], 'rows': [{'업체코드': 'A01'}, {'업체코드': 'A02'}],
         'source': {'kind': 'demo', 'file': '등록업체.csv', 'truncated': False}}]
    texts = ['업체코드는 필수입니다.', '납품일은 인증만료일 이하여야 합니다. 만료일 당일도 유효합니다.', '업체코드는 등록업체 목록에 있어야 합니다.']
    p['documents'] = [{'name': '구매지침.md', 'segments': [{'text': t, 'line': i} for i, t in enumerate(texts, 1)]}]
    p['rules'] = [{'id': 'rule-' + str(i), 'text': t, 'source': {'file': '구매지침.md', 'line': i, 'quote': t},
                   'status': 'confirmed', 'table': 'suppliers', 'column': '납품일' if i == 2 else '업체코드',
                   'kind': ['required', 'date_order', 'reference'][i-1],
                   'params': {} if i == 1 else {'other_column': '인증만료일'} if i == 2 else {'target_table': 'registry', 'target_column': '업체코드'}}
                  for i, t in enumerate(texts, 1)]
    return p
