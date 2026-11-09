"""Offline envelope adapter only; no references, retrieval or answer generation."""
import argparse
import hashlib
import json
from pathlib import Path
from scripts.graphrag_check import canonical_bytes


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    rows_path = args.run / 'rows.jsonl'
    before = hashlib.sha256(rows_path.read_bytes()).hexdigest()
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    groups = {arm: [] for arm in ('A1', 'B', 'C', 'D', 'E')}
    seen = set()
    for row in rows:
        key = (row['question_id'], row['arm'])
        if key in seen:
            raise ValueError('duplicate question/arm')
        seen.add(key)
        r = row['result']
        out = {k: r[k] for k in ('status', 'selected_chunks', 'selected_chunk_ids', 'evidence_sha256') if k in r}
        out.update(question_id=row['question_id'], arm=row['arm'], error=r.get('error'))
        if r['status'] == 'ok':
            raw = canonical_bytes(r['selected_chunks'])
            if hashlib.sha256(raw).hexdigest() != r['evidence_sha256']:
                raise ValueError('saved evidence hash mismatch')
            out['evidence_bytes'] = len(raw)
        groups[row['arm']].append(out)
    args.output.mkdir(parents=True, exist_ok=False)
    for arm, outputs in groups.items():
        (args.output / (arm + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in outputs))
    if hashlib.sha256(rows_path.read_bytes()).hexdigest() != before:
        raise ValueError('input changed')
    manifest = {str(rows_path): before, str(Path(__file__)): hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    manifest.update({str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.glob('*.jsonl')})
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({arm: len(v) for arm, v in groups.items()}))


if __name__ == '__main__':
    main()
