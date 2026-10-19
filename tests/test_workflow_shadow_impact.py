"""Offline software checks; fixture coverage is declared, not independently proven."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.workflow_shadow_impact import MAX_BYTES, canonical, evaluate, read_input

ROOT = Path(__file__).resolve().parents[1]


def projection(target="packet", coverage="partial"):
    source = json.loads((ROOT / "research/operations/designs/workflow-shadow-example.json").read_text())
    nodes = [{k: n[k] for k in ("id", "version")} for n in source["nodes"]]
    return {
        "snapshot": {"nodes": nodes, "edges": [
            {k: e[k] for k in ("dependent", "prerequisite")} for e in source["edges"]
        ], "coverage": coverage},
        "candidates": ["methods-review", "implementation-review"],
        "change": {"node_id": target, "old_version": next(n["version"] for n in nodes if n["id"] == target),
                   "new_version": "replacement"},
    }


def graph(ids, edges, candidates, target="t", coverage="partial"):
    return {"snapshot": {"nodes": [{"id": x, "version": "v1"} for x in ids],
                         "edges": [{"dependent": a, "prerequisite": b} for a, b in edges],
                         "coverage": coverage},
            "candidates": candidates,
            "change": {"node_id": target, "old_version": "v1", "new_version": "v2"}}


class ShadowImpactTests(unittest.TestCase):
    def assert_invalid(self, payload, code):
        result = evaluate(payload)
        self.assertEqual(result["status"], "invalid")
        self.assertIn(code, result["errors"])
        self.assertIsNone(result["snapshot_hash"])
        self.assertTrue(all(r["impact"] == "unknown" and not r["witness_path"] for r in result["candidate_results"]))
        return result

    def test_real_projection_and_nonmutation(self):
        payload = projection()
        before = copy.deepcopy(payload)
        result = evaluate(payload)
        self.assertEqual(payload, before)
        self.assertEqual(result["status"], "evaluated")
        self.assertFalse(result["actual_shacl_executed"])
        for row in result["candidate_results"]:
            stem = row["id"].removesuffix("-review")
            self.assertEqual(row["impact"], "stale")
            self.assertEqual(row["witness_path"], [row["id"], stem + "-request", "packet"])

    def test_partial_and_authored_complete_control(self):
        for coverage, expected in [("partial", "unknown"), ("complete", "unaffected")]:
            with self.subTest(coverage=coverage):
                rows = evaluate(projection("methods-request", coverage))["candidate_results"]
                self.assertEqual([r["impact"] for r in rows], [expected, "stale"])

    def test_cycles_ties_target_and_direction(self):
        p = graph(["z", "a", "s", "t", "up"],
                  [("s", "z"), ("s", "a"), ("z", "t"), ("a", "s"), ("a", "t"), ("t", "up")],
                  ["s", "t", "up"])
        rows = evaluate(p)["candidate_results"]
        self.assertEqual(rows[0]["witness_path"], ["s", "a", "t"])
        self.assertEqual(rows[1]["witness_path"], ["t"])
        self.assertEqual(rows[2]["impact"], "unknown")
        p["snapshot"]["edges"] = [{"dependent": "s", "prerequisite": "a"}, {"dependent": "a", "prerequisite": "s"}]
        self.assertEqual(evaluate(p)["candidate_results"][0]["impact"], "unknown")

    def test_duplicate_edges_collapse_but_hash_preserves_order(self):
        p = graph(["s", "t"], [("s", "t")], ["s"])
        original = evaluate(p)
        p["snapshot"]["edges"] *= 2
        duplicate = evaluate(p)
        self.assertEqual(original["candidate_results"], duplicate["candidate_results"])
        self.assertNotEqual(original["snapshot_hash"], duplicate["snapshot_hash"])
        expected = hashlib.sha256(canonical(p["snapshot"])).hexdigest()
        self.assertEqual(duplicate["snapshot_hash"], expected)
        p["snapshot"]["nodes"].reverse()
        self.assertNotEqual(evaluate(p)["snapshot_hash"], expected)

    def test_invalid_schema_and_versions(self):
        cases = []
        p = projection(); p["snapshot"]["nodes"].append(p["snapshot"]["nodes"][0]); cases.append((p, "duplicate_node_id"))
        p = projection(); p["candidates"] *= 2; cases.append((p, "duplicate_candidate"))
        p = projection(); p["change"]["old_version"] = "wrong"; cases.append((p, "version_conflict"))
        p = projection(); p["change"]["node_id"] = "absent"; cases.append((p, "unknown_change_target"))
        p = projection(); p["change"]["new_version"] = p["change"]["old_version"]; cases.append((p, "unchanged_version"))
        p = projection(); p["snapshot"]["edges"][0]["prerequisite"] = "absent"; cases.append((p, "missing_edge_endpoint"))
        p = projection(); p["candidates"] = ["absent"]; cases.append((p, "unknown_candidate"))
        p = projection(); p["snapshot"]["coverage"] = True; cases.append((p, "invalid_coverage"))
        p = projection(); p["change"]["new_version"] = True; cases.append((p, "invalid_change"))
        p = projection(); p["snapshot"]["nodes"][0]["kind"] = "packet"; cases.append((p, "invalid_node"))
        p = projection(); p["event"] = {}; cases.append((p, "invalid_payload_fields"))
        for payload, code in cases:
            with self.subTest(code=code):
                before = copy.deepcopy(payload)
                self.assert_invalid(payload, code)
                self.assertEqual(payload, before)

    def test_malformed_candidates_recover_only_valid_strings(self):
        p = projection(); p["candidates"] = ["methods-review", True, {}, "", "methods-review", "other"]
        result = self.assert_invalid(p, "invalid_candidate")
        self.assertEqual([r["id"] for r in result["candidate_results"]], ["methods-review", "other"])
        for candidates in [None, "methods-review", {}, 0]:
            p["candidates"] = candidates
            self.assert_invalid(p, "invalid_candidates_or_bound")

    def test_strings_are_data_and_unicode_exact(self):
        target = "t'; DROP ALL; $(touch /tmp/not-executed) 한글"
        p = graph([target, " é", "e\u0301"], [(" é", target)], [" é", "e\u0301"], target)
        rows = evaluate(p)["candidate_results"]
        self.assertEqual([r["impact"] for r in rows], ["stale", "unknown"])
        self.assertIn("한글".encode(), canonical(p))

    def test_object_bounds_and_non_json(self):
        p = graph([str(i) for i in range(101)], [], [], "0")
        self.assert_invalid(p, "invalid_nodes_or_bound")
        p = graph(["t"], [("t", "t")] * 201, ["t"])
        self.assert_invalid(p, "invalid_edges_or_bound")
        p = graph(["t"], [], ["t"] * 101)
        self.assert_invalid(p, "invalid_candidates_or_bound")
        p = projection(); p["change"]["new_version"] = "한" * MAX_BYTES
        self.assert_invalid(p, "payload_byte_limit")
        for value in [float("nan"), float("inf"), {1, 2}, "\ud800"]:
            p = projection(); p["change"]["new_version"] = value
            self.assert_invalid(p, "invalid_json_value")

    def test_cli_parser_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.json", Path(directory) / "output.json"
            source.write_text(json.dumps(projection()))
            command = [sys.executable, str(ROOT / "scripts/workflow_shadow_impact.py"), "--input", str(source), "--output", str(output)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            saved = output.read_bytes()
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertEqual(output.read_bytes(), saved)
            for raw, error in [
                ('{"candidates":["x"],"x":1,"x":2}', "duplicate_json_key"),
                ('{"candidates":["x"],"value":NaN}', "nonfinite_json_constant"),
                ('{"candidates":', "malformed_json"),
                (' ' * (MAX_BYTES + 1), "payload_byte_limit"),
            ]:
                source.write_text(raw)
                result = read_input(source)
                self.assertIn(error, result["errors"])
                self.assertEqual(result["status"], "invalid")
            source.write_bytes(b"\xff")
            self.assertIn("malformed_json", read_input(source)["errors"])


if __name__ == "__main__":
    unittest.main()
