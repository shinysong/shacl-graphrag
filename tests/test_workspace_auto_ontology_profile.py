"""Offline authored SQLite fixtures; no native or semantic execution evidence."""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from apps.factory_lab.auto_ontology_profile import prepare_profile, ProfileError
from apps.factory_lab.workspace_database import SQLiteSources


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = SQLiteSources(self.root / 'registry')

    def source(self, ddl, rows=None):
        path = self.root / 'source.sqlite'
        with sqlite3.connect(path) as connection:
            connection.executescript(ddl)
            if rows:
                for sql, values in rows:
                    connection.executemany(sql, values)
        record = self.registry.register(path)
        return record['source_id']

    def prepare(self, source, name='profile', limit=2):
        return prepare_profile(self.registry, source, self.root / name, limit_per_table=limit)

    def test_composite_pk_types_schema_and_repeatable_selection(self):
        source = self.source('CREATE TABLE facts(a INTEGER NOT NULL,b TEXT NOT NULL,'
                             'value, payload BLOB, PRIMARY KEY(a,b)); CREATE INDEX by_value ON facts(value);',
            [('INSERT INTO facts VALUES (?,?,?,?)',
              [(2, 'a', 3.25, b'\x00\xff'), (1, 'z', 7, b''), (1, 'a', '007', b'abc'), (3, 'a', None, None)])])
        original = self.registry._data(self.registry._record(source))
        before_path = (self.root / 'source.sqlite').read_bytes()
        first = self.prepare(source)
        self.assertEqual(first['status'], 'complete', first)
        self.assertEqual(first['source']['total_rows'], 4)
        self.assertEqual(first['sample']['total_rows'], 2)
        self.assertEqual(first['source']['schema_sha256'], first['sample']['schema_sha256'])
        with sqlite3.connect(self.root / 'profile/sample.sqlite') as con:
            self.assertEqual(con.execute('SELECT a,b,value,payload,typeof(value) FROM facts ORDER BY a,b').fetchall(),
                             [(1, 'a', '007', b'abc', 'text'), (1, 'z', 7, b'', 'integer')])
        second = self.prepare(source, name='second')
        self.assertEqual(first['tables'], second['tables'])
        self.assertEqual(self.registry._data(self.registry._record(source)), original)
        self.assertEqual((self.root / 'source.sqlite').read_bytes(), before_path)
        self.assertEqual(first['sample']['sha256'], sha256((self.root / 'profile/sample.sqlite').read_bytes()).hexdigest())
        self.assertEqual((self.root / 'profile').stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.root / 'profile/sample.sqlite').stat().st_mode & 0o777, 0o400)

    def test_blob_float_null_and_quoted_identifiers_survive(self):
        source = self.source('CREATE TABLE "a""b"(id INTEGER PRIMARY KEY,value,payload BLOB);',
            [('INSERT INTO "a""b" VALUES (?,?,?)', [(1, 1.125, b'\xff\x00'), (2, None, None)])])
        result = self.prepare(source)
        self.assertEqual(result['status'], 'complete', result)
        with sqlite3.connect(self.root / 'profile/sample.sqlite') as con:
            self.assertEqual(con.execute('SELECT * FROM "a""b" ORDER BY id').fetchall(),
                             [(1, 1.125, b'\xff\x00'), (2, None, None)])

    def test_fk_projection_omission_preserves_declaration_without_repair(self):
        source = self.source('CREATE TABLE parent(id INTEGER PRIMARY KEY);'
                             'CREATE TABLE child(id INTEGER PRIMARY KEY,parent_id INTEGER REFERENCES parent(id));'
                             'INSERT INTO parent VALUES(1),(2),(3); INSERT INTO child VALUES(1,3),(2,1);')
        result = self.prepare(source, limit=1)
        self.assertEqual(result['status'], 'complete', result)
        self.assertEqual(result['source_fk_check']['violations'], 0)
        self.assertEqual(result['sample_fk_check']['violations'], 1)
        self.assertEqual(result['foreign_key_policy'], 'preserve_declarations_no_closure_repair')
        self.assertIn('projection_omissions', result['fk_interpretation']['sample'])
        with sqlite3.connect(self.root / 'profile/sample.sqlite') as con:
            self.assertEqual(con.execute('SELECT * FROM child').fetchall(), [(1, 3)])
            self.assertEqual(con.execute('SELECT * FROM parent').fetchall(), [(1,)])
            self.assertEqual(len(con.execute('PRAGMA foreign_key_list(child)').fetchall()), 1)

    def test_large_source_remains_full_and_sample_bounded(self):
        source = self.source('CREATE TABLE facts(id INTEGER PRIMARY KEY,value TEXT);',
                             [('INSERT INTO facts VALUES (?,?)', [(i, str(i)) for i in range(1501)])])
        result = self.prepare(source, limit=1000)
        self.assertEqual(result['status'], 'complete', result)
        self.assertEqual(result['source']['total_rows'], 1501)
        self.assertEqual(result['sample']['total_rows'], 1000)
        self.assertNotEqual(result['source']['sha256'], result['sample']['sha256'])

    def test_empty_without_rowid_composite_table_supported(self):
        source = self.source('CREATE TABLE facts(a TEXT,b INTEGER,PRIMARY KEY(a,b)) WITHOUT ROWID;')
        result = self.prepare(source)
        self.assertEqual(result['status'], 'complete', result)
        self.assertEqual(result['sample']['total_rows'], 0)

    def test_nullable_primary_key_rejected_and_failure_retained(self):
        source = self.source('CREATE TABLE facts(id TEXT PRIMARY KEY,value); INSERT INTO facts VALUES("a",1);')
        result = self.prepare(source)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('Nullable', result['error'])
        self.assertIsNone(result['sample'])
        self.assertEqual(json.loads((self.root / 'profile/manifest.json').read_text()), result)

    def test_unsupported_schema_rejected(self):
        ddls = ['CREATE TABLE facts(id INTEGER PRIMARY KEY); CREATE VIEW v AS SELECT * FROM facts;',
                'CREATE TABLE facts(id INTEGER PRIMARY KEY); CREATE TRIGGER t AFTER INSERT ON facts BEGIN SELECT 1; END;',
                'CREATE TABLE facts(id INTEGER PRIMARY KEY, x AS (id+1));',
                'CREATE TABLE facts(id TEXT NOT NULL PRIMARY KEY COLLATE NOCASE);',
                'CREATE TABLE facts(id INTEGER PRIMARY KEY); CREATE INDEX partial ON facts(id) WHERE id>0;',
                'CREATE TABLE facts(id INTEGER PRIMARY KEY); CREATE INDEX expr ON facts(id+1);']
        for i, ddl in enumerate(ddls):
            with self.subTest(ddl=ddl):
                path = self.root / 'source.sqlite'
                if path.exists():
                    path.unlink()
                result = self.prepare(self.source(ddl), name='profile' + str(i))
                self.assertEqual(result['status'], 'failed')
                self.assertIsNone(result['sample'])

    def test_nonfinite_selected_value_rejected(self):
        source = self.source('CREATE TABLE facts(id INTEGER PRIMARY KEY,value REAL);',
                             [('INSERT INTO facts VALUES(?,?)', [(1, float('inf'))])])
        result = self.prepare(source)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('Nonfinite', result['error'])

    def test_full_source_byte_bound_rejects_before_materialization(self):
        source = self.source('CREATE TABLE facts(id INTEGER PRIMARY KEY);')
        with patch('apps.factory_lab.auto_ontology_profile.MAX_BYTES', 2):
            result = self.prepare(source)
        self.assertEqual(result['status'], 'failed')
        self.assertFalse((self.root / 'profile/sample.sqlite').exists())
        self.assertIsNone(result['sample'])

    def test_bounds_existing_directory_and_symlink_never_overwritten(self):
        source = self.source('CREATE TABLE facts(id INTEGER PRIMARY KEY);')
        for value in (0, 1001, True):
            with self.assertRaises(ProfileError):
                self.prepare(source, limit=value)
        target = self.root / 'profile'
        target.mkdir()
        marker = target / 'keep'
        marker.write_bytes(b'original')
        with self.assertRaises(FileExistsError):
            self.prepare(source)
        symlink = self.root / 'linked'
        symlink.symlink_to(target)
        with self.assertRaises(FileExistsError):
            self.prepare(source, name='linked')
        self.assertEqual(marker.read_bytes(), b'original')

    def test_swapped_registry_record_rejected_before_sample_materialization(self):
        source = self.source('CREATE TABLE facts(id INTEGER PRIMARY KEY);')
        other = self.registry.register(self.root / 'source.sqlite')['source_id']
        path = self.registry.root / (source + '.json')
        path.chmod(0o600)
        path.write_bytes((self.registry.root / (other + '.json')).read_bytes())
        result = self.prepare(source)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('identity', result['error'])
        self.assertIsNone(result['sample'])
        self.assertFalse((self.root / 'profile' / 'sample.sqlite').exists())
        self.assertEqual(self.registry._record(source)['source_id'], other)

    def test_tampered_registry_source_and_deadline_leave_failed_manifest(self):
        source = self.source('CREATE TABLE facts(id INTEGER PRIMARY KEY);')
        with patch('apps.factory_lab.auto_ontology_profile.time.monotonic', side_effect=[0, 11]):
            timed = self.prepare(source, name='timed')
        self.assertEqual(timed['status'], 'failed')
        self.assertIn('time limit', timed['error'])
        snapshot = self.registry.root / (source + '.sqlite')
        snapshot.chmod(0o600)
        snapshot.write_bytes(b'tampered')
        result = self.prepare(source)
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(result['sample'])
        self.assertEqual(snapshot.read_bytes(), b'tampered')
