import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import numpy as np
import pytest
from prepare_graphrag_hybrid import validate_vectors, prepare


def matrix(n):
    x = np.zeros((n, 384), dtype=np.float32)
    x[:, 0] = 1
    return x


@pytest.mark.parametrize('dtype', [np.bool_, np.float64, np.int64])
def test_reject_non_float32_including_numpy_bool(dtype):
    with pytest.raises(ValueError):
        validate_vectors(matrix(2).astype(dtype), matrix(1), 2, 1)


def test_shape_nonfinite_and_norm_guards():
    for bad in (matrix(1), np.full((2,384), np.nan, dtype=np.float32), matrix(2)*2):
        with pytest.raises(ValueError):
            validate_vectors(bad, matrix(1), 2, 1)


def test_failure_keeps_question_and_next_question():
    c = [{'child_id':'a','search_text':'bolt'}, {'child_id':'b','search_text':'nut'}]
    q = [{'question_id':'q1','question':'bolt'}, {'question_id':'q2','question':'nut'}]
    old = [{'question_id':'q1','status':'ok','top_children':[{'child_id':'b'},{'child_id':'a'}]},
           {'question_id':'q2','status':'ok','top_children':[{'child_id':'a'},{'child_id':'b'}]}]
    rows = prepare(c,q,matrix(2),matrix(2),old)
    assert len(rows)==2
    assert rows[0]['status']=='candidate_error'
    assert rows[1]['status']=='ready_for_reranker'
    assert rows[1]['candidate_child_ids']==['a','b']


def test_question_order_guard():
    with pytest.raises(ValueError):
        prepare([{'child_id':'a','search_text':'bolt'}], [{'question_id':'q1','question':'bolt'}],
                matrix(1),matrix(1),[{'question_id':'wrong'}])
