"""Bounded trusted-operator backup, separate from untrusted draft import.

A bundle contains the entire workspace store and its immutable registered inputs.
Hashes detect corruption; they do not authenticate an operator or confer approval.
Stop writers while creating a backup. Mutable originals and external runtimes are
not included. Registry source_path values remain historical provenance.
"""
from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import tempfile
import time

from .workspace_database import SQLiteSources
from .workspace_source_documents import DocumentSources

MAX_BYTES = 1024 * 1024 * 1024
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_FILES = 402
FORMAT = 'trusted-workspace-backup-1'


def _hash(data):
    return sha256(data).hexdigest()


def _read(path, maximum=MAX_FILE_BYTES):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise ValueError('Backup input is not a bounded regular file')
        data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError('Backup input exceeds byte limit')
        return data


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(0o600)


def _references(path):
    sources = set()
    documents = set()
    def scan(value):
        if isinstance(value, dict):
            doc = value.get('document_id')
            if isinstance(doc, str) and re.fullmatch('[0-9a-f]{32}', doc):
                documents.add(doc)
            for child in value.values():
                scan(child)
        elif isinstance(value, list):
            for child in value:
                scan(child)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA trusted_schema=OFF')
        deadline = time.monotonic() + 30
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        if db.execute('PRAGMA user_version').fetchone()[0] != 1:
            raise ValueError('Unsupported workspace store version')
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)] or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Workspace store integrity check failed')
        if db.execute("SELECT count(*) FROM operations WHERE state='running'").fetchone()[0]:
            raise ValueError('Quiesce operations before backup; running history is not portable')
        for content, digest in db.execute('SELECT content,digest FROM revisions'):
            if _hash(content.encode()) != digest:
                raise ValueError('Workspace revision digest mismatch')
            draft = json.loads(content)
            if draft.get('adapter') == 'registered-database-1':
                sources.add(draft['database']['source_id'])
            elif draft.get('adapter') not in ('commerce-csv-1', 'factory-csv-1'):
                raise ValueError('Unsupported workspace adapter for portable backup')
            scan(draft)
        for (content,) in db.execute('SELECT content FROM review_buffers UNION ALL SELECT request FROM operations UNION ALL SELECT result FROM operations WHERE result IS NOT NULL'):
            scan(json.loads(content))
    return sources, documents


