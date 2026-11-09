"""Offline consumed-question locator diagnostic; no scorer or retrieval input."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from graphrag_explicit_anchor import resolve

INPUTS = {
    'questions': 'research/graphrag-evidence-1/development-questions.json',
    'source': 'research/graphrag-evidence-1/source-corpus-v1.json',
    'resolver': 'scripts/graphrag_explicit_anchor.py',
    'validator': 'scripts/graphrag_expand.py',
    'contract': 'research/refined-hybrid-1/explicit-anchor-contract-v1.json',
    'runner': 'scripts/run_explicit_anchor_diagnostic.py',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    out.mkdir(parents=True, exist_ok=False)
    blobs = {key: Path(path).read_bytes() for key, path in INPUTS.items()}
    hashes = {key: hashlib.sha256(b).hexdigest() for key, b in blobs.items()}
    frozen = out / 'frozen'; frozen.mkdir()
    for key, b in blobs.items():
        (frozen / Path(INPUTS[key]).name).write_bytes(b)
    questions = json.loads(blobs['questions'])['questions']
    if (len(questions) != 24 or any(set(q) != {'question_id', 'question'}
            or not isinstance(q['question'], str) or not isinstance(q['question_id'], str)
            for q in questions)
            or len({q['question_id'] for q in questions}) != 24):
        raise ValueError('expected all 24 unique question-only development records')
    # Persist full denominator before the loop; interruption leaves unprocessed IDs visible.
    manifest = dict(inputs=INPUTS, input_hashes=hashes, planned_question_ids=[q['question_id'] for q in questions],
                    consumed_development=True, scorer_used=False, retrieval_run=False, paid_calls=0)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    rows = []
    with (out / 'results.jsonl').open('w') as handle:
        for q in questions:
            try:
                # question_id is output lineage only, never provided to the resolver.
                result = resolve(q['question'], blobs['source'])
                row = dict(question_id=q['question_id'], execution_status='ok', result=result)
            except Exception as exc:
                row = dict(question_id=q['question_id'], execution_status='error',
                           error_type=type(exc).__name__, result=None)
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=False) + '\n'); handle.flush()
    stable = all(hashlib.sha256(Path(INPUTS[k]).read_bytes()).hexdigest() == v for k,v in hashes.items())
    summary = dict(planned=24, processed=len(rows), errors=sum(r['execution_status'] != 'ok' for r in rows),
        outcome_counts=dict(Counter(r['result']['status'] for r in rows if r['result'])),
        unique_candidate_nodes=sorted({nid for r in rows if r['result'] for nid in r['result']['candidate_node_ids']}),
        input_hashes_stable=stable, consumed_development=True,
        limitation='Literal locator resolution only; no question interpretation, answerability, truth, retrieval gain or fresh benchmark.',
        paid_calls=0, retrieval_run=False)
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if stable and not summary['errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
