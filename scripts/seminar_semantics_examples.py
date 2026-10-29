"""Tiny executed teaching examples of inference and validation, not a research benchmark."""
from __future__ import annotations
import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
from rdflib import Graph, Namespace, RDF
from owlrl import DeductiveClosure, RDFS_Semantics, OWLRL_Semantics
from pyshacl import validate

EX = Namespace('https://example.org/sensor/')
SH = Namespace('http://www.w3.org/ns/shacl#')
PREFIX = '''@prefix ex: <https://example.org/sensor/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
'''
# region sensor_data
DATA = '''ex:TS1 a ex:TemperatureSensor ;
    ex:observes ex:RoomA .'''
# endregion sensor_data
# region sensor_schema
SCHEMA = '''ex:TemperatureSensor rdfs:subClassOf ex:Sensor .
ex:Sensor rdfs:subClassOf ex:Device .
ex:observes rdfs:domain ex:Sensor ; rdfs:range ex:Room ;
    owl:inverseOf ex:observedBy .'''
# endregion sensor_schema
# region manufacturer_shape
MANUFACTURER_SHAPE = '''ex:ManufacturerShape a sh:NodeShape ;
    sh:targetNode ex:TS1 ;
    sh:property [
        sh:path ex:manufacturer ;
        sh:minCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:message "제조사 식별자를 하나 이상 기록하세요."
    ] .'''
# endregion manufacturer_shape
# region type_shape
TYPE_SHAPE = '''ex:ExplicitTypeShape a sh:NodeShape ;
    sh:targetNode ex:TS1 ;
    sh:property [
        sh:path rdf:type ;
        sh:hasValue ex:Device
    ] .'''
# endregion type_shape

# region expand
def expand_copy(original, mode):
    expanded = Graph()
    for triple in original:
        expanded.add(triple)
    semantics = {'rdfs': RDFS_Semantics, 'owlrl': OWLRL_Semantics}
    if mode != 'original':
        DeductiveClosure(semantics[mode]).expand(expanded)
    return expanded
# endregion expand

# region sensor_validate
def check(graph, shape_text):
    shapes = Graph().parse(data=PREFIX + shape_text, format='turtle')
    conforms, report, text = validate(
        graph, shacl_graph=shapes, inference='none')
    return bool(conforms), report, text
# endregion sensor_validate

def summary_report(report):
    return sorted([{
        'focus': str(report.value(r, SH.focusNode)),
        'path': str(report.value(r, SH.resultPath)),
        'component': str(report.value(r, SH.sourceConstraintComponent)).split('#')[-1],
    } for r in report.subjects(RDF.type, SH.ValidationResult)], key=lambda r: (r['path'], r['component']))

def build(output):
    output.mkdir(parents=True, exist_ok=True)
    original = Graph().parse(data=PREFIX + DATA + '\n' + SCHEMA, format='turtle')
    before = set(original)
    records = []
    for mode in ['original', 'rdfs', 'owlrl']:
        graph = expand_copy(original, mode)
        conforms, report, text = check(graph, MANUFACTURER_SHAPE + '\n' + TYPE_SHAPE)
        records.append({'mode': mode, 'TS1_is_Device': (EX.TS1, RDF.type, EX.Device) in graph,
                        'RoomA_is_Room': (EX.RoomA, RDF.type, EX.Room) in graph,
                        'RoomA_observedBy_TS1': (EX.RoomA, EX.observedBy, EX.TS1) in graph,
                        'manufacturer_recorded': bool(list(graph.objects(EX.TS1, EX.manufacturer))),
                        'conforms_two_shapes': conforms, 'violations': summary_report(report)})
        graph.serialize(destination=output/f'{mode}.ttl', format='turtle')
        report.serialize(destination=output/f'{mode}-validation.ttl', format='turtle')
    assert set(original) == before
    assert [r['TS1_is_Device'] for r in records] == [False, True, True]
    assert [r['RoomA_is_Room'] for r in records] == [False, True, True]
    assert [r['RoomA_observedBy_TS1'] for r in records] == [False, False, True]
    assert [len(r['violations']) for r in records] == [2, 1, 1]
    cases=[]
    additions = {'valid': 'ex:TS1 ex:manufacturer ex:MakerA .', 'missing': '',
                 'literal': 'ex:TS1 ex:manufacturer "MakerA" .',
                 'unverified_iri': 'ex:TS1 ex:manufacturer ex:UnverifiedMaker .'}
    for name, extra in additions.items():
        graph = Graph().parse(data=PREFIX + DATA + '\n' + extra, format='turtle')
        conforms, report, text = check(graph, MANUFACTURER_SHAPE)
        cases.append({'case': name, 'added_fact': extra or '(제조사 기록 없음)', 'conforms': conforms,
                      'violations': summary_report(report), 'real_world_truth': 'not_verified'})
        graph.serialize(destination=output/f'case-{name}.ttl', format='turtle')
        report.serialize(destination=output/f'case-{name}-report.ttl', format='turtle')
    assert [c['conforms'] for c in cases] == [True, False, False, True]
    # Positive Datalog-style reachability: finite set closure, not path enumeration.
    # region reachability
    edges = {('A', 'B'), ('B', 'C')}
    reachable = set(edges)
    while True:
        additions = {(x, z) for x, y in reachable
                     for y2, z in edges if y == y2}
        updated = reachable | additions
        if updated == reachable:
            break
        reachable = updated
    # endregion reachability
    assert reachable == {('A', 'B'), ('B', 'C'), ('A', 'C')}
    (output/'sensor-data.ttl').write_text(PREFIX + DATA)
    (output/'sensor-schema.ttl').write_text(PREFIX + SCHEMA)
    (output/'manufacturer-shape.ttl').write_text(PREFIX + MANUFACTURER_SHAPE)
    (output/'explicit-type-shape.ttl').write_text(PREFIX + TYPE_SHAPE)
    result={'purpose':'tiny executed teaching examples, not benchmark or external truth validation',
            'versions':{p:version(p) for p in ['rdflib','owlrl','pyshacl']},
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'llm_calls':0, 'original_graph_unchanged':True, 'queries':records, 'shape_cases':cases,
            'reachability':sorted([list(x) for x in reachable])}
    (output/'semantics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('docs/experiments/seminar/semantics'))
    build(p.parse_args().output)
