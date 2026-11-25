"""Catalog navigation is bounded and read-only, not a readiness certificate."""
from copy import deepcopy

import pytest

from apps.factory_lab.workspace_service import WorkspaceService
from apps.factory_lab.workspace_query_contracts import ReviewedQueryContracts
from tests.test_workspace_database_adapter import workspace


@pytest.fixture
def catalog_workspace(workspace, tmp_path):
    adapter, draft, _ = workspace
    service = WorkspaceService(tmp_path / 'catalog.sqlite', database_registry=adapter.registry)
    row = service.handle({'action': 'create_database', 'title': 'Catalog',
                          'source_id': draft['database']['source_id'], 'metadata': {}, 'domain': 'generic'})
    return service, row


def save(service, row, kind, key, result=None, state='completed', request=None):
    op, _ = service.store.begin(row['id'], row['revision'], key, kind, request or {})
    if state != 'running':
        service.store.finish(op['id'], state, result=result,
                             error='Preserved failure' if state == 'failed' else None)
    return op['id']


def catalog(service, row, category='query', cursor=None):
    return service.handle({'action': 'database_review_catalog', 'id': row['id'],
                           'revision': row['revision'], 'category': category, 'cursor': cursor})


def artifact(row, fingerprint='first', status='approved'):
    return {'artifact': {'spec': {'id': 'same_query', 'title': 'Same title',
                                'question_scope': 'Saved version', 'parameters': {'status': 'text'},
                                'output_kind': 'recorded_facts', 'policy_references': []},
                         'source': deepcopy(row['draft']['database']), 'fingerprint': fingerprint,
                         'status': status, 'review': {'revision': 1}},
            'relation_operation_ids': []}


def test_catalog_pages_preserve_versions_and_workspace_boundary(catalog_workspace):
    service, row = catalog_workspace
    older = save(service, row, 'database_query_approve', 'old', artifact(row),
                 request={'proposal_operation_id': 'older-proposal'})
    other = service.store.create('Other workspace', row['draft'])
    foreign = save(service, other, 'database_query_approve', 'foreign', artifact(other))
    for n in range(21):
        save(service, row, 'unrelated', f'noise-{n}', {})
    newer = save(service, row, 'database_query_approve', 'new', artifact(row, 'second'))
    page = catalog(service, row)
    assert [item['id'] for item in page['items']] == [newer]
    assert page['scanned_count'] == page['page_scan_limit'] == 20
    assert page['next_cursor'] is not None
    final = catalog(service, row, cursor=page['next_cursor'])
    assert [item['id'] for item in final['items']] == [older]
    assert final['next_cursor'] is None
    items = page['items'] + final['items']
    assert {item['logical_id'] for item in items} == {'same_query'}
    assert {item['fingerprint'] for item in items} == {'first', 'second'}
    assert foreign not in {item['id'] for item in items}
    # Category filtering does not consume unseen matches or imply an empty catalog.
    empty = catalog(service, row, category='paragraph')
    assert empty['items'] == [] and empty['next_cursor'] is not None


