"""Build four consumed synthetic development examples, never call a model API.

This script is a demo builder, not the future independent experimental scorer.
Python uses visible rows only; OWL-RL checks reachability parity, while SHACL
checks explicit certificate field conditions. Source rows are UI-only context.
"""
from __future__ import annotations

import copy
import hashlib
import json
from importlib.metadata import version
from collections import deque
from datetime import date
from pathlib import Path

from owlrl import DeductiveClosure, OWLRL_Semantics
from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, OWL, XSD

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/experiments/evidence-report-demo'
SPEC = ROOT / 'research/evidence-report-1'
EX = Namespace('https://example.org/evidence-report/')
POLICY = {
    'id': 'R-CERT-1', 'version': '1',
    'text': '만료일 당일까지 인증은 유효합니다. 인증이 유효하면 이 인증으로 인한 제품 재검토는 불필요합니다. '
            '만료된 인증의 대상 부품에서 질문 제품까지 partOf 경로가 있으면 재검토가 필요합니다. '
            '판정에 필요한 인증 정보나 관계 근거가 부족하면 unknown입니다. '
            '재검토는 안전성이나 출하 승인 판정이 아닙니다.',
}
SHAPES = '''@prefix ex: <https://example.org/evidence-report/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:CertificateShape a sh:NodeShape; sh:targetClass ex:Certificate;
 sh:property [ sh:path ex:certifies; sh:minCount 1; sh:maxCount 1; sh:nodeKind sh:IRI ];
 sh:property [ sh:path ex:expiresOn; sh:minCount 1; sh:maxCount 1; sh:datatype xsd:date ].
'''
INSTRUCTION = '''주어진 자료와 R-CERT-1만 사용해 질문에 답하세요. 제공되지 않은 원천의 사실은 추측하지 마세요.
JSON 객체로 decision(required/not_required/unknown), rule_id, support_row_ids 배열,
missing 배열, explanation(한국어)을 반환하세요. 인용은 제공된 행 ID만 사용하세요.
'''


def fixtures():
    cert = {'row_id': 'r-cert', 'kind': 'certificate', 'id': 'CERT-Q',
            'part': 'PART-Q', 'expires_on': '2026-10-01'}
    edges = [
        {'row_id': 'r-bom-1', 'kind': 'relation', 'subject': 'PART-Q', 'predicate': 'partOf', 'object': 'ASM-Q'},
        {'row_id': 'r-bom-2', 'kind': 'relation', 'subject': 'ASM-Q', 'predicate': 'partOf', 'object': 'PROD-Q'},
        {'row_id': 'r-noise', 'kind': 'relation', 'subject': 'PART-Z', 'predicate': 'partOf', 'object': 'PROD-Z'},
    ]
    nodes = {'PART-Q': 'Part', 'ASM-Q': 'Assembly', 'PROD-Q': 'Product', 'PART-Z': 'Part', 'PROD-Z': 'Product'}
    base = {'question': '2026-10-27 현재 CERT-Q의 상태 때문에 PROD-Q를 재검토해야 하며 근거는 무엇인가요?',
            'certificate_id': 'CERT-Q', 'product_id': 'PROD-Q', 'as_of': '2026-10-27',
            'nodes': nodes, 'policy': POLICY,
            'scope': '제공된 기록만 판단 근거로 사용합니다. 관계의 완전성은 보장하지 않습니다.',
            'rows': [cert] + edges}
    result = []
    labels = [('expired_connected', '만료 인증 · 연결 확인'), ('valid_connected', '유효 인증 · 재검토 불필요'),
              ('retrieval_omission', '검색에서 빠진 관계'), ('source_absence', '원천에도 없는 관계')]
    for key, label in labels:
        visible = copy.deepcopy(base)
        if key == 'valid_connected':
            visible['rows'][0]['expires_on'] = '2026-12-31'
        source = copy.deepcopy(visible['rows'])
        if key in {'retrieval_omission', 'source_absence'}:
            visible['rows'] = [r for r in visible['rows'] if r['row_id'] != 'r-bom-2']
        if key == 'source_absence':
            source = copy.deepcopy(visible['rows'])
        result.append({'id': key, 'label': label, 'visible': visible, 'source_rows': source})
    return result


def find_path(rows, start, target):
    """Return one shortest visible partOf witness; never inspect full source."""
    queue = deque([(start, [])]); seen = {start}
    while queue:
        node, path = queue.popleft()
        if node == target:
            return path
        for row in rows:
            if row.get('predicate') == 'partOf' and row.get('subject') == node:
                nxt = row['object']
                if nxt not in seen:
                    seen.add(nxt); queue.append((nxt, path + [row['row_id']]))
    return None


