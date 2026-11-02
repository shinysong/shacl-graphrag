"""Frozen A1/A2 local vector retrieval; references only enter a separate scorer."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import traceback
from graphrag_dense import Encoder, file_hash, rank_pack
from graphrag_semantic_projection import project

BASE = Path('research/graphrag-evidence-1')

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--tokenizer', type=Path, required=True)
    a = parser.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    summary = {'status': 'started', 'paid_calls': 0, 'generation_calls': 0,
               'scope': 'Consumed development; search projection and candidate eligibility, not DB engines'}
    questions = []
    outputs = {'A1': [], 'A2': []}
    try:
        import numpy as np
        source_path = BASE/'source-corpus-v1.json'
        question_path = BASE/'dense-retrieval-001/frozen/development-questions.json'
        query_path = BASE/'dense-retrieval-001/query-vectors.npy'
        if file_hash(source_path) != '900bb25d15bcb4dbab89076d3a1372d84762829dcd645bae7c17bc60b9693ac8':
            raise ValueError('source changed')
        old_manifest = json.loads((BASE/'dense-retrieval-001/manifest.json').read_text())
        expected_q = old_manifest['files']['research/graphrag-evidence-1/development-questions.json']
        if file_hash(question_path) != expected_q or file_hash(query_path) != '7e3c1cbd13026766b29ab07872437d71e4225db2ddbd8e81dde1938fb0d65aed':
            raise ValueError('saved query binding mismatch')
        questions = json.loads(question_path.read_text())['questions']
        if len(questions) != 24 or any(set(q) != {'question_id','question'} for q in questions):
            raise ValueError('question contract')
        source = json.loads(source_path.read_text())
        encoder = Encoder(a.model, a.tokenizer)
        children = project(source, encoder.count)
        assert len({c['parent_id'] for c in children}) == 814
        frozen = a.output/'frozen';frozen.mkdir()
        inputs = [source_path, question_path, query_path, Path(__file__),
                  Path('scripts/graphrag_semantic_projection.py'), Path('scripts/graphrag_dense.py'),
                  Path('scripts/build_graphrag_search.py'), Path('scripts/graphrag_expand.py'),
                  Path('research/vector-refinement-1/protocol.md')]
        manifest = {'files': {str(p): file_hash(p) for p in inputs},
                    'model_sha256': file_hash(a.model), 'tokenizer_sha256': file_hash(a.tokenizer),
                    'config': {'child_k':20,'parent_k':8,'accounting_token_cap':4096,'byte_cap':64000,
                               'A1':'all projected parents','A2':'node parents only',
                               'query_vectors':'reuse original A exactly','max_seconds':900}}
        for p in inputs:shutil.copyfile(p, frozen/p.name)
        save(a.output/'manifest.json', manifest);save(a.output/'children.json', children)
        vectors = np.lib.format.open_memmap(a.output/'child-vectors.npy', mode='w+', dtype=np.float32, shape=(len(children),384))
        vectors[:] = np.nan;vectors.flush()
        with (a.output/'progress.jsonl').open('w') as log:
            for i in range(0,len(children),2):
                if time.monotonic()-started>900:raise TimeoutError('900s batch boundary limit')
                texts = [c['search_text'] for c in children[i:i+2]]
                vectors[i:i+len(texts)] = encoder.encode(texts);vectors.flush()
                log.write(json.dumps({'encoded':i+len(texts),'total':len(children)})+'\n');log.flush()
        qv = np.load(query_path, allow_pickle=False)
        if qv.shape != (24,384) or not np.isfinite(qv).all() or not np.allclose(np.linalg.norm(qv,axis=1),1,atol=1e-5,rtol=0):
            raise ValueError('query vectors invalid')
        chunks = {c['chunk_id']:c for c in source['chunks']}
        for arm in outputs:
            indices = [i for i,c in enumerate(children) if arm == 'A1' or c['chunk_type']=='node']
            subset = [children[i] for i in indices]
            for q, vector in zip(questions,qv):
                row = {'question_id':q['question_id'],'arm':arm,'generation_executed':False}
                try:
                    row.update(rank_pack(subset,vectors[indices] @ vector,chunks,encoder.count))
                except Exception as exc:
                    row.update(status='retrieval_error',error=str(exc))
                outputs[arm].append(row)
        summary.update(status='completed',children=len(children),parents=814,
                       node_children=sum(c['chunk_type']=='node' for c in children),
                       max_tokens=max(c['token_count'] for c in children),
                       arms={k:{'saved':len(v),'ok':sum(x['status']=='ok' for x in v)} for k,v in outputs.items()},
                       vector_sha256=file_hash(a.output/'child-vectors.npy'))
    except Exception as exc:
        summary.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        (a.output/'failure.txt').write_text(traceback.format_exc())
        for arm in outputs:
            existing={r['question_id'] for r in outputs[arm]}
            outputs[arm].extend({'question_id':q['question_id'],'arm':arm,'status':'retrieval_error','error':summary['error'],'generation_executed':False} for q in questions if q['question_id'] not in existing)
        raise
    finally:
        for arm,rows in outputs.items():
            (a.output/f'{arm}.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        summary['elapsed_seconds']=time.monotonic()-started
        save(a.output/'summary.json',summary)
        print(json.dumps(summary))

if __name__=='__main__':main()
