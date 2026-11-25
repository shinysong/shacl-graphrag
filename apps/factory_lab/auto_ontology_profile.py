"""Offline deterministic profiling input preparation; no upstream execution.

The complete registered snapshot remains authoritative. A profile is a biased
primary-key prefix, not a representative sample or complete relational dataset.
Only a trusted local operator may select the registry and destination parent.
"""
from contextlib import closing
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time

MAX_BYTES = 16 * 1024 * 1024
MAX_TABLES = 12
MAX_COLUMNS = 40
TIMEOUT_SECONDS = 10


class ProfileError(ValueError):
    """Bounded, public-safe profile rejection."""


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def _hash(raw):
    return sha256(raw).hexdigest()


def _typed(value):
    if value is None:
        return ['null']
    if type(value) is int:
        return ['integer', str(value)]
    if type(value) is float:
        if not math.isfinite(value):
            raise ProfileError('Nonfinite selected SQLite value is unsupported')
        return ['real', value.hex()]
    if isinstance(value, str):
        return ['text', value]
    if isinstance(value, bytes):
        return ['blob', value.hex()]
    raise ProfileError('Unsupported SQLite value type')


def _typed_rows(rows):
    return [[_typed(value) for value in row] for row in rows]


def _structure(connection):
    """Exact schema semantics excluding storage-layout-dependent root pages."""
    objects = [list(row) for row in connection.execute(
        'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name')]
    return objects


def _fk_check(connection):
    # Store bounded hashes/counts rather than every potentially large witness.
    count = 0
    digest = sha256()
    for row in connection.execute('PRAGMA foreign_key_check'):
        count += 1
        digest.update(_json(list(row)) + b'\n')
    return {'violations': count, 'witness_stream_sha256': digest.hexdigest()}


