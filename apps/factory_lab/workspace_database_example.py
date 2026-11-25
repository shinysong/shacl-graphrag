"""One opt-in, synthetic SQLite example through the real registered DB boundary.

Only trusted packaged SQL is executed to create an owned local source; browsers
supply no path, connection string, SQL, target, interpretation or approval.
Repeated creates reuse one verified registry snapshot and create new workspaces.
"""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading

_LOCK = threading.Lock()
SQL = Path(__file__).resolve().parents[2] / 'examples/factory_lab/database-onboarding/shop.sql'
EXAMPLE_ID = 'shop-sqlite-v1'


def create(adapter):
    registry = adapter.registry
    with _LOCK:
        raw = SQL.read_bytes()
        source_hash = hashlib.sha256(raw).hexdigest()
        marker = registry.root / 'shop-example-v1.receipt'
        if marker.exists():
            saved = json.loads(marker.read_text())
            if saved['sql_sha256'] != source_hash:
                raise ValueError('Example definition changed; register a new example version')
            info = registry.inspect(saved['source_id'], sample_limit=1)
            if info['snapshot_sha256'] != saved['snapshot_sha256']:
                raise ValueError('Example source binding changed')
        else:
            # Private operator-owned location. Register a whole immutable snapshot
            # through the same capture/inspection path as other SQLite sources.
            with tempfile.TemporaryDirectory(prefix='shop-example-', dir=registry.root) as folder:
                path = Path(folder) / 'shop.sqlite'
                with closing(sqlite3.connect(path)) as db:
                    db.executescript(raw.decode('utf-8'))
                    if db.execute('PRAGMA foreign_key_check').fetchall():
                        raise ValueError('Packaged example has invalid foreign keys')
                # Retain the original source as well as its registered snapshot.
                path.replace(registry.root / 'shop-example-v1.source')
            info = registry.register(registry.root / 'shop-example-v1.source', label='예시 DB · 쇼핑몰 주문과 상품')
            descriptor = {'source_id': info['source_id'], 'snapshot_sha256': info['snapshot_sha256'],
                          'sql_sha256': source_hash, 'example_id': EXAMPLE_ID}
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as stream:
                json.dump(descriptor, stream)
        return adapter.create(info['source_id'], {
            'example_id': EXAMPLE_ID, 'data_origin': 'authored_synthetic',
            'license': 'CC0-1.0', 'definition_sha256': source_hash,
            'mapping_generation': 'schema_observation_no_llm',
        }, domain='쇼핑몰 SQLite 예시')


def describe(registry, draft):
    """Recognize the owned example by registry binding, never client metadata."""
    marker = registry.root / 'shop-example-v1.receipt'
    if not marker.exists():
        return None
    saved = json.loads(marker.read_text())
    database = draft.get('database', {})
    if (saved.get('example_id') != EXAMPLE_ID or
            saved.get('sql_sha256') != hashlib.sha256(SQL.read_bytes()).hexdigest() or
            database.get('source_id') != saved.get('source_id') or
            database.get('snapshot_sha256') != saved.get('snapshot_sha256')):
        return None
    return {'id': EXAMPLE_ID, 'origin': 'authored_synthetic', 'license': 'CC0-1.0',
            'initial_generation': 'schema_observation_no_llm',
            'table_count': 3, 'row_count': 11}