def _validate_inputs(root):
    sources, documents = _references(root / 'workspace.sqlite')
    databases = SQLiteSources(root / 'databases')
    docs = DocumentSources(root / 'documents', databases, max_bytes=8 * 1024 * 1024,
                           max_paragraph_bytes=65536, max_paragraphs=20000)
    expected = {'workspace.sqlite'}
    for ident in sources:
        record = databases._record(ident)
        if record['source_id'] != ident:
            raise ValueError('Registered database identity mismatch')
        data = databases._data(record)
        if record['snapshot_bytes'] != len(data):
            raise ValueError('Registered database size mismatch')
        expected.update(f'databases/{ident}{suffix}' for suffix in ('.json', '.sqlite'))
    found = set()
    for path in (root / 'documents').glob('*.json'):
        record, _ = docs._load(path.stem)
        if record['source_id'] not in sources:
            raise ValueError('Unrelated document in backup')
        docs._binding(record['source_id'], record['snapshot_sha256'])
        found.add(path.stem)
        expected.update(f'documents/{path.stem}{suffix}' for suffix in ('.json', '.txt'))
    if not documents <= found:
        raise ValueError('Referenced registered document missing')
    # Bind every historical database draft to its actual immutable snapshot.
    with closing(sqlite3.connect((root / 'workspace.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
        for (content,) in db.execute('SELECT content FROM revisions'):
            draft = json.loads(content)
            if draft.get('adapter') == 'registered-database-1':
                binding = draft['database']
                if databases._record(binding['source_id'])['snapshot_sha256'] != binding['snapshot_sha256']:
                    raise ValueError('Workspace source hash binding mismatch')
    return expected


def _destination(destination, excluded):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must not exist')
    parent = destination.parent.resolve(strict=True)
    destination = parent / destination.name
    for source in excluded:
        source = Path(source).resolve()
        if destination == source or source in destination.parents:
            raise ValueError('Destination must be isolated from inputs')
    return destination


def create_backup(workspace, database_registry, document_registry, destination):
    """Create one coherent full-store snapshot; return manifest hash to pin restore."""
    workspace = Path(workspace).absolute()
    database_registry = Path(database_registry).absolute()
    document_registry = Path(document_registry).absolute() if document_registry else None
    destination = _destination(destination, [workspace, database_registry] + ([document_registry] if document_registry else []))
    if workspace.is_symlink() or not workspace.is_file():
        raise ValueError('Workspace store must be an existing regular file')
    with tempfile.TemporaryDirectory(prefix='.workspace-backup-', dir=destination.parent) as folder:
        stage = Path(folder) / 'bundle'
        stage.mkdir(mode=0o700)
        deadline = time.monotonic() + 30
        def progress(status, remaining, total):
            if time.monotonic() > deadline or total * page_size > MAX_FILE_BYTES:
                raise ValueError('Workspace snapshot exceeded time or byte limit')
        with closing(sqlite3.connect(workspace.as_uri() + '?mode=ro', uri=True, timeout=10)) as src:
            page_size = src.execute('PRAGMA page_size').fetchone()[0]
            with closing(sqlite3.connect(stage / 'workspace.sqlite')) as dst:
                src.backup(dst, pages=128, progress=progress, sleep=0.01)
                dst.execute('PRAGMA journal_mode=DELETE')
        (stage / 'workspace.sqlite').chmod(0o600)
        copied_bytes = (stage / 'workspace.sqlite').stat().st_size
        copied_files = 1
        def copy_input(source, target):
            nonlocal copied_bytes, copied_files
            if copied_files >= MAX_FILES:
                raise ValueError('Backup exceeds file count limit')
            data = _read(source, min(MAX_FILE_BYTES, MAX_BYTES - copied_bytes))
            copied_bytes += len(data)
            copied_files += 1
            _write(target, data)
        sources, required_documents = _references(stage / 'workspace.sqlite')
        for ident in sources:
            if not isinstance(ident, str) or not re.fullmatch('[0-9a-f]{32}', ident):
                raise ValueError('Invalid database reference')
            for suffix in ('.json', '.sqlite'):
                copy_input(database_registry / (ident + suffix), stage / 'databases' / (ident + suffix))
        # Preserve the bound catalog, including documents not yet used in an operation.
        if document_registry:
            paths = list(document_registry.glob('*.json'))
            if len(paths) > 100:
                raise ValueError('Document catalog exceeds supported bound')
            for path in paths:
                record = json.loads(_read(path, 8192))
                if record.get('source_id') in sources or path.stem in required_documents:
                    if not re.fullmatch('[0-9a-f]{32}', path.stem):
                        raise ValueError('Invalid document identity')
                    for suffix in ('.json', '.txt'):
                        copy_input(document_registry / (path.stem + suffix), stage / 'documents' / (path.stem + suffix))
        paths = _validate_inputs(stage)
        files = {name: {'sha256': _hash(_read(stage / name)), 'bytes': (stage / name).stat().st_size}
                 for name in sorted(paths)}
        if len(files) > MAX_FILES or sum(x['bytes'] for x in files.values()) > MAX_BYTES:
            raise ValueError('Backup exceeds total file or byte limit')
        manifest = {'format': FORMAT, 'scope': 'entire_workspace_store_and_bound_immutable_inputs',
                    'trust': 'trusted_local_operator_only', 'files': files,
                    'mutable_originals_included': False, 'external_runtimes_included': False}
        data = json.dumps(manifest, sort_keys=True, indent=2).encode()
        _write(stage / 'manifest.json', data)
        # mkdir reserves a previously absent destination, never replacing another bundle.
        destination.mkdir(mode=0o700)
        try:
            for child in stage.iterdir():
                shutil.move(str(child), destination / child.name)
        except BaseException:
            shutil.rmtree(destination)
            raise
    return {'manifest_sha256': _hash(data), 'files': len(files), 'bytes': sum(x['bytes'] for x in files.values())}


def restore_backup(bundle, destination, *, manifest_sha256, trusted_local=False):
    """Restore exact bytes/IDs into a new private directory; never merge approvals."""
    if trusted_local is not True:
        raise ValueError('Restore requires explicit trusted-local operator acknowledgement')
    bundle = Path(bundle).absolute()
    destination = _destination(destination, [bundle])
    raw = _read(bundle / 'manifest.json', 1024 * 1024)
    if _hash(raw) != manifest_sha256:
        raise ValueError('Backup manifest hash mismatch')
    manifest = json.loads(raw)
    if manifest.get('format') != FORMAT or not isinstance(manifest.get('files'), dict):
        raise ValueError('Unsupported backup manifest')
    files = manifest['files']
    if len(files) > MAX_FILES or not files:
        raise ValueError('Backup file count outside supported bound')
    total = 0
    with tempfile.TemporaryDirectory(prefix='.workspace-restore-', dir=destination.parent) as folder:
        stage = Path(folder) / 'restored'
        stage.mkdir(mode=0o700)
        for name, info in files.items():
            if not re.fullmatch(r'workspace\.sqlite|databases/[0-9a-f]{32}\.(?:sqlite|json)|documents/[0-9a-f]{32}\.(?:txt|json)', name):
                raise ValueError('Invalid backup member path')
            if (type(info.get('bytes')) is not int or not 0 <= info['bytes'] <= MAX_FILE_BYTES):
                raise ValueError('Invalid backup member size')
            total += info['bytes']
            if total > MAX_BYTES:
                raise ValueError('Backup exceeds total byte limit')
            parent = (bundle / name).parent
            if parent.is_symlink():
                raise ValueError('Backup directory symlinks are unsupported')
            data = _read(bundle / name, info['bytes'])
            if len(data) != info['bytes'] or _hash(data) != info['sha256']:
                raise ValueError('Backup member integrity mismatch')
            _write(stage / name, data)
        if set(files) != _validate_inputs(stage):
            raise ValueError('Backup manifest does not match referenced input closure')
        _write(stage / 'manifest.json', raw)
        destination.mkdir(mode=0o700)
        try:
            for child in stage.iterdir():
                shutil.move(str(child), destination / child.name)
        except BaseException:
            shutil.rmtree(destination)
            raise
    return {'manifest_sha256': manifest_sha256, 'files': len(files), 'bytes': total,
            'operation_history': 'preserved_without_execution', 'approval_authority': 'trusted_local_backup'}
