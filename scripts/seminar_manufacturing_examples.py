"""Tiny executed teaching examples of inference and validation, not a research benchmark."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from importlib.metadata import version
from pathlib import Path
from rdflib import Graph, Namespace, RDF
from owlrl import DeductiveClosure, RDFS_Semantics, OWLRL_Semantics
from pyshacl import validate

EX = Namespace('https://example.org/manufacturing/')
SH = Namespace('http://www.w3.org/ns/shacl#')
PREFIX = '''@prefix ex: <https://example.org/manufacturing/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
'''
# region manufacturing_data
DATA = '''ex:P1 a ex:Bolt ;
    ex:installedIn ex:A1 .'''
# endregion manufacturing_data
# region manufacturing_schema
SCHEMA = '''ex:Bolt rdfs:subClassOf ex:Fastener .
ex:Fastener rdfs:subClassOf ex:Component .
ex:installedIn rdfs:domain ex:Component ; rdfs:range ex:Assembly ;
    owl:inverseOf ex:hasPart .'''
# endregion manufacturing_schema
# region manufacturer_shape
MANUFACTURER_SHAPE = '''ex:ManufacturerShape a sh:NodeShape ;
    # 이 검사는 P1의 제조사 기록만 확인한다.
    sh:targetNode ex:P1 ;
    sh:property [
        sh:path ex:manufacturer ;
        # 값이 하나 이상이고 IRI인지 검사한다.
        sh:minCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:message "제조사 식별자를 하나 이상 기록하세요."
    ] .'''
# endregion manufacturer_shape
# region type_shape
TYPE_SHAPE = '''ex:ExplicitTypeShape a sh:NodeShape ;
    sh:targetNode ex:P1 ;
    sh:property [
        sh:path rdf:type ;
        sh:hasValue ex:Component
    ] .'''
# endregion type_shape

# region expand
def expand_copy(original, mode):
    # 원본을 보존하고 복사본에만 함의된 트리플을 추가한다.
    expanded = Graph()
    for triple in original:
        expanded.add(triple)
    semantics = {'rdfs': RDFS_Semantics, 'owlrl': OWLRL_Semantics}
    # RDFS는 상하위 타입·domain/range, OWL-RL은 역관계도 확장한다.
    if mode != 'original':
        DeductiveClosure(semantics[mode]).expand(expanded)
    return expanded
# endregion expand

# region sensor_validate
def check(graph, shape_text):
    shapes = Graph().parse(data=PREFIX + shape_text, format='turtle')
    # 추론은 여기서 실행하지 않는다. 선택한 그래프를 Shape와 대조한다.
    conforms, report, text = validate(
        graph, shacl_graph=shapes, inference='none')
    # 적합 여부, RDF 보고서, 사람이 읽는 보고서를 함께 반환한다.
    return bool(conforms), report, text
# endregion sensor_validate

def summary_report(report):
    return sorted([{
        'focus': str(report.value(r, SH.focusNode)),
        'path': str(report.value(r, SH.resultPath)),
        'component': str(report.value(r, SH.sourceConstraintComponent)).split('#')[-1],
    } for r in report.subjects(RDF.type, SH.ValidationResult)], key=lambda r: (r['path'], r['component']))


def save_validation_return(output, graph, conforms, report, report_text):
    """Capture all three actual pySHACL return values for the slide."""
    report_turtle = report.serialize(format='turtle')
    (output/'validation-return.txt').write_text(report_text)
    (output/'validation-return.ttl').write_text(report_turtle)
    captured = {
        'case': 'missing', 'inference': 'none', 'conforms': conforms,
        'data_file': 'case-missing.ttl', 'shape_file': 'manufacturer-shape.ttl',
        'data_triples': sorted([[str(term) for term in triple] for triple in graph]),
        'report_rdf_turtle': report_turtle, 'report_text': report_text,
        'violations': summary_report(report),
        'interpretation': 'Selected graph failed the declared constraint; external truth is not verified.',
    }
    (output/'validation-return.json').write_text(json.dumps(captured, ensure_ascii=False, indent=2))
    # 화면의 보고서도 저장된 실제 반환값에서 만든다.
    excerpt = '\n'.join(line for line in report_text.splitlines()
                        if line.startswith(('Validation Report', 'Conforms:', 'Results (',
                                            '\tFocus Node:', '\tResult Path:', '\tMessage:')))
    view = f'''<div class="validation-capture">
  <div class="validation-capture-header"><span>pySHACL · 실제 실행 반환값</span><code>missing manufacturer</code></div>
  <div class="validation-return-grid">
    <section><h3>① conforms</h3><p class="validation-false">{str(conforms).lower()}</p><p>선택한 그래프가 제조사 필수 기록 조건을 충족하지 못했다.</p><p>현실에서 제조사가 없거나 사실이 거짓이라는 판정은 아니다.</p></section>
    <section><h3>② report · RDF 그래프</h3><dl><dt>focusNode</dt><dd>ex:P1</dd><dt>resultPath</dt><dd>ex:manufacturer</dd><dt>constraint</dt><dd>sh:MinCountConstraintComponent</dd></dl><p>sh:minCount 1 · 제조사 값이 최소 하나 필요하다.</p></section>
  </div>
  <section class="validation-terminal"><h3>③ text · 실제 보고서 발췌</h3><pre><code>{html.escape(excerpt)}</code></pre></section>
  <details><summary>전체 text 반환값</summary><pre><code>{html.escape(report_text)}</code></pre></details>
  <details><summary>전체 RDF 보고서 · Turtle</summary><pre><code>{html.escape(report_turtle)}</code></pre></details>
  <p class="validation-source">출처: scripts/seminar_manufacturing_examples.py → manufacturing/validation-return.json · inference='none'</p>
</div>
<style>
.validation-capture{{border:1px solid #536579;border-radius:16px;overflow:hidden;background:#f7fafc;color:#172b3a}}
.validation-capture-header{{display:flex;justify-content:space-between;gap:12px;padding:14px 20px;background:#203446;color:#f5f8fc;font-size:.8em}}
.validation-return-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:18px 22px}}
.validation-capture h3{{margin:0 0 8px;font-size:.9em;color:inherit}}
.validation-capture p{{font-size:.72em;line-height:1.55;margin:8px 0}}
.validation-capture .validation-false{{font:700 1.7em monospace;color:#a72e36;margin:8px 0}}
.validation-capture dl{{display:grid;grid-template-columns:auto 1fr;gap:6px 12px;font-size:.65em;margin:12px 0}}
.validation-capture dd{{margin:0;overflow-wrap:anywhere;font-family:monospace}}
.validation-terminal{{background:#112230;color:#e5edf5;padding:16px 22px}}
.validation-capture pre{{margin:6px 0;background:transparent!important;color:inherit!important;font-size:.64em;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.5;box-shadow:none!important;border:0!important}}
.validation-capture pre code{{color:inherit!important;background:transparent!important}}
.validation-capture details{{padding:8px 22px;font-size:.8em}}
.validation-capture .validation-source{{padding:0 22px 10px;font-size:.55em;color:#46576b;overflow-wrap:anywhere}}
@media(max-width:640px){{.validation-return-grid{{grid-template-columns:1fr}}.validation-capture-header{{flex-direction:column}}}}
</style>'''
    views = output.parent/'views'
    views.mkdir(parents=True, exist_ok=True)
    (views/'validation_return.html').write_text(view)


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    original = Graph().parse(data=PREFIX + DATA + '\n' + SCHEMA, format='turtle')
    before = set(original)
    records = []
    for mode in ['original', 'rdfs', 'owlrl']:
        graph = expand_copy(original, mode)
        conforms, report, text = check(graph, MANUFACTURER_SHAPE + '\n' + TYPE_SHAPE)
        records.append({'mode': mode, 'P1_is_Component': (EX.P1, RDF.type, EX.Component) in graph,
                        'A1_is_Assembly': (EX.A1, RDF.type, EX.Assembly) in graph,
                        'A1_hasPart_P1': (EX.A1, EX.hasPart, EX.P1) in graph,
                        'manufacturer_recorded': bool(list(graph.objects(EX.P1, EX.manufacturer))),
                        'conforms_two_shapes': conforms, 'violations': summary_report(report)})
        graph.serialize(destination=output/f'{mode}.ttl', format='turtle')
        report.serialize(destination=output/f'{mode}-validation.ttl', format='turtle')
    assert set(original) == before
    assert [r['P1_is_Component'] for r in records] == [False, True, True]
    assert [r['A1_is_Assembly'] for r in records] == [False, True, True]
    assert [r['A1_hasPart_P1'] for r in records] == [False, False, True]
    assert [len(r['violations']) for r in records] == [2, 1, 1]
    cases=[]
    additions = {'valid': 'ex:P1 ex:manufacturer ex:MakerA .', 'missing': '',
                 'literal': 'ex:P1 ex:manufacturer "MakerA" .',
                 'unverified_iri': 'ex:P1 ex:manufacturer ex:UnverifiedMaker .'}
    for name, extra in additions.items():
        graph = Graph().parse(data=PREFIX + DATA + '\n' + extra, format='turtle')
        conforms, report, text = check(graph, MANUFACTURER_SHAPE)
        if name == 'missing':
            save_validation_return(output, graph, conforms, report, text)
        cases.append({'case': name, 'added_fact': extra or '(제조사 기록 없음)', 'conforms': conforms,
                      'violations': summary_report(report), 'real_world_truth': 'not_verified'})
        graph.serialize(destination=output/f'case-{name}.ttl', format='turtle')
        report.serialize(destination=output/f'case-{name}-report.ttl', format='turtle')
    assert [c['conforms'] for c in cases] == [True, False, False, True]
    # Positive Datalog-style reachability: finite set closure, not path enumeration.
    # region reachability
    edges = {('P1', 'A1'), ('A1', 'PRODUCT_X')}
    reachable = set(edges)
    while True:
        additions = {(x, z) for x, y in reachable
                     for y2, z in edges if y == y2}
        updated = reachable | additions
        if updated == reachable:
            break
        reachable = updated
    # endregion reachability
    assert reachable == {('P1', 'A1'), ('A1', 'PRODUCT_X'), ('P1', 'PRODUCT_X')}
    (output/'manufacturing-data.ttl').write_text(PREFIX + DATA)
    (output/'manufacturing-schema.ttl').write_text(PREFIX + SCHEMA)
    (output/'manufacturer-shape.ttl').write_text(PREFIX + MANUFACTURER_SHAPE)
    (output/'explicit-type-shape.ttl').write_text(PREFIX + TYPE_SHAPE)
    result={'purpose':'tiny executed teaching examples, not benchmark or external truth validation',
            'versions':{p:version(p) for p in ['rdflib','owlrl','pyshacl']},
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'llm_calls':0, 'original_graph_unchanged':True, 'queries':records, 'shape_cases':cases,
            'reachability':sorted([list(x) for x in reachable])}
    (output/'manufacturing.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('docs/experiments/seminar/manufacturing'))
    build(p.parse_args().output)
