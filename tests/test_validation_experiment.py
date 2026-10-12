"""Protect scoring against false positives, execution failures and wrong locations."""

import tempfile
import unittest
from pathlib import Path

from scripts.run_validation_experiment import run_case, score


class ValidationExperimentTests(unittest.TestCase):
    def test_scoring_separates_errors_from_true_negatives(self):
        rows = [
            {"status": "completed", "expected": [["x"]], "conforms": False, "matches_expected": True},
            {"status": "completed", "expected": [["x"]], "conforms": True, "matches_expected": False},
            {"status": "completed", "expected": [], "conforms": False, "matches_expected": False},
            {"status": "completed", "expected": [], "conforms": True, "matches_expected": True},
            {"status": "error", "expected": [], "matches_expected": False},
        ]
        result = score(rows)
        self.assertEqual([result[k] for k in ("tp", "fn", "fp", "tn", "errors")], [1, 1, 1, 1, 1])
        self.assertEqual(result["recall"], 0.5)
        self.assertEqual(result["false_positive_rate"], 0.5)
        self.assertEqual(result["error_rate"], 0.2)
        self.assertIsNone(score([])["recall"])

    def test_correct_violation_with_wrong_expected_location_fails(self):
        case = {
            "id": "wrong_location", "remove": 'ex:Alice ex:name "Alice" .', "add": "",
            "expected": [["https://example.org/lab/SomeoneElse", "https://example.org/lab/name",
                          "http://www.w3.org/ns/shacl#MinCountConstraintComponent"]],
        }
        with tempfile.TemporaryDirectory() as directory:
            row = run_case(case, Path(directory))
        self.assertFalse(row["conforms"])
        self.assertFalse(row["matches_expected"])

    def test_invalid_mutation_is_an_error(self):
        case = {"id": "bad_mutation", "remove": 'ex:Alice ex:name "Absent" .', "add": "", "expected": []}
        with tempfile.TemporaryDirectory() as directory:
            row = run_case(case, Path(directory))
        self.assertEqual(row["status"], "error")
        self.assertEqual(score([row])["tn"], 0)


if __name__ == "__main__":
    unittest.main()
