"""Selected recorded stock comparison, not allocation or order approval.

Only two reviewed columns from one CSV are read. Unrelated policy readiness is
not a prerequisite; the full replacement-proposal path remains unchanged.
"""
from copy import deepcopy
import re
from rdflib import Graph, Namespace, RDF, Literal, XSD
from pyshacl import validate
from . import preparation as p


def catalog(draft):
    if draft['adapter'] != p.ADAPTER:
        return None
    chosen = {}
    for field in ('id', 'available'):
        matches = [e for e in draft['entries'] if e['kind'] == 'mapping'
                   and e['status'] == 'approved' and e['target'] == 'skus.' + field]
        if len(matches) != 1:
            return None
        chosen[field] = matches[0]
    if chosen['id']['source']['file'] != chosen['available']['source']['file']:
        return None
    source = next(s for s in draft['sources'] if s['name'] == chosen['id']['source']['file'])
    return {'file': source['name'], 'sha256': source['sha256'],
            'fields': {k: {'entry_id': e['id'], 'column': e['source']['column'],
                           'reviewed_interpretation': e.get('interpretation', '')}
                       for k, e in chosen.items()},
            'identifiers': list(dict.fromkeys(r[chosen['id']['source']['column']]
                                            for r in source['rows'] if r[chosen['id']['source']['column']])),
            'notice': 'Compare recorded SKU availability against requested units only. No reservation, freshness guarantee, order eligibility, discount or shipping check.'}


def execute(draft, arguments):
    draft = p.restore_draft(draft)
    if (not isinstance(arguments, dict) or set(arguments) != {'sku', 'quantity'}
            or not isinstance(arguments['sku'], str) or not 1 <= len(arguments['sku']) <= 2000
            or type(arguments['quantity']) is not int or not 1 <= arguments['quantity'] <= 1000000000):
        raise ValueError('Stock comparison requires an exact SKU and integer quantity in 1..1000000000')
    scope = catalog(draft)
    if scope is None:
        raise ValueError('Review exactly one SKU ID and available quantity column in the same file first')
    source = next(s for s in draft['sources'] if s['name'] == scope['file'])
    fields = scope['fields']
    records = [{'values': {k: row[v['column']] for k, v in fields.items()},
                'source': {'file': source['name'], 'sha256': source['sha256'], **deepcopy(loc)}}
               for row, loc in zip(source['rows'], source['locations'])
               if row[fields['id']['column']] == arguments['sku']]
    result = {'mode': 'recorded_stock_check', 'metadata': deepcopy(draft['metadata']),
              'scope': scope, 'request': deepcopy(arguments), 'records': records,
              'status': 'unknown', 'comparison': None, 'validation': None,
              'unchecked': ['source freshness', 'other files or warehouses', 'existing reservations',
                            'product substitution', 'customer consent', 'discount', 'shipping', 'order approval'],
              'notice': scope['notice']}
    if len(records) != 1:
        result['reason'] = 'not_found_in_selected_source' if not records else 'ambiguous_sku_records'
        return result
    raw = records[0]['values']['available']
    if raw == '':
        result['reason'] = 'available_quantity_missing'
        return result
    if not re.fullmatch(r'0|[1-9][0-9]*', raw) or len(raw) > 10 or int(raw) > 1000000000:
        result['reason'] = 'available_quantity_format_unsupported'
        return result
    available = int(raw)
    quantity = arguments['quantity']
    ns = Namespace('urn:workspace:stock:')
    sh = Namespace('http://www.w3.org/ns/shacl#')
    data = Graph()
    data.add((ns.record, ns.available, Literal(available, datatype=XSD.integer)))
    shapes = Graph()
    shapes.add((ns.shape, RDF.type, sh.NodeShape))
    shapes.add((ns.shape, sh.targetNode, ns.record))
    shapes.add((ns.shape, sh.property, ns.property))
    shapes.add((ns.property, sh.path, ns.available))
    shapes.add((ns.property, sh.minCount, Literal(1)))
    shapes.add((ns.property, sh.datatype, XSD.integer))
    shapes.add((ns.property, sh.minInclusive, Literal(quantity)))
    conforms, report, _ = validate(data, shacl_graph=shapes, inference='none')
    python_pass = available >= quantity
    result.update(status='recorded_quantity_sufficient' if python_pass else 'recorded_quantity_insufficient',
                  comparison={'available': available, 'requested': quantity, 'same_policy_python_pass': python_pass},
                  validation={'shacl_conforms': bool(conforms), 'agrees_with_python': bool(conforms) == python_pass,
                              'data_turtle': data.serialize(format='turtle'),
                              'shapes_turtle': shapes.serialize(format='turtle'),
                              'report_turtle': report.serialize(format='turtle'),
                              'scope': 'One parsed source quantity versus supplied requested units; conformance does not establish source truth, freshness, or order eligibility.'})
    return result
