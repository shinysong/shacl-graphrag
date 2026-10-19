import unittest
from copy import deepcopy
from unittest.mock import patch

from scripts import run_workflow_binding_probe as probe


class WorkflowBindingProbeTests(unittest.TestCase):
    def base(self):
        return deepcopy(probe.authored_cases()[0]["input"])

    def assert_both(self, packet, status, reasons, executed):
        for checker in (probe.check_python, probe.check_shacl):
            with self.subTest(checker=checker.__name__):
                self.assertEqual(
                    checker(packet),
                    {
                        "status": status,
                        "reason_codes": sorted(reasons),
                        "checker_executed": executed,
                    },
                )

    def test_authored_matrix_and_independent_backends(self):
        cases = probe.authored_cases()
        self.assertEqual(len(cases), 12)
        self.assertEqual(len({c["name"] for c in cases}), 12)
        for case in cases:
            with self.subTest(case=case["name"]):
                python = probe.check_python(case["input"])
                # The RDF backend cannot silently delegate to Python.
                with (
                    patch.object(
                        probe,
                        "check_python",
                        side_effect=AssertionError("shared decision"),
                    ),
                    patch.object(probe, "validate", wraps=probe.validate) as validate,
                ):
                    rdf = probe.check_shacl(case["input"])
                    self.assertEqual(validate.call_count, int(rdf["checker_executed"]))
                self.assertEqual(python, rdf)
                self.assertEqual(python["status"], case["expected_status"])

    def test_all_reasons_retained(self):
        p = self.base()
        p["approval"] = dict.fromkeys(probe.BINDINGS, "other")
        p["approved"] = False
        p["dependencies"][0]["current_version"] = "v2"
        self.assert_both(
            p,
            "deny",
            [f + "_mismatch" for f in probe.BINDINGS]
            + ["approval_not_granted", "dependency_version_mismatch"],
            True,
        )

    def test_incomplete_precedes_known_denial(self):
        p = self.base()
        p.update(complete=False, approved=False)
        with patch.object(probe, "validate", side_effect=AssertionError("must skip")):
            self.assert_both(p, "unknown", ["incomplete_evidence"], False)

    def test_missing_or_null_at_each_boundary(self):
        paths = (
            [(k,) for k in self.base()]
            + [(k, f) for k in ("request", "approval") for f in probe.BINDINGS]
            + [
                ("dependencies", 0, f)
                for f in ("id", "approved_version", "current_version")
            ]
        )
        for path in paths:
            for null in (False, True):
                p = self.base()
                parent = p
                for part in path[:-1]:
                    parent = parent[part]
                if null:
                    parent[path[-1]] = None
                else:
                    del parent[path[-1]]
                with self.subTest(path=path, null=null):
                    self.assert_both(p, "unknown", ["missing_evidence"], False)

    def test_schema_errors_reject_coercion_and_extras(self):
        for path, value in [
            (("approved",), 1),
            (("complete",), "true"),
            (("dependencies",), {}),
            (("request", "target_id"), 1),
            (("approval", "target_version"), ""),
            (("dependencies", 0, "id"), " "),
            (("dependencies", 0, "current_version"), False),
        ]:
            p = self.base()
            parent = p
            for part in path[:-1]:
                parent = parent[part]
            parent[path[-1]] = value
            self.assert_both(p, "unknown", ["schema_error"], False)
        for path in ((), ("request",), ("dependencies", 0)):
            p = self.base()
            parent = p
            for part in path:
                parent = parent[part]
            parent["extra"] = "unsupported"
            self.assert_both(p, "unknown", ["schema_error"], False)
        for p in ([], True, "invalid"):
            outcome = probe.check_python(p)
            self.assertEqual(outcome["status"], "unknown")
            self.assertIn("schema_error", outcome["reason_codes"])
            self.assertEqual(outcome, probe.check_shacl(p))

    def test_strings_are_exact_and_safe_rdf_literals(self):
        p = self.base()
        p["request"]["target_id"] = 'x" ; ex:approved true . #\n한글'
        p["approval"]["target_id"] = p["request"]["target_id"]
        self.assert_both(p, "allow", ["contract_satisfied"], True)
        p["approval"]["target_version"] = "v1 "
        self.assert_both(p, "deny", ["target_version_mismatch"], True)

    def test_dependency_order_and_duplicates_do_not_hide_conflicts(self):
        p = self.base()
        p["dependencies"] += [
            {"id": "part-A", "approved_version": "v2", "current_version": "v2"},
            {"id": "part-A", "approved_version": "v1", "current_version": "v1"},
        ]
        for deps in (p["dependencies"], list(reversed(p["dependencies"]))):
            p["dependencies"] = deps
            self.assert_both(p, "deny", ["conflicting_dependency_records"], True)
        self.assertEqual(
            len(
                list(
                    probe.evidence_graph(p).objects(
                        probe.EX.evidence, probe.EX.dependency
                    )
                )
            ),
            3,
        )

    def test_declared_invalidation_is_direct_deterministic_baseline(self):
        declared = {"z": ["a", "a"], "b": ["a", "c"], "c": ["other"], "empty": []}
        self.assertEqual(probe.invalidation_set(declared, ["a", "a"]), ["b", "z"])
        self.assertEqual(probe.invalidation_set(declared, ["unknown"]), [])
        self.assertEqual(probe.invalidation_set(declared, []), [])
        # No transitive propagation from b to an entry mentioning b.
        self.assertEqual(probe.invalidation_set({"b": ["a"], "d": ["b"]}, ["a"]), ["b"])


if __name__ == "__main__":
    unittest.main()
