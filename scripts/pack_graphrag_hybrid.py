"""Pack saved B logits with unchanged A parent selection and token accounting."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
from graphrag_dense import file_hash, rank_pack


def pack_one(candidate, scored, children, chunks, count):
    if candidate['question_id'] != scored['question_id']:
        raise ValueError('question mismatch')
    if candidate['status'] != 'ready_for_reranker' or scored['status'] != 'ok':
        raise ValueError('upstream failure retained')
    ids = candidate['candidate_child_ids']
    if not 1 <= len(ids) <= 20 or ids != sorted(set(ids)):
        raise ValueError('invalid candidate IDs/count')
    if [s['child_id'] for s in scored['scores']] != ids:
        raise ValueError('partial, reordered or unexpected scores')
    subset = [children[i] for i in ids]
    return rank_pack(subset, [s['score'] for s in scored['scores']], chunks, count,
                     child_k=len(ids), parent_k=8, token_cap=4096, byte_cap=64000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    summary = {'status': 'started', 'planned_questions': 24, 'new_model_calls': 0}
    try:
        manifest = json.loads(args.manifest.read_text())
        for path, expected in manifest['hashes'].items():
            if file_hash(path) != expected:
                raise ValueError('hash mismatch: ' + path)
        if importlib.metadata.version('tokenizers') != '0.22.1':
            raise ValueError('original A tokenizer runtime required')
        from tokenizers import Tokenizer
        p = manifest['paths']
        tokenizer = Tokenizer.from_file(p['tokenizer'])
        tokenizer.no_padding()
        tokenizer.no_truncation()
        count = lambda text: len(tokenizer.encode(text).ids)
        source = json.loads(Path(p['source']).read_text())
        children_list = json.loads(Path(p['children']).read_text())
        children = {c['child_id']: c for c in children_list}
        chunks = {c['chunk_id']: c for c in source['chunks']}
        questions = json.loads(Path(p['questions']).read_text())['questions']
        candidates = [json.loads(x) for x in Path(p['candidates']).read_text().splitlines()]
        scored = json.loads(Path(p['scores']).read_text())
        ids = [q['question_id'] for q in questions]
        if len(ids) != 24 or len(set(ids)) != 24 or len(children) != 1483 or len(chunks) != 814:
            raise ValueError('bound input cardinality mismatch')
        if any([r['question_id'] for r in records] != ids for records in (candidates, scored)):
            raise ValueError('missing/duplicate/reordered question records')
        frozen = args.output / 'frozen'
        frozen.mkdir()
        for name, path in p.items():
            if name != 'tokenizer':
                shutil.copyfile(path, frozen / Path(path).name)
        shutil.copyfile(args.manifest, args.output / 'manifest.json')
        for name in ('pack_graphrag_hybrid.py','graphrag_dense.py','build_graphrag_search.py','graphrag_expand.py'):
            shutil.copyfile(Path('scripts') / name, frozen / name)
        config_hash = file_hash(args.manifest)
        for q, candidate, score in zip(questions, candidates, scored):
            row = {'run_id': args.output.name, 'question_id': q['question_id'], 'arm': 'B',
                   'attempt_id': 1, 'generation_executed': False,
                   'source_sha256': manifest['hashes'][p['source']],
                   'configuration_sha256': config_hash}
            try:
                if candidate.get('question') != q['question']:
                    raise ValueError('question text mismatch')
                result = pack_one(candidate, score, children, chunks, count)
                row.update(result, error=None if result['status']=='ok' else 'no parent fits budget')
                row['seed_chunk_ids'] = list(result['selected_chunk_ids'])
                row['candidate_chunk_ids'] = [r['parent_id'] for r in result['top_parents']]
            except Exception as exc:
                row.update(status='retrieval_error', error=f'{type(exc).__name__}: {exc}')
            rows.append(row)
        summary.update(status='completed', ok=sum(r['status']=='ok' for r in rows))
    except Exception as exc:
        summary.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        summary['ok'] = sum(r['status']=='ok' for r in rows)
        summary['failures'] = 24-summary['ok']
        if summary['status']=='completed' and summary['failures']:
            summary['status']='partial_failure'
        (args.output/'retrieval.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary))


if __name__ == '__main__':
    main()
