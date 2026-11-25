"""Offline operator CLI checks, not policy interpretation or approval tests."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from apps.factory_lab.document_sources_cli import main
from apps.factory_lab.workspace_database import SQLiteSources


class DocumentSourcesCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        database = self.root / 'private.sqlite'
        with sqlite3.connect(database) as connection:
            connection.execute('CREATE TABLE items (id INTEGER PRIMARY KEY)')
            connection.execute('INSERT INTO items VALUES (1)')
        self.databases = SQLiteSources(self.root / 'databases')
        self.database = self.databases.register(database)
        self.documents = self.root / 'documents'
        self.source = self.root / 'secret-policy.md'
        self.original = b'# Policy\r\n\r\nExternal review required.\r\n'
        self.source.write_bytes(self.original)

    def args(self, command, *extra, source_id=None, digest=None):
        return list(map(str, ['--database-registry', self.databases.root,
                             '--registry', self.documents, command, *extra,
                             '--source-id', source_id or self.database['source_id'],
                             '--snapshot-sha256', digest or self.database['snapshot_sha256']]))

    def invoke(self, arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(arguments), 0)
        self.assertNotIn(str(self.root), output.getvalue())
        self.assertNotIn('source_path', output.getvalue())
        return json.loads(output.getvalue())

    def failure(self, arguments, code=1):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            with self.assertRaises(SystemExit) as raised:
                main(arguments)
        self.assertEqual(raised.exception.code, code)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn(str(self.root), error.getvalue())
        self.assertNotIn('secret-policy', error.getvalue())
        self.assertNotIn('Traceback', error.getvalue())

    def register(self, **binding):
        return self.invoke(self.args('register', self.source, '--label', 'Policy',
                                     '--version', '2026-11', **binding))

    def test_registration_restart_listing_and_original_bytes(self):
        registered = self.register()
        self.assertEqual(registered['document_sha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(registered['source_id'], self.database['source_id'])
        self.assertEqual(registered['snapshot_sha256'], self.database['snapshot_sha256'])
        self.assertEqual(registered['version'], '2026-11')
        self.assertEqual(registered['approval'], 'external_review_required')
        self.assertEqual(registered['applicability'], 'unassessed')
        frozen = self.documents / (registered['document_id'] + '.txt')
        self.assertEqual(frozen.read_bytes(), self.original)
        self.source.write_bytes(b'New version\n')
        newer = self.register()
        self.source.unlink()
        listing = self.invoke(self.args('list'))
        self.assertEqual(listing['total'], 2)
        self.assertEqual({d['document_id'] for d in listing['documents']},
                         {registered['document_id'], newer['document_id']})
        self.assertEqual(frozen.read_bytes(), self.original)
        self.assertEqual(frozen.stat().st_mode & 0o777, 0o400)

    def test_pagination_and_binding_filter(self):
        self.register()
        self.register()
        page = self.invoke(self.args('list', '--limit', 1))
        self.assertEqual((page['total'], len(page['documents']), page['truncated']), (2, 1, True))
        next_page = self.invoke(self.args('list', '--offset', 1, '--limit', 1))
        self.assertFalse(next_page['truncated'])
        self.assertNotEqual(page['documents'], next_page['documents'])
        other = self.databases.register(self.root / 'private.sqlite')
        empty = self.invoke(self.args('list', source_id=other['source_id'], digest=other['snapshot_sha256']))
        self.assertEqual(empty['total'], 0)

    def test_wrong_hash_unknown_source_and_corrupt_database_rejected(self):
        for binding in ({'digest': '0' * 64}, {'source_id': '0' * 32}):
            self.failure(self.args('register', self.source, '--label', 'Policy', '--version', '1', **binding))
        self.assertFalse(list(self.documents.glob('*.json')))
        self.register()
        snapshot = self.databases.root / (self.database['source_id'] + '.sqlite')
        snapshot.chmod(0o600)
        snapshot.write_bytes(b'corrupt')
        self.failure(self.args('list'))
        self.failure(self.args('register', self.source, '--label', 'Policy', '--version', '2'))
        self.assertEqual(len(list(self.documents.glob('*.json'))), 1)

    def test_missing_registries_are_not_created_by_list(self):
        self.failure(self.args('list'))
        self.assertFalse(self.documents.exists())
        arguments = self.args('register', self.source, '--label', 'Policy', '--version', '1')
        missing = self.root / 'secret-policy-database'
        arguments[1] = str(missing)
        self.failure(arguments)
        self.assertFalse(missing.exists())
        self.assertFalse(self.documents.exists())

    def test_format_bounds_missing_source_and_os_errors_are_redacted(self):
        for content in (b'\xff', b'contains\0binary', b'x' * 16385):
            self.source.write_bytes(content)
            self.failure(self.args('register', self.source, '--label', 'Policy', '--version', '1'))
        self.source.unlink()
        self.failure(self.args('register', self.source, '--label', 'Policy', '--version', '1'))
        self.source.write_bytes(self.original)
        self.register()
        for options in (('--limit', '101'), ('--offset', '-1')):
            self.failure(self.args('list', *options))
        blocked = self.root / 'secret-policy-file'
        blocked.write_text('not a directory')
        arguments = self.args('register', self.source, '--label', 'Policy', '--version', '1')
        arguments[3] = str(blocked / 'child')
        self.failure(arguments)

    def test_argument_errors_and_missing_explicit_metadata_are_redacted(self):
        self.failure(self.args('list', '--limit', str(self.source)), code=2)
        self.failure(self.args('list', '--unexpected', str(self.source)), code=2)
        for options in ([], ['--label', 'Policy'], ['--version', '1']):
            self.failure(self.args('register', self.source, *options), code=2)

    def test_shared_registry_rejected_and_umask_restored(self):
        before = os.umask(0o077)
        os.umask(before)
        self.register()
        observed = os.umask(before)
        self.assertEqual(observed, before)
        arguments = self.args('list')
        arguments[3] = str(self.databases.root)
        self.failure(arguments)
        observed = os.umask(before)
        self.assertEqual(observed, before)


if __name__ == '__main__':
    unittest.main()
