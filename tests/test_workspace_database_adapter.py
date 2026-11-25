"""Offline adapter boundary tests; no business benchmark or paid calls."""
from copy import deepcopy
import json
import sqlite3

import pytest

from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_database_adapter import DatabaseWorkspaceAdapter


@pytest.fixture
def workspace(tmp_path):
    path = tmp_path / 'operator.sqlite'
    with sqlite3.connect(path) as con:
        con.executescript('''
            CREATE TABLE authors (code TEXT PRIMARY KEY, label TEXT);
            CREATE TABLE "odd records" (
                "arbitrary key" INTEGER PRIMARY KEY,
                "source code" TEXT REFERENCES authors(code),
                "unfamiliar field" TEXT, private_note TEXT);
        ''')
        con.execute('INSERT INTO authors VALUES (?, ?)', ('owner', 'Example'))
        con.executemany('INSERT INTO "odd records" VALUES (?, ?, ?, ?)',
                        ((i, 'owner', f'value-{i}', 'unreviewed') for i in range(12017)))
    registry = SQLiteSources(tmp_path / 'private-registry')
    registered = registry.register(path)
    adapter = DatabaseWorkspaceAdapter(registry)
    return adapter, adapter.create(registered['source_id']), path


def approve(adapter, draft, column, table='odd records'):
    entry = next(e for e in draft['entries'] if e['source']['file'] == table
                 and e['source']['column'] == column)
    updated = adapter.change(draft, entry['id'], 'approved', interpretation='Reviewed raw field')
    return updated, entry['id']


def test_whole_snapshot_late_row_and_only_approved_fields(workspace):
    adapter, draft, _ = workspace
    table = next(s for s in draft['sources'] if s['name'] == 'odd records')
    assert table['row_count'] == 12017
    assert len(table['sample']) == 5
    assert 'rows' not in table
    assert all(e['status'] == 'pending' for e in draft['entries'])
    assert adapter.row_catalog(draft) == []
    assert draft['capabilities']['document_policy'] == 'unsupported'
    draft, key = approve(adapter, draft, 'arbitrary key')
    draft, _ = approve(adapter, draft, 'unfamiliar field')
    result = adapter.execute_rows(draft, {'entry_id': key, 'value': 12016})
    assert result['records'][0]['values'] == {'arbitrary key': 12016, 'unfamiliar field': 'value-12016'}
    assert result['total_matching_rows'] == result['returned_count'] == 1
    assert result['total_source_rows'] == 12017
    assert result['source_version'] == draft['database']['snapshot_sha256']
    assert not result['truncated']
    assert 'private_note' in result['unreviewed_fields']
    serialized = json.dumps(draft)
    assert 'operator.sqlite' not in serialized and 'private-registry' not in serialized


def test_duplicate_values_have_exact_count_and_bound(workspace):
    adapter, draft, _ = workspace
    draft, key = approve(adapter, draft, 'source code')
    result = adapter.execute_rows(draft, {'entry_id': key, 'value': 'owner'}, limit=3)
    assert result['total_matching_rows'] == 12017
    assert result['returned_count'] == result['limit'] == 3
    assert result['truncated']
    assert len(result['records']) == 3
    absent = adapter.execute_rows(draft, {'entry_id': key, 'value': 'absent'})
    assert absent['status'] == 'not_found_in_snapshot'
    assert absent['total_matching_rows'] == 0
    assert not absent['truncated']


def test_foreign_keys_preserved_not_autoapproved(workspace):
    adapter, draft, _ = workspace
    proposal = draft['relationship_proposals'][0]
    assert proposal['declaration']['table'] == 'authors'
    assert proposal['declaration']['from'] == 'source code'
    assert proposal['status'] == 'pending' and not proposal['executable']
    changed = deepcopy(draft)
    changed['relationship_proposals'][0]['status'] = 'approved'
    with pytest.raises(ValueError):
        adapter.restore(changed)