def prepare_profile(registry, source_id, destination, *, limit_per_table=1000):
    """Create sample.sqlite + manifest.json in a new private directory.

    Existing/symlink destinations are rejected without writes. Once the owned
    directory exists, every caught preparation failure leaves a failed manifest
    and any partial artifact. A failed artifact must never be ingested. Parent
    directories must be trusted and protected from replacement by the operator.
    """
    if type(limit_per_table) is not int or not 1 <= limit_per_table <= 1000:
        raise ProfileError('Sample row limit must be an integer from 1 to 1000')
    destination = Path(destination).absolute()
    # mkdir(exist_ok=False) rejects both ordinary and dangling symlink targets.
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    destination.chmod(0o700)
    manifest = {'format': 'auto-ontology-profile-1', 'status': 'preparing',
                'policy': 'declared-primary-key-ascending-v1',
                'limit_per_table': limit_per_table, 'source_id': source_id,
                'stage': 'source_read', 'sample': None, 'tables': [],
                'approval': 'not_granted', 'upstream_invoked': False,
                'limitations': ['Deterministic biased prefix, not representative sampling.',
                                'Declared FK metadata retained; sample can omit referenced rows.',
                                'No semantic generation, complete-source truth or upstream profiling claim.',
                                'Deadline is cooperative; filesystem reads are checked after return.']}
    def save():
        temporary = destination / 'manifest.tmp'
        temporary.write_bytes(_json(manifest) + b'\n')
        temporary.chmod(0o600)
        temporary.replace(destination / 'manifest.json')
    save()
    deadline = time.monotonic() + TIMEOUT_SECONDS
    def check():
        if time.monotonic() >= deadline:
            raise ProfileError('Profile preparation exceeded time limit')
    def progress():
        return int(time.monotonic() >= deadline)
    sample_path = destination / 'sample.sqlite'
    try:
        record = registry._record(source_id)
        if record.get('source_id') != source_id:
            raise ProfileError('Registered source identity differs from request')
        data = registry._data(record)
        check()
        if len(data) > MAX_BYTES:
            raise ProfileError('Complete source exceeds 16 MiB profile limit')
        manifest['source'] = {'source_id': source_id, 'sha256': _hash(data), 'bytes': len(data)}
        manifest['stage'] = 'selection'
        save()
        selected = {}
        with closing(sqlite3.connect(':memory:')) as original:
            original.deserialize(data)
            original.execute('PRAGMA trusted_schema=OFF')
            original.execute('PRAGMA query_only=ON')
            original.set_progress_handler(progress, 1000)
            structure = _structure(original)
            if any(row[0] in ('view', 'trigger') for row in structure):
                raise ProfileError('Views and triggers are unsupported for profiling')
            table_list = list(original.execute('PRAGMA table_list'))
            if any(row[2] in ('virtual', 'shadow') for row in table_list):
                raise ProfileError('Virtual and shadow tables are unsupported for profiling')
            tables = sorted(row[1] for row in table_list
                            if row[0] == 'main' and row[2] == 'table' and not row[1].startswith('sqlite_'))
            if not 1 <= len(tables) <= MAX_TABLES:
                raise ProfileError('Profile requires 1 to 12 ordinary tables')
            if any(sql and re.search(r'\bCOLLATE\b', sql, re.I)
                   for _, _, _, sql in structure):
                raise ProfileError('Explicit collation declarations are unsupported')
            manifest['source']['schema_sha256'] = _hash(_json(structure))
            manifest['schema'] = structure
            for name in tables:
                check()
                quoted = _quote(name)
                columns = [list(row) for row in original.execute('PRAGMA table_xinfo(' + quoted + ')')]
                if not 1 <= len(columns) <= MAX_COLUMNS or any(col[6] != 0 for col in columns):
                    raise ProfileError('Generated/hidden columns or unsupported column count')
                primary = sorted((col for col in columns if col[5] > 0), key=lambda col: col[5])
                if not primary:
                    raise ProfileError('Every table requires a declared primary key')
                indexes = [list(row) for row in original.execute('PRAGMA index_list(' + quoted + ')')]
                integer_rowid_pk = (len(primary) == 1 and primary[0][2].upper() == 'INTEGER'
                                    and not any(index[3] == 'pk' for index in indexes))
                if not integer_rowid_pk and any(not col[3] for col in primary):
                    raise ProfileError('Nullable declared primary keys are unsupported')
                index_metadata = []
                for index in indexes:
                    info = [list(row) for row in original.execute('PRAGMA index_xinfo(' + _quote(index[1]) + ')')]
                    if index[4] or any(row[1] == -2 or row[4] not in (None, 'BINARY') for row in info):
                        raise ProfileError('Partial/expression/nonbinary indexes are unsupported')
                    index_metadata.append({'index': index, 'columns': info})
                keys = [col[1] for col in primary]
                key_sql = ','.join(_quote(key) for key in keys)
                null_sql = ' OR '.join(_quote(key) + ' IS NULL' for key in keys)
                if original.execute('SELECT 1 FROM ' + quoted + ' WHERE ' + null_sql + ' LIMIT 1').fetchone():
                    raise ProfileError('Primary key contains NULL')
                if original.execute('SELECT 1 FROM ' + quoted + ' GROUP BY ' + key_sql +
                                    ' HAVING count(*)>1 LIMIT 1').fetchone():
                    raise ProfileError('Primary key is not unique')
                order = ','.join(_quote(key) + ' COLLATE BINARY ASC' for key in keys)
                count = original.execute('SELECT count(*) FROM ' + quoted).fetchone()[0]
                sql = 'SELECT * FROM ' + quoted + ' ORDER BY ' + order + ' LIMIT ?'
                rows = list(original.execute(sql, (limit_per_table,)))
                typed = _typed_rows(rows)
                key_indexes = [next(i for i, col in enumerate(columns) if col[1] == key) for key in keys]
                key_rows = [tuple(row[i] for i in key_indexes) for row in rows]
                selected[name] = {'keys': key_rows, 'typed_rows': typed, 'query': sql, 'order': order}
                manifest['tables'].append({'name': name, 'source_rows': count, 'selected_rows': len(rows),
                    'pk_columns': keys, 'columns': columns, 'indexes': index_metadata,
                    'foreign_keys': [list(row) for row in original.execute('PRAGMA foreign_key_list(' + quoted + ')')],
                    'selection_sql': sql, 'selection_parameters': [limit_per_table],
                    'key_selection_sha256': _hash(_json(_typed_rows(key_rows))),
                    'selected_rows_sha256': _hash(_json(typed))})
            manifest['source']['total_rows'] = sum(t['source_rows'] for t in manifest['tables'])
            manifest['source_fk_check'] = _fk_check(original)
        check()
        manifest['selection_manifest_sha256'] = _hash(_json(manifest['tables']))
        manifest['stage'] = 'materialization'
        save()
        # Exact source copy preserves DDL, affinities and stored scalar types.
        with sample_path.open('xb') as target:
            target.write(data)
        sample_path.chmod(0o600)
        with closing(sqlite3.connect(sample_path)) as sample:
            sample.execute('PRAGMA trusted_schema=OFF')
            sample.execute('PRAGMA foreign_keys=OFF')
            sample.execute('PRAGMA secure_delete=ON')
            sample.set_progress_handler(progress, 1000)
            for table in manifest['tables']:
                check()
                name = table['name']
                quoted = _quote(name)
                key_sql = ','.join(_quote(key) for key in table['pk_columns'])
                # Membership is computed on the original full copy before each
                # independent table deletion; no FK closure or value repair.
                sample.execute('DELETE FROM ' + quoted + ' WHERE (' + key_sql + ') NOT IN '
                               '(SELECT ' + key_sql + ' FROM ' + quoted + ' ORDER BY ' +
                               selected[name]['order'] + ' LIMIT ?)', (limit_per_table,))
            sample.commit()
            check()
            sample.execute('VACUUM')
            check()
            manifest['stage'] = 'verification'
            save()
            if _structure(sample) != structure:
                raise ProfileError('Sample structural schema differs from complete source')
            for table in manifest['tables']:
                check()
                name = table['name']
                rows = list(sample.execute(selected[name]['query'], (limit_per_table + 1,)))
                if _typed_rows(rows) != selected[name]['typed_rows']:
                    raise ProfileError('Sample selected values differ from complete source')
            manifest['sample_fk_check'] = _fk_check(sample)
            integrity = list(sample.execute('PRAGMA integrity_check'))
            if integrity != [('ok',)]:
                raise ProfileError('Sample SQLite integrity check failed')
        check()
        sample_bytes = sample_path.read_bytes()
        if len(sample_bytes) > MAX_BYTES:
            raise ProfileError('Derived sample exceeds byte limit')
        current = registry._record(source_id)
        if current.get('source_id') != source_id or registry._data(current) != data:
            raise ProfileError('Registered source changed during preparation')
        check()
        manifest.update(status='complete', stage='complete',
            sqlite_version=sqlite3.sqlite_version,
            foreign_key_policy='preserve_declarations_no_closure_repair',
            fk_interpretation={'source': 'original_source_condition',
                'sample': 'may_include_original_violations_and_projection_omissions',
                'new_violation_attribution': 'not_individually_classified'},
            sample={'file': 'sample.sqlite', 'sha256': _hash(sample_bytes), 'bytes': len(sample_bytes),
                    'schema_sha256': _hash(_json(structure)),
                    'total_rows': sum(t['selected_rows'] for t in manifest['tables'])})
        sample_path.chmod(0o400)
    except (ValueError, TypeError, KeyError, OSError, sqlite3.Error, UnicodeError) as exc:
        manifest.update(status='failed', error_class=type(exc).__name__,
                        error=str(exc) if isinstance(exc, ProfileError) else 'Profile preparation failed; retained artifacts are incomplete',
                        sample=None)
    save()
    return manifest
