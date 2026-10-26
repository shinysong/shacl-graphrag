"""Development software checks only; no frozen performance fixtures read."""
from copy import deepcopy
import check_technology_selection_python as checks
from technology_selection_python import PythonArm
from technology_selection_sqlite import SQLiteArm
from technology_selection_rdf import RDFArm


def run():
    arms = (PythonArm, SQLiteArm, RDFArm)
    for arm in arms:
        checks.PythonArm = arm
        checks.main()  # Literal assertions, not merely agreement with Python.
    cases = []
    for quantity, expected in [(0, 'violation'), (-1, 'violation'), (10, 'accept'), (11, 'violation')]:
        p = checks.packet(); p['tables']['receipt'][0]['quantity'] = quantity
        cases.append((p, expected, None))
    for received, expected in [('2026-01-01', 'accept'), ('2026-10-01', 'violation'), ('2025-12-31', 'violation')]:
        p = checks.packet(); p['tables']['receipt'][0]['received_at'] = received
        cases.append((p, expected, None))
    for status, expected in [('Rejected', 'violation'), ('Other', 'unknown')]:
        p = checks.packet(); p['tables']['inspection'][0]['status'] = status
        cases.append((p, expected, None))
    p = checks.packet()
    def edge(occ, source, target):
        return dict(occurrence_id=occ, id=occ, component_item=source, component_revision='R1', parent_item=target, parent_revision='R1', active=True)
    p['tables']['component_edge'] = [edge('b', 'part', 'B'), edge('d', 'B', 'X'), edge('a', 'part', 'A'), edge('z', 'A', 'X')]
    cases.append((deepcopy(p), 'accept', ['a', 'z']))
    p['tables']['component_edge'].append(dict(edge('invalid', 'Q', 'Z'), active='yes'))
    cases.append((deepcopy(p), 'accept', ['a', 'z']))
    outputs = 0
    for p, expected, witness in cases:
        answers = []
        for arm in arms:
            instance = arm(p); answer = instance.query(); answers.append(answer)
            assert answer['receipt'] == expected
            if witness is not None:
                x = next(x for x in answer['products'] if x['id'] == 'X')
                assert x['candidate'] == 'yes' and x['witness'] == witness
                if any(e['id'] == 'invalid' for e in p['tables']['component_edge']):
                    assert answer['impact_graph_completeness'] == 'partial'
                    assert next(x for x in answer['products'] if x['id'] == 'U')['candidate'] == 'unknown'
            if hasattr(instance, 'close'): instance.close()
            outputs += 1
        assert answers[0] == answers[1] == answers[2], p['scene_id']
    print(f'3 arms x14 literal software checks; {len(cases)} extra cases/{outputs} outputs with full parity; 0 performance fixture executions')


if __name__ == '__main__':
    run()
