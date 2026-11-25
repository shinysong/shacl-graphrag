"""Pure bounded RDF projection of a saved relational query result.

The service must load both artifacts from its immutable same-workspace store and
verify current bindings. This module checks internal consistency, not identity,
source authenticity, business interpretation or external truth. It never reads a
registry, executes a query, starts a reasoner or fetches ontology imports.
"""
from copy import deepcopy
import base64
import hashlib
import json
import re

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

FORMAT = 'query-result-rdf-projection-1'
NAMESPACE = 'urn:factory-lab:semantics:'
MAX_ROWS = 200
MAX_COLUMNS = 20
MAX_TRIPLES = 5000
MAX_COMBINED_BYTES = 64 * 1024
MAX_ONTOLOGY_BYTES = 16 * 1024
MAX_ONTOLOGY_TRIPLES = 128
RDFS_PREDICATES = frozenset((RDFS.subClassOf, RDFS.subPropertyOf, RDFS.domain, RDFS.range))
VERSIONS = frozenset(('reviewed-query-1', 'reviewed-query-2', 'reviewed-query-3'))


class ProjectionError(ValueError):
    """Unsupported or inconsistent input; no partial projection is returned."""


def _require(condition, message):
    if not condition:
        raise ProjectionError(message)


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ProjectionError('Expected finite UTF-8 JSON') from exc


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _fingerprint(value):
    return _sha(_json(value))


def _keys(value, keys):
    _require(isinstance(value, dict) and set(value) == set(keys.split()), 'Unsupported or missing projection fields')


def _text(value):
    _require(isinstance(value, str) and 0 < len(value.strip()) <= 4000, 'Provide bounded interpretation text')
    _json(value)


def _iri(value, *, local=False):
    _require(isinstance(value, str) and len(value) <= 512 and
             re.fullmatch(r'[A-Za-z][A-Za-z0-9+.-]*:[^\s<>"{}|^`\\]+', value) is not None,
             'Expected absolute bounded IRI')
    _json(value)
    if local:
        _require(value.startswith(NAMESPACE) and len(value) > len(NAMESPACE), 'Projection vocabulary must use local semantics namespace')
    return URIRef(value)


def _nt(triples):
    """RDFLib escapes RDF terms; sorting complete NT lines fixes byte order."""
    graph = Graph()
    for triple in triples:
        graph.add(triple)
    return ''.join(line + '\n' for line in sorted(graph.serialize(format='nt').splitlines()) if line).encode('utf-8')


def _partition(raw, *, triples=None):
    result = {'text': raw.decode('utf-8'), 'sha256': _sha(raw), 'bytes': len(raw)}
    if triples is not None:
        result['triple_count'] = triples
    return result


def normalize_ontology(raw):
    """Validate bounded IRI-only RDFS axioms and preserve original/normalized bytes.

    Version 1 deliberately excludes labels, instance assertions, class declaration
    triples and OWL. No unsupported statement is silently removed. Empty ontology
    is permitted (and clearly has zero axioms). Turtle parsing is from bytes only.
    """
    _require(type(raw) is bytes and len(raw) <= MAX_ONTOLOGY_BYTES, 'Ontology exceeds byte limit or is not bytes')
    try:
        text = raw.decode('utf-8', 'strict')
    except UnicodeError as exc:
        raise ProjectionError('Ontology must be UTF-8') from exc
    # Conservative lexical checks also reject these constructs in comments. This
    # avoids an implicit document base before RDFLib resolves relative references.
    _require(re.search(r'(?i)(?:@base\b|\bBASE\s*<)', text) is None, 'Ontology base directives are unsupported')
    for token in re.findall(r'<([^>]*)>', text):
        _iri(token)
    graph = Graph()
    try:
        graph.parse(data=text, format='turtle', publicID='urn:factory-lab:ontology:')
    except Exception as exc:
        raise ProjectionError('Invalid bounded Turtle ontology') from exc
    _require(len(graph) <= MAX_ONTOLOGY_TRIPLES, 'Ontology exceeds triple limit')
    for subject, predicate, obj in graph:
        _require(all(isinstance(term, URIRef) for term in (subject, predicate, obj)), 'Ontology terms must be IRIs; literals and blank nodes unsupported')
        for term in (subject, predicate, obj):
            _iri(str(term))
        _require(predicate in RDFS_PREDICATES, 'Unsupported ontology predicate; only declared RDFS axioms allowed')
    normalized = _nt(graph)
    return {'original': {**_partition(raw), 'base64': base64.b64encode(raw).decode('ascii')},
            'normalized': _partition(normalized, triples=len(graph)), 'profile': 'rdfs',
            'semantic_interpretation_verified': False}


