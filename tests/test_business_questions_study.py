"""Behavioral edge checks; fixtures' declared expected outputs remain independent."""

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "business", Path(__file__).parents[1] / "scripts/run_business_questions_study.py"
)
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)


class BusinessQuestionsTests(unittest.TestCase):
    def packet(self, task, index=0):
        return copy.deepcopy(
            [c["packet"] for c in b.make_cases() if c["packet"]["task"] == task][index]
        )

    def result(self, p):
        return b.decide(p, b.select_json(p))

    def test_units_are_convertible_but_not_assumed(self):
        p = self.packet("M2")
        self.assertEqual(self.result(p)["status"], "eligible")
        p["observed_records"][0].update(tolerance=0.05, unit="mm")
        self.assertEqual(self.result(p)["status"], "eligible")
        p["observed_records"][0]["unit"] = "inch"
        self.assertEqual(self.result(p)["status"], "unknown")

    def test_direct_parent_role_publication_and_window(self):
        p = self.packet("F1")
        self.assertEqual(self.result(p)["value"], "LEI-P")
        for change in (
            {"relation": "FUND_MANAGER"},
            {"end": "2026-10-11"},
            {"registration_status": "RETIRED"},
            {"snapshot_date": "2026-10-11"},
        ):
            q = copy.deepcopy(p)
            q["observed_records"][0].update(change)
            self.assertEqual(self.result(q)["status"], "unknown")
        p["observed_records"][0]["end"] = b.ASOF
        self.assertEqual(self.result(p)["status"], "known")

    def test_exception_scope_and_conflicting_parent(self):
        p = self.packet("F1")
        ex = b.rec(
            "x",
            "exception",
            subject="LEI-A",
            relation="ULTIMATE_ACCOUNTING",
            reason="NATURAL_PERSONS",
        )
        p["observed_records"].append(ex)
        self.assertEqual(self.result(p)["status"], "known")
        ex["relation"] = "DIRECT_ACCOUNTING"
        self.assertEqual(self.result(p)["status"], "conflict")

    def test_ultimate_parent_is_not_fund_manager(self):
        p = self.packet("F2")
        self.assertIs(self.result(p)["value"], True)
        for r in p["observed_records"]:
            r["relation"] = "FUND_MANAGER"
        self.assertEqual(self.result(p)["status"], "unknown")
        self.assertIs(b.raw_lookup(p)["value"], True)

    def test_legal_and_registration_status_namespaces(self):
        p = self.packet("F3")
        self.assertEqual(self.result(p)["status"], "review_ready")
        p["observed_records"][0]["registration_status"] = "LAPSED"
        self.assertEqual(self.result(p)["status"], "review_required")
        self.assertEqual(b.raw_lookup(p)["status"], "review_ready")
        p["observed_records"][0]["snapshot_date"] = "2025-01-01"
        self.assertEqual(self.result(p)["status"], "incomplete")

    def test_irrelevant_change_and_missing_dependency_scope(self):
        p = self.packet("M3", 1)
        self.assertEqual(self.result(p)["value"], [])
        p["internal_policy"]["complete_dependencies"] = False
        self.assertEqual(self.result(p)["status"], "unknown")

    def test_conflicting_measurements_and_missing_certificate(self):
        self.assertEqual(self.result(self.packet("M2", 3))["status"], "conflict")
        self.assertEqual(self.result(self.packet("M2", 2))["status"], "unknown")

    def test_actual_sparql_record_retrieval_parity(self):
        # Representative multi-kind and typed literal packets, not a full matrix run.
        for task, index in [
            ("M1", 3),
            ("M2", 0),
            ("M2", 2),
            ("M3", 0),
            ("F1", 1),
            ("F3", 0),
        ]:
            p = self.packet(task, index)
            js = sorted(b.select_json(p), key=lambda r: r["id"])
            rdf = b.select_rdf(p)
            self.assertEqual(js, rdf)
            self.assertEqual(b.decide(p, js), b.decide(p, rdf))

    def test_runtime_does_not_include_evaluation_labels(self):
        cases = b.make_cases()
        self.assertEqual(len(cases), 36)
        for c in cases:
            self.assertEqual(
                set(c["packet"]),
                {
                    "task",
                    "question",
                    "asof",
                    "observed_records",
                    "published_schema",
                    "internal_policy",
                },
            )
            self.assertNotIn("scenario", c["packet"])

    def test_existing_destination_refused(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaises(FileExistsError),
        ):
            b.run(directory)


if __name__ == "__main__":
    unittest.main()
