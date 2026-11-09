"""Posthoc consumed-development diagnosis; NEVER a retrieval/generation input.
Reads scorer missing-node labels only to locate saved failures, never repairs output.
"""
import hashlib,json,shutil
from pathlib import Path
from collections import Counter
from scripts.graphrag_expand import _index

PATHS={'source':'research/graphrag-evidence-1/source-corpus-v1.json',
       'scores':'research/refined-hybrid-1/support-score-c-001/scores.json',
       'B':'research/refined-hybrid-1/retrieval-001/retrieval.jsonl',
       'C':'research/refined-hybrid-1/relation-001/C.jsonl',
       'rerank':'research/refined-hybrid-1/rerank-001/results.json',
       'children':'research/refined-hybrid-1/rerank-001/children.json',
       'code':'scripts/diagnose_nominal_idc.py','indexer':'scripts/graphrag_expand.py'}


def main():
    hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in PATHS.values()}
    out=Path('research/refined-hybrid-1/idc-diagnosis-001');out.mkdir(exist_ok=False)
    summary={'status':'failed','scope':'posthoc scorer-labelled consumed development; no rerun or repair',
             'planned':6,'generation_executed':False,'retrieval_modified':False};results=[]
    try:
        source=json.loads(Path(PATHS['source']).read_text());nodes,edges,_,node_chunks,_=_index(source)
        scores=json.loads(Path(PATHS['scores']).read_text())['results']
        selected=[s for s in scores if s['task']=='nominal_idc']
        if len(selected)!=6:raise ValueError('unexpected diagnostic denominator')
        envelopes={a:{r['question_id']:r for r in map(json.loads,Path(PATHS[a]).read_text().splitlines())} for a in ['B','C']}
        rerank={r['question_id']:r for r in json.loads(Path(PATHS['rerank']).read_text())}
        children=json.loads(Path(PATHS['children']).read_text());child_map={x['child_id']:x['parent_id'] for x in children}
        if len(set(child_map.values()))!=len(children):raise ValueError('diagnostic expects current one-child-per-parent projection')
        (out/'frozen').mkdir()
        for key,path in PATHS.items():shutil.copyfile(path,out/'frozen'/(key+'-'+Path(path).name))
        (out/'manifest.json').write_text(json.dumps({'paths':PATHS,'hashes':hashes,'scorer_labels':'offline diagnosis only; prohibited as runtime inputs'},indent=2))
        for s in selected:
            row={'question_id':s['question_id'],'status':'error'}
            try:
                q=s['question_id'];b=envelopes['B'][q];c=envelopes['C'][q]
                assert b['status']==c['status']=='ok' and rerank[q]['status']=='ok'
                assert s['complete_support'] is False and s['evidence_state']=='present_in_supplied_bundle'
                assert len(s['missing_node_sets'])==1
                assert b['selected_chunk_ids']==c['seed_chunk_ids']
                ranked=sorted(rerank[q]['scores'],key=lambda x:(-x['score'],x['child_id']))
                ranks={child_map[r['child_id']]:i+1 for i,r in enumerate(ranked)}
                assert [child_map[r['child_id']] for r in ranked[:8]]==[r['parent_id'] for r in b['top_parents']]
                seed_nodes=[cid.removeprefix('node:') for cid in c['seed_chunk_ids'] if cid.startswith('node:')]
                seed_outgoing=[e['edge_id'] for e in edges.values() if e['subject'] in seed_nodes]
                seed_incoming=[e['edge_id'] for e in edges.values() if e['target'] in seed_nodes]
                missing=[]
                for nid in s['missing_node_sets'][0]:
                    assert nid in nodes
                    cid=node_chunks[nid];assert cid not in c['selected_chunk_ids']
                    if cid in b['skipped_budget_ids']:bstage='B_budget_skip'
                    elif cid not in ranks:bstage='absent_from_B_rerank_candidates'
                    elif ranks[cid]>8:bstage='outside_B_first8'
                    else:raise ValueError('unexplained B missing node')
                    if cid in c['skipped_budget_ids']:cstage='C_budget_skip'
                    elif cid in c['first8_excluded_ids']:cstage='C_first8_exclusion'
                    elif cid not in c['candidate_chunk_ids']:cstage='not_discovered_by_C'
                    else:raise ValueError('unexplained C missing node')
                    missing.append({'node_id':nid,'node_type':nodes[nid]['node_type'],'B_parent_rank':ranks.get(cid),
                                    'B_stage':bstage,'C_stage':cstage})
                row.update(status='ok',missing_nodes=missing,seed_node_types=[nodes[n]['node_type'] for n in seed_nodes],
                           seed_chunk_ids=c['seed_chunk_ids'],seed_outgoing_edge_ids=sorted(seed_outgoing),
                           seed_incoming_edge_ids=sorted(seed_incoming),C_candidates_equal_seed=c['candidate_chunk_ids']==c['seed_chunk_ids'],
                           C_budget_skips=c['skipped_budget_ids'],C_first8_exclusions=c['first8_excluded_ids'])
            except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
            results.append(row);(out/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in results))
        for path,h in hashes.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h
        good=[r for r in results if r['status']=='ok']
        summary.update(status='completed' if len(good)==6 else 'partial_failure',ok=len(good),failed=6-len(good),
                       zero_outgoing_seed_questions=sum(not r['seed_outgoing_edge_ids'] for r in good),
                       unchanged_candidate_questions=sum(r['C_candidates_equal_seed'] for r in good),
                       missing_node_occurrences=sum(len(r['missing_nodes']) for r in good),
                       B_missing_stages=dict(Counter(n['B_stage'] for r in good for n in r['missing_nodes'])),
                       C_missing_stages=dict(Counter(n['C_stage'] for r in good for n in r['missing_nodes'])))
    except Exception as exc:summary['error']=f'{type(exc).__name__}: {exc}';raise
    finally:
        summary.update(processed=len(results),unprocessed=6-len(results))
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
