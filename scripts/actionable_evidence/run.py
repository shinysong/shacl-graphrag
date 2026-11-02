"""Run isolated offline rows. Never reads scorer contents or imports generator."""
import argparse
import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'research/actionable-evidence-1'
ARMS = ('direct_local_candidate', 'matched_Python_relation_candidate', 'SHACL_AF_relation_candidate')
POST = ('no_postcheck', 'shadow_revalidation')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if not args.run_id.replace('-', '').isalnum():
        raise SystemExit('Invalid run ID')
    output = STUDY / 'runs' / args.run_id
    output.mkdir(parents=True, exist_ok=False)
    inputs = sorted((STUDY / 'fixtures/runtime').glob('*.json'))
    if len(inputs) != 32:
        raise SystemExit('Expected exactly32 frozen inputs')
    manifest = json.loads((STUDY / 'fixtures/manifest.json').read_text())
    for p in inputs:
        assert hashlib.sha256(p.read_bytes()).hexdigest() == manifest['runtime_sha256'][p.stem]
    if args.smoke:
        inputs = [p for p in inputs if p.stem in ('c000', 'c008')]
    expected = len(inputs) * len(ARMS) * len(POST)
    assert expected == (12 if args.smoke else 192)
    files = list((ROOT / 'scripts/actionable_evidence').glob('*.py')) + list(STUDY.glob('*.ttl'))
    files += [STUDY/'implementation-contract.md', STUDY/'protocol.json', ROOT/'uv.lock']
    files += list((STUDY/'fixtures').rglob('*.json'))
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    freeze = dict(started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  expected_rows=expected, smoke=args.smoke, timeout_seconds=30,
                  attempts_per_row=1, hashes=hashes, versions={n:importlib.metadata.version(n) for n in ('rdflib','pyshacl')},
                  api_calls=0, source_mutations=0)
    (output/'freeze.json').write_text(json.dumps(freeze, indent=2)+'\n')
    count, failures = 0, 0
    with (output/'outputs.jsonl').open('x') as sink:
        for path in inputs:
            for arm in ARMS:
                for post in POST:
                    key = f'{path.stem}-{arm}-{post}'
                    start = time.monotonic()
                    row = dict(case_id=path.stem, arm=arm, postcheck=post,
                               input_sha256=manifest['runtime_sha256'][path.stem])
                    cmd = [sys.executable, '-m', 'scripts.actionable_evidence.runtime', '--input', str(path),
                           '--arm', arm, '--postcheck', post]
                    try:
                        done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
                        (output/f'{key}.stderr.txt').write_text(done.stderr)
                        (output/f'{key}.stdout.txt').write_text(done.stdout)
                        row['exit_code'] = done.returncode
                        if done.returncode:
                            row.update(status='execution_error', error=done.stderr[-2000:])
                        else:
                            row.update(status='ok', result=json.loads(done.stdout))
                    except subprocess.TimeoutExpired as exc:
                        def decode(v):
                            return v.decode(errors='replace') if isinstance(v, bytes) else (v or '')
                        (output/f'{key}.stderr.txt').write_text(decode(exc.stderr))
                        (output/f'{key}.stdout.txt').write_text(decode(exc.stdout))
                        row.update(status='timeout', exit_code=None, error='30second timeout; no retry')
                    except (ValueError, OSError) as exc:
                        row.update(status='execution_error', error=str(exc))
                    row['elapsed_seconds'] = time.monotonic()-start
                    sink.write(json.dumps(row, sort_keys=True)+'\n'); sink.flush()
                    count += 1; failures += row['status'] != 'ok'
            print(json.dumps({'completed_cases': path.stem, 'rows': count, 'failures': failures}), flush=True)
    changed = [rel for rel, digest in hashes.items() if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest]
    result = dict(rows=count, expected_rows=expected, failures=failures, changed_inputs=changed,
                  finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (output/'completion.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    if failures or changed or count!=expected:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
