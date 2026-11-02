import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from graphrag_dense import rank_pack
from graphrag_expand import canonical


class DensePackingTests(unittest.TestCase):
    def setUp(self):
        self.children = [{"child_id": "a1", "parent_id": "a"}, {"child_id": "a2", "parent_id": "a"},
                         {"child_id": "b1", "parent_id": "b"}, {"child_id": "c1", "parent_id": "c"}]
        self.chunks = {x: {"chunk_id": x, "text": "x" * (1000 if x == "a" else 5)} for x in "abc"}

    def test_dense_topk_dedup_tie_and_budget_skips(self):
        r = rank_pack(self.children, [.9, .8, .9, .5], self.chunks, len, token_cap=200)
        self.assertEqual([p["parent_id"] for p in r["top_parents"]], ["a", "b", "c"])
        self.assertEqual(r["selected_chunk_ids"], ["b", "c"])
        self.assertEqual(r["skipped_budget_ids"], ["a"])
        self.assertEqual(r["accounting_tokens"], len(canonical(r["selected_chunks"]).decode()))
        self.assertIsNone(r["evidence_tokens"])

    def test_child_cutoff_and_empty_selection(self):
        r = rank_pack(self.children, [1, .9, .8, .7], self.chunks, len, child_k=1, token_cap=20)
        self.assertEqual(r["status"], "budget_error")
        self.assertEqual(r["selected_chunks"], [])
        self.assertEqual(len(r["top_parents"]), 1)

    def test_invalid_scores_counts_bounds(self):
        for scores in ([1], [1, float("nan"), 0, 0], [True, 1, 0, 0]):
            with self.assertRaises(ValueError):
                rank_pack(self.children, scores, self.chunks, len)
        with self.assertRaises(ValueError):
            rank_pack(self.children, [1]*4, self.chunks, len, child_k=0)
        with self.assertRaises(ValueError):
            rank_pack(self.children, [1]*4, self.chunks, lambda _: -1)


if __name__ == "__main__":
    unittest.main()