def _validate_artifacts(result, approved):
    _require(isinstance(result, dict) and isinstance(approved, dict), 'Saved artifacts required')
    _require(result.get('version') in VERSIONS and result.get('query_kind') is None,
             'Only relational saved query outputs supported')
    _require(result.get('status') == 'complete' and result.get('truncated') is False,
             'Incomplete or truncated query cannot be projected for launch')
    rows = result.get('rows')
    _require(isinstance(rows, list) and len(rows) <= MAX_ROWS, 'Query row limit exceeded')
    for count in ('returned_count', 'total_output_rows'):
        _require(type(result.get(count)) is int and result[count] == len(rows), 'Saved query row counts disagree')
    _require(approved.get('kind') == 'query' and approved.get('status') == 'approved'
             and approved.get('version') == result['version'], 'Matching approved relational query required')
    body = {k: v for k, v in approved.items() if k not in ('fingerprint', 'status', 'review')}
    _require(approved.get('fingerprint') == _fingerprint(body), 'Approved query fingerprint changed')
    review = approved.get('review')
    _require(isinstance(review, dict) and review.get('human_confirmed') is True
             and review.get('approved_fingerprint') == approved['fingerprint'], 'Query approval binding missing')
    provenance = result.get('provenance')
    _require(isinstance(provenance, dict), 'Query provenance missing')
    for key in ('source', 'dependencies', 'origin', 'review'):
        _require(provenance.get(key) == approved.get(key), 'Query provenance differs from approval: ' + key)
    _require(provenance.get('contract_fingerprint') == approved['fingerprint']
             and provenance.get('dependency_fingerprint') == _fingerprint(approved.get('dependencies')),
             'Query dependency or contract fingerprint changed')
    source = provenance['source']
    _require(isinstance(source, dict) and isinstance(source.get('snapshot_sha256'), str)
             and re.fullmatch('[0-9a-f]{64}', source['snapshot_sha256']) is not None
             and isinstance(source.get('source_id'), str) and bool(source['source_id']), 'Query source binding missing')
    spec = approved.get('spec')
    _require(isinstance(spec, dict) and spec.get('query_kind') is None, 'Only relational query spec supported')
    _require(isinstance(provenance.get('parameters'), dict)
             and set(provenance['parameters']) == set(spec.get('parameters', {})), 'Query parameter bindings differ')
    outputs = {}
    for category in ('projection', 'aggregates'):
        _require(isinstance(spec.get(category), list), 'Query output definition missing')
        for expression in spec[category]:
            _require(isinstance(expression, dict) and isinstance(expression.get('name'), str)
                     and expression['name'] not in outputs, 'Ambiguous query output names')
            outputs[expression['name']] = {'category': category, 'expression': deepcopy(expression)}
    for row in rows:
        _require(isinstance(row, dict) and set(row) == set(outputs), 'Saved row does not match output schema')
    _json(result)
    return outputs


def _literal(value, datatype, name, expression, result):
    if datatype == 'text':
        _require(type(value) is str, 'Text projection requires text value')
        _json(value)
        return Literal(value, datatype=XSD.string)
    _require(datatype == 'integer', 'Unsupported projection datatype')
    product = expression.get('op') == 'sum_product'
    if product:
        metadata = result.get('product_aggregate_observations', {}).get(name, {})
        _require(metadata.get('value_encoding') == 'decimal_integer_string', 'Integer string encoding metadata missing')
        _require(type(value) is str and re.fullmatch(r'(?:0|-?[1-9][0-9]*)', value) is not None
                 and len(value) <= 20, 'Expected canonical exact integer string')
        integer = int(value)
    else:
        _require(type(value) is int, 'Integer projection requires exact JSON integer')
        integer = value
    _require(-(2**63) <= integer < 2**63, 'Integer outside signed-64 range')
    return Literal(str(integer), datatype=XSD.integer, normalize=False)


