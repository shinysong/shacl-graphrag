"""Prepare a bounded offline profiling artifact; never invoke upstream or models."""
import argparse
import json
import os
from pathlib import Path

from .auto_ontology_profile import prepare_profile
from .workspace_database import SQLiteSources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', required=True, type=Path)
    parser.add_argument('--source-id', required=True)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--limit', type=int, default=1000)
    args = parser.parse_args(argv)
    if not args.registry.is_dir():
        parser.error('Existing local registry required')
    os.umask(0o077)
    try:
        result = prepare_profile(SQLiteSources(args.registry), args.source_id,
                                 args.destination, limit_per_table=args.limit)
    except (ValueError, OSError):
        parser.exit(1, 'Profile destination or bounds rejected; existing files were not replaced.\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
