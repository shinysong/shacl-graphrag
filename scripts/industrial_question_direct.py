"""Predeclared capability ablation: direct eligible edges only, no closure.

Absence with complete edge coverage is reported no even though multihop may exist:
this is an intentionally incomplete algorithm, not a proposed safe workflow.
Receipt, graph completeness and recheck policy remain shared and unchanged.
"""
from industrial_question_python import (validate_input, resolve, equality, text,
                                       receipt_decision, graph, recheck)


def evaluate(packet):
    tables = validate_input(packet)
    question, receipt = packet['question'], tables['receipt'][0]
    if equality(receipt.get('id'), question.get('receipt_id')) is not True:
        raise ValueError('receipt question does not identify supplied receipt')
    links, linked = {}, {}
    for name, field in (('order_line', 'order_line_id'), ('inspection', 'inspection_id'), ('certificate', 'certificate_id')):
        links[name], linked[name] = resolve(tables[name], receipt.get(field))
    result = 'unknown'
    if all(v == 'resolved' for v in links.values()):
        result = receipt_decision(receipt, linked['order_line'], linked['inspection'], linked['certificate'])
    target = (question.get('target_item'), question.get('target_revision'))
    if not all(text(v) for v in target):
        raise ValueError('missing impact target identity')
    adjacency, complete, excluded = graph(tables, packet.get('coverage', []))
    direct = {}
    for occurrence, other in adjacency.get(target, []):
        if other != target:
            direct.setdefault(other, [occurrence])
    _, cert = resolve(tables['certificate'], question.get('certificate_id'))
    products = []
    for product in tables['product']:
        witness = direct.get((product['id'], product['revision']), [])
        candidate = 'yes' if witness else ('no' if complete else 'unknown')
        products.append(dict(id=product['id'], revision=product['revision'], candidate=candidate,
                             recheck=recheck(candidate, product, cert, question), witness=witness))
    return dict(scene_id=packet['scene_id'], receipt_id=receipt['id'], receipt=result, links=links,
                products=products, impact_graph_completeness='complete' if complete else 'partial',
                diagnostics={'excluded_edges': excluded, 'capability': 'direct_edges_only'})
