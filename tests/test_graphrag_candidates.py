import math
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from graphrag_candidates import candidates, terms


def corpus(texts):
    return [{"child_id": f"c{i:02}", "search_text": t} for i, t in enumerate(texts)]


def test_unicode_tokenization():
    assert terms("검사_IDC450 AA-aa!") == ["검사", "idc", "450", "aa", "aa"]


def test_hand_calculated_bm25_and_duplicate_query_terms():
    c = corpus(["bolt bolt", "nut"])
    a = candidates(c, "bolt", [0, 0])
    expected = math.log(2) * 2 * 2.2 / (2 + 1.2 * (0.25 + 0.75 * 2 / 1.5))
    assert a["lexical"][0]["score"] == pytest.approx(expected)
    assert a == candidates(c, "bolt BOLT bolt", [0, 0])


def test_cutoff_ties_and_input_permutation():
    c = corpus(["bolt"] * 12)
    a = candidates(c, "bolt", [0] * 12)
    assert a["candidate_child_ids"] == [f"c{i:02}" for i in range(10)]
    assert a == candidates(list(reversed(c)), "bolt", [0] * 12)
    assert a["overlap_count"] == 10


def test_disjoint_union_and_no_fill():
    c = corpus(["nut"] * 10 + ["bolt"] * 10)
    a = candidates(c, "bolt", list(range(20, 0, -1)))
    assert a["candidate_count"] == 20
    b = candidates(c, "nut", list(range(20, 0, -1)))
    assert b["candidate_count"] == 10


def test_no_lexical_match_and_empty_documents():
    for texts in (["nut", "bolt"], ["", ""]):
        a = candidates(corpus(texts), "???", [0, -1])
        assert a["lexical"] == []
        assert a["candidate_count"] == 2


@pytest.mark.parametrize("score", [float("nan"), float("inf"), True])
def test_invalid_scores(score):
    with pytest.raises(ValueError):
        candidates(corpus(["bolt"]), "bolt", [score])


def test_invalid_indices():
    for c, scores in [([], []), (corpus(["bolt"]), []), ([{"child_id":"x", "search_text":"a"}] * 2, [1, 2])]:
        with pytest.raises(ValueError):
            candidates(c, "bolt", scores)
