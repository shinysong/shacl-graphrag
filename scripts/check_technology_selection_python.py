"""Hand-authored software checks, not performance samples or business truth."""
from copy import deepcopy
from technology_selection_python import PythonArm


def packet():
    scope = dict(part='part', revision='R1', facility='factory')
    t = dict(receipt=[dict(occurrence_id='r', id='receipt', **scope, order_line_id='order', inspection_id='inspection', certificate_id='certificate', quantity=5, uom='Nos', received_at='2026-09-15')],
             order_line=[dict(occurrence_id='o', id='order', **scope, remaining_quantity=10, uom='Nos')],
             inspection=[dict(occurrence_id='i', id='inspection', **scope, receipt_id='receipt', status='Accepted')],
             certificate=[dict(occurrence_id='c', id='certificate', **scope, status='Active', valid_from='2026-01-01', expires='2026-10-01')],
             component_edge=[dict(occurrence_id='edge', id='edge', component_item='part', component_revision='R1', parent_item='X', parent_revision='R1', active=True)],
             product=[dict(occurrence_id='p'+x, id=x, revision='R1', facility='factory', requires_current_certificate=True) for x in 'XEFU'])
    return dict(scene_id='software', policy_id='technology-selection-1', tables=t, coverage=[dict(occurrence_id='coverage', table='component_edge', complete=True)],
                question=dict(receipt_id='receipt', target_item='part', target_revision='R1', certificate_id='certificate', as_of='2026-10-21'))


def main():
    count = 0
    p = packet()
    a = PythonArm(p)
    out = a.query()
    assert out['receipt'] == 'accept'
    assert next(x for x in out['products'] if x['id'] == 'X')['recheck'] == 'required'
    assert not out['unknown_checks'] and not out['violated_checks']
    count += 1
    for value in (True, 1.5, '5', 2**31, None):
        q = deepcopy(p); q['tables']['receipt'][0]['quantity'] = value
        result = PythonArm(q).query()
        assert result['receipt'] == 'unknown'
        assert result['unknown_checks'] == [dict(rule_id='quantity', support=['o', 'r'])]
        count += 1
    q = deepcopy(p); q['tables']['order_line'][0]['part'] = 'wrong'; q['tables']['receipt'][0]['quantity'] = None
    result = PythonArm(q).query()
    assert result['receipt'] == 'violation' and result['violated_checks'] == [dict(rule_id='order-part', support=['o', 'r'])]
    count += 1
    q = deepcopy(p); q['tables']['order_line'].append(dict(q['tables']['order_line'][0], occurrence_id='o2'))
    result = PythonArm(q).query()
    assert result['receipt'] == 'unknown' and result['unknown_checks'] == [dict(rule_id='link-order_line', support=['o', 'o2', 'r'])]
    count += 1
    q = deepcopy(p); q['tables']['certificate'] = []
    result = PythonArm(q).query()
    assert result['unknown_checks'] == [dict(rule_id='link-certificate', support=['r'])]
    count += 1
    q = deepcopy(p); q['tables']['certificate'][0]['expires'] = '2026-02-30'
    assert PythonArm(q).query()['unknown_checks'] == [dict(rule_id='certificate-dates', support=['c', 'r'])]
    count += 1
    q = deepcopy(p); q['tables']['component_edge'].append(dict(q['tables']['component_edge'][0], occurrence_id='duplicate'))
    result = PythonArm(q).query()
    assert result['impact_graph_completeness'] == 'partial' and all(x['candidate'] == 'unknown' for x in result['products'])
    count += 1
    q = deepcopy(p); q['tables']['component_edge'].append(dict(occurrence_id='cycle', id='cycle', component_item='X', component_revision='R1', parent_item='part', parent_revision='R1', active=True))
    result = PythonArm(q).query()
    assert next(x for x in result['products'] if x['id'] == 'X')['witness'] == ['edge']
    count += 1
    a.update(dict(operation='deactivate_incoming', product_id='X', revision='R1'))
    assert all(x['candidate'] == 'no' for x in a.query()['products'])
    assert p['tables']['component_edge'][0]['active'] is True
    count += 1
    a = PythonArm(p)
    a.update(dict(operation='set_certificate_expiry', certificate_id='certificate', expires='2026-11-01'))
    assert all(x['recheck'] == 'not_required' for x in a.query()['products'])
    assert a.query() == a.query()
    count += 1
    print(f'{count} handcrafted software checks passed; 0 performance fixture executions')


if __name__ == '__main__':
    main()
