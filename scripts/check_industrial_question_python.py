"""Non-study software checks: handcrafted records, no frozen study labels imported."""
import copy
from industrial_question_python import evaluate, number, day, interval, shortest_paths, recheck


def packet():
    tables = {
        'receipt': [dict(id='r', part='c', revision='1', facility='f', order_line_id='o',
                         inspection_id='i', certificate_id='s', quantity='2', uom='Nos', received_at='2026-09-01')],
        'order_line': [dict(id='o', part='c', revision='1', facility='f', remaining_quantity='3', uom='Nos')],
        'inspection': [dict(id='i', receipt_id='r', part='c', revision='1', facility='f', status='Accepted')],
        'certificate': [dict(id='s', part='c', revision='1', facility='f', valid_from='2026-01-01', expires='2026-10-01', status='Active')],
        'product': [dict(id=p, revision='1', facility='f', requires_current_certificate=True) for p in ('p', 'q', 'x', 'y')],
        'component_edge': [dict(id='a', component_item='c', component_revision='1', parent_item='m', parent_revision='1', active=True),
                           dict(id='b', component_item='m', component_revision='1', parent_item='p', parent_revision='1', active=True)]}
    for name, rows in tables.items():
        for i, row in enumerate(rows):
            row['occurrence_id'] = f'{name}:{i}'
    return dict(scene_id='software', policy_id='industrial-questions-1',
                question=dict(receipt_id='r', target_item='c', target_revision='1', certificate_id='s', as_of='2026-10-01'),
                tables=tables, coverage=[dict(occurrence_id='coverage', table='component_edge', complete=True)])


def run():
    for value in (True, None, float('nan'), float('inf'), '1e2', ' 2', {}, []):
        assert number(value) is None
    assert number('-1.2') is not None and number(1e2) == 100
    assert day('2026-02-30') is None and day('2026-1-01') is None
    assert interval(dict(valid_from='2026-01-01', expires='2026-01-01')) is None
    p = packet(); out = evaluate(p)
    assert out['receipt'] == 'accept' and out['products'][0]['recheck'] == 'required'
    assert out['products'][0]['witness'] == ['component_edge:0', 'component_edge:1']
    assert out['products'][1]['candidate'] == 'no'
    p['tables']['inspection'] = []
    assert evaluate(p)['receipt'] == 'unknown' and evaluate(p)['impact_graph_completeness'] == 'complete'
    p = packet(); duplicate = copy.deepcopy(p['tables']['order_line'][0]); duplicate['occurrence_id'] = 'second'
    p['tables']['order_line'].append(duplicate)
    assert evaluate(p)['links']['order_line'] == 'ambiguous' and evaluate(p)['receipt'] == 'unknown'
    p = packet(); p['tables']['receipt'][0]['quantity'] = True
    assert evaluate(p)['receipt'] == 'unknown'
    p['tables']['inspection'][0]['status'] = 'Rejected'
    assert evaluate(p)['receipt'] == 'violation'
    p = packet(); p['tables']['component_edge'][0]['active'] = 1
    assert evaluate(p)['products'][0]['candidate'] == 'unknown'
    p = packet(); duplicate = copy.deepcopy(p['tables']['component_edge'][0]); duplicate['occurrence_id'] = 'duplicate-edge'
    p['tables']['component_edge'].append(duplicate)
    assert evaluate(p)['products'][0]['candidate'] == 'unknown'
    assert len(evaluate(p)['diagnostics']['excluded_edges']) == 2
    p = packet(); p['coverage'][0]['complete'] = 'true'
    assert evaluate(p)['products'][0]['candidate'] == 'yes' and evaluate(p)['products'][1]['candidate'] == 'unknown'
    p = packet(); p['tables']['certificate'][0]['expires'] = 'bad'
    assert evaluate(p)['receipt'] == 'unknown' and evaluate(p)['products'][0]['recheck'] == 'unknown'
    p['tables']['product'][0]['requires_current_certificate'] = False
    assert evaluate(p)['products'][0]['recheck'] == 'not_required'
    paths = shortest_paths({'a': [('z', 'c'), ('a', 'b')], 'b': [('b', 'd')], 'c': [('c', 'd')], 'd': [('d', 'a')]}, 'a')
    # shortest_paths expects the sorted adjacency supplied by graph().
    assert paths['d'] == ['z', 'c'] and 'a' not in paths
    paths = shortest_paths({'a': [('a', 'b'), ('z', 'c')], 'b': [('b', 'd')], 'c': [('c', 'd')]}, 'a')
    assert paths['d'] == ['a', 'b']
    for mutation in ('occurrence', 'product', 'container'):
        p = packet()
        if mutation == 'occurrence': p['tables']['inspection'][0]['occurrence_id'] = 'receipt:0'
        if mutation == 'product': p['tables']['product'][1]['id'] = 'p'
        if mutation == 'container': p['tables']['order_line'] = {}
        try:
            evaluate(p)
        except ValueError:
            pass
        else:
            raise AssertionError(mutation)
    p = packet(); cert = p['tables']['certificate'][0]; product = p['tables']['product'][0]; q = p['question']
    cert['status'] = 'Inactive'
    assert recheck('yes', product, cert, q) == 'required'
    q['as_of'] = '2026-09-01'
    assert recheck('yes', product, cert, q) == 'unknown'
    cert['status'] = 'unexpected'
    assert recheck('yes', product, cert, q) == 'unknown'
    assert recheck('yes', product, None, q) == 'unknown'
    print('PASS: handcrafted scalar, joins, precedence, path, coverage and structural-error checks; no study arms run')


if __name__ == '__main__':
    run()
