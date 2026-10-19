import copy
import unittest
from unittest.mock import patch

from rdflib.namespace import SH

from scripts import workflow_required_roles as w


def payload(change=True, roles=None, coverage="complete"):
    return {"data_change": change, "completed_roles": roles if roles is not None else
            ["methods", "implementation"], "coverage": coverage}


def arms(data, policy):
    return [w.evaluate_coded(data, policy["version"]), w.evaluate_json(data, policy),
            w.evaluate_rdf(data, policy)]


class RequiredRolesTests(unittest.TestCase):
    def assert_decisions(self, data, policy, expected):
        for result in arms(data, policy):
            self.assertEqual(expected, result["decision"], result)

    def test_policy_change_and_docs_only(self):
        self.assert_decisions(payload(), w.POLICY_V1, "satisfied")
        self.assert_decisions(payload(), w.POLICY_V2, "missing")
        for policy in (w.POLICY_V1, w.POLICY_V2):
            self.assert_decisions(payload(False), policy, "satisfied")

    def test_unknown_condition_and_partial_evidence(self):
        for roles in ([], ["methods", "implementation", "data-steward"]):
            self.assert_decisions(payload(None, roles), w.POLICY_V2, "unknown")
            self.assertFalse(w.evaluate_rdf(payload(None, roles), w.POLICY_V2)
                             ["actual_shacl_executed"])
        self.assert_decisions(payload(None), w.POLICY_V1, "satisfied")
        self.assert_decisions(payload(coverage="partial"), w.POLICY_V2, "unknown")
        self.assert_decisions(payload(True, ["methods", "implementation", "data-steward"],
                                      "partial"), w.POLICY_V2, "satisfied")
        result = w.evaluate_rdf(payload(coverage="partial"), w.POLICY_V2)
        self.assertIs(result["shacl_conforms"], False)
        self.assertTrue(result["actual_shacl_executed"])

    def test_strict_input_validation(self):
        malformed = [None, {}, {**payload(), "extra": True}]
        for field, values in {"data_change": [0, 1, "true", []],
                              "completed_roles": ["methods", [""], [1], ["x", "x"],
                                                  ["x"] * 21, ["x" * 81]],
                              "coverage": [None, [], "COMPLETE"]}.items():
            malformed.extend({**payload(), field: value} for value in values)
        for data in malformed:
            for result in arms(data, w.POLICY_V2):
                self.assertEqual(("invalid", "unknown"),
                                 (result["status"], result["decision"]))
                self.assertFalse(result["actual_shacl_executed"])

    def test_policy_grammar(self):
        policies = [None, {}, {**w.POLICY_V2, "extra": 1},
                    {**w.POLICY_V2, "version": "v3"}]
        for field, value in (("field", "other"), ("equals", 1), ("role", "")):
            policy = copy.deepcopy(w.POLICY_V2)
            policy["conditional_roles"][0][field] = value
            policies.append(policy)
        for policy in policies:
            for evaluate in (w.evaluate_json, w.evaluate_rdf):
                self.assertEqual("invalid", evaluate(payload(), policy)["status"])

    def test_actual_constraints_and_validator_failure(self):
        validate = w.pyshacl.validate
        with patch.object(w.pyshacl, "validate", wraps=validate) as spy:
            result = w.evaluate_rdf(payload(), w.POLICY_V2)
            self.assertEqual("missing", result["decision"])
            self.assertIs(result["shacl_conforms"], False)
            spy.assert_called_once()
            shapes = spy.call_args.kwargs["shacl_graph"]
            self.assertEqual(4, len(list(shapes.triples((None, SH.hasValue, None)))))
            self.assertEqual(1, len(list(shapes.triples((None, SH["or"], None)))))
        with patch.object(w.pyshacl, "validate", side_effect=RuntimeError("failure")):
            result = w.evaluate_rdf(payload(), w.POLICY_V2)
            self.assertEqual("unknown", result["decision"])
            self.assertIsNone(result["shacl_conforms"])
            self.assertTrue(result["actual_shacl_executed"])
            self.assertEqual("evaluated", result["status"])

    def test_declarative_roles_are_compiled_not_hardcoded(self):
        policy = {"version": "v2", "base_roles": ["custom"], "conditional_roles": [
            {"field": "data_change", "equals": True, "role": 'literal"; injected'}]}
        for evaluate in (w.evaluate_json, w.evaluate_rdf):
            self.assertEqual("missing", evaluate(payload(True, ["custom"]), policy)["decision"])
            self.assertEqual("satisfied", evaluate(payload(False, ["custom"]), policy)["decision"])
            self.assertEqual("satisfied", evaluate(payload(True, ["custom", 'literal"; injected']),
                                                     policy)["decision"])


if __name__ == "__main__":
    unittest.main()
