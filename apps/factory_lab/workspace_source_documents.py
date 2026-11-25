"""Private immutable UTF-8 source documents bound to registered DB snapshots.

Only trusted local operators call register with paths. Public reads take opaque
IDs and pinned hashes. Paragraphs are deterministic text spans, not inferred
policy rules; no PDF parsing, applicability assessment or approval occurs here.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

from .workspace_database import DatabaseSourceError


class DocumentSourceError(ValueError):
    """Public-safe errors omit local paths and source contents."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()


def _identifier(value, length=32):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value) is not None


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


class DocumentSources:
    """Local operator registry; public results contain no filesystem paths.

    Defaults support 100 documents of up to 2 MiB each. Oversized individual
    lines are rejected; other long paragraphs split at original line boundaries.
    Exact original bytes remain private, including whitespace between paragraphs.
    Registry integrity hashes detect corruption, not a malicious local operator
    able to rewrite both content and manifests. Human review is external.
    """

    def __init__(self, private_directory, database_sources, *, max_documents=100,
                 max_bytes=2 * 1024 * 1024, max_paragraph_bytes=16384,
                 max_paragraphs=10000, max_response_bytes=256 * 1024):
        bounds = ((max_documents, 1, 100), (max_bytes, 1, 8 * 1024 * 1024),
                  (max_paragraph_bytes, 1, 65536), (max_paragraphs, 1, 20000),
                  (max_response_bytes, 1024, 1024 * 1024))
        if any(not _integer(*bound) for bound in bounds):
            raise DocumentSourceError('Invalid document registry limits')
        self.root = Path(private_directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.database_sources = database_sources
        self.max_documents = max_documents
        self.max_bytes = max_bytes
        self.max_paragraph_bytes = max_paragraph_bytes
        self.max_paragraphs = max_paragraphs
        self.max_response_bytes = max_response_bytes

    @contextmanager
    def _lock(self):
        try:
            fd = os.open(self.root / '.registry.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'a') as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                yield
        except OSError:
            raise DocumentSourceError('Document registry unavailable') from None

    @staticmethod
    def _read(path, maximum):
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
                    raise DocumentSourceError('Document unavailable or exceeds byte limit')
                data = stream.read(maximum + 1)
                if len(data) > maximum:
                    raise DocumentSourceError('Document exceeds byte limit')
                return data
        except (OSError, ValueError, TypeError):
            raise DocumentSourceError('Document unavailable or invalid') from None

    def _binding(self, source_id, snapshot_sha256):
        if not _identifier(source_id) or not _identifier(snapshot_sha256, 64):
            raise DocumentSourceError('Invalid registered database binding')
        try:
            record = self.database_sources._record(source_id)
            if record['source_id'] != source_id or record['snapshot_sha256'] != snapshot_sha256:
                raise DocumentSourceError('Registered database binding mismatch')
            self.database_sources._data(record)
        except (DatabaseSourceError, KeyError, TypeError, ValueError):
            raise DocumentSourceError('Registered database binding unavailable or invalid') from None

    def _paragraphs(self, data, paragraph_byte_limit=None):
        paragraph_byte_limit = paragraph_byte_limit or self.max_paragraph_bytes
        try:
            text = data.decode('utf-8', errors='strict')
        except UnicodeError:
            raise DocumentSourceError('Only UTF-8 text documents are supported') from None
        if '\x00' in text:
            raise DocumentSourceError('Binary documents are unsupported')
        paragraphs, current, start, size = [], [], 1, 0
        def flush(end):
            if current:
                value = ''.join(current)
                digest = _sha(value.encode('utf-8'))
                paragraphs.append({'paragraph_id': f'p{len(paragraphs) + 1:05d}-{digest[:12]}',
                                   'line_start': start, 'line_end': end,
                                   'paragraph_sha256': digest, 'text': value})
                if len(paragraphs) > self.max_paragraphs:
                    raise DocumentSourceError('Document exceeds paragraph limit')
        # LF defines lines; retain CRLF and trailing LF exactly in returned text.
        pieces = text.split('\n')
        lines = [piece + '\n' for piece in pieces[:-1]]
        if pieces[-1]:
            lines.append(pieces[-1])
        for number, line in enumerate(lines, 1):
            length = len(line.encode('utf-8'))
            if length > paragraph_byte_limit:
                raise DocumentSourceError('Document line exceeds paragraph byte limit')
            if not line.strip():
                flush(number - 1)
                current, size = [], 0
                continue
            if current and size + length > paragraph_byte_limit:
                flush(number - 1)
                current, size = [], 0
            if not current:
                start = number
            current.append(line)
            size += length
        flush(len(lines))
        return paragraphs

    def _response(self, value):
        if len(_json(value)) > self.max_response_bytes:
            raise DocumentSourceError('Response exceeds byte limit; request a smaller page')
        return value

    @staticmethod
    def _public(record):
        keys = ('document_id', 'label', 'version', 'format', 'source_id',
                'snapshot_sha256', 'document_sha256', 'document_bytes', 'paragraph_count')
        return {**{key: record[key] for key in keys},
                'approval': 'external_review_required', 'applicability': 'unassessed'}

    def register(self, source_path, *, source_id, snapshot_sha256,
                 label='Source document', version='1'):
        """Trusted operator only. New registration never replaces older bytes."""
        self._binding(source_id, snapshot_sha256)
        if (not isinstance(label, str) or not 1 <= len(label) <= 120 or
                not isinstance(version, str) or not 1 <= len(version) <= 80):
            raise DocumentSourceError('Provide short public document label and version')
        try:
            source = Path(source_path).absolute()
        except (TypeError, ValueError, OSError):
            raise DocumentSourceError('Document unavailable or invalid') from None
        if source.suffix.lower() not in ('.txt', '.md', '.markdown'):
            raise DocumentSourceError('Only text and Markdown source files are supported')
        data = self._read(source, self.max_bytes)
        paragraphs = self._paragraphs(data)
        identifier = uuid.uuid4().hex
        record = {'document_id': identifier, 'source_id': source_id,
                  'snapshot_sha256': snapshot_sha256, 'label': label, 'version': version,
                  'format': 'utf8-paragraphs-v1', 'source_path': str(source),
                  'document_sha256': _sha(data), 'document_bytes': len(data),
                  'paragraph_count': len(paragraphs),
                  'paragraph_byte_limit': self.max_paragraph_bytes}
        manifest = {**record, 'manifest_sha256': _sha(_json(record))}
        if len(_json(manifest)) > 8192:
            raise DocumentSourceError('Document metadata exceeds byte limit')
        public = self._response(self._public(record))
        with self._lock():
            if len(list(self.root.glob('*.json'))) >= self.max_documents:
                raise DocumentSourceError('Document registry capacity reached')
            try:
                for suffix, content in (('.txt', data), ('.json', _json(manifest))):
                    fd = os.open(self.root / (identifier + suffix), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(content)
                    (self.root / (identifier + suffix)).chmod(0o400)
            except OSError:
                raise DocumentSourceError('Document registration could not be saved') from None
        return public

    def _load(self, document_id):
        if not _identifier(document_id):
            raise DocumentSourceError('Unknown registered document')
        try:
            manifest = json.loads(self._read(self.root / (document_id + '.json'), 8192))
            digest = manifest.pop('manifest_sha256')
            keys = {'document_id', 'source_id', 'snapshot_sha256', 'label', 'version',
                    'format', 'source_path', 'document_sha256', 'document_bytes', 'paragraph_count',
                    'paragraph_byte_limit'}
            if (set(manifest) != keys or digest != _sha(_json(manifest)) or
                    manifest['document_id'] != document_id or
                    manifest['format'] != 'utf8-paragraphs-v1' or
                    not _identifier(manifest['source_id']) or
                    not _identifier(manifest['snapshot_sha256'], 64) or
                    not _identifier(manifest['document_sha256'], 64) or
                    not isinstance(manifest['label'], str) or not 1 <= len(manifest['label']) <= 120 or
                    not isinstance(manifest['version'], str) or not 1 <= len(manifest['version']) <= 80 or
                    not isinstance(manifest['source_path'], str) or
                    not Path(manifest['source_path']).is_absolute() or
                    not _integer(manifest['document_bytes'], 0, self.max_bytes) or
                    not _integer(manifest['paragraph_count'], 0, self.max_paragraphs) or
                    not _integer(manifest['paragraph_byte_limit'], 1, self.max_paragraph_bytes)):
                raise ValueError
            data = self._read(self.root / (document_id + '.txt'), self.max_bytes)
            if len(data) != manifest['document_bytes'] or _sha(data) != manifest['document_sha256']:
                raise ValueError
            paragraphs = self._paragraphs(data, manifest['paragraph_byte_limit'])
            if len(paragraphs) != manifest['paragraph_count']:
                raise ValueError
            return manifest, paragraphs
        except (ValueError, TypeError, KeyError, AttributeError):
            raise DocumentSourceError('Registered document integrity check failed') from None

    def _bound_document(self, document_id, source_id, snapshot_sha256):
        self._binding(source_id, snapshot_sha256)
        record, paragraphs = self._load(document_id)
        if record['source_id'] != source_id or record['snapshot_sha256'] != snapshot_sha256:
            raise DocumentSourceError('Document database binding mismatch')
        return record, paragraphs

    @staticmethod
    def _page(offset, limit):
        if not _integer(offset, 0, 20000) or not _integer(limit, 1, 100):
            raise DocumentSourceError('Invalid document page bounds')

    def catalog(self, source_id, *, snapshot_sha256, offset=0, limit=20):
        self._page(offset, limit)
        self._binding(source_id, snapshot_sha256)
        paths = sorted(self.root.glob('*.json'))
        if len(paths) > self.max_documents:
            raise DocumentSourceError('Document registry exceeds capacity')
        documents = []
        for path in paths:
            record, _ = self._load(path.stem)
            if record['source_id'] == source_id and record['snapshot_sha256'] == snapshot_sha256:
                documents.append(self._public(record))
        return self._response({'documents': documents[offset:offset + limit], 'total': len(documents),
                               'offset': offset, 'limit': limit, 'truncated': offset + limit < len(documents)})

    def inspect(self, document_id, *, source_id, snapshot_sha256, offset=0, limit=50):
        self._page(offset, limit)
        record, paragraphs = self._bound_document(document_id, source_id, snapshot_sha256)
        descriptors = [{k: v for k, v in p.items() if k != 'text'} for p in paragraphs[offset:offset + limit]]
        return self._response({**self._public(record), 'paragraphs': descriptors,
                               'offset': offset, 'limit': limit, 'truncated': offset + limit < len(paragraphs)})

    def read_paragraph(self, document_id, paragraph_id, *, source_id,
                       snapshot_sha256, document_sha256):
        record, paragraphs = self._bound_document(document_id, source_id, snapshot_sha256)
        if not _identifier(document_sha256, 64) or document_sha256 != record['document_sha256']:
            raise DocumentSourceError('Document hash binding mismatch')
        for paragraph in paragraphs:
            if paragraph['paragraph_id'] == paragraph_id:
                return self._response({**self._public(record), **paragraph,
                                       'scope': 'exact_original_paragraph'})
        raise DocumentSourceError('Unknown registered paragraph')

    def check_drift(self, document_id, *, source_id, snapshot_sha256):
        record, _ = self._bound_document(document_id, source_id, snapshot_sha256)
        try:
            current = self._read(record['source_path'], self.max_bytes)
        except DocumentSourceError:
            return self._response({**self._public(record), 'status': 'source_unavailable', 'freshness': 'unknown'})
        observed = _sha(current)
        return self._response({**self._public(record), 'status': 'unchanged' if observed == record['document_sha256'] else 'changed',
                               'observed_document_sha256': observed, 'freshness': 'observation_at_check_time_only'})
