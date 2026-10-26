"""Shared parsing, provenance, witnesses and recheck policy; no receipt verdicts."""
from copy import deepcopy
from collections import defaultdict
import industrial_question_python as base


def integer(value):
    return value if type(value) is int and abs(value) <= 2**31 - 1 else None


def normalize(packet):
    p = deepcopy(packet)
    if p.get('policy_id') != 'technology-selection-1':
        raise ValueError('unsupported policy')
    t = p['tables']
    if set(t) != set(base.TABLES) or any(not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows) for rows in t.values()):
        raise ValueError('invalid tables')
    rows = [r for rs in t.values() for r in rs] + p['coverage']
    ids = [r.get('occurrence_id') for r in rows]
    if any(not base.text(x) for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('invalid occurrence IDs')
    if len(t['receipt']) != 1 or len(t['product']) != 4 or len(t['component_edge']) > 1024:
        raise ValueError('out of scope')
    products = [(r.get('id'), r.get('revision')) for r in t['product']]
    if any(not all(base.text(x) for x in pair) for pair in products) or len(set(products)) != 4:
        raise ValueError('invalid product universe')
    r, q = t['receipt'][0], p['question']
    if not base.text(r.get('id')) or r['id'] != q.get('receipt_id'):
        raise ValueError('receipt identity mismatch')
    target = (q.get('target_item'), q.get('target_revision'))
    if not all(base.text(x) for x in target):
        raise ValueError('invalid target')
    indexes = {}
    for name in ('order_line', 'inspection', 'certificate'):
        index = defaultdict(list)
        for row in t[name]:
            if base.text(row.get('id')):
                index[row['id']].append(row)
        indexes[name] = index
    links, linked, checks = {}, {}, []
    for name, field in [('order_line', 'order_line_id'), ('inspection', 'inspection_id'), ('certificate', 'certificate_id')]:
        key = r.get(field)
        matches = indexes[name].get(key, []) if base.text(key) else []
        links[name] = 'missing' if not matches else 'resolved' if len(matches) == 1 else 'ambiguous'
        linked[name] = matches[0] if len(matches) == 1 else None
        if len(matches) != 1:
            checks.append(dict(rule_id='link-' + name, kind='unresolved', values=None,
                               support=sorted({r['occurrence_id'], *(x['occurrence_id'] for x in matches)})))
    def add(label, kind, values, used):
        checks.append(dict(rule_id=label, kind=kind, values=values,
                           support=sorted({x['occurrence_id'] for x in used})))
    if all(x == 'resolved' for x in links.values()):
        o, i, c = (linked[n] for n in ('order_line', 'inspection', 'certificate'))
        for name, row in [('order', o), ('inspection', i), ('certificate', c)]:
            for field in ('part', 'revision', 'facility'):
                a, b = r.get(field), row.get(field)
                add(name + '-' + field, 'equal', [a, b] if base.text(a) and base.text(b) else None, [r, row])
        a, b = i.get('receipt_id'), r.get('id')
        add('inspection-receipt', 'equal', [a, b] if base.text(a) and base.text(b) else None, [r, i])
        a, b = integer(r.get('quantity')), integer(o.get('remaining_quantity'))
        add('quantity', 'quantity', [a, b] if a is not None and b is not None and r.get('uom') == o.get('uom') == 'Nos' else None, [r, o])
        for name, row, allowed in [('inspection', i, ('Accepted', 'Rejected')), ('certificate', c, ('Active', 'Inactive'))]:
            v = row.get('status')
            add(name + '-status', name + '-status', [v] if v in allowed else None, [row])
        span, received = base.interval(c), base.day(r.get('received_at'))
        add('certificate-dates', 'interval', [span[0].toordinal(), received.toordinal(), span[1].toordinal()] if span and received else None, [r, c])
    adjacency, complete, excluded = base.graph(t, p['coverage'])
    key = q.get('certificate_id')
    matches = indexes['certificate'].get(key, []) if base.text(key) else []
    return dict(packet=p, checks=checks, links=links, adjacency=adjacency, complete=complete,
                excluded=excluded, target=target, cert=matches[0] if len(matches) == 1 else None)


def assemble(state, failed, members, paths):
    """Membership is engine-owned; a witness disagreement is an execution error."""
    p = state['packet']
    checks = state['checks']
    known = {c['rule_id'] for c in checks if c['values'] is not None}
    if not set(failed) <= known:
        raise ValueError('engine returned unknown rule')
    def diagnostic(c):
        return dict(rule_id=c['rule_id'], support=c['support'])
    violations = sorted([diagnostic(c) for c in checks if c['rule_id'] in failed], key=lambda c: c['rule_id'])
    unknown = sorted([diagnostic(c) for c in checks if c['values'] is None], key=lambda c: c['rule_id'])
    products = []
    for row in sorted(p['tables']['product'], key=lambda r: (r['id'], r['revision'])):
        node = (row['id'], row['revision'])
        witness = paths.get(node, [])
        if (node in members) != bool(witness):
            raise ValueError('engine membership/witness disagreement')
        candidate = 'yes' if node in members else 'no' if state['complete'] else 'unknown'
        products.append(dict(id=node[0], revision=node[1], candidate=candidate, witness=witness,
                             recheck=base.recheck(candidate, row, state['cert'], p['question'])))
    return dict(scene_id=p['scene_id'], receipt_id=p['tables']['receipt'][0]['id'],
                receipt='violation' if violations else 'unknown' if unknown else 'accept', links=state['links'],
                products=products, impact_graph_completeness='complete' if state['complete'] else 'partial',
                violated_checks=violations, unknown_checks=unknown)


def updated_packet(state, command):
    p = deepcopy(state['packet'])
    op = command['operation']
    changed = []
    if op == 'deactivate_incoming':
        for r in p['tables']['component_edge']:
            if (r.get('parent_item'), r.get('parent_revision')) == (command['product_id'], command['revision']):
                if r.get('active') is True:
                    changed.append(r['occurrence_id'])
                r['active'] = False
    elif op == 'set_certificate_expiry':
        for r in p['tables']['certificate']:
            if r.get('id') == command['certificate_id']:
                r['expires'] = command['expires']
                changed.append(r['occurrence_id'])
    else:
        raise ValueError('unsupported update')
    return p, sorted(changed)
