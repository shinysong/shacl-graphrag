"""Offline consumed-label diagnosis; never runtime retrieval."""
import hashlib
import json
from collections import Counter
from pathlib import Path

PATHS = {
    'source': 'research/graphrag-evidence-1/source-corpus-v1.json',
    'rows': 'research/answer-evidence-1/anchor-on-001/rows.jsonl',
    'scores': 'research/answer-evidence-1/anchor-support-001/C/scores.json',
}
OUT = Path('research/answer-evidence-1/anchor-idc-diagnosis-001')


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    paths = dict(PATHS, diagnostic=__file__)
    hashes = {k: hashlib.sha256(Path(p).read_bytes()).hexdigest() for k,p in paths.items()}
    (OUT/'frozen').mkdir()
    for k,p in paths.items():
        (OUT/'frozen'/(k+'-'+Path(p).name)).write_bytes(Path(p).read_bytes())
    (OUT/'manifest.json').write_text(json.dumps(dict(paths=paths,hashes=hashes,scope='posthoc labels; forbidden at runtime'),indent=2))
    summary=dict(planned=6,processed=0,unprocessed=6,ok=0,failed=0,paid_calls=0)
    results=[]
    try:
        source=json.loads(Path(PATHS['source']).read_text())
        node_chunks={c['node_id']:c['chunk_id'] for c in source['chunks'] if c['chunk_type']=='node'}
        rows=[json.loads(x) for x in Path(PATHS['rows']).read_text().splitlines()]
        by={(r['question_id'],r['arm']):r for r in rows}
        if len(rows)!=120 or len(by)!=120:raise ValueError('unexpected run keys')
        selected=[r for r in json.loads(Path(PATHS['scores']).read_text())['results'] if r['task']=='nominal_idc']
        if len(selected)!=6 or len({r['question_id'] for r in selected})!=6:raise ValueError('unexpected diagnostic denominator')
        (OUT/'planned.json').write_text(json.dumps([r['question_id'] for r in selected],indent=2))
        for score in selected:
            result=dict(question_id=score['question_id'],status='error')
            try:
                q=score['question_id'];b=by[q,'B'];c=by[q,'C'];e=by[q,'E']
                if not (score['complete_support'] is False and score['evidence_state']=='present_in_supplied_bundle' and len(score['missing_node_sets'])==1):raise ValueError('unexpected support state')
                if any(r['result']['status']!='ok' for r in (b,c,e)):raise ValueError('upstream failure')
                ids=c['upstream']['expansion']['candidate_chunk_ids']
                if ids!=e['upstream']['expansion']['candidate_chunk_ids']:raise ValueError('candidate mismatch')
                if c['result']['selected_chunk_ids']!=e['result']['selected_chunk_ids']:raise ValueError('selected mismatch')
                anchor=b['upstream']['locator']['candidate_chunk_ids'];missing=[]
                for nid in score['missing_node_sets'][0]:
                    cid=node_chunks[nid]
                    if cid in c['result']['selected_chunk_ids']:raise ValueError('missing label conflicts with saved evidence')
                    if cid not in ids:stage='not_in_expansion'
                    elif cid in c['upstream']['excluded_after_eight']:stage='outside_first_eight'
                    elif cid in c['result']['skipped_budget_ids']:stage='message_budget_skip'
                    else:raise ValueError('unexplained omission')
                    missing.append(dict(node_id=nid,chunk_id=cid,candidate_position_1based=ids.index(cid)+1 if cid in ids else None,stage=stage))
                result.update(status='ok',anchor_chunk_ids=anchor,anchor_in_B=all(cid in b['result']['selected_chunk_ids'] for cid in anchor),anchor_in_C=all(cid in c['result']['selected_chunk_ids'] for cid in anchor),B_selected_ids=b['result']['selected_chunk_ids'],C_candidate_ids=ids,C_selected_ids=c['result']['selected_chunk_ids'],missing_nodes=missing)
            except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
            results.append(result)
            (OUT/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in results))
        if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=hashes[k] for k,p in paths.items()):raise ValueError('input changed')
        good=[r for r in results if r['status']=='ok']
        summary.update(ok=len(good),failed=len(results)-len(good),anchor_in_B=sum(r['anchor_in_B'] for r in good),anchor_in_C=sum(r['anchor_in_C'] for r in good),missing_node_occurrences=sum(len(r['missing_nodes']) for r in good),missing_stages=dict(Counter(n['stage'] for r in good for n in r['missing_nodes'])),input_hashes_stable=True)
    except Exception as exc:
        summary['error']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        summary.update(processed=len(results),unprocessed=6-len(results))
        (OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
