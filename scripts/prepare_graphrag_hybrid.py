"""Freeze B candidates using original A NumPy runtime; no reranker or gold."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil

from graphrag_candidates import candidates
from graphrag_dense import file_hash


def validate_vectors(child_vectors, query_vectors, child_count, query_count):
    import numpy as np
    for values, count in ((child_vectors, child_count), (query_vectors, query_count)):
        if values.dtype != np.dtype('float32') or values.shape != (count, 384):
            raise ValueError('expected float32 vector matrix with bound shape')
        if not np.isfinite(values).all():
            raise ValueError('nonfinite vectors')
        if not np.allclose(np.linalg.norm(values, axis=1), 1, atol=1e-5, rtol=0):
            raise ValueError('non-unit vectors')


def prepare(children, questions, cv, qv, saved_a):
    import numpy as np
    validate_vectors(cv, qv, len(children), len(questions))
    if len(saved_a) != len(questions) or [x['question_id'] for x in saved_a] != [q['question_id'] for q in questions]:
        raise ValueError('A/question order mismatch')
    rows = []
    for q, vector, old in zip(questions, qv, saved_a):
        row = {'question_id': q['question_id'], 'status': 'candidate_error',
               'reranking_executed': False}
        try:
            scores = cv @ vector
            if scores.dtype != np.dtype('float32') or not np.isfinite(scores).all():
                raise ValueError('invalid score dtype/values')
            top = sorted(range(len(children)), key=lambda i: (-float(scores[i]), children[i]['child_id']))[:20]
            if old['status'] != 'ok' or [children[i]['child_id'] for i in top] != [h['child_id'] for h in old['top_children']]:
                raise ValueError('dense ranking differs from saved A')
            row.update(candidates(children, q['question'], scores))
            row['question'] = q['question']
            row['dense_top20_agrees_with_A'] = True
        except Exception as exc:
            row.update(status='candidate_error', error=f'{type(exc).__name__}: {exc}')
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    summary = {'status': 'started', 'planned_questions': 24, 'reranking_executed': False}
    try:
        manifest = json.loads(args.manifest.read_text())
        for path, expected in manifest['hashes'].items():
            if file_hash(path) != expected:
                raise ValueError('hash mismatch: ' + path)
        if importlib.metadata.version('numpy') != '2.3.4':
            raise ValueError('original A numpy2.3.4 required')
        import numpy as np
        paths = manifest['paths']
        children = json.loads(Path(paths['children']).read_text())
        questions = json.loads(Path(paths['questions']).read_text())['questions']
        if len(children) != 1483 or len(questions) != 24:
            raise ValueError('bound corpus counts mismatch')
        if len({c['child_id'] for c in children}) != 1483 or len({q['question_id'] for q in questions}) != 24:
            raise ValueError('duplicate IDs')
        if any(set(q) != {'question_id', 'question'} for q in questions):
            raise ValueError('only original question records permitted')
        cv = np.load(paths['child_vectors'], allow_pickle=False)
        qv = np.load(paths['query_vectors'], allow_pickle=False)
        old = [json.loads(line) for line in Path(paths['saved_A']).read_text().splitlines()]
        frozen = args.output / 'frozen'
        frozen.mkdir()
        for key in ('children', 'questions'):
            shutil.copyfile(paths[key], frozen / (key + '.json'))
        shutil.copyfile(args.manifest, args.output / 'manifest.json')
        for path in ('scripts/prepare_graphrag_hybrid.py', 'scripts/graphrag_candidates.py'):
            shutil.copyfile(path, frozen / Path(path).name)
        rows = prepare(children, questions, cv, qv, old)
        failed = sum(r['status'] != 'ready_for_reranker' for r in rows)
        summary.update(status='completed' if not failed else 'partial_failure',
                       attempted=len(rows), ready=len(rows)-failed, failures=failed,
                       candidate_pairs=sum(r.get('candidate_count', 0) for r in rows))
    except Exception as exc:
        summary.update(status='failed', error=f'{type(exc).__name__}: {exc}',
                       attempted=0, ready=0, failures=24)
        raise
    finally:
        data = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
        (args.output / 'candidates.jsonl').write_text(data)
        summary['candidates_sha256'] = hashlib.sha256(data.encode()).hexdigest()
        (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary))


if __name__ == '__main__':
    main()
