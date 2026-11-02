import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("search_builder", Path(__file__).parents[1] / "scripts/build_graphrag_search.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SearchSlicesTests(unittest.TestCase):
    def test_unicode_roundtrip_contiguous_offsets_and_budget(self):
        text = '한글🧪e\u0301 {"value": 12}\n' * 31
        rows = m.build_children({"chunks": [{"chunk_id": "node:A", "text": text}]}, len, 64)
        self.assertEqual("".join(r["text"] for r in rows), text)
        self.assertGreater(len(rows), 1)
        cursor = 0
        for i, r in enumerate(rows):
            self.assertEqual((r["start"], r["ordinal"]), (cursor, i))
            self.assertEqual(r["text"], text[r["start"]:r["end"]])
            self.assertLessEqual(len(r["search_text"]), 64)
            self.assertEqual(r["parent_sha256"], m.sha(text.encode()))
            cursor = r["end"]
        self.assertEqual(cursor, len(text))

    def test_determinism_and_ambiguous_looking_ids(self):
        corpus = {"chunks": [{"chunk_id": x, "text": "abc"} for x in ("a:0", "a", "🧪")]}
        rows = m.build_children(corpus, len)
        self.assertEqual(rows, m.build_children(corpus, len))
        self.assertEqual(len({r["child_id"] for r in rows}), 3)

    def test_reject_bad_input_and_unsplittable_prefix(self):
        valid = {"chunk_id": "node:A", "text": "abc"}
        for chunks in ([], [valid, valid], [{"chunk_id": "", "text": "a"}], [{"chunk_id": "a", "text": ""}]):
            with self.assertRaises(ValueError):
                m.build_children({"chunks": chunks}, len)
        for cap in (0, 513, True):
            with self.assertRaises(ValueError):
                m.build_children({"chunks": [valid]}, len, cap)
        with self.assertRaises(ValueError):
            m.build_children({"chunks": [valid]}, len, 1)

    def test_aggregation_max_tie_missing_and_permutation(self):
        children = [{"child_id": k, "parent_id": p} for k, p in (("a1", "a"), ("a2", "a"), ("b1", "b"), ("c1", "c"))]
        scores = [{"child_id": k, "score": v} for k, v in (("b1", .7), ("a1", .1), ("a2", .7))]
        result = m.aggregate_parents(children, scores)
        self.assertEqual([r["parent_id"] for r in result], ["a", "b"])
        self.assertEqual(result[0]["contributing_child_ids"], ["a2", "a1"])
        self.assertEqual(result, m.aggregate_parents(children, list(reversed(scores))))
        self.assertEqual(m.aggregate_parents(children, []), [])

    def test_aggregation_rejects_invalid_scores_and_ids(self):
        children = [{"child_id": "a", "parent_id": "p"}]
        for score in (float("nan"), float("inf"), True, "1"):
            with self.assertRaises(ValueError):
                m.aggregate_parents(children, [{"child_id": "a", "score": score}])
        for rows in ([{"child_id": "unknown", "score": 1}], [{"child_id": "a", "score": 1}] * 2):
            with self.assertRaises(ValueError):
                m.aggregate_parents(children, rows)


if __name__ == "__main__":
    unittest.main()
