"""Operator-only SQLite registration; never expose source paths to the browser.

Run with ``uv run --locked python -m apps.factory_lab.database_sources_cli``.
Registration captures the whole bounded database. It neither approves mappings
nor calls a language model. The local registry is private and single-user.
"""
import argparse
import json
import os
from pathlib import Path

from .workspace_database import DatabaseSourceError, SQLiteSources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True,
                        help='Private directory for immutable SQLite snapshots')
    commands = parser.add_subparsers(dest='command', required=True)
    register = commands.add_parser('register', help='Capture an authorized local SQLite database')
    register.add_argument('source', type=Path)
    register.add_argument('--label', required=True,
                          help='Public label; do not include private paths or secrets')
    inspect = commands.add_parser('inspect', help='Read schema, exact counts and bounded samples')
    inspect.add_argument('source_id')
    inspect.add_argument('--sample-limit', type=int, default=5)
    drift = commands.add_parser('check-drift', help='Compare current original with the saved snapshot')
    drift.add_argument('source_id')
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.command != 'register' and not args.registry.is_dir():
            raise DatabaseSourceError('Registered source directory is unavailable')
        registry = SQLiteSources(args.registry)
        if args.command == 'register':
            result = registry.register(args.source, label=args.label)
        elif args.command == 'inspect':
            result = registry.inspect(args.source_id, sample_limit=args.sample_limit)
        else:
            result = registry.check_drift(args.source_id)
    except (DatabaseSourceError, OSError):
        # OS messages can expose the private source/registry path.
        parser.exit(1, 'Source operation failed; verify the local path, identifier and supported SQLite bounds.\n')
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
