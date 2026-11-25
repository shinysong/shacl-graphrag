"""Inert resolution controls, authored native-schema fixtures; no upstream calls."""
from copy import deepcopy
from hashlib import sha256

import pytest
import yaml

from apps.factory_lab.workspace_extension_relations import resolve_relation
from apps.factory_lab.workspace_extensions import import_auto_ontology
from apps.factory_lab.workspace_store import encode


def fixture(change=None, semantic=True):
    tables = [{'id': 't1', 'name': 'lines', 'columns': [
        {'id': 'c1', 'name': 'owner'}]}, {'id': 't2', 'name': 'owners', 'pk': ['id'],
        'columns': [{'id': 'c2', 'name': 'id'}, {'id': 'c3', 'name': 'other'}]}]
    doc = {'data_layer': {'databases': [{'id': 'db', 'schemas': [
        {'id': 'schema', 'name': 'main', 'tables': tables}]}],
        'foreign_keys': [{'source_column_id': 'c1', 'target_column_id': 'c2'}]},
        'semantic_layer': {'terms': [{'id': 'term', 'represents': ['t2'],
            'columns_attributes': [{'id': 'attr', 'column_id': 'c2'}]}],
            'concepts': [{'id': 'concept', 'term_ids': ['term'],
                'keys': [{'id': 'key', 'column_ids': ['c2']}]}],
            'semantic_fks': [{'column_id': 'c1', 'concept_key_id': 'key',
                'column_attribute_id': 'attr', 'use_in_join_paths': True}]}}
    if change:
        change(doc)
    h = 'b' * 64
    draft = {'adapter': 'registered-database-1',
        'database': {'source_id': 'registered', 'snapshot_sha256': h},
        'sources': [{'name': 'lines', 'sha256': h, 'headers': ['owner']},
                    {'name': 'owners', 'sha256': h, 'headers': ['id', 'other']}],
        'entries': [{'id': eid, 'kind': 'mapping', 'status': 'approved',
            'source': {'file': table, 'column': column, 'sha256': h}}
            for eid, table, column in [('e1', 'lines', 'owner'), ('e2', 'owners', 'id'), ('e3', 'owners', 'other')]]}
    row = {'id': 'workspace', 'revision': 2, 'draft': draft,
           'digest': sha256(encode(draft).encode()).hexdigest()}
    proposal = import_auto_ontology(yaml.safe_dump(doc).encode(),
        base_workspace_digest=row['digest'], source_hashes={'lines': h, 'owners': h})
    op = {'id': 'import', 'workspace': row['id'], 'revision': 2,
          'kind': 'extension_import', 'state': 'completed', 'result': proposal}
    args = {'candidate_id': proposal['relations'][1 if semantic else 0]['id'],
        'child_entry_id': 'e1', 'parent_entry_id': 'e2', 'interpretation': 'Recorded owner reference'}
    return op, row, args


@pytest.mark.parametrize('semantic', [False, True])
def test_supported_binding_is_inert_and_preserves_inputs(semantic):
    op, row, args = fixture(semantic=semantic)
    before = deepcopy((op, row))
    result = resolve_relation(op, row, **args)
    assert result['native_endpoints']['parent'] == {'table': 'owners', 'column': 'id'}
    assert result['approval'] == 'not_granted'
    assert result['producer_authenticated'] is False
    assert result['upstream_input_verified'] is False
    assert result['raw_sha256'] == op['result']['raw_sha256']
    assert (op, row) == before


def test_explicit_endpoint_edit_retains_original():
    op, row, args = fixture()
    args['parent_entry_id'] = 'e3'
    with pytest.raises(ValueError, match='explicit reason'):
        resolve_relation(op, row, **args)
    result = resolve_relation(op, row, **args, edit_reason='Local revised endpoint; engine check still required')
    assert result['endpoint_edit'] is True
    assert result['native_endpoints']['parent']['column'] == 'id'
    assert result['chosen_endpoints']['parent']['column'] == 'other'


