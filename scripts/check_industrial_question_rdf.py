"""Non-study handcrafted cross-checks; never reads the 24-scene expectations."""
from check_industrial_question_python import packet
from industrial_question_python import evaluate as python_evaluate
from industrial_question_rdf import evaluate as rdf_evaluate


def compare(p, receipt, candidate='yes', recheck='required', graph='complete'):
    py, rdf = python_evaluate(p), rdf_evaluate(p)
    for key in ('receipt', 'links', 'products', 'impact_graph_completeness'):
        assert py[key] == rdf[key], (key, py[key], rdf[key])
    assert rdf['receipt'] == receipt
    assert rdf['products'][0]['candidate'] == candidate
    assert rdf['products'][0]['recheck'] == recheck
    assert rdf['impact_graph_completeness'] == graph
    return rdf


def run():
    count = 0
    p = packet(); out = compare(p, 'accept'); count += 1
    assert out['diagnostics']['shacl_executed'] and out['diagnostics']['shacl_conforms']
    assert out['diagnostics']['closure_triples'] > out['diagnostics']['asserted_triples']
    for field, value in (('part', 'wrong'), ('revision', 'wrong'), ('facility', 'wrong')):
        p = packet(); p['tables']['order_line'][0][field] = value
        out = compare(p, 'violation'); count += 1
        assert out['diagnostics']['violated_checks']
    for received, expected in (('2026-01-01', 'accept'), ('2025-12-31', 'violation'), ('2026-10-01', 'violation')):
        p = packet(); p['tables']['receipt'][0]['received_at'] = received
        compare(p, expected); count += 1
    for q, expected in (('0', 'violation'), ('4', 'violation'), (True, 'unknown'), ('bad', 'unknown')):
        p = packet(); p['tables']['receipt'][0]['quantity'] = q
        compare(p, expected); count += 1
    p = packet(); p['tables']['inspection'][0]['status'] = 'Rejected'
    p['tables']['certificate'][0]['expires'] = 'bad'
    compare(p, 'violation', recheck='unknown'); count += 1
    p = packet(); p['tables']['inspection'] = []
    out = compare(p, 'unknown'); count += 1
    assert not out['diagnostics']['shacl_executed']
    p = packet(); p['tables']['component_edge'][0]['active'] = False
    compare(p, 'accept', 'no', 'not_required'); count += 1
    p = packet(); p['tables']['component_edge'][0]['component_revision'] = '2'
    compare(p, 'accept', 'no', 'not_required'); count += 1
    p = packet(); p['tables']['component_edge'][0]['component_item'] = 'm'
    p['tables']['component_edge'][0]['parent_item'] = 'c'
    compare(p, 'accept', 'no', 'not_required'); count += 1
    p = packet(); p['coverage'].append(dict(occurrence_id='coverage2', table='component_edge', complete=True))
    compare(p, 'accept', graph='partial'); count += 1
    p = packet(); p['tables']['component_edge'].append(dict(id='cycle', occurrence_id='cycle', component_item='p',
                   component_revision='1', parent_item='c', parent_revision='1', active=True))
    compare(p, 'accept'); count += 1
    p = packet(); p['tables']['certificate'][0]['status'] = 'Inactive'
    compare(p, 'violation'); count += 1
    p = packet(); p['tables']['certificate'][0]['valid_from'] = '2026-10-01'
    compare(p, 'unknown', recheck='unknown'); count += 1
    print(f'PASS: {count} handcrafted comparisons; actual OWL-RL and SHACL executed; no study cohort execution')


if __name__ == '__main__':
    run()
