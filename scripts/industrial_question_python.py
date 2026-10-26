"""Same-policy Python baseline. No scorer, source repair, file access or API calls."""
from collections import Counter, deque
from datetime import date
from decimal import Decimal, InvalidOperation
import re

TABLES = ('receipt', 'order_line', 'inspection', 'certificate', 'component_edge', 'product')


def text(value):
    return isinstance(value, str) and bool(value)


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    if isinstance(value, str) and not re.fullmatch(r'[+-]?[0-9]+(\.[0-9]+)?', value):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def day(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def interval(cert):
    start, end = day(cert.get('valid_from')), day(cert.get('expires'))
    return (start, end) if start and end and start < end else None


def validate_input(packet):
    """Structural errors raise; runner must save failure and retain fixed denominators."""
    if not isinstance(packet, dict) or packet.get('policy_id') != 'industrial-questions-1':
        raise ValueError('invalid packet/policy')
    if not text(packet.get('scene_id')) or not isinstance(packet.get('question'), dict):
        raise ValueError('invalid scene/question')
    tables = packet.get('tables')
    if not isinstance(tables, dict) or set(tables) != set(TABLES):
        raise ValueError('invalid tables')
    occurrences = []
    for name in TABLES:
        if not isinstance(tables[name], list) or any(not isinstance(r, dict) for r in tables[name]):
            raise ValueError('invalid table container')
        occurrences.extend(r.get('occurrence_id') for r in tables[name])
    coverage = packet.get('coverage', [])
    if not isinstance(coverage, list) or any(not isinstance(r, dict) for r in coverage):
        raise ValueError('invalid coverage container')
    occurrences.extend(r.get('occurrence_id') for r in coverage)
    if any(not text(v) for v in occurrences) or len(set(occurrences)) != len(occurrences):
        raise ValueError('invalid occurrence identity')
    products = tables['product']
    if len(tables['receipt']) != 1 or len(products) != 4 or len(occurrences) > 100:
        raise ValueError('out of bounded scope')
    if any(not text(r.get(k)) for r in products for k in ('id', 'revision')):
        raise ValueError('invalid product identity')
    if len({(r['id'], r['revision']) for r in products}) != 4:
        raise ValueError('ambiguous product universe')
    return tables


def resolve(rows, key):
    matches = [r for r in rows if text(key) and r.get('id') == key]
    return ('missing', None) if not matches else (('ambiguous', None) if len(matches) > 1 else ('resolved', matches[0]))


def equality(a, b):
    return None if not text(a) or not text(b) else a == b


def aggregate(checks):
    return 'violation' if False in checks else ('unknown' if None in checks else 'accept')


def receipt_decision(receipt, order, inspection, cert):
    checks = [equality(receipt.get(k), row.get(k))
              for row in (order, inspection, cert) for k in ('part', 'revision', 'facility')]
    checks.append(equality(inspection.get('receipt_id'), receipt.get('id')))
    q, remaining = number(receipt.get('quantity')), number(order.get('remaining_quantity'))
    checks.append(None if q is None or remaining is None or receipt.get('uom') != 'Nos' or order.get('uom') != 'Nos'
                  else 0 < q <= remaining)
    checks.append({'Accepted': True, 'Rejected': False}.get(str(inspection.get('status'))))
    checks.append({'Active': True, 'Inactive': False}.get(str(cert.get('status'))))
    span, received = interval(cert), day(receipt.get('received_at'))
    checks.append(None if not span or not received else span[0] <= received < span[1])
    return aggregate(checks)


def graph(tables, coverage):
    declarations = [r.get('complete') for r in coverage if r.get('table') == 'component_edge']
    complete = len(declarations) == 1 and declarations[0] is True
    counts = Counter(r['id'] for r in tables['component_edge'] if text(r.get('id')))
    adjacency = {}
    excluded = []
    for edge in tables['component_edge']:
        valid = all(text(edge.get(k)) for k in ('id', 'component_item', 'component_revision', 'parent_item', 'parent_revision'))
        valid = valid and type(edge.get('active')) is bool and counts[edge['id']] == 1
        if not valid:
            complete = False
            excluded.append(edge['occurrence_id'])
            continue
        if not edge['active']:
            continue
        a = (edge['component_item'], edge['component_revision'])
        b = (edge['parent_item'], edge['parent_revision'])
        adjacency.setdefault(a, []).append((edge['occurrence_id'], b))
    for edges in adjacency.values():
        edges.sort()
    return adjacency, complete, excluded


def shortest_paths(adjacency, target):
    paths, queue = {target: []}, deque([target])
    while queue:
        node = queue.popleft()
        for occurrence, other in adjacency.get(node, []):
            if other not in paths:
                paths[other] = paths[node] + [occurrence]
                queue.append(other)
    paths.pop(target, None)  # positive non-reflexive closure, including cycles
    return paths


def recheck(candidate, product, cert, question):
    if candidate != 'yes':
        return 'not_required' if candidate == 'no' else 'unknown'
    if cert is None:
        return 'unknown'
    scope = [equality(cert.get('part'), question.get('target_item')),
             equality(cert.get('revision'), question.get('target_revision')),
             equality(cert.get('facility'), product.get('facility'))]
    required = product.get('requires_current_certificate')
    if required is False or False in scope:
        return 'not_required'
    if type(required) is not bool or None in scope:
        return 'unknown'
    span, now = interval(cert), day(question.get('as_of'))
    status = cert.get('status')
    if not span or not now or status not in ('Active', 'Inactive'):
        return 'unknown'
    if now >= span[1]:
        return 'required'
    return 'not_required' if span[0] <= now < span[1] and status == 'Active' else 'unknown'


def evaluate(packet):
    tables = validate_input(packet)
    question, receipt = packet['question'], tables['receipt'][0]
    links, linked = {}, {}
    for name, field in (('order_line', 'order_line_id'), ('inspection', 'inspection_id'), ('certificate', 'certificate_id')):
        links[name], linked[name] = resolve(tables[name], receipt.get(field))
    if equality(receipt.get('id'), question.get('receipt_id')) is not True:
        raise ValueError('receipt question does not identify supplied receipt')
    result = 'unknown'
    if all(v == 'resolved' for v in links.values()):
        result = receipt_decision(receipt, linked['order_line'], linked['inspection'], linked['certificate'])
    target = (question.get('target_item'), question.get('target_revision'))
    if not all(text(v) for v in target):
        raise ValueError('missing impact target identity')
    adjacency, complete, excluded = graph(tables, packet.get('coverage', []))
    paths = shortest_paths(adjacency, target)
    _, cert = resolve(tables['certificate'], question.get('certificate_id'))
    products = []
    for product in tables['product']:
        witness = paths.get((product['id'], product['revision']), [])
        candidate = 'yes' if witness else ('no' if complete else 'unknown')
        products.append(dict(id=product['id'], revision=product['revision'], candidate=candidate,
                             recheck=recheck(candidate, product, cert, question), witness=witness))
    return dict(scene_id=packet['scene_id'], receipt_id=receipt['id'], receipt=result, links=links,
                products=products, impact_graph_completeness='complete' if complete else 'partial',
                diagnostics={'excluded_edges': excluded})