@pytest.mark.parametrize('mutation', [
    lambda d: d['semantic_layer']['concepts'][0]['keys'][0].update(column_ids=['c2', 'c3']),
    lambda d: d['semantic_layer']['terms'][0]['columns_attributes'][0].update(column_id='c3'),
    lambda d: d['semantic_layer']['semantic_fks'][0].update(concept_key_id='missing'),
    lambda d: d['semantic_layer']['semantic_fks'][0].update(join_columns='DROP TABLE owners'),
    lambda d: d['semantic_layer']['semantic_fks'][0].update(use_in_join_paths='yes'),
    lambda d: d['semantic_layer']['semantic_fks'][0].update(executable=True),
    lambda d: d['semantic_layer']['concepts'][0]['keys'][0].update(expression='SELECT 1'),
    lambda d: d['data_layer']['databases'][0]['schemas'][0]['tables'][1]['columns'][0].update(sql='SELECT 1'),
])
def test_unsupported_and_conflicting_candidates(mutation):
    op, row, args = fixture(mutation)
    with pytest.raises(ValueError):
        resolve_relation(op, row, **args)


def test_unrelated_unsupported_content_does_not_enable_or_block_relation():
    op, row, args = fixture(lambda d: d['semantic_layer'].update(sql_attributes={'sql': ['SELECT 1']}))
    result = resolve_relation(op, row, **args)
    assert 'SELECT' not in encode(result)


@pytest.mark.parametrize('target', ['attribute', 'key'])
def test_single_semantic_target_is_supported(target):
    def change(doc):
        doc['semantic_layer']['semantic_fks'][0].pop(
            'concept_key_id' if target == 'attribute' else 'column_attribute_id')
    op, row, args = fixture(change)
    assert resolve_relation(op, row, **args)['endpoint_edit'] is False


def test_duplicate_native_column_names_are_not_guessed():
    def change(doc):
        doc['data_layer']['databases'][0]['schemas'][0]['tables'][1]['columns'][1]['name'] = 'id'
    op, row, args = fixture(change)
    with pytest.raises(ValueError, match='Ambiguous native column'):
        resolve_relation(op, row, **args)


@pytest.mark.parametrize('mutation', [
    lambda op, row: op.update(revision=1),
    lambda op, row: op.update(workspace='other'),
    lambda op, row: op.update(state='failed'),
    lambda op, row: op['result'].update(base_workspace_digest='c' * 64),
    lambda op, row: op['result']['source_hashes'].update(lines='c' * 64),
    lambda op, row: row['draft']['entries'][0].update(status='pending'),
    lambda op, row: op['result']['relations'][1]['source_payload'].update(column_id='c3'),
    lambda op, row: op['result'].update(raw_base64='!'),
    lambda op, row: op['result'].update(raw_sha256='0' * 64),
])
def test_stale_tampered_and_malformed_bindings(mutation):
    op, row, args = fixture()
    mutation(op, row)
    with pytest.raises(ValueError):
        resolve_relation(op, row, **args)


def test_pending_field_rejected_even_with_consistent_digest():
    op, row, args = fixture()
    row['draft']['entries'][0]['status'] = 'pending'
    row['digest'] = sha256(encode(row['draft']).encode()).hexdigest()
    op['result']['base_workspace_digest'] = row['digest']
    with pytest.raises(ValueError, match='needs approval'):
        resolve_relation(op, row, **args)


def test_table_join_is_not_executable():
    op, row, args = fixture(lambda d: d['data_layer'].update(joins=[{'source_table_id': 't1', 'target_table_id': 't2'}]))
    args['candidate_id'] = next(r['id'] for r in op['result']['relations'] if r['kind'] == 'joins')
    with pytest.raises(ValueError, match='Unsupported relation kind'):
        resolve_relation(op, row, **args)


def test_bound_and_malformed_entry_points():
    op, row, args = fixture()
    with pytest.raises(ValueError):
        resolve_relation({}, row, **args)
    args['interpretation'] = 'x' * 4001
    with pytest.raises(ValueError):
        resolve_relation(op, row, **args)
