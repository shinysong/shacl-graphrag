"""Offline policy equivalence and information-boundary checks, not a benchmark."""

import copy
import itertools
import json
import unittest

from rdflib import Literal

from scripts.hybrid_complexity_core import (
    EX,
    VARIANTS,
    check_python,
    check_shacl,
    generate_cases,
    project_rdf,
    projection_stats,
)


class HybridComplexityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases, cls.truth = generate_cases()

    def case(self, load="full", depth=4, variant="clean", distractors=0):
        return copy.deepcopy(
            next(
                c
                for c in self.cases
                if all(
                    self.truth[c["id"]][k] == v
                    for k, v in {
                        "constraint_load": load,
                        "depth": depth,
                        "variant": variant,
                        "distractors": distractors,
                        "seed": 11,
                    }.items()
                )
            )
        )

    def parity(self, case, expected):
        py, sh = check_python(case), check_shacl(case)
        for key in py:
            self.assertEqual(py[key], sh[key], key)
        self.assertEqual(py["decision"], expected)
        return sh

    def test_factorial_and_bounds(self):
        self.assertEqual(len(self.cases), 120)
        factors = {
            (
                v["depth"],
                v["constraint_load"],
                v["distractors"],
                v["variant"],
                v["seed"],
            )
            for v in self.truth.values()
        }
        self.assertEqual(
            factors,
            set(
                itertools.product(
                    (1, 2, 4), ("basic", "full"), (0, 8), VARIANTS, (11, 29)
                )
            ),
        )
        for case in self.cases:
            self.assertEqual(set(case), {"id", "question", "contract", "records"})
            self.assertLessEqual(len(case["records"]), 30)
            self.assertLess(len(json.dumps(case, indent=2)), 12000)

    def test_factors_do_not_change_unrelated_evidence(self):
        basic = self.case(load="basic")
        full = self.case(load="full")
        self.assertEqual(basic["records"], full["records"])
        extra = self.case(distractors=8)
        self.assertEqual(full["records"], extra["records"][:-8])

    def test_metadata_variant_is_load_sensitive_with_identical_facts(self):
        for depth, distractors, seed in itertools.product((1, 2, 4), (0, 8), (11, 29)):
            paired = {
                load: next(
                    c
                    for c in self.cases
                    if all(
                        self.truth[c["id"]][k] == v
                        for k, v in {
                            "constraint_load": load,
                            "depth": depth,
                            "distractors": distractors,
                            "seed": seed,
                            "variant": "metadata_violation",
                        }.items()
                    )
                )
                for load in ("basic", "full")
            }
            self.assertEqual(paired["basic"]["records"], paired["full"]["records"])
            for load, expected in (("basic", "allow"), ("full", "deny")):
                case = paired[load]
                gold = self.truth[case["id"]]
                self.assertEqual(gold["expected_decision"], expected)
                self.assertEqual(gold["original_truth_decision"], expected)
                self.assertEqual(gold["original_records"], case["records"])
                self.assertEqual(check_python(case)["decision"], expected)
            full = check_python(paired["full"])
            self.assertEqual(
                [issue["id"] for issue in full["issues"]],
                ["node_not_permitted" if seed == 11 else "record_dates_invalid"],
            )

    def test_all_cases_independent_checker_parity(self):
        for case in self.cases:
            with self.subTest(id=case["id"]):
                self.parity(case, self.truth[case["id"]]["expected_decision"])

    def test_false_fact_is_not_runtime_visible(self):
        clean = self.case(variant="clean")
        false = self.case(variant="conforming_false_fact")
        self.assertEqual(clean["records"], false["records"])
        self.assertEqual(clean["contract"], false["contract"])
        self.assertEqual(self.truth[false["id"]]["original_truth_decision"], "deny")
        self.assertTrue(self.parity(false, "allow")["conforms"])
        false["gold"] = self.truth[false["id"]]
        with self.assertRaises(ValueError):
            check_python(false)
        with self.assertRaises(ValueError):
            check_shacl(false)

    def test_bad_dates_class_and_certificate(self):
        for field, value, kind in (
            ("valid_to", "2026-09-30", "link"),
            ("valid_from", "2027-01-01", "link"),
            ("business_class", "Unqualified", "entity"),
            ("issuer", "not-authorized", "certificate"),
            ("status", "revoked", "certificate"),
            ("permitted", False, "entity"),
        ):
            case = self.case()
            next(r for r in case["records"] if r["kind"] == kind)[field] = value
            self.assertFalse(self.parity(case, "deny")["conforms"])

    def test_missing_is_warning_not_known_violation(self):
        for field, kind in (
            ("valid_from", "link"),
            ("business_class", "entity"),
            ("issuer", "certificate"),
        ):
            case = self.case()
            del next(r for r in case["records"] if r["kind"] == kind)[field]
            result = self.parity(case, "abstain")
            self.assertTrue(result["conforms"])
            self.assertTrue(all(i["severity"] == "unknown" for i in result["issues"]))
        for variant in ("source_missing",):
            self.assertTrue(
                self.parity(self.case(variant=variant), "abstain")["conforms"]
            )
        case = self.case()
        case["records"] = [r for r in case["records"] if r["kind"] != "certificate"]
        self.parity(case, "abstain")

    def test_observed_expiry_fails_even_with_missing_start(self):
        case = self.case()
        link = next(r for r in case["records"] if r["kind"] == "link")
        del link["valid_from"]
        link["valid_to"] = "2020-01-01"
        result = self.parity(case, "deny")
        self.assertEqual(
            {i["id"] for i in result["issues"]},
            {"record_dates_missing", "record_dates_invalid"},
        )

    def test_path_omission_at_each_depth(self):
        for index in range(4):
            case = self.case()
            case["records"].remove(
                [r for r in case["records"] if r["kind"] == "link"][index]
            )
            self.parity(case, "abstain")

    def test_basic_ignores_metadata_and_irrelevant_records(self):
        case = self.case(load="basic", distractors=8)
        for r in case["records"]:
            if r["kind"] == "entity":
                r["permitted"] = False
            if "valid_to" in r:
                r["valid_to"] = "2020-01-01"
        self.parity(case, "allow")
        self.parity(self.case(distractors=8), "allow")

    def test_rdf_projection_preserves_records_not_gold_or_decisions(self):
        case = self.case(distractors=8)
        graph = project_rdf(case)
        self.assertEqual(
            len(list(graph.triples((None, EX.record_id, None)))), len(case["records"])
        )
        for r in case["records"]:
            self.assertIn((EX[r["id"]], EX.record_id, Literal(r["id"])), graph)
            if r["kind"] == "link":
                self.assertIn((EX[r["from"]], EX.outgoing, EX[r["id"]]), graph)
                self.assertIn((EX[r["id"]], EX["from"], EX[r["from"]]), graph)
        for field in ("name", "notes", "decision", "variant", "expected_decision"):
            self.assertFalse(list(graph.triples((None, EX[field], None))))
        stats = projection_stats(case)
        self.assertEqual(stats["record_count"], len(case["records"]))
        self.assertEqual(stats["triple_count"], len(graph))

    def test_known_failure_dominates_missing(self):
        case = self.case(variant="source_missing")
        case["records"][0]["permitted"] = False
        result = self.parity(case, "deny")
        self.assertEqual(result["atoms"]["path"], "unknown")
        self.assertEqual(result["atoms"]["permitted"], "fail")


if __name__ == "__main__":
    unittest.main()
