"""Offline registry integrity tests; no policy correctness or model claims."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_source_documents import DocumentSources, DocumentSourceError


class DocumentSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'source.sqlite'
        with sqlite3.connect(self.db) as con:
            con.execute('CREATE TABLE things (id INTEGER PRIMARY KEY)')
            con.execute('INSERT INTO things VALUES (1)')
        self.databases = SQLiteSources(self.root / 'databases')
        self.database = self.databases.register(self.db)
        self.binding = {k: self.database[k] for k in ('source_id', 'snapshot_sha256')}
        self.registry = DocumentSources(self.root / 'documents', self.databases)
        self.source = self.root / 'private-policy.md'
        self.original = '# Policy\r\n\r\nOnly a prerequisite.\r\nNo final approval.\r\n\r\n한글 원문\n'
        self.source.write_bytes(self.original.encode())
        self.document = self.registry.register(self.source, **self.binding, label='Policy', version='v1')
        self.id = self.document['document_id']

    def read(self, descriptor, paragraph_id, registry=None):
        return (registry or self.registry).read_paragraph(
            descriptor['document_id'], paragraph_id, **self.binding,
            document_sha256=descriptor['document_sha256'])

    def test_exact_bytes_lines_hashes_restart_and_public_redaction(self):
        info = self.registry.inspect(self.id, **self.binding)
        self.assertEqual(info['paragraph_count'], 3)
        paragraph = info['paragraphs'][1]
        self.assertEqual((paragraph['line_start'], paragraph['line_end']), (3, 4))
        result = self.read(info, paragraph['paragraph_id'])
        self.assertEqual(result['text'], 'Only a prerequisite.\r\nNo final approval.\r\n')
        self.assertEqual(result['paragraph_sha256'], hashlib.sha256(result['text'].encode()).hexdigest())
        self.assertEqual(info['document_sha256'], hashlib.sha256(self.original.encode()).hexdigest())
        restarted = DocumentSources(self.registry.root, self.databases)
        self.assertEqual(restarted.inspect(self.id, **self.binding), info)
        self.assertEqual(self.read(info, paragraph['paragraph_id'], restarted), result)
        self.assertEqual((self.registry.root / (self.id + '.txt')).read_bytes(), self.original.encode())
        self.assertEqual(result['approval'], 'external_review_required')
        self.assertEqual(result['applicability'], 'unassessed')
        public = json.dumps([info, result, self.registry.catalog(**self.binding)])
        self.assertNotIn(str(self.root), public)
        self.assertNotIn('source_path', public)

    def test_drift_does_not_replace_snapshot_and_new_version_is_separate(self):
        self.assertEqual(self.registry.check_drift(self.id, **self.binding)['status'], 'unchanged')
        self.source.write_text('Replacement content\n')
        self.assertEqual(self.registry.check_drift(self.id, **self.binding)['status'], 'changed')
        newer = self.registry.register(self.source, **self.binding, version='v2')
        self.assertNotEqual(newer['document_id'], self.id)
        info = self.registry.inspect(self.id, **self.binding)
        self.assertEqual(self.read(info, info['paragraphs'][0]['paragraph_id'])['text'], '# Policy\r\n')
        self.source.unlink()
        self.assertEqual(self.registry.check_drift(self.id, **self.binding)['status'], 'source_unavailable')
        self.assertEqual(self.registry.inspect(self.id, **self.binding), info)

    def test_wrong_database_and_hash_bindings_fail(self):
        other = self.databases.register(self.db)
        other_binding = {k: other[k] for k in self.binding}
        with self.assertRaises(DocumentSourceError):
            self.registry.inspect(self.id, **other_binding)
        with self.assertRaises(DocumentSourceError):
            self.registry.inspect(self.id, source_id=self.binding['source_id'], snapshot_sha256='f' * 64)
        info = self.registry.inspect(self.id, **self.binding)
        with self.assertRaises(DocumentSourceError):
            self.registry.read_paragraph(self.id, info['paragraphs'][0]['paragraph_id'],
                                         **self.binding, document_sha256='0' * 64)
        snapshot = self.databases.root / (self.binding['source_id'] + '.sqlite')
        snapshot.chmod(0o600)
        snapshot.write_bytes(b'corrupted')
        with self.assertRaises(DocumentSourceError):
            self.registry.inspect(self.id, **self.binding)

    def test_manifest_content_corruption_and_symlinks_rejected(self):
        manifest = self.registry.root / (self.id + '.json')
        original = manifest.read_bytes()
        manifest.chmod(0o600)
        for bad in (b'[]', b'null', b'{}', b'"string"', b'not JSON'):
            manifest.write_bytes(bad)
            with self.assertRaises(DocumentSourceError):
                self.registry.inspect(self.id, **self.binding)
        parsed = json.loads(original)
        parsed['source_path'] = '/private/changed.txt'
        manifest.write_text(json.dumps(parsed))
        with self.assertRaises(DocumentSourceError):
            self.registry.check_drift(self.id, **self.binding)
        manifest.write_bytes(original)
        content = self.registry.root / (self.id + '.txt')
        content.chmod(0o600)
        content.write_bytes(b'wrong content')
        with self.assertRaises(DocumentSourceError):
            self.registry.inspect(self.id, **self.binding)
        content.unlink()
        content.symlink_to(self.source)
        with self.assertRaises(DocumentSourceError):
            self.registry.inspect(self.id, **self.binding)

    def test_pagination_capacity_and_nonapproval(self):
        for i in range(24):
            self.registry.register(self.source, **self.binding, version=str(i))
        catalog = self.registry.catalog(**self.binding, limit=20)
        self.assertEqual(catalog['total'], 25)
        self.assertEqual(len(catalog['documents']), 20)
        self.assertTrue(catalog['truncated'])
        second = self.registry.catalog(**self.binding, offset=20)
        self.assertEqual(len(second['documents']), 5)
        self.assertFalse(second['truncated'])
        info = self.registry.inspect(self.id, **self.binding, limit=1)
        self.assertEqual(len(info['paragraphs']), 1)
        self.assertTrue(info['truncated'])
        restricted = DocumentSources(self.root / 'small-registry', self.databases, max_documents=1)
        restricted.register(self.source, **self.binding)
        with self.assertRaises(DocumentSourceError):
            restricted.register(self.source, **self.binding)

    def test_size_format_utf8_binary_and_traversal_bounds(self):
        for name, content in (('wrong.pdf', b'text'), ('binary.txt', b'a\0b'),
                              ('invalid.md', b'\xff'), ('large.md', b'x' * 16385)):
            path = self.root / name
            path.write_bytes(content)
            with self.assertRaises(DocumentSourceError) as raised:
                self.registry.register(path, **self.binding)
            self.assertNotIn(str(self.root), str(raised.exception))
        for invalid in ('../private-policy.md', str(self.source), 'a' * 32, None, {}):
            with self.assertRaises(DocumentSourceError):
                self.registry.inspect(invalid, **self.binding)
        for limit in (True, 0, 101, '20'):
            with self.assertRaises(DocumentSourceError):
                self.registry.catalog(**self.binding, limit=limit)
        small = DocumentSources(self.root / 'tiny', self.databases, max_bytes=2)
        with self.assertRaises(DocumentSourceError):
            small.register(self.source, **self.binding)
        alias = self.root / 'alias.md'
        alias.symlink_to(self.source)
        with self.assertRaises(DocumentSourceError):
            self.registry.register(alias, **self.binding)

    def test_long_paragraphs_split_on_original_line_boundaries(self):
        self.source.write_bytes(b'12345\n67890\nabc\n')
        registry = DocumentSources(self.root / 'split', self.databases, max_paragraph_bytes=12)
        doc = registry.register(self.source, **self.binding)
        info = registry.inspect(doc['document_id'], **self.binding)
        self.assertEqual([(p['line_start'], p['line_end']) for p in info['paragraphs']], [(1, 2), (3, 3)])
        self.assertEqual(self.read(doc, info['paragraphs'][0]['paragraph_id'], registry)['text'], '12345\n67890\n')
        restarted = DocumentSources(registry.root, self.databases)
        self.assertEqual(restarted.inspect(doc['document_id'], **self.binding), info)
        bound = DocumentSources(self.root / 'paragraph-limit', self.databases, max_paragraph_bytes=6, max_paragraphs=2)
        with self.assertRaises(DocumentSourceError):
            bound.register(self.source, **self.binding)

    def test_encoded_response_size_limit_is_enforced(self):
        self.source.write_text('한' * 500)
        registry = DocumentSources(self.root / 'response-limit', self.databases, max_response_bytes=1024)
        doc = registry.register(self.source, **self.binding)
        info = registry.inspect(doc['document_id'], **self.binding)
        with self.assertRaises(DocumentSourceError):
            self.read(doc, info['paragraphs'][0]['paragraph_id'], registry)


if __name__ == '__main__':
    unittest.main()
