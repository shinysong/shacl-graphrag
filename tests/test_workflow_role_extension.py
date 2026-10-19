"""Software checks for authored registration; no real review is created."""
import copy
import json
import unittest

from scripts import run_workflow_role_extension as experiment


class RoleExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_bytes = experiment.RECORD.read_bytes()
        cls.record = json.loads(cls.source_bytes)
        cls.result = experiment.run(experiment.RECORD)

    def test_original_unchanged_and_no_source_update(self):
        before = copy.deepcopy(self.record)
        cases = experiment.build_cases(self.record)
        self.assertEqual(self.record, before)
        self.assertEqual(cases[0]["input"], self.record["cases"][0]["input"])
        self.assertEqual(experiment.RECORD.read_bytes(), self.source_bytes)
        original_nodes = cases[0]["input"]["snapshot"]["nodes"]
        for case in self.result["cases"]:
            snapshot = case["input"]["snapshot"]
            self.assertEqual(snapshot["nodes"][:5], original_nodes)
            self.assertEqual(snapshot["coverage"], "partial")
            self.assertTrue(all(arm["input_unchanged"] for arm in case["arms"].values()))

    def test_omission_unknown_and_existing_decisions_preserved(self):
        baseline, added, omitted, methods = self.result["cases"]
        for name in ("python", "rdf"):
            def rows(case):
                return {r["id"]: r for r in case["arms"][name]["output"]["candidate_results"]}
            self.assertEqual({k: rows(added)[k] for k in rows(baseline)}, rows(baseline))
            missing = rows(omitted)[experiment.REVIEW]
            self.assertEqual(missing["impact"], "unknown")
            self.assertEqual(missing["witness_path"], [])
            self.assertEqual(missing["reasons"], ["no_path_partial_coverage"])
            for case in (baseline, added, omitted, methods):
                self.assertTrue(case["arms"][name]["score"]["status_map_matches"])
        self.assertEqual(self.result["arm_counts"]["rdf"]["actual_shacl_invocations"], 4)
        self.assertEqual(self.result["arm_counts"]["python"]["actual_shacl_invocations"], 0)


if __name__ == "__main__":
    unittest.main()
