"""Operator-registered SQLite snapshots, never arbitrary model SQL.

Registration is a trusted local operation, not an HTTP upload/path parameter.
The private registry contains paths; public descriptors never do. SQLite's backup
API captures a consistent committed database including WAL contents. Reads use
hash-verified snapshot bytes in a query-only connection, not the mutable source.
Drift checks are observations at check time, not promises of continued freshness.
"""
from contextlib import closing, contextmanager
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import time
import uuid


class DatabaseSourceError(ValueError):
    """Safe to display: messages deliberately omit private paths/SQL."""


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _bounded(value, maximum, label):
    if type(value) is not int or not 1 <= value <= maximum:
        raise DatabaseSourceError(f'{label} is outside the allowed bound')
    return value


def _digest(data):
    return hashlib.sha256(data).hexdigest()


class SQLiteSources:
    """Private local registry. Give browsers only inspect()/lookup() results.

    Whole database snapshots are limited by bytes/time, never by a row prefix.
    No views/virtual tables are exposed. Filters are exact SQLite equality (IS
    for NULL), not business identifiers or semantic interpretation. Operators
    must register only data they authorize users to inspect.
    """

    def __init__(self, private_directory, *, max_bytes=256 * 1024 * 1024, timeout=10):
        self.root = Path(private_directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.max_bytes = max_bytes
        self.timeout = timeout

    def _capture(self, source):
        deadline = time.monotonic() + self.timeout
        def progress(status, remaining, total):
            if time.monotonic() > deadline:
                raise DatabaseSourceError('Source snapshot timed out')
            if total * page_size > self.max_bytes:
                raise DatabaseSourceError('Source snapshot exceeds byte limit')
        try:
            with tempfile.TemporaryDirectory(dir=self.root) as folder:
                target = Path(folder) / 'capture.sqlite'
                with closing(sqlite3.connect(Path(source).as_uri() + '?mode=ro', uri=True,
                                     timeout=self.timeout)) as src:
                    src.execute('PRAGMA query_only=ON')
                    page_size = src.execute('PRAGMA page_size').fetchone()[0]
                    with closing(sqlite3.connect(target)) as dst:
                        src.backup(dst, pages=128, progress=progress, sleep=0.01)
                        # Normalize the owned copy only: deserialize cannot open
                        # a WAL-mode image without filesystem sidecars.
                        dst.execute('PRAGMA journal_mode=DELETE')
                if target.stat().st_size > self.max_bytes:
                    raise DatabaseSourceError('Source snapshot exceeds byte limit')
                return target.read_bytes()
        except (sqlite3.Error, OSError):
            raise DatabaseSourceError('Source snapshot unavailable or invalid') from None

    def register(self, source_path, *, label='SQLite source'):
        """Trusted operator only; returns a public opaque descriptor."""
        if not isinstance(label, str) or not 1 <= len(label) <= 120:
            raise DatabaseSourceError('Provide a short public source label')
        source = Path(source_path).resolve()
        data = self._capture(source)
        source_id = uuid.uuid4().hex
        record = {'source_id': source_id, 'label': label,
                  'snapshot_sha256': _digest(data), 'snapshot_bytes': len(data),
                  'source_path': str(source), 'format': 'sqlite-snapshot-v1'}
        # Validate supported tables before registering anything durable.
        with self._connection(data) as con:
            self._catalog(con)
        snapshot = self.root / (source_id + '.sqlite')
        snapshot.write_bytes(data)
        snapshot.chmod(0o400)
        manifest = self.root / (source_id + '.json')
        manifest.write_text(json.dumps(record), encoding='utf-8')
        manifest.chmod(0o600)
        return self._public(record)

    def _record(self, source_id):
        if not isinstance(source_id, str) or len(source_id) != 32 or any(c not in '0123456789abcdef' for c in source_id):
            raise DatabaseSourceError('Unknown registered source')
        try:
            return json.loads((self.root / (source_id + '.json')).read_text())
        except (OSError, ValueError):
            raise DatabaseSourceError('Unknown registered source') from None

    @staticmethod
    def _public(record):
        return {k: record[k] for k in ('source_id', 'label', 'snapshot_sha256',
                                      'snapshot_bytes', 'format')}

    @contextmanager
    def _connection(self, data):
        con = sqlite3.connect(':memory:')
        try:
            con.deserialize(data)
            con.execute('PRAGMA trusted_schema=OFF')
            con.execute('PRAGMA query_only=ON')
            deadline = time.monotonic() + self.timeout
            con.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            con.row_factory = sqlite3.Row
            yield con
        except sqlite3.Error:
            raise DatabaseSourceError('Snapshot query failed or exceeded time limit') from None
        finally:
            con.close()

    def _data(self, record):
        try:
            path = self.root / (record['source_id'] + '.sqlite')
            if path.stat().st_size > self.max_bytes:
                raise DatabaseSourceError('Snapshot exceeds byte limit')
            data = path.read_bytes()
        except OSError:
            raise DatabaseSourceError('Registered snapshot unavailable') from None
        if _digest(data) != record['snapshot_sha256']:
            raise DatabaseSourceError('Registered snapshot integrity mismatch')
        return data

    @staticmethod
    def _catalog(con):
        tables = [r['name'] for r in con.execute('PRAGMA table_list')
                  if r['schema'] == 'main' and r['type'] == 'table' and not r['name'].startswith('sqlite_')]
        if not tables or len(tables) > 100:
            raise DatabaseSourceError('Source must contain between 1 and 100 ordinary tables')
        result = {}
        for table in sorted(tables):
            columns = [dict(r) for r in con.execute(f'PRAGMA table_xinfo({_quote(table)})')]
            if len(columns) > 200:
                raise DatabaseSourceError('Source table exceeds column limit')
            result[table] = columns
        return result

    @staticmethod
    def _rows(cursor):
        # Keep large strings/BLOBs bounded and explicitly mark truncation.
        def value(v):
            if isinstance(v, bytes):
                return {'type': 'blob', 'bytes': len(v), 'sha256': _digest(v)}
            if isinstance(v, str) and len(v) > 2000:
                return {'type': 'text', 'prefix': v[:2000], 'characters': len(v), 'truncated': True}
            return v
        return [{k: value(row[k]) for k in row.keys()} for row in cursor]

    def inspect(self, source_id, *, sample_limit=5):
        _bounded(sample_limit, 20, 'Sample limit')
        record = self._record(source_id)
        with self._connection(self._data(record)) as con:
            tables = []
            for table, columns in self._catalog(con).items():
                tables.append({'name': table, 'columns': columns,
                               'primary_key': [c['name'] for c in sorted(columns, key=lambda c: c['pk']) if c['pk']],
                               'foreign_keys': [dict(r) for r in con.execute(f'PRAGMA foreign_key_list({_quote(table)})')],
                               'row_count': con.execute(f'SELECT count(*) FROM {_quote(table)}').fetchone()[0],
                               'sample': self._rows(con.execute(f'SELECT * FROM {_quote(table)} LIMIT ?', (sample_limit,)))})
        return {**self._public(record), 'tables': tables, 'sample_limit': sample_limit,
                'scope': 'complete_snapshot_tables_with_bounded_samples'}

    def lookup(self, source_id, *, table, filters, columns=None, limit=50):
        _bounded(limit, 200, 'Lookup limit')
        if not isinstance(filters, dict) or not 1 <= len(filters) <= 10:
            raise DatabaseSourceError('Provide between 1 and 10 exact filters')
        record = self._record(source_id)
        with self._connection(self._data(record)) as con:
            catalog = self._catalog(con)
            if not isinstance(table, str) or table not in catalog:
                raise DatabaseSourceError('Unknown source table')
            available = [c['name'] for c in catalog[table] if c['hidden'] != 1]
            columns = available if columns is None else columns
            if not isinstance(columns, list) or not columns or any(not isinstance(c, str) or c not in available for c in columns) or len(columns) != len(set(columns)):
                raise DatabaseSourceError('Choose distinct source columns')
            if any(not isinstance(c, str) or c not in available for c in filters):
                raise DatabaseSourceError('Unknown filter column')
            if any(type(v) not in (str, int, float, type(None)) or isinstance(v, str) and len(v) > 2000 or isinstance(v, int) and not -(2**63) <= v < 2**63 or isinstance(v, float) and not math.isfinite(v) for v in filters.values()):
                raise DatabaseSourceError('Unsupported exact filter value')
            where = ' AND '.join(f'{_quote(c)} IS ?' for c in filters)
            sql = f'SELECT {", ".join(map(_quote, columns))} FROM {_quote(table)} WHERE {where} LIMIT ?'
            rows = self._rows(con.execute(sql, (*filters.values(), limit + 1)))
        truncated = len(rows) > limit
        return {**self._public(record), 'table': table, 'columns': columns,
                'rows': rows[:limit], 'limit': limit, 'truncated': truncated,
                'status': 'matched' if rows else 'not_found_in_snapshot',
                'scope': 'whole_snapshot_table_exact_lookup'}

    def check_drift(self, source_id):
        record = self._record(source_id)
        self._data(record)
        try:
            observed = _digest(self._capture(Path(record['source_path'])))
        except DatabaseSourceError:
            return {**self._public(record), 'status': 'source_unavailable',
                    'freshness': 'unknown'}
        return {**self._public(record), 'status': 'unchanged' if observed == record['snapshot_sha256'] else 'changed',
                'observed_snapshot_sha256': observed,
                'freshness': 'observation_at_check_time_only'}