@pytest.mark.parametrize('domain', ['healthcare', 'finance', 'manufacturing'])
def test_domain_label_never_changes_arbitrary_schema(workspace, domain):
    adapter, draft, _ = workspace
    other = adapter.create(draft['database']['source_id'], domain=domain)
    assert other['entries'] == draft['entries']
    assert other['sources'] == draft['sources']
    assert other['adapter'] == 'registered-database-1'
    assert not any(e['target'].startswith('products.') for e in other['entries'])


def test_pending_approval_and_interpretation_required(workspace):
    adapter, draft, _ = workspace
    key = draft['entries'][0]['id']
    with pytest.raises(ValueError, match='Review'):
        adapter.execute_rows(draft, {'entry_id': key, 'value': 'owner'})
    with pytest.raises(ValueError, match='interpretation'):
        adapter.change(draft, key, 'approved')
    with pytest.raises(ValueError):
        adapter.change(draft, key, 'excluded')
    with pytest.raises(ValueError):
        adapter.change(draft, key, 'approved', target='products.id', interpretation='Wrong domain')


@pytest.mark.parametrize('mutation', ['hash', 'field', 'missing', 'id', 'table', 'source_id'])
def test_source_binding_tamper_fails_closed(workspace, mutation):
    adapter, draft, _ = workspace
    changed = deepcopy(draft)
    if mutation == 'hash':
        changed['database']['snapshot_sha256'] = '0' * 64
    elif mutation == 'field':
        changed['entries'][0]['source']['column'] = 'missing'
    elif mutation == 'missing':
        changed['entries'].pop()
    elif mutation == 'id':
        changed['entries'][0]['id'] = 'wrong'
    elif mutation == 'table':
        changed['sources'][0]['headers'].append('missing')
    elif mutation == 'source_id':
        changed['database']['source_id'] = '/etc/passwd'
    with pytest.raises(ValueError):
        adapter.restore(changed)


def test_snapshot_bytes_fail_closed_and_mutable_source_stays_separate(workspace):
    adapter, draft, path = workspace
    draft, key = approve(adapter, draft, 'arbitrary key')
    with sqlite3.connect(path) as con:
        con.execute('DELETE FROM "odd records"')
    result = adapter.execute_rows(draft, {'entry_id': key, 'value': 12016})
    assert result['returned_count'] == 1
    source_id = draft['database']['source_id']
    assert adapter.registry.check_drift(source_id)['status'] == 'changed'
    snapshot = adapter.registry.root / (source_id + '.sqlite')
    snapshot.chmod(0o600)
    with snapshot.open('ab') as stream:
        stream.write(b'tamper')
    with pytest.raises(ValueError, match='integrity'):
        adapter.execute_rows(draft, {'entry_id': key, 'value': 12016})


@pytest.mark.parametrize('value', [True, [], {}, float('inf'), 'x' * 2001])
def test_unsupported_filter_values(workspace, value):
    adapter, draft, _ = workspace
    draft, key = approve(adapter, draft, 'arbitrary key')
    with pytest.raises(ValueError):
        adapter.execute_rows(draft, {'entry_id': key, 'value': value})


def test_no_sql_paths_or_unbounded_queries(workspace):
    adapter, draft, _ = workspace
    draft, key = approve(adapter, draft, 'source code')
    for selection in ({'sql': 'SELECT * FROM authors'},
                      {'entry_id': key, 'value': 'owner', 'path': '/tmp/other.sqlite'},
                      {'entry_id': key, 'value': 'owner', 'columns': ['private_note']}):
        with pytest.raises(ValueError):
            adapter.execute_rows(draft, selection)
    for limit in (0, 201, True, '50'):
        with pytest.raises(ValueError):
            adapter.execute_rows(draft, {'entry_id': key, 'value': 'owner'}, limit=limit)
    injection = adapter.execute_rows(draft, {'entry_id': key, 'value': "' OR 1=1 --"})
    assert injection['total_matching_rows'] == 0
