"""Register/list authorized local UTF-8 documents against immutable SQLite snapshots.

Run with ``uv run --locked python -m apps.factory_lab.document_sources_cli``.
Registration preserves original bytes; it does not interpret or approve policy.
Labels and versions are public metadata and must not contain paths or secrets.
"""
import argparse
import json
import os
from pathlib import Path

from .workspace_database import DatabaseSourceError, SQLiteSources
from .workspace_source_documents import DocumentSourceError, DocumentSources


class _SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's ordinary errors echo invalid values, potentially paths.
        self.exit(2, 'Invalid document command arguments; use --help for required options.\n')


def main(argv=None):
    parser = _SafeParser(description=__doc__)
    parser.add_argument('--database-registry', type=Path, required=True,
                        help='Existing private SQLite snapshot registry')
    parser.add_argument('--registry', type=Path, required=True,
                        help='Separate private directory for immutable documents')
    commands = parser.add_subparsers(dest='command', required=True)
    register = commands.add_parser('register', help='Capture authorized text or Markdown bytes')
    register.add_argument('source', type=Path)
    register.add_argument('--label', required=True, help='Public label without paths or secrets')
    register.add_argument('--version', required=True, help='Explicit public document version')
    listing = commands.add_parser('list', help='List documents bound to one saved database snapshot')
    listing.add_argument('--offset', type=int, default=0)
    listing.add_argument('--limit', type=int, default=20)
    for command in (register, listing):
        command.add_argument('--source-id', required=True)
        command.add_argument('--snapshot-sha256', required=True)
    args = parser.parse_args(argv)
    previous_umask = os.umask(0o077)
    try:
        if not args.database_registry.is_dir():
            raise DocumentSourceError('Existing database registry required')
        if args.registry.resolve() == args.database_registry.resolve():
            raise DocumentSourceError('Separate registry directories required')
        if args.command == 'list' and not args.registry.is_dir():
            raise DocumentSourceError('Existing document registry required')
        databases = SQLiteSources(args.database_registry)
        documents = DocumentSources(args.registry, databases)
        binding = {'source_id': args.source_id, 'snapshot_sha256': args.snapshot_sha256}
        if args.command == 'register':
            result = documents.register(args.source, **binding,
                                        label=args.label, version=args.version)
        else:
            result = documents.catalog(**binding, offset=args.offset, limit=args.limit)
    except (DatabaseSourceError, DocumentSourceError, OSError, ValueError, RuntimeError):
        parser.exit(1, 'Document operation failed; verify registry directories, snapshot binding, '
                    'document format and supported bounds.\n')
    finally:
        os.umask(previous_umask)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