def compute(visible):
    rows = visible['rows']
    certs = [r for r in rows if r.get('kind') == 'certificate' and r.get('id') == visible['certificate_id']]
    graph = Graph(); graph.bind('ex', EX)
    graph.add((EX.partOf, RDF.type, OWL.TransitiveProperty))
    for key, kind in visible['nodes'].items():
        graph.add((EX[key], RDF.type, EX[kind]))
    for row in rows:
        if row.get('kind') == 'certificate':
            graph.add((EX[row['id']], RDF.type, EX.Certificate))
            if row.get('part'):
                graph.add((EX[row['id']], EX.certifies, EX[row['part']]))
            if row.get('expires_on'):
                graph.add((EX[row['id']], EX.expiresOn, Literal(row['expires_on'], datatype=XSD.date)))
        elif row.get('predicate') == 'partOf':
            graph.add((EX[row['subject']], EX.partOf, EX[row['object']]))
    conforms, _, report_text = validate(graph, shacl_graph=Graph().parse(data=SHAPES, format='turtle'), inference='none')
    derived = Graph()
    for triple in graph:
        derived.add(triple)
    DeductiveClosure(OWLRL_Semantics).expand(derived)
    report = {'decision': 'unknown', 'rule_id': POLICY['id'], 'support_row_ids': [], 'path_row_ids': [],
              'missing': [], 'reason': '', 'validation': {'conforms': bool(conforms), 'text': report_text},
              'derivation': {'python_reachable': None, 'owlrl_reachable': None}}
    if len(certs) != 1 or not conforms:
        report['missing'] = ['하나의 유효한 인증서 행과 대상 부품·만료일']
        report['reason'] = '인증서 입력 조건을 확인할 수 없습니다.'
        return report
    cert = certs[0]
    expiry = date.fromisoformat(cert['expires_on']); as_of = date.fromisoformat(visible['as_of'])
    path = find_path(rows, cert['part'], visible['product_id'])
    # Non-reflexive source/target in the bounded schema. This is not a general OWL proof checker.
    python_reachable = path is not None
    owl_reachable = (EX[cert['part']], EX.partOf, EX[visible['product_id']]) in derived
    if python_reachable != owl_reachable:
        raise AssertionError('Visible graph reachability mismatch')
    report['derivation'] = {'python_reachable': python_reachable, 'owlrl_reachable': owl_reachable}
    report['support_row_ids'] = [cert['row_id']]
    if expiry >= as_of:
        report['decision'] = 'not_required'
        report['reason'] = '인증이 기준일에 유효하므로 이 인증으로 인한 재검토는 불필요합니다.'
    elif path is not None:
        report['decision'] = 'required'; report['path_row_ids'] = path
        report['support_row_ids'] += path
        report['reason'] = '만료된 인증의 대상 부품에서 질문 제품까지 연결 경로가 확인됩니다.'
    else:
        report['missing'] = ['인증 대상 부품에서 질문 제품까지의 완전한 partOf 경로']
        report['reason'] = '제공된 관계로는 제품까지의 연결을 확인할 수 없습니다. 누락 원인은 이 자료만으로 구별하지 못합니다.'
    return report


def prompt(visible, report, arm):
    payload = copy.deepcopy(visible)
    if arm in {'B', 'C'}:
        payload['computed_decision'] = report['decision']
    if arm == 'C':
        payload['computed_evidence'] = {k: report[k] for k in ['rule_id', 'support_row_ids', 'path_row_ids', 'missing', 'reason']}
    return INSTRUCTION + json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def build():
    cases = fixtures()
    for case in cases:
        case['report'] = compute(case['visible'])
        case['prompts'] = {arm: prompt(case['visible'], case['report'], arm) for arm in 'ABC'}
        case['model_output'] = None
    # Authored development expectations; never used to construct runtime reports.
    assert [c['report']['decision'] for c in cases] == ['required', 'not_required', 'unknown', 'unknown']
    assert cases[2]['visible'] == cases[3]['visible']
    assert cases[2]['report'] == cases[3]['report']
    assert cases[2]['prompts'] == cases[3]['prompts']
    assert cases[2]['source_rows'] != cases[3]['source_rows']
    for case in cases:
        assert set(case['report']['support_row_ids']) <= {r['row_id'] for r in case['visible']['rows']}
    boundary = copy.deepcopy(cases[0]['visible']); boundary['rows'][0]['expires_on'] = boundary['as_of']
    assert compute(boundary)['decision'] == 'not_required'
    missing = copy.deepcopy(cases[0]['visible']); del missing['rows'][0]['expires_on']
    assert compute(missing)['decision'] == 'unknown'
    duplicate = copy.deepcopy(cases[0]['visible']); duplicate['rows'].append(copy.deepcopy(duplicate['rows'][0]))
    assert compute(duplicate)['decision'] == 'unknown'
    graph = copy.deepcopy(cases[0]['visible']); graph['rows'][2]['predicate'] = 'storedAt'
    assert compute(graph)['decision'] == 'unknown'
    font_path = ROOT/'docs/experiments/seminar/Pretendard-Regular.woff2'
    font_bytes = font_path.read_bytes()
    template_bytes = (SPEC/'demo-template.html').read_bytes()
    record = {'study': 'evidence-report-1', 'status': 'consumed_demo_only_no_model_calls',
              'synthetic': True, 'cases': cases, 'paid_calls': 0,
              'checks': ['four decisions', 'observationally identical missing states', 'visible citations',
                         'expiry boundary', 'missing expiry', 'duplicate certificate rows', 'wrong relation role'],
              'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'protocol_sha256': hashlib.sha256((SPEC/'protocol.json').read_bytes()).hexdigest(),
              'template_sha256': hashlib.sha256(template_bytes).hexdigest(),
              'font_sha256': hashlib.sha256(font_bytes).hexdigest(),
              'dependencies': {name: version(name) for name in ['rdflib', 'pyshacl', 'owlrl']}}
    OUT.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(record, ensure_ascii=False, indent=2)
    (OUT/'demo.json').write_text(raw+'\n')
    (OUT/'shapes.ttl').write_text(SHAPES)
    template = template_bytes.decode()
    # Inline JSON is data, never HTML. Escape script terminators and HTML delimiters.
    page = template.replace('__DEMO_JSON__', raw.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e'))
    import base64
    page = page.replace('__FONT_SRC__', 'url(data:font/woff2;base64,'+base64.b64encode(font_bytes).decode()+')')
    (OUT/'index.html').write_text(page)
    print(json.dumps({'cases': len(cases), 'checks': len(record['checks']), 'model_calls': 0, 'html': str(OUT/'index.html')}, ensure_ascii=False))


if __name__ == '__main__':
    build()