def test_catalog_does_not_restore_validate_execute_or_mutate(catalog_workspace, monkeypatch):
    service, row = catalog_workspace
    save(service, row, 'database_query_approve', 'approved', artifact(row))
    before = service.store.operations(row['id'])
    def forbidden(*args, **kwargs):
        raise AssertionError('Catalog must not do authoritative work or mutate storage')
    monkeypatch.setattr(service.store, 'begin', forbidden)
    monkeypatch.setattr(service.store, 'finish', forbidden)
    monkeypatch.setattr(type(service._database()), 'restore', forbidden)
    for method in ('propose', 'approve', 'execute', 'propose_relation', 'approve_relation'):
        monkeypatch.setattr(ReviewedQueryContracts, method, forbidden)
    page = catalog(service, row)
    item = page['items'][0]
    assert item['artifact_state'] == 'approved'
    assert item['operation_state'] == 'completed'
    assert item['readiness'] == 'unknown' and item['readiness_check'] == 'not_checked'
    assert item['readiness_reasons'][0]['code'] == 'authoritative_checks_not_run'
    assert service.store.operations(row['id']) == before
    capabilities = page['capabilities']
    engine = ReviewedQueryContracts(service._database())
    assert capabilities['query_families'] == ['relational', 'directed_reachability']
    reach = capabilities['directed_reachability']
    assert reach['node_budget_includes_seed'] is True
    assert reach['display_truncation_separate_from_closure'] is True
    assert reach['incomplete_total'] is None
    assert reach['identity_integer_encoding'] == 'decimal_integer_string'
    assert capabilities['limits']['max_rows'] == engine.max_rows
    assert capabilities['limits']['max_steps'] == engine.max_steps
    assert capabilities['filter_operators'] == ['eq', 'lt', 'lte', 'gt', 'gte', 'is_null']
    assert capabilities['aggregate_operators'] == ['sum', 'count_rows', 'count_distinct', 'sum_product']
    assert capabilities['sum_product']['unit'] == 'reviewed_annotation_not_dimensional_verification'
    assert capabilities['scalar_bindings']['client_value_override'] is False
    assert capabilities['typed_comparisons']['comparison'] == 'binary_exact'
    assert capabilities['documents_configured'] is False
    assert capabilities['readiness_preflight'] is False


def test_catalog_states_and_relation_paragraph_metadata(catalog_workspace):
    service, row = catalog_workspace
    pending = artifact(row, status='pending')
    proposal = save(service, row, 'database_query_propose', 'proposal', pending)
    failed = save(service, row, 'database_query_approve', 'failed', state='failed')
    running = save(service, row, 'database_query_approve', 'running', state='running')
    items = {item['id']: item for item in catalog(service, row)['items']}
    assert items[proposal]['artifact_state'] == 'pending'
    assert items[proposal]['proposal_operation_id'] == proposal
    for operation_id in (failed, running):
        assert items[operation_id]['artifact_state'] == 'not_saved'
        assert items[operation_id]['approval_operation_id'] is None
    relation = artifact(row)
    relation['artifact']['spec'] = {'id': 'owner', 'child_entry_id': 'c', 'parent_entry_id': 'p',
                                   'interpretation': 'Owner link', 'join_policy': 'left_many_to_one_preserve_root'}
    relation['artifact']['dependencies'] = {
        key: {'entry': {'source': {'file': table, 'column': 'code'}}}
        for key, table in [('c', 'records'), ('p', 'authors')]}
    relation_id = save(service, row, 'database_relation_approve', 'relation', relation)
    rel = catalog(service, row, 'relation')['items'][0]
    assert rel['id'] == relation_id
    assert rel['child'] == {'entry_id': 'c', 'table': 'records', 'column': 'code'}
    review = {'status': 'approved_reference', 'binding': row['draft']['database'],
              'interpretation': 'Reviewed meaning', 'paragraph': {
                  'document_id': 'doc', 'label': 'Policy', 'version': 'v1', 'document_sha256': 'hash',
                  'paragraph_id': 'p1', 'paragraph_sha256': 'paragraph-hash', 'line_start': 2, 'line_end': 4,
                  'text': 'Full text is loaded separately', 'source_path': '/private/operator/path'}}
    review_id = save(service, row, 'database_document_review', 'paragraph', review)
    paragraph = catalog(service, row, 'paragraph')['items'][0]
    assert paragraph['review_operation_id'] == review_id
    assert paragraph['artifact_state'] == 'approved_reference'
    assert paragraph['document']['line_start'] == 2
    assert 'source_path' not in paragraph['document'] and 'text' not in paragraph['document']


@pytest.mark.parametrize('category,cursor', [('all', None), ([], None), ('query', True), ('query', -1), ('query', '1')])
def test_catalog_rejects_invalid_pagination_without_operation(catalog_workspace, category, cursor):
    service, row = catalog_workspace
    before = service.store.operations(row['id'])
    with pytest.raises(ValueError):
        catalog(service, row, category, cursor)
    assert service.store.operations(row['id']) == before
