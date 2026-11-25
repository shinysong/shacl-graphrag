"""Actual complete SQLite tables; no paid calls or model-quality claims."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from apps.factory_lab.workspace_database import SQLiteSources, DatabaseSourceError


class SQLiteSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'private-source.sqlite'
        with sqlite3.connect(self.source) as con:
            con.execute('CREATE TABLE groups (code TEXT PRIMARY KEY)')
            con.execute("INSERT INTO groups VALUES ('g1')")
            con.execute('CREATE TABLE records (id INTEGER PRIMARY KEY, group_code TEXT REFERENCES groups(code), value TEXT)')
            con.executemany('INSERT INTO records VALUES (?, ?, ?)', ((i, 'g1', f'value-{i}') for i in range(10000)))
        self.registry = SQLiteSources(self.root / 'private-registry')
        self.desc = self.registry.register(self.source, label='Registered test source')
        self.id = self.desc['source_id']

    def test_full_counts_bounded_sample_and_beyond_prefix(self):
        info = self.registry.inspect(self.id, sample_limit=3)
        table = next(t for t in info['tables'] if t['name'] == 'records')
        self.assertEqual(table['row_count'], 10000)
        self.assertEqual(len(table['sample']), 3)
        self.assertEqual(table['primary_key'], ['id'])
        self.assertEqual(table['foreign_keys'][0]['table'], 'groups')
        found = self.registry.lookup(self.id, table='records', filters={'id': 9999})
        self.assertEqual(found['rows'][0]['value'], 'value-9999')
        self.assertFalse(found['truncated'])
        self.assertNotIn(str(self.root), json.dumps(info))
        self.assertNotIn('source_path', json.dumps(found))
        self.assertEqual(SQLiteSources(self.registry.root).inspect(self.id), self.registry.inspect(self.id))

    def test_snapshot_stability_and_drift(self):
        self.assertEqual(self.registry.check_drift(self.id)['status'], 'unchanged')
        with sqlite3.connect(self.source) as con:
            con.execute("UPDATE records SET value='new-value' WHERE id=9999")
        self.assertEqual(self.registry.check_drift(self.id)['status'], 'changed')
        self.assertEqual(self.registry.lookup(self.id, table='records', filters={'id': 9999})['rows'][0]['value'], 'value-9999')
        self.source.unlink()
        self.assertEqual(self.registry.check_drift(self.id)['status'], 'source_unavailable')
        self.assertEqual(self.registry.inspect(self.id)['tables'][1]['row_count'], 10000)

    def test_bounded_matches_and_null(self):
        result = self.registry.lookup(self.id, table='records', filters={'group_code': 'g1'}, columns=['id'], limit=2)
        self.assertEqual(len(result['rows']), 2)
        self.assertTrue(result['truncated'])
        self.assertEqual(self.registry.lookup(self.id, table='records', filters={'id': None})['status'], 'not_found_in_snapshot')

    def test_injection_and_unregistered_paths(self):
        for kwargs in ({'table': 'records; DROP TABLE records; --', 'filters': {'id': 1}},
                       {'table': 'records', 'filters': {'id OR 1=1': 1}},
                       {'table': 'records', 'filters': {'id': 1}, 'columns': ['id); DELETE FROM records;--']}):
            with self.assertRaises(DatabaseSourceError):
                self.registry.lookup(self.id, **kwargs)
        self.assertEqual(self.registry.lookup(self.id, table='records', filters={'value': "' OR 1=1 --"})['rows'], [])
        for source_id in ('../private-source', str(self.source), 'a' * 32):
            with self.assertRaises(DatabaseSourceError):
                self.registry.inspect(source_id)
        with sqlite3.connect(self.source) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM records').fetchone()[0], 10000)

    def test_quoted_real_identifiers_are_valid(self):
        with sqlite3.connect(self.source) as con:
            con.execute('CREATE TABLE "odd"" table" ("select" TEXT)')
            con.execute('INSERT INTO "odd"" table" VALUES (?)', ('actual value',))
        source_id = self.registry.register(self.source)['source_id']
        self.assertEqual(self.registry.lookup(source_id, table='odd" table', filters={'select': 'actual value'})['rows'], [{'select': 'actual value'}])

    def test_failures_and_limits(self):
        for limit in (0, 201, True, '10'):
            with self.assertRaises(DatabaseSourceError):
                self.registry.lookup(self.id, table='records', filters={'id': 1}, limit=limit)
        for filters in ({}, {'id': []}, {'id': 2**64}, {'id': float('nan')}, {'id': float('inf')}):
            with self.assertRaises(DatabaseSourceError):
                self.registry.lookup(self.id, table='records', filters=filters)
        with self.assertRaises(DatabaseSourceError):
            self.registry.inspect(self.id, sample_limit=21)
        with self.assertRaises(DatabaseSourceError):
            SQLiteSources(self.root / 'tiny', max_bytes=100).register(self.source)
        for path in (self.root / 'absent', self.root / 'bad.sqlite'):
            if path.name == 'bad.sqlite':
                path.write_text('not sqlite')
            with self.assertRaises(DatabaseSourceError) as error:
                self.registry.register(path)
            self.assertNotIn(str(self.root), str(error.exception))
        self.assertFalse((self.root / 'absent').exists())

    def test_tampering_fails_closed(self):
        snapshot = self.registry.root / (self.id + '.sqlite')
        snapshot.chmod(0o600)
        with snapshot.open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(DatabaseSourceError, 'integrity mismatch'):
            self.registry.lookup(self.id, table='records', filters={'id': 1})

    def test_wal_commits_and_uncommitted_isolation(self):
        con = sqlite3.connect(self.source)
        self.addCleanup(con.close)
        con.execute('PRAGMA journal_mode=WAL')
        con.execute("UPDATE records SET value='WAL committed' WHERE id=9999")
        con.commit()
        con.execute("UPDATE records SET value='uncommitted' WHERE id=9999")
        source_id = self.registry.register(self.source)['source_id']
        self.assertEqual(self.registry.lookup(source_id, table='records', filters={'id': 9999})['rows'][0]['value'], 'WAL committed')
        self.assertEqual(self.registry.check_drift(source_id)['status'], 'unchanged')
        con.commit()
        self.assertEqual(self.registry.check_drift(source_id)['status'], 'changed')

    def test_read_connection_rejects_writes(self):
        record = self.registry._record(self.id)
        with self.assertRaises(DatabaseSourceError):
            with self.registry._connection(self.registry._data(record)) as con:
                con.execute('DELETE FROM records')
        self.assertEqual(self.registry.inspect(self.id)['tables'][1]['row_count'], 10000)

    def test_large_values_are_explicitly_bounded(self):
        with sqlite3.connect(self.source) as con:
            con.execute('UPDATE records SET value=? WHERE id=1', ('x' * 3000,))
            con.execute('UPDATE records SET value=? WHERE id=2', (b'blob',))
        source_id = self.registry.register(self.source)['source_id']
        text = self.registry.lookup(source_id, table='records', filters={'id': 1})['rows'][0]['value']
        blob = self.registry.lookup(source_id, table='records', filters={'id': 2})['rows'][0]['value']
        self.assertTrue(text['truncated'])
        self.assertEqual(text['characters'], 3000)
        self.assertEqual(blob['bytes'], 4)


if __name__ == '__main__':
    unittest.main()