def build_projection(execution_artifact, *, workspace_id, execution_operation_id,
                     approved_query_artifact, projection_spec, ontology_bytes):
    """Return deterministic, JSON-serializable source-backed projection evidence.

    References are supplied by the trusted service after immutable-store lookup;
    this pure function cannot authenticate them. Caller must persist original
    request/ontology before calling, including on failure. No partial output is
    returned on unsupported, incomplete or oversized input. No approval is granted.
    """
    for value in (workspace_id, execution_operation_id):
        _require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) is not None, 'Invalid saved operation/workspace identifier')
    outputs = _validate_artifacts(execution_artifact, approved_query_artifact)
    spec = projection_spec
    _keys(spec, 'row_class_iri columns null_policy subject_policy interpretation limitations')
    row_class = _iri(spec['row_class_iri'], local=True)
    _require(spec['null_policy'] == 'omit_with_manifest' and spec['subject_policy'] == 'execution_row_ordinal', 'Unsupported projection policy')
    _text(spec['interpretation'])
    _require(isinstance(spec['limitations'], list) and 1 <= len(spec['limitations']) <= 20, 'Projection limitations required')
    for limitation in spec['limitations']:
        _text(limitation)
    columns = spec['columns']
    _require(isinstance(columns, list) and 1 <= len(columns) <= MAX_COLUMNS, 'Projection column limit exceeded')
    seen_names, seen_predicates = set(), set()
    for column in columns:
        _keys(column, 'output_name predicate_iri datatype')
        name = column['output_name']
        _require(isinstance(name, str) and name in outputs and name not in seen_names, 'Unknown or duplicate output column')
        predicate = _iri(column['predicate_iri'], local=True)
        _require(predicate not in seen_predicates, 'Duplicate projection predicate')
        _require(column['datatype'] in ('text', 'integer'), 'Unsupported projection datatype')
        seen_names.add(name)
        seen_predicates.add(predicate)
    ontology = normalize_ontology(ontology_bytes)
    data, semantics, mapping, nulls = [], [], [], []
    rows = execution_artifact['rows']
    for ordinal, row in enumerate(rows):
        subject = URIRef(f'urn:factory-lab:query-result:{workspace_id}:{execution_operation_id}:row:{ordinal}')
        typed = (subject, RDF.type, row_class)
        semantics.append(typed)
        mapping.append({'partition': 'projection_semantics', 'triple': _nt([typed]).decode(),
                        'row_ordinal': ordinal, 'origin': 'reviewed_row_class_declaration'})
        for column in columns:
            name = column['output_name']
            value = row[name]
            origin = {'row_ordinal': ordinal, 'output_name': name, 'value': value,
                      'output_expression': outputs[name]}
            if value is None:
                nulls.append(origin)
                continue
            term = _literal(value, column['datatype'], name, outputs[name]['expression'], execution_artifact)
            triple = (subject, URIRef(column['predicate_iri']), term)
            data.append(triple)
            mapping.append({'partition': 'projection_data', 'triple': _nt([triple]).decode(), **origin})
    data_raw, semantic_raw = _nt(data), _nt(semantics)
    ontology_raw = ontology['normalized']['text'].encode('utf-8')
    triple_count = len(data) + len(semantics) + ontology['normalized']['triple_count']
    _require(triple_count <= MAX_TRIPLES, 'Combined projection exceeds triple limit')
    combined = data_raw + semantic_raw + ontology_raw
    _require(len(combined) <= MAX_COMBINED_BYTES, 'Combined RDF exceeds byte limit')
    provenance = execution_artifact['provenance']
    manifest = {
        'workspace_id': workspace_id, 'execution_operation_id': execution_operation_id,
        'source': deepcopy(provenance['source']),
        'execution_artifact_sha256': _fingerprint(execution_artifact),
        'approved_query_artifact_sha256': _fingerprint(approved_query_artifact),
        'contract_fingerprint': provenance['contract_fingerprint'],
        'dependency_fingerprint': provenance['dependency_fingerprint'],
        'dependencies': deepcopy(provenance['dependencies']),
        'parameters': deepcopy(provenance['parameters']), 'query_review': deepcopy(provenance['review']),
        'query_spec': deepcopy(approved_query_artifact['spec']),
        'query_status': execution_artifact['status'], 'query_truncated': execution_artifact['truncated'],
        'returned_count': len(rows), 'total_output_rows': execution_artifact['total_output_rows'],
        'matched_root_rows': execution_artifact.get('matched_root_rows'),
        'aggregate_null_exclusions': deepcopy(execution_artifact.get('aggregate_null_exclusions', {})),
        'query_output_kind': execution_artifact.get('output_kind'),
        'query_limitations': deepcopy(execution_artifact.get('limitations', [])),
        'query_scope': execution_artifact.get('scope'),
        'rows_are': 'immutable_query_result_observations_not_physical_entity_identity',
        'projection_complete': True, 'completeness_scope': 'declared_projection_of_saved_result_only',
        'unselected_columns': sorted(set(outputs) - seen_names), 'null_omissions': nulls,
        'null_counts': {c['output_name']: sum(n['output_name'] == c['output_name'] for n in nulls) for c in columns},
        'triple_origins': mapping,
        'limits': {'rows': MAX_ROWS, 'columns': MAX_COLUMNS, 'triples': MAX_TRIPLES,
                   'combined_bytes': MAX_COMBINED_BYTES, 'ontology_bytes': MAX_ONTOLOGY_BYTES,
                   'ontology_triples': MAX_ONTOLOGY_TRIPLES},
    }
    result = {'format': FORMAT, 'profile': 'rdfs', 'status': 'pending', 'approval': 'not_granted',
              'policy': 'advisory', 'source_binding': 'caller_must_verify_saved_store_and_current_revision',
              'projection_spec': deepcopy(spec), 'manifest': manifest,
              'projection_data': _partition(data_raw, triples=len(data)),
              'projection_semantics': _partition(semantic_raw, triples=len(semantics)),
              'ontology': ontology, 'combined_input': _partition(combined, triples=triple_count)}
    result['fingerprint'] = _fingerprint(result)
    return result
