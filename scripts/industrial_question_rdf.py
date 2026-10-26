"""OWL-RL closure + actual SHACL receipt constraints, with disclosed shared adapter.

Shares structural validation, joins, parsing, edge exclusions, witness extraction
and recheck aggregation with Python. Does not call its receipt_decision/evaluate.
SHACL receives values, never precomputed pass/fail booleans. No scorer access.
"""
import json
from pathlib import Path
from urllib.parse import quote
from rdflib import Graph, Namespace, URIRef, BNode, Literal, RDF, OWL, XSD
from owlrl import DeductiveClosure, OWLRL_Semantics
from pyshacl import validate
from industrial_question_python import (validate_input, resolve, text, equality,
    number, day, interval, graph, shortest_paths, recheck)

EX = Namespace('urn:industrial:')
SH = Namespace('http://www.w3.org/ns/shacl#')
SHAPES = Path(__file__).resolve().parents[1] / 'research/industrial-questions/receipt-shapes.ttl'


def entity(key):
    # Injective encoding of a tuple of exact item/revision strings.
    return URIRef('urn:industrial:item:' + quote(json.dumps(key, ensure_ascii=False, separators=(',', ':')), safe=''))


def receipt_graph(receipt, order, inspection, cert):
    data = Graph()
    unknown = []
    def check(label, kind, values):
        node = URIRef('urn:industrial:check:' + label)
        data.add((node, RDF.type, EX[kind]))
        for predicate, value in values.items():
            data.add((node, EX[predicate], value))
    for name, row in (('order', order), ('inspection', inspection), ('certificate', cert)):
        for key in ('part', 'revision', 'facility'):
            a, b = receipt.get(key), row.get(key)
            label = name + '-' + key
            if not text(a) or not text(b):
                unknown.append(label)
            else:
                check(label, 'EqualityCheck', {'left': Literal(a), 'right': Literal(b)})
    a, b = receipt.get('id'), inspection.get('receipt_id')
    if not text(a) or not text(b):
        unknown.append('inspection-receipt')
    else:
        check('inspection-receipt', 'EqualityCheck', {'left': Literal(a), 'right': Literal(b)})
    q, r = number(receipt.get('quantity')), number(order.get('remaining_quantity'))
    if q is None or r is None or receipt.get('uom') != 'Nos' or order.get('uom') != 'Nos':
        unknown.append('quantity')
    else:
        check('quantity', 'QuantityCheck', {'quantity': Literal(q, datatype=XSD.decimal),
                                           'remaining': Literal(r, datatype=XSD.decimal)})
    for label, row, kind, allowed in (('inspection-status', inspection, 'InspectionCheck', ('Accepted', 'Rejected')),
                                     ('certificate-status', cert, 'CertificateCheck', ('Active', 'Inactive'))):
        value = row.get('status')
        if value not in allowed:
            unknown.append(label)
        else:
            check(label, kind, {'status': Literal(value)})
    span, received = interval(cert), day(receipt.get('received_at'))
    if not span or not received:
        unknown.append('certificate-dates')
    else:
        check('certificate-dates', 'DateCheck', {'start': Literal(span[0].toordinal()),
              'end': Literal(span[1].toordinal()), 'received': Literal(received.toordinal())})
    return data, unknown


def receipt_decision(receipt, order, inspection, cert):
    data, unknown = receipt_graph(receipt, order, inspection, cert)
    shapes = Graph().parse(SHAPES, format='turtle')
    conforms, report, _ = validate(data, shacl_graph=shapes, inference='none', advanced=False)
    if not isinstance(report, Graph):
        raise RuntimeError('SHACL validation failure, not policy violation')
    violations = sorted(str(node) for node in report.objects(None, SH.focusNode))
    if not conforms and not violations:
        raise RuntimeError('nonconformance without reported witness')
    decision = 'violation' if not conforms else ('unknown' if unknown else 'accept')
    return decision, dict(shacl_conforms=bool(conforms), violated_checks=violations, unknown_checks=unknown)


def evaluate(packet):
    tables = validate_input(packet)
    question, receipt = packet['question'], tables['receipt'][0]
    if equality(receipt.get('id'), question.get('receipt_id')) is not True:
        raise ValueError('receipt question does not identify supplied receipt')
    links, linked = {}, {}
    for name, field in (('order_line', 'order_line_id'), ('inspection', 'inspection_id'), ('certificate', 'certificate_id')):
        links[name], linked[name] = resolve(tables[name], receipt.get(field))
    result, diagnostics = 'unknown', {'shacl_executed': False}
    if all(v == 'resolved' for v in links.values()):
        result, diagnostics = receipt_decision(receipt, linked['order_line'], linked['inspection'], linked['certificate'])
        diagnostics['shacl_executed'] = True
    target = (question.get('target_item'), question.get('target_revision'))
    if not all(text(v) for v in target):
        raise ValueError('missing impact target identity')
    adjacency, complete, excluded = graph(tables, packet.get('coverage', []))
    rdf = Graph()
    rdf.add((EX.reaches, RDF.type, OWL.TransitiveProperty))
    for a, edges in adjacency.items():
        for _, b in edges:
            rdf.add((entity(a), EX.reaches, entity(b)))
    asserted_count = len(rdf)
    DeductiveClosure(OWLRL_Semantics).expand(rdf)
    # Witness extraction cannot override or repair OWL membership.
    paths = shortest_paths(adjacency, target)
    _, cert = resolve(tables['certificate'], question.get('certificate_id'))
    products = []
    for product in tables['product']:
        key = (product['id'], product['revision'])
        member = key != target and (entity(target), EX.reaches, entity(key)) in rdf
        witness = paths.get(key, [])
        if member != bool(witness):
            raise RuntimeError('OWL membership / path witness disagreement')
        candidate = 'yes' if member else ('no' if complete else 'unknown')
        products.append(dict(id=key[0], revision=key[1], candidate=candidate,
                             recheck=recheck(candidate, product, cert, question), witness=witness))
    diagnostics.update(excluded_edges=excluded, asserted_triples=asserted_count, closure_triples=len(rdf),
                       shared_recheck_policy=True)
    return dict(scene_id=packet['scene_id'], receipt_id=receipt['id'], receipt=result, links=links,
                products=products, impact_graph_completeness='complete' if complete else 'partial', diagnostics=diagnostics)
