#!/usr/bin/env python3
"""Recompute archived development scores offline; never launch a database/model.

Run from the repository root. Hashes detect changes against a local snapshot;
they do not authenticate remote execution or establish external factual truth.
"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile

BASE = Path('research/backend-reasoning-review-1')
RUNS = {
    'offline-001': ('bindings', ('backend', 'case_id')),
    'live-001': ('bindings', ('backend', 'case_id')),
    'inference-offline-001': ('inference', ('variant', 'arm', 'query_id')),
    'inference-live-001': ('inference', ('variant', 'arm', 'query_id')),
    'updates-offline-001': ('updates', ('event', 'arm', 'query_id')),
    'updates-live-001': ('updates', ('event', 'arm', 'query_id')),
    'rdf-import-live-001': ('import', ('case', 'operation')),
    'import-followup-live-001': ('import', ('case', 'operation')),
    'advisory-replay-001': ('advisory', ('id', 'policy')),
    'advisory-scope-001': ('scope', ('row_index', 'policy', 'checker')),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coverage(plan, rows, fields):
    key = lambda row: tuple(row[field] for field in fields)
    planned, observed = [key(x) for x in plan], [key(x) for x in rows]
    if len(set(planned)) != len(planned):
        raise ValueError('duplicate planned slot')
    if len(set(observed)) != len(observed):
        raise ValueError('duplicate observed slot')
    if set(planned) != set(observed):
        raise ValueError('missing or unplanned observed slot')
    return len(planned)


def verify_manifest(root, entries):
    for relative, expected in entries.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f'missing/out-of-root artifact: {relative}')
        if sha(path) != expected:
            raise ValueError(f'changed artifact: {relative}')


def verify_cleanup(path):
    receipts = json.loads(path.read_text())
    for row in receipts:
        if row.get('status', 'completed') != 'completed':
            raise ValueError(f'failed cleanup in {path}')
        receipt = row.get('receipt', row)
        if receipt is None:  # SQLite/RDFLib have no remote cleanup receipt.
            if row.get('backend') not in ('sqlite_python', 'rdflib_offline'):
                raise ValueError(f'unexpected null cleanup in {path}')
        elif receipt.get('remaining') not in (0, False):
            raise ValueError(f'nonempty or missing cleanup count in {path}')
    return len(receipts)


def replay(name, scorer, fields, scratch):
    original = BASE / name
    plan = json.loads((original / 'plan.json').read_text())
    rows = [json.loads(line) for line in (original / 'results.jsonl').read_text().splitlines()]
    count = coverage(plan, rows, fields)
    copy = scratch / name
    copy.mkdir()
    for filename in ('plan.json', 'results.jsonl', 'inputs.json', 'cases.json'):
        if (original / filename).exists():
            shutil.copyfile(original / filename, copy / filename)
    old_argv = sys.argv
    try:
        sys.argv = [f'score_{scorer}.py', str(copy)]
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            runpy.run_path(str(BASE / 'evaluation' / f'score_{scorer}.py'), run_name='__main__')
        (copy / 'scorer.log').write_text(captured.getvalue())
    finally:
        sys.argv = old_argv
    if json.loads((copy / 'evaluation.json').read_text()) != json.loads((original / 'evaluation.json').read_text()):
        raise ValueError(f'archived evaluation differs: {name}')
    cleanup_count = verify_cleanup(original / 'cleanup.json') if (original / 'cleanup.json').exists() else 0
    if (original / 'final-cleanup.json').exists():
        final = json.loads((original / 'final-cleanup.json').read_text())
        if final != {'constraints': [], 'nodes': [{'count': 0}]}:
            raise ValueError(f'nonempty final cleanup: {name}')
    return {'run': name, 'planned': count, 'observed': len(rows), 'evaluation_reproduced': True,
            'cleanup_receipts_checked': cleanup_count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory under ignored _workspace')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output = args.output.resolve()
    if not output.is_relative_to(root / '_workspace') or output.exists():
        parser.error('output must be a new directory under _workspace')
    output.mkdir(parents=True)
    manifest_path = BASE / 'evaluation' / 'artifact-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    result = {'status': 'failed', 'network_calls': 0, 'scope': 'Saved development artifacts only; no QA efficacy or remote execution authentication.', 'runs': []}
    try:
        verify_manifest(root, manifest['sha256'])
        with tempfile.TemporaryDirectory(prefix='replay-', dir=output) as temporary:
            for name, (scorer, fields) in RUNS.items():
                result['runs'].append(replay(name, scorer, fields, Path(temporary)))
        # Ensure scorers did not mutate any original archived artifact.
        verify_manifest(root, manifest['sha256'])
        result.update(status='passed', manifest_sha256=sha(manifest_path), hashed_artifacts=len(manifest['sha256']))
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
    (output / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
