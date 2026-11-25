"""Private trusted-operator full-store backup/restore, separate from draft import.

Stop application writers before backup. Restore only a trusted local bundle into
an absent directory; supply the manifest hash returned at backup time. Start the
server with restored workspace.sqlite, databases/ and documents/ paths. Original
mutable sources, credentials, models and native binaries are not bundled.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3

from .workspace_backup import create_backup, restore_backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    backup = sub.add_parser('backup')
    backup.add_argument('--workspace', type=Path, required=True)
    backup.add_argument('--database-registry', type=Path, required=True)
    backup.add_argument('--document-registry', type=Path)
    backup.add_argument('--destination', type=Path, required=True)
    restore = sub.add_parser('restore')
    restore.add_argument('--bundle', type=Path, required=True)
    restore.add_argument('--destination', type=Path, required=True)
    restore.add_argument('--manifest-sha256', required=True)
    restore.add_argument('--trusted-local-backup', action='store_true', required=True)
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if args.command == 'backup':
            result = create_backup(args.workspace, args.database_registry,
                                   args.document_registry, args.destination)
        else:
            result = restore_backup(args.bundle, args.destination,
                                    manifest_sha256=args.manifest_sha256,
                                    trusted_local=args.trusted_local_backup)
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError, RecursionError):
        parser.exit(1, 'Backup/restore failed; inspect local input integrity, quiescence, bounds and destination.\n')
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
