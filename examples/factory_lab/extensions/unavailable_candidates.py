"""One fixed-query extension, runnable offline from the repository root.

Run: uv run --locked python -m examples.factory_lab.extensions.unavailable_candidates
This example does not register a new tool in the default six-query demo.
"""
from rdflib import Literal
from apps.factory_lab.public_runtime import EXAMPLES
from apps.factory_lab.graph import validate_args
from apps.factory_lab.rdf_graph import templates, decode
from experiments.factory_complexity.tools import Views, RDFStudyTools
from experiments.query_contracts.core import CatalogIndex

CONTRACT = {
    'id': 'unavailable_candidates.v1', 'tool': 'unavailable_candidates', 'revision': 1,
    'description': 'Capability candidates recorded as unavailable for an order; 주문의 역량 후보 중 사용 불가 상태인 설비',
    'input': {'order_id': {'semantic_type': 'OrderId'}},
    'output_bindings': {'rows[].order.id': 'OrderId', 'rows[].machine.id': 'MachineId'},
    'evidence_support': ['recorded_unavailable_capability_candidates'],
    'does_not_establish': ['schedule', 'physical_approval', 'qualification_applicability', 'complete_source'],
    'empty_semantics': 'No match in this selected view, not global absence.', 'result_limit': 30,
}
BINDING = ('order_id', 'Order', {'order.id': 'Order', 'machine.id': 'Machine'})


def run(order_id):
    validate_args('replacement_candidates', {'order_id': order_id})
    views = Views(EXAMPLES / 'snapshots')
    source, _ = views.snapshot('factory-v3')
    if not any(n['id']==order_id and n['kind']=='Order' for n in source['nodes']):
        raise ValueError('Known Order ID required')
    backend = RDFStudyTools(views)
    query, roles, columns, limit = templates('factory-v3', 'replacement_candidates', {'order_id': order_id})
    anchor = '?machine f:CAPABLE_OF ?cap; f:id ?machine_id .'
    if query.count(anchor) != 1:
        raise ValueError('Template changed; inspect the extension before use')
    query = query.replace(anchor, anchor + ' ?machine f:status ' + Literal('unavailable').n3() + ' .')
    rows = decode([{str(k): v for k, v in row.asdict().items()} for row in backend.dataset.query(query)], 'factory-v3', roles, columns)
    return {'tool': CONTRACT['tool'], 'arguments': {'order_id': order_id}, 'rows': rows,
            'query': query, 'limit_reached': len(rows) >= limit, 'scope': CONTRACT['does_not_establish']}


if __name__ == '__main__':
    import json
    print(json.dumps({'retrieved': CatalogIndex([CONTRACT]).search('사용 불가 대체 후보', 1),
                      'result': run('O17')}, ensure_ascii=False, indent=2))
