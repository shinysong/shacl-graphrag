import copy
import hashlib
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from score_graphrag_support import score, canonical


class SupportTests(unittest.TestCase):
    def setUp(self):
        a = {"id": "A", "coupon": "P", "archive_path": "file", "sha256": "hash",
             "dictionary_refs": {"setting": "D"}, "values": {"setting": 1}}
        d = {"id": "D", "coupon": "P", "archive_path": "file", "sha256": "hash", "code": 1}
        wrong = dict(d, id="OTHER", coupon="Q")
        self.chunks = [{"chunk_id": "node:"+x["id"], "chunk_type": "node", "node_id": x["id"],
                        "text": canonical(x).decode()} for x in (a,d,wrong)]
        self.edge = {"chunk_id": "edge:e", "chunk_type": "edge", "edge_id": "e", "text": '{"subject":"A","target":"D"}'}
        self.source = {"chunks": self.chunks+[self.edge]}
        self.ref = {"question_id": "q", "target_record": "A", "task": "lookup", "required_link_field": "setting",
                    "evidence_state": "present_in_supplied_bundle", "admissible_node_sets": [["A", "D"]]}

    def envelope(self, chunks):
        raw = canonical(chunks)
        return {"question_id": "q", "status": "ok", "selected_chunks": chunks,
                "selected_chunk_ids": [x["chunk_id"] for x in chunks],
                "evidence_sha256": hashlib.sha256(raw).hexdigest(), "evidence_bytes": len(raw)}

    def run_score(self, outputs, ref=None):
        return score(self.source, {"references": [ref or self.ref]}, outputs)

    def test_complete_embedded_link_without_extra_edge(self):
        row = self.run_score([self.envelope(self.chunks[:2])])["results"][0]
        self.assertTrue(row["complete_support"])
        self.assertEqual(row["node_coverage"], 1)

    def test_edge_only_cannot_replace_nodes(self):
        row = self.run_score([self.envelope([self.edge])])["results"][0]
        self.assertFalse(row["complete_support"])
        self.assertEqual(row["node_coverage"], 0)

    def test_wrong_scope_same_value_partial_not_complete(self):
        row = self.run_score([self.envelope([self.chunks[0],self.chunks[2]])])["results"][0]
        self.assertFalse(row["complete_support"])
        self.assertEqual(row["node_coverage"], .5)

    def test_source_tampering_rehashed_and_bad_hash(self):
        bad = copy.deepcopy(self.chunks[:2]);bad[1]["text"] += " "
        for env in (self.envelope(bad), dict(self.envelope(self.chunks[:2]), evidence_sha256="bad")):
            self.assertEqual(self.run_score([env])["results"][0]["retrieval_state"], "invalid_evidence")

    def test_missing_failed_outputs_keep_denominator(self):
        for rows, state in (([], "missing_output"), ([{"question_id":"q", "status":"retrieval_error"}], "retrieval_failure")):
            result = self.run_score(rows)
            self.assertEqual(result["summary"]["source_present"], 1)
            self.assertEqual(result["summary"]["complete_support"], 0)
            self.assertEqual(result["results"][0]["retrieval_state"], state)

    def test_source_absence_is_null_not_vacuous_success(self):
        ref = dict(self.ref, evidence_state="absent_from_supplied_bundle", admissible_node_sets=[], required_link_field=None)
        r = self.run_score([self.envelope([self.edge])], ref)
        self.assertIsNone(r["results"][0]["complete_support"])
        self.assertEqual(r["summary"]["source_absent_separate"], 1)

    def test_duplicate_extra_and_bad_reference_rejected(self):
        env = self.envelope(self.chunks[:2])
        for rows in ([env,env], [dict(env,question_id="extra")]):
            with self.assertRaises(ValueError):self.run_score(rows)
        for group in ([["A","OTHER"]], [["missing"]]):
            with self.assertRaises(ValueError):self.run_score([env],dict(self.ref,admissible_node_sets=group))

    def test_inputs_not_mutated(self):
        env = [self.envelope(self.chunks[:2])]
        before = copy.deepcopy((self.source,self.ref,env))
        self.run_score(env)
        self.assertEqual(before,(self.source,self.ref,env))


if __name__ == "__main__":
    unittest.main()
