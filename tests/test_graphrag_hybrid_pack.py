import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import pytest
from pack_graphrag_hybrid import pack_one


def fixture():
    return ({'question_id':'q','status':'ready_for_reranker','candidate_child_ids':['a','b']},
            {'question_id':'q','status':'ok','scores':[{'child_id':'a','score':1.0},{'child_id':'b','score':2.0}]},
            {'a':{'child_id':'a','parent_id':'p'},'b':{'child_id':'b','parent_id':'p'}},
            {'p':{'chunk_id':'p','text':'source'}})


def test_max_child_parent_and_original_payload():
    c,s,children,chunks=fixture()
    r=pack_one(c,s,children,chunks,len)
    assert r['selected_chunks']==[chunks['p']]
    assert r['top_parents'][0]['score']==2
    assert r['evidence_tokens'] is None


@pytest.mark.parametrize('kind',['partial','duplicate','failed','nonfinite'])
def test_failed_or_partial_scores_never_pack(kind):
    c,s,children,chunks=fixture()
    if kind=='partial':s['scores'].pop()
    elif kind=='duplicate':s['scores'][1]['child_id']='a'
    elif kind=='failed':s['status']='rerank_error'
    else:s['scores'][0]['score']=float('nan')
    with pytest.raises(ValueError):pack_one(c,s,children,chunks,len)
