"""Trusted adapter source executed only in the bounded container for artifacts."""


def evaluate(packet):
    from rdflib import Graph, URIRef, Literal, RDF, SH
    from rdflib.plugins.sparql.parser import parseQuery
    from pyshacl import validate
    policies = ('customer_analysis', 'quantity_sign', 'nonnegative_price')
    required = {'customer_analysis': (), 'quantity_sign': ('InvoiceNo', 'Quantity'),
                'nonnegative_price': ('UnitPrice',)}
    rows = packet['normalized_rows']
    keys = [(r['row_id'], p) for r in rows for p in policies]

    def failure(stage, reason):
        return {'stage': stage, 'reason': reason,
                'decisions': [{'row_id': r, 'policy': p, 'status': 'error'} for r, p in keys],
                'reports': {}, 'precheck_unknown': []}

    raw = packet['shape_turtle']
    if not isinstance(raw, str) or len(raw.encode()) > 65536:
        return failure('artifact_unsupported', 'shape_byte_limit')
    try:
        shapes = Graph().parse(data=raw, format='turtle')
    except Exception as exc:
        return failure('artifact_parse_error', type(exc).__name__)
    allowed = {RDF.type, RDF.first, RDF.rest}
    allowed.update(SH[name] for name in (
        'property', 'path', 'minCount', 'maxCount', 'minInclusive', 'maxInclusive',
        'minExclusive', 'maxExclusive', 'datatype', 'nodeKind', 'pattern', 'flags',
        'in', 'or', 'and', 'not', 'xone', 'node', 'class', 'hasValue',
        'equals', 'disjoint', 'lessThan', 'lessThanOrEquals',
        'sparql', 'select', 'message', 'name', 'description'))
    if any(p not in allowed for _, p, _ in shapes):
        return failure('artifact_unsupported', 'predicate_outside_declared_subset')
    if any(o not in (SH.NodeShape, SH.PropertyShape) for o in shapes.objects(None, RDF.type)):
        return failure('artifact_unsupported', 'unsupported_rdf_type')
    if any(not isinstance(o, URIRef) for o in shapes.objects(None, SH.path)):
        return failure('artifact_unsupported', 'only_direct_IRI_paths')
    roots = {p: URIRef('urn:retail:shape:'+p) for p in policies}
    if any((root, RDF.type, SH.NodeShape) not in shapes for root in roots.values()):
        return failure('artifact_unsupported', 'missing_declared_root')

    def inspect_ast(node):
        # Parse-tree inspection, not a lexical SERVICE search that can hit literals.
        if getattr(node, 'name', None) == 'ServiceGraphPattern':
            raise ValueError('service_not_supported')
        if isinstance(node, dict):
            if 'datasetClause' in node and node['datasetClause']:
                raise ValueError('dataset_clause_not_supported')
            for value in node.values():
                inspect_ast(value)
        elif isinstance(node, (list, tuple)) or type(node).__name__ == 'ParseResults':
            for value in node:
                inspect_ast(value)

    try:
        for query in shapes.objects(None, SH.select):
            if not isinstance(query, Literal):
                raise ValueError('select_literal_required')
            ast = parseQuery(str(query))
            if ast[1].name != 'SelectQuery':
                raise ValueError('select_only')
            inspect_ast(ast)
    except Exception as exc:
        return failure('artifact_unsupported', type(exc).__name__)
    data = Graph().parse(data=packet['data_turtle'], format='turtle')
    decisions = []
    reports = {}
    unknown = []
    for policy, root in roots.items():
        graph = Graph()
        for triple in shapes:
            graph.add(triple)
        eligible = []
        for row in rows:
            if any(row['fields'][f]['state'] != 'valid' for f in required[policy]):
                d = {'row_id': row['row_id'], 'policy': policy, 'status': 'unknown'}
                decisions.append(d); unknown.append(d)
            else:
                eligible.append(row)
                graph.add((root, SH.targetNode, URIRef(row['uri'])))
        if not eligible:
            reports[policy] = {'executed': False, 'target_count': 0}
            continue
        try:
            conforms, report, _ = validate(data, shacl_graph=graph, inference='none',
                                          advanced=False, js=False, do_owl_imports=False)
            if not isinstance(report, Graph):
                raise RuntimeError('NonGraphValidationReport')
            failed = {str(n) for n in report.objects(None, SH.focusNode)}
            reports[policy] = {'executed': True, 'target_count': len(eligible),
                               'conforms': bool(conforms), 'report_turtle': report.serialize(format='turtle')}
            decisions.extend({'row_id': r['row_id'], 'policy': policy,
                              'status': 'violation' if r['uri'] in failed else 'pass'} for r in eligible)
        except Exception as exc:
            reports[policy] = {'executed': True, 'error_type': type(exc).__name__}
            decisions.extend({'row_id': r['row_id'], 'policy': policy, 'status': 'error'} for r in eligible)
    return {'stage': 'validation_attempted', 'decisions': decisions,
            'reports': reports, 'precheck_unknown': unknown}
