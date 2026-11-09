"""Prepare refined hybrid candidates from frozen A1; no model or gold inputs."""
import argparse
import json
from pathlib import Path
import shutil

from graphrag_dense import file_hash
from prepare_graphrag_hybrid import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    summary = {'status': 'failed', 'planned_questions': 24, 'paid_calls': 0,
               'reranking_executed': False}
    try:
        manifest = json.loads(args.manifest.read_text())
        paths = manifest['paths']
        required = set(paths.values()) | {str(Path(__file__).relative_to(Path.cwd())) if Path(__file__).is_absolute() else __file__,
            'scripts/prepare_graphrag_hybrid.py', 'scripts/graphrag_candidates.py', 'scripts/graphrag_dense.py'}
        if not required <= set(manifest['hashes']):
            raise ValueError('missing input/code hash binding')
        for path, expected in manifest['hashes'].items():
            if file_hash(path) != expected:
                raise ValueError('hash mismatch: ' + path)
        import importlib.metadata
        if importlib.metadata.version('numpy') != '2.3.4':
            raise ValueError('original numpy runtime required')
        import numpy as np
        children = json.loads(Path(paths['children']).read_text())
        questions = json.loads(Path(paths['questions']).read_text())['questions']
        if len(children) != 814 or len(questions) != 24:
            raise ValueError('refined development counts mismatch')
        if len({c['child_id'] for c in children}) != 814 or len({q['question_id'] for q in questions}) != 24:
            raise ValueError('duplicate IDs')
        if any(set(q) != {'question_id', 'question'} for q in questions):
            raise ValueError('runtime questions must contain only ID and text')
        saved = [json.loads(x) for x in Path(paths['saved_A']).read_text().splitlines()]
        frozen = args.output / 'frozen'
        frozen.mkdir()
        for key, path in paths.items():
            shutil.copyfile(path, frozen / (key + Path(path).suffix))
        for path in required - set(paths.values()):
            shutil.copyfile(path, frozen / Path(path).name)
        shutil.copyfile(args.manifest, args.output / 'manifest.json')
        rows = prepare(children, questions,
                       np.load(paths['child_vectors'], allow_pickle=False),
                       np.load(paths['query_vectors'], allow_pickle=False), saved)
        failures = sum(r['status'] != 'ready_for_reranker' for r in rows)
        summary.update(status='completed' if not failures else 'partial_failure',
                       attempted=len(rows), ready=len(rows)-failures, failures=failures,
                       candidate_pairs=sum(r.get('candidate_count', 0) for r in rows))
    finally:
        output = args.output / 'candidates.jsonl'
        output.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows))
        summary['candidates_sha256'] = file_hash(output)
        (args.output / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
        print(json.dumps(summary))


if __name__ == '__main__':
    main()
