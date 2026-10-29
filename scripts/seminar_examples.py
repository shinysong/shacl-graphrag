"""Small offline teaching examples; not a new benchmark or LLM experiment."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from importlib.metadata import version
from rdflib import Graph, Namespace, Literal, RDF
from rdflib.namespace import XSD
from pyshacl import validate
from unified_rule_lifecycle import (
    make_valid_base_tables, generic_tables_to_rdf,
    build_shacl_shapes_for_round, evaluate_arm_p_python,
    evaluate_arm_s_sqlite, evaluate_arm_g_shacl,
    extract_shacl_llm_report, build_llm_prompt_modes,
)

# region shape
SHAPE = '''@prefix ex: <https://example.org/seminar/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:OrderShape a sh:NodeShape ;
    sh:targetClass ex:Order ;
    sh:property [
        sh:path ex:discount ;
        sh:minCount 1 ; sh:maxCount 1 ;
        sh:datatype xsd:decimal ;
        sh:maxInclusive 0.15
    ] .'''
# endregion shape

# region mapping
def order_graph(discount):
    ex = Namespace('https://example.org/seminar/')
    graph = Graph()
    graph.bind('ex', ex)
    graph.add((ex.order1, RDF.type, ex.Order))
    if discount is not None:
        graph.add((ex.order1, ex.discount,
                   Literal(discount, datatype=XSD.decimal)))
    return graph
# endregion mapping

# region validate
def check_discount(discount):
    data = order_graph(discount)
    shapes = Graph().parse(data=SHAPE, format='turtle')
    conforms, report, text = validate(data, shacl_graph=shapes)
    return conforms, report, text
# endregion validate


def build(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    sh = Namespace('http://www.w3.org/ns/shacl#')
    cases = []
    for name, value in [('within_limit', '0.12'), ('over_limit', '0.20'), ('missing', None)]:
        conforms, report, report_text = check_discount(value)
        findings = []
        for result in report.subjects(RDF.type, sh.ValidationResult):
            findings.append({
                'focusNode': str(report.value(result, sh.focusNode)),
                'resultPath': str(report.value(result, sh.resultPath)),
                'value': str(report.value(result, sh.value)) if report.value(result, sh.value) is not None else None,
                'constraint': str(report.value(result, sh.sourceConstraintComponent)).split('#')[-1],
            })
        cases.append({'case': name, 'input': {'discount': value}, 'conforms': bool(conforms), 'results': findings})
        (output / f'{name}.ttl').write_text(order_graph(value).serialize(format='turtle'))
        (output / f'{name}-report.ttl').write_text(report.serialize(format='turtle'))
        (output / f'{name}-report.txt').write_text(report_text)
    (output / 'shape.ttl').write_text(SHAPE)
    # region project
    tables = make_valid_base_tables(rev1_div='DIV_SALES')
    decisions = {
        'Python': evaluate_arm_p_python(tables, 'R3'),
        'SQLite': evaluate_arm_s_sqlite(tables, 'R3'),
        'SHACL': evaluate_arm_g_shacl(tables, 'R3'),
    }
    report = extract_shacl_llm_report(tables, 'R3')
    prompts = build_llm_prompt_modes(tables, round_id='R3')
    # endregion project
    assert decisions['Python'] == decisions['SQLite'] == decisions['SHACL']
    assert decisions['Python']['decision'] == 'blocked'
    assert [c['conforms'] for c in cases] == [True, False, False]
    (output / 'project-input.json').write_text(json.dumps(tables, ensure_ascii=False, indent=2))
    (output / 'project-data.ttl').write_text(generic_tables_to_rdf(tables).serialize(format='turtle'))
    (output / 'project-shapes.ttl').write_text(build_shacl_shapes_for_round('R3').serialize(format='turtle'))
    (output / 'project-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    for key, value in prompts.items():
        (output / f'{key}.txt').write_text(value)
    source_files = [Path(__file__), Path(__file__).with_name('unified_rule_lifecycle.py')]
    summary = {'purpose': 'executed teaching examples; not benchmark evidence', 'paid_calls': 0, 'llm_calls': 0,
               'versions': {p: version(p) for p in ['rdflib', 'pyshacl']},
               'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},
               'mini_cases': cases, 'project_decisions': decisions, 'project_report': report}
    (output / 'examples.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({'mini_cases': len(cases), 'project_decisions': decisions, 'versions': summary['versions']}, ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('docs/experiments/seminar/examples'))
    build(parser.parse_args().output)
