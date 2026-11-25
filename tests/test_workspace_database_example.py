"""Real SQLite example registration and partial-review reuse, no model/network."""
from pathlib import Path
import pytest

from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_service import WorkspaceService


def test_example_uses_real_snapshot_and_no_implicit_approval(tmp_path):
    registry = SQLiteSources(tmp_path / 'registry')
    svc = WorkspaceService(tmp_path / 'workspaces.sqlite', database_registry=registry)
    row = svc.handle({'action': 'example_database'})
    assert row['database_example']['initial_generation'] == 'schema_observation_no_llm'
    assert len(row['draft']['sources']) == 3
    assert sum(s['row_count'] for s in row['draft']['sources']) == 11
    assert len(row['draft']['entries']) == 10
    assert all(e['status'] == 'pending' and e['interpretation'] == '' for e in row['draft']['entries'])
    assert len(row['draft']['relationship_proposals']) == 2
    assert row['row_lookup_catalog'] == []
    assert row['operations'] == [] and row['model_proposals']['enabled'] is False
    product = next(s for s in row['draft']['sources'] if s['name'] == 'products')
    assert product['row_count'] == 6 and len(product['sample']) == 5
    # Repeated creates share the immutable original, not the review decisions.
    second = svc.handle({'action': 'example_database'})
    assert second['id'] != row['id']
    assert second['draft']['database'] == row['draft']['database']
    assert len(list(registry.root.glob('*.json'))) == 1
    assert len(svc.store.list(False)) == 2
    field = next(e for e in row['draft']['entries'] if e['source']['file'] == 'products')
    rejected = svc.handle({'action': 'lookup', 'id': row['id'], 'revision': 1,
        'request_key': 'unapproved', 'selection': {'entry_id': field['id'], 'value': 'P-106'}})
    assert rejected['operation']['state'] == 'failed'
    meanings = {'sku': '商品番号', 'name': '商品名', 'available': '記録上の利用可能数'}
    decisions = [{'entry_id': e['id'], 'status': 'approved', 'target': 'source_only',
                  'note': '', 'interpretation': meanings[e['source']['column']]}
                 for e in row['draft']['entries'] if e['source']['file'] == 'products']
    reviewed = svc.handle({'action': 'change', 'id': row['id'], 'revision': 1, 'decisions': decisions})
    assert sum(e['status'] == 'approved' for e in reviewed['draft']['entries']) == 3
    assert sum(e['status'] == 'pending' for e in reviewed['draft']['entries']) == 7
    # P-106 lies beyond the five saved preview rows; full snapshot is queried.
    key = next(e for e in reviewed['draft']['entries'] if e['source']['file'] == 'products' and e['source']['column'] == 'sku')
    lookup = svc.handle({'action': 'lookup', 'id': row['id'], 'revision': 2,
        'request_key': 'reviewed', 'selection': {'entry_id': key['id'], 'value': 'P-106'}})
    assert lookup['operation']['state'] == 'completed'
    assert lookup['operation']['result']['records'][0]['values'] == {'sku': 'P-106', 'name': '텀블러', 'available': 5}
    assert lookup['operation']['result']['total_source_rows'] == 6
    assert svc.store.operation(row['id'], rejected['operation']['id']) == rejected['operation']
    assert svc.view(second['id'])['row_lookup_catalog'] == []


def test_only_trusted_registered_example_gets_walkthrough(tmp_path):
    registry = SQLiteSources(tmp_path / 'registry')
    svc = WorkspaceService(tmp_path / 'workspaces.sqlite', database_registry=registry)
    example = svc.handle({'action': 'example_database'})
    from apps.factory_lab.workspace_database_example import describe
    fake = {'database': {**example['draft']['database'], 'source_id': '0' * 32},
            'metadata': {'example_id': 'shop-sqlite-v1'}}
    assert describe(registry, fake) is None
    receipt = registry.root / 'shop-example-v1.receipt'
    receipt.write_text(receipt.read_text().replace('"sql_sha256": "', '"sql_sha256": "bad'))
    with pytest.raises(ValueError, match='definition changed'):
        svc.handle({'action': 'example_database'})
    assert len(svc.store.list(False)) == 1


def test_example_requires_operator_registry_and_accepts_no_browser_path(tmp_path):
    svc = WorkspaceService(tmp_path / 'workspaces.sqlite')
    with pytest.raises(ValueError, match='not configured'):
        svc.handle({'action': 'example_database'})
    with pytest.raises(ValueError, match='Unknown workspace action'):
        svc.handle({'action': 'example_database', 'path': '/tmp/user.sqlite'})
    assert svc.store.list(False) == []
