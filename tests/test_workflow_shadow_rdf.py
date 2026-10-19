"""Small offline software parity checks, not a benchmark or truth validation."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from rdflib import BNode, Literal, RDF, XSD

from scripts import workflow_shadow_impact as reference
from scripts import workflow_shadow_rdf as rdf

ROOT = Path(__file__).resolve().parents[1]


def fixture(ids=("s", "t"), edges=(("s", "t"),), candidates=("s",), target="t"):
    return {"snapshot": {"nodes": [{"id": x, "version": "v1"} for x in ids],
                         "edges": [{"dependent": a, "prerequisite": b} for a, b in edges],
                         "coverage": "partial"},
            "candidates": list(candidates),
            "change": {"node_id": target, "old_version": "v1", "new_version": "v2"}}


class RdfShadowTests(unittest.TestCase):
    def parity(self, payload, expected=None):
        expected = reference.evaluate(payload) if expected is None else copy.deepcopy(expected)
        before = json.dumps(payload, sort_keys=True)
        real_validate = rdf.pyshacl.validate
        with patch.object(reference, "evaluate", side_effect=AssertionError("reference called")), \
                patch.object(rdf.pyshacl, "validate", wraps=real_validate) as validation:
            actual = rdf.evaluate(payload)
        self.assertEqual(json.dumps(payload, sort_keys=True), before)
        valid = expected["status"] == "evaluated"
        self.assertEqual(validation.call_count, int(valid))
        expected.update(evaluator="rdf_pyshacl", actual_shacl_executed=valid,
                        shacl_conforms=True if valid else None)
        self.assertEqual(actual, expected)
        return actual

    def test_saved_three_cases(self):
        record = json.loads((ROOT / "docs/experiments/records/20261015-workflow-shadow-single.json").read_text())
        self.assertEqual(len(record["cases"]), 3)
        for case in record["cases"]:
            with self.subTest(case=case["id"]):
                self.parity(case["input"], case["output"])

    def test_cycles_ties_direction_and_self(self):
        p = fixture(("z", "a", "s", "t", "up"),
                    (("s", "z"), ("s", "a"), ("z", "t"), ("a", "s"), ("a", "t"), ("t", "up")),
                    ("s", "t", "up"))
        rows = self.parity(p)["candidate_results"]
        self.assertEqual([r["witness_path"] for r in rows], [["s", "a", "t"], ["t"], []])
        p["snapshot"]["edges"] = [{"dependent": "s", "prerequisite": "a"},
                                   {"dependent": "a", "prerequisite": "s"}]
        self.parity(p)

    def test_literal_ids_versions_and_duplicate_edges(self):
        target = 't"; DROP ALL; <urn:evil> $(touch /tmp/not-executed) 한글'
        p = fixture((target, " é", "e\u0301"), ((" é", target),), (" é", "e\u0301"), target)
        p["snapshot"]["nodes"][1]["version"] = '<x> " } DELETE WHERE {?s ?p ?o}'
        graph, terms = rdf.encode(p["snapshot"])
        self.assertTrue(all(isinstance(term, BNode) for term in terms.values()))
        self.assertEqual(str(graph.value(terms[target], rdf.W.id)), target)
        original = self.parity(p)
        p["snapshot"]["edges"] *= 2
        repeated = self.parity(p)
        self.assertEqual(original["candidate_results"], repeated["candidate_results"])
        self.assertNotEqual(original["snapshot_hash"], repeated["snapshot_hash"])

    def test_invalid_preflight_skips_shacl(self):
        for mutation in (lambda p: p["change"].update(old_version="wrong"),
                         lambda p: p["snapshot"]["edges"][0].update(prerequisite="absent"),
                         lambda p: p["candidates"].append("s"),
                         lambda p: p["change"].update(new_version="x" * reference.MAX_BYTES),
                         lambda p: p["change"].update(new_version=float("nan"))):
            p = fixture()
            mutation(p)
            self.parity(p)

    def assert_unknown(self, output, conforms, executed=True):
        self.assertEqual(output["status"], "invalid")
        self.assertIsNone(output["snapshot_hash"])
        self.assertEqual(output["actual_shacl_executed"], executed)
        self.assertIs(output["shacl_conforms"], conforms)
        self.assertTrue(output["errors"])
        self.assertTrue(all(r["impact"] == "unknown" and r["witness_path"] == []
                            for r in output["candidate_results"]))

    def test_validator_rejection_exception_and_nonboolean(self):
        for answer in (False, None):
            with patch.object(rdf.pyshacl, "validate", return_value=(answer, None, "fake")) as mocked:
                self.assert_unknown(rdf.evaluate(fixture()), answer)
                mocked.assert_called_once()
        with patch.object(rdf.pyshacl, "validate", side_effect=RuntimeError("synthetic failure")) as mocked:
            self.assert_unknown(rdf.evaluate(fixture()), None)
            mocked.assert_called_once()
        with patch.object(rdf, "encode", side_effect=RuntimeError("conversion failure")), \
                patch.object(rdf.pyshacl, "validate") as mocked:
            self.assert_unknown(rdf.evaluate(fixture()), None, executed=False)
            mocked.assert_not_called()

    def test_real_shacl_rejects_conversion_defects(self):
        encode = rdf.encode
        mutations = [lambda g, t: g.remove((t["s"], rdf.W.id, None)),
                     lambda g, t: g.add((t["s"], rdf.W.id, Literal("extra", datatype=XSD.string))),
                     lambda g, t: g.set((t["s"], rdf.W.id, Literal(12))),
                     lambda g, t: g.remove((t["s"], rdf.W.version, None)),
                     lambda g, t: g.add((t["s"], rdf.W.version, Literal("extra", datatype=XSD.string))),
                     lambda g, t: g.set((t["s"], rdf.W.version, Literal(12))),
                     lambda g, t: g.remove((t["t"], RDF.type, rdf.W.Node))]
        for mutate in mutations:
            def broken(snapshot):
                graph, terms = encode(snapshot)
                mutate(graph, terms)
                return graph, terms
            with patch.object(rdf, "encode", side_effect=broken):
                self.assert_unknown(rdf.evaluate(fixture()), False)


if __name__ == "__main__":
    unittest.main()
