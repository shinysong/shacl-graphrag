"""Operator-only installed upstream invocation; does not authorize paid calls."""
import argparse
import json
import os
from pathlib import Path

from .auto_ontology_bridge import AutoOntologyError, BridgeLimits, invoke
from .workspace_database import DatabaseSourceError, SQLiteSources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', required=True, type=Path)
    parser.add_argument('--source-id', required=True)
    parser.add_argument('--output-root', required=True, type=Path)
    parser.add_argument('--upstream-root', required=True, type=Path)
    parser.add_argument('--upstream-python', required=True, type=Path)
    parser.add_argument('--operator-config', required=True, type=Path,
                        help='Private JSON with explicit postgres and optional trusted gateway settings')
    parser.add_argument('--mode', choices=('catalog', 'semantic'), default='catalog')
    parser.add_argument('--limits', type=Path, help='Optional JSON BridgeLimits overrides')
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        if not args.registry.is_dir():
            raise AutoOntologyError('Registry unavailable')
        config = json.loads(args.operator_config.read_text())
        limits = BridgeLimits(**json.loads(args.limits.read_text())) if args.limits else BridgeLimits()
        receipt = invoke(SQLiteSources(args.registry), args.source_id, output_root=args.output_root,
                         upstream_root=args.upstream_root, python_executable=args.upstream_python,
                         operator_config=config, mode=args.mode, limits=limits)
    except (AutoOntologyError, DatabaseSourceError, OSError, ValueError, TypeError):
        parser.exit(1, 'Invocation rejected or failed; inspect private receipts and operator configuration.\n')
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt['status'] == 'returned_requires_review' else 1


if __name__ == '__main__':
    raise SystemExit(main())
