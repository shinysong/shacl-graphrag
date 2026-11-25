"""Authored artifact boundary tests, no services, native process or gold."""
from copy import deepcopy
import hashlib
import json

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from apps.factory_lab.workspace_query_projection import (
    build_projection, normalize_ontology, ProjectionError, NAMESPACE,
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def inputs(rows=None, product=False):
    if rows is None:
        rows = [{'identifier': 'O1', 'quantity': 7}, {'identifier': 'O2', 'quantity': None}]
    spec = {'id': 'authored', 'title': 'Authored recorded quantity', 'question_scope': 'Recorded quantities only',
            'parameters': {'status': 'text'},
            'projection': [{'name': 'identifier', 'field': {'entry_id': 'id', 'alias': 'r'}}],
            'aggregates': [{'name': 'quantity', 'op': 'sum_product' if product else 'sum',
                            'field': {'entry_id': 'quantity', 'alias': 'r'}}]}
    body = {'version': 'reviewed-query-2' if product else 'reviewed-query-1', 'kind': 'query', 'spec': spec,
            'source': {'source_id': 'source', 'snapshot_sha256': 'a' * 64},
            'dependencies': {'fields': {'quantity': {'entry': {'interpretation': 'Recorded units'},
                'external_annotations': [{'operation_id': 'original-import', 'raw_sha256': 'b' * 64}]}},
                'relations': {'order': {'origin': {'import_operation_id': 'current-import'}}}},
            'origin': {'kind': 'authored-test'}}
    approved = {**body, 'fingerprint': digest(body), 'status': 'approved'}
    approved['review'] = {'human_confirmed': True, 'approved_fingerprint': approved['fingerprint'],
                          'actor': 'scripted', 'note': 'Not expert validation', 'revision': 2}
    result = {'version': body['version'], 'status': 'complete', 'truncated': False,
              'rows': rows, 'returned_count': len(rows), 'total_output_rows': len(rows),
              'matched_root_rows': 12, 'aggregate_null_exclusions': {'quantity': 1},
              'scope': 'complete_registered_snapshot_query_not_external_truth',
              'output_kind': 'recorded_facts', 'limitations': ['Authored test only'],
              'provenance': {k: deepcopy(approved[k]) for k in ('source', 'dependencies', 'origin', 'review')}}
    result['provenance'].update(contract_fingerprint=approved['fingerprint'],
        dependency_fingerprint=digest(approved['dependencies']), parameters={'status': 'delivered'})
    if product:
        result['product_aggregate_observations'] = {'quantity': {'value_encoding': 'decimal_integer_string'}}
    projection = {'row_class_iri': NAMESPACE + 'QuantityObservation',
        'columns': [{'output_name': 'identifier', 'predicate_iri': NAMESPACE + 'identifier', 'datatype': 'text'},
                    {'output_name': 'quantity', 'predicate_iri': NAMESPACE + 'quantity', 'datatype': 'integer'}],
        'null_policy': 'omit_with_manifest', 'subject_policy': 'execution_row_ordinal',
        'interpretation': 'Recorded query result observation, not entity identity',
        'limitations': ['Query aggregates are not physical source records']}
    ontology = ('@prefix ex: <' + NAMESPACE + '> .\n'
                '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
                'ex:QuantityObservation rdfs:subClassOf ex:ReviewEvidence .\n').encode()
    return result, dict(workspace_id='work', execution_operation_id='exec',
        approved_query_artifact=approved, projection_spec=projection, ontology_bytes=ontology)


def test_deterministic_immutable_projection_and_partition_provenance():
    result, kwargs = inputs()
    before = deepcopy((result, kwargs))
    first = build_projection(result, **kwargs)
    second = build_projection(result, **kwargs)
    assert first == second and (result, kwargs) == before
    manifest = first['manifest']
    assert manifest['source'] == result['provenance']['source']
    assert manifest['dependencies'] == result['provenance']['dependencies']
    assert manifest['query_spec'] == kwargs['approved_query_artifact']['spec']
    assert manifest['rows_are'] == 'immutable_query_result_observations_not_physical_entity_identity'
    assert manifest['null_counts'] == {'identifier': 0, 'quantity': 1}
    assert manifest['null_omissions'][0]['row_ordinal'] == 1
    assert first['projection_data']['triple_count'] == 3
    assert first['projection_semantics']['triple_count'] == 2
    assert first['ontology']['original']['text'].encode() == kwargs['ontology_bytes']
    assert first['combined_input']['text'] == ''.join([
        first['projection_data']['text'], first['projection_semantics']['text'], first['ontology']['normalized']['text']])
    assert first['approval'] == 'not_granted' and first['status'] == 'pending'
    assert manifest['projection_complete'] is True
    assert manifest['completeness_scope'] == 'declared_projection_of_saved_result_only'


def test_unicode_escaping_and_injection_remain_one_literal():
    value = '한글 🧪 " \\ \n <urn:evil> <urn:p> <urn:o> .\r\t'
    result, kwargs = inputs([{'identifier': value, 'quantity': -(2**63)}])
    projected = build_projection(result, **kwargs)
    graph = Graph().parse(data=projected['projection_data']['text'], format='nt')
    subject = URIRef('urn:factory-lab:query-result:work:exec:row:0')
    assert len(graph) == 2
    assert graph.value(subject, URIRef(NAMESPACE + 'identifier')) == Literal(value, datatype=XSD.string)
    assert graph.value(subject, URIRef(NAMESPACE + 'quantity')).toPython() == -(2**63)


def test_duplicate_rows_remain_distinct_observations():
    result, kwargs = inputs([{'identifier': 'same', 'quantity': 1}] * 2)
    projected = build_projection(result, **kwargs)
    graph = Graph().parse(data=projected['projection_data']['text'], format='nt')
    assert len(set(graph.subjects())) == 2 and len(graph) == 4
    semantics = Graph().parse(data=projected['projection_semantics']['text'], format='nt')
    assert len(list(semantics.triples((None, RDF.type, None)))) == 2


def test_zero_rows_still_validate_columns_from_approved_spec():
    result, kwargs = inputs([])
    projected = build_projection(result, **kwargs)
    assert projected['projection_data']['triple_count'] == 0
    assert projected['manifest']['returned_count'] == 0
    kwargs['projection_spec']['columns'][0]['output_name'] = 'absent'
    with pytest.raises(ProjectionError, match='Unknown'):
        build_projection(result, **kwargs)


@pytest.mark.parametrize('value', [2**63, -(2**63)-1, True, 3.0, '3'])
def test_invalid_integer_or_ambiguous_string_rejected(value):
    result, kwargs = inputs([{'identifier': 'one', 'quantity': value}])
    with pytest.raises(ProjectionError):
        build_projection(result, **kwargs)


def test_product_exact_integer_string_and_encoding_metadata():
    result, kwargs = inputs([{'identifier': 'one', 'quantity': str(2**63-1)}], product=True)
    projected = build_projection(result, **kwargs)
    graph = Graph().parse(data=projected['projection_data']['text'], format='nt')
    assert list(graph.objects(None, URIRef(NAMESPACE + 'quantity')))[0].toPython() == 2**63-1
    del result['product_aggregate_observations']
    with pytest.raises(ProjectionError, match='encoding metadata'):
        build_projection(result, **kwargs)


@pytest.mark.parametrize('value', ['01', '+1', '-0', str(2**63), '1e3'])
def test_product_noncanonical_or_overflow_strings_fail(value):
    result, kwargs = inputs([{'identifier': 'one', 'quantity': value}], product=True)
    with pytest.raises(ProjectionError):
        build_projection(result, **kwargs)


def test_wrong_text_type_and_nonfinite_json_fail():
    result, kwargs = inputs([{'identifier': 4, 'quantity': 1}])
    with pytest.raises(ProjectionError, match='Text'):
        build_projection(result, **kwargs)
    result['rows'][0]['quantity'] = float('nan')
    with pytest.raises(ProjectionError, match='finite'):
        build_projection(result, **kwargs)


@pytest.mark.parametrize('change', [
    lambda r: r.update(truncated=True),
    lambda r: r.update(status='partial'),
    lambda r: r.update(returned_count=1),
    lambda r: r.update(total_output_rows=True),
    lambda r: r.update(query_kind='directed_reachability'),
    lambda r: r['rows'][0].update(extra='unapproved'),
    lambda r: r['provenance'].update(contract_fingerprint='c'*64),
    lambda r: r['provenance']['source'].update(snapshot_sha256='c'*64),
    lambda r: r['provenance']['parameters'].update(extra='unknown'),
    lambda r: r['provenance']['dependencies']['fields'].clear(),
])
def test_incomplete_or_mismatched_saved_artifacts_rejected(change):
    result, kwargs = inputs()
    change(result)
    with pytest.raises(ProjectionError):
        build_projection(result, **kwargs)


def test_changed_approved_spec_fails_fingerprint_binding():
    result, kwargs = inputs()
    kwargs['approved_query_artifact']['spec']['title'] = 'changed'
    with pytest.raises(ProjectionError, match='fingerprint'):
        build_projection(result, **kwargs)


@pytest.mark.parametrize('change', [
    lambda p: p['columns'].append(dict(p['columns'][0])),
    lambda p: p['columns'][0].update(datatype='date'),
    lambda p: p['columns'][0].update(predicate_iri='https://external.invalid/p'),
    lambda p: p.update(row_class_iri='urn:factory-lab:semantics:bad>'),
    lambda p: p.update(subject_policy='entity_id'),
    lambda p: p.update(null_policy='infer_absence'),
    lambda p: p.update(extra='unsupported'),
    lambda p: p.update(limitations=[]),
])
def test_unsupported_projection_contract_rejected(change):
    result, kwargs = inputs()
    change(kwargs['projection_spec'])
    with pytest.raises(ProjectionError):
        build_projection(result, **kwargs)


def test_subset_projection_retains_explicit_unselected_columns():
    result, kwargs = inputs()
    kwargs['projection_spec']['columns'] = kwargs['projection_spec']['columns'][:1]
    projected = build_projection(result, **kwargs)
    assert projected['manifest']['unselected_columns'] == ['quantity']
    assert projected['manifest']['null_omissions'] == []


@pytest.mark.parametrize('raw', [
    b'<urn:a> <http://www.w3.org/2002/07/owl#imports> <https://example.invalid/> .',
    b'<urn:a> a <urn:b> .',
    b'<urn:a> <http://www.w3.org/2000/01/rdf-schema#label> "label" .',
    b'[] <http://www.w3.org/2000/01/rdf-schema#subClassOf> <urn:b> .',
    b'<urn:a> <http://www.w3.org/2000/01/rdf-schema#subClassOf> "literal" .',
    b'<relative> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <urn:b> .',
    b'@base <https://example.invalid/> . <urn:a> <urn:p> <urn:b> .',
    b'BASE <https://example.invalid/> <urn:a> <urn:p> <urn:b> .',
    b'@prefix ex: <relative/> . ex:a ex:p ex:b .',
    b'@prefix ex: <> . ex:a ex:p ex:b .',
    b'not turtle', b'\xff',
])
def test_unsupported_ontology_no_silent_stripping(raw):
    with pytest.raises(ProjectionError):
        normalize_ontology(raw)


def test_ontology_order_normalized_but_original_bytes_preserved():
    first = b'<urn:a> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <urn:b> .\n'
    second = b'<urn:p> <http://www.w3.org/2000/01/rdf-schema#range> <urn:b> .\n'
    a, b = normalize_ontology(first + second), normalize_ontology(second + first)
    assert a['normalized'] == b['normalized']
    assert a['original']['sha256'] != b['original']['sha256']
    assert a['normalized']['triple_count'] == 2


def test_bounds_no_partial_projection():
    result, kwargs = inputs([{'identifier': 'one', 'quantity': 1}] * 201)
    with pytest.raises(ProjectionError, match='row limit'):
        build_projection(result, **kwargs)
    result, kwargs = inputs([{'identifier': 'x' * 65536, 'quantity': 1}])
    with pytest.raises(ProjectionError, match='byte limit'):
        build_projection(result, **kwargs)
    result, kwargs = inputs()
    kwargs['projection_spec']['columns'] *= 11
    with pytest.raises(ProjectionError, match='column limit'):
        build_projection(result, **kwargs)
    with pytest.raises(ProjectionError, match='byte limit'):
        normalize_ontology(b' ' * 16385)
    triples = b''.join(f'<urn:a{i}> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <urn:b> .\n'.encode() for i in range(129))
    with pytest.raises(ProjectionError, match='triple limit'):
        normalize_ontology(triples)
