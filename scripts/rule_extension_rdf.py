"""Joined-operand RDF mapping, actual SHACL Core and result translation."""
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal, RDF
from pyshacl import validate
from rule_extension_common import prepare, assemble
EX = Namespace('urn:rule-extension:')
SH = Namespace('http://www.w3.org/ns/shacl#')
SHAPES = Path(__file__).resolve().parents[1]/'research/rule-extension/release-shapes-v1.ttl'


def evaluate(packet,policy):
    checks = prepare(packet,policy)
    data = Graph()
    ids = {}
    for c in checks:
        focus = URIRef(EX+c['rule_id']); ids[focus] = c['rule_id']
        data.add((focus,RDF.type,EX['unknown' if c['values'] is None else c['kind']]))
        if c['values'] is not None:
            for field,value in zip(('a','b','c'),c['values']):
                data.add((focus,EX[field],Literal(value)))
    _,report,_ = validate(data,shacl_graph=Graph().parse(SHAPES),inference='none',advanced=False)
    failed,unknown = set(),set()
    for result in report.subjects(RDF.type,SH.ValidationResult):
        focus = report.value(result,SH.focusNode)
        if focus not in ids:
            raise ValueError('unexpected focus')
        (unknown if report.value(result,SH.resultSeverity) == SH.Warning else failed).add(ids[focus])
    return assemble(checks,failed,unknown)
