"""Synthetic software tests, not independent source or effectiveness cases."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from scripts.graphrag_check import canonical_bytes, check_evidence


def chunk(data, kind="node"):
    identifier = data["id" if kind == "node" else "edge_id"]
    return {"chunk_id": kind + ":" + identifier, "chunk_type": kind,
            kind + "_id": identifier, "text": canonical_bytes(data).decode()}


def envelope(chunks):
    encoded = canonical_bytes(chunks)
    return {"status": "ok", "selected_chunks": chunks,
            "selected_chunk_ids": [c["chunk_id"] for c in chunks],
            "evidence_sha256": hashlib.sha256(encoded).hexdigest(), "evidence_bytes": len(encoded)}


def fixtures():
    common = {"coupon": "PP3", "archive_path": "PP3/workbook.xlsx", "sha256": "a" * 64}
    annotation = dict(common, id="PP3:10", sheet="PP3", values={"defect": 1},
                      dictionary_refs={"defect": "PP3:defect_code:1"}, field_cells={"defect": "A10"})
    target = dict(common, id="PP3:defect_code:1", sheet="defect_code", code=1,
                  values=[1, "Porosity 한글"], excel_row=2)
    edge = dict(edge_id="PP3:10|defect|PP3:defect_code:1", subject=annotation["id"], target=target["id"],
                field="defect", relation_type="defect_code", code=1,
                provenance=dict(common, sheet="PP3", cell="A10", target_sheet="defect_code", target_excel_row=2))
    return annotation, target, edge


class EvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.annotation, self.target, self.edge = fixtures()

    def run_nodes(self, *nodes):
        return check_evidence(envelope([chunk(n) for n in nodes]))

    def reference_status(self, result):
        return next(r["status"] for r in result["results"] if ":dictionary_ref:" in r["check_id"])

    def test_reference_without_edge_and_nonmutation(self):
        saved = envelope([chunk(self.annotation), chunk(self.target)])
        before = canonical_bytes(saved)
        result = check_evidence(saved)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["complete"])
        self.assertFalse(result["truncated"])
        self.assertEqual(self.reference_status(result), "pass")
        self.assertEqual(canonical_bytes(saved), before)
        self.assertNotIn("pass", result)

    def test_missing_target_and_wrong_namespace_equal_value(self):
        self.assertEqual(self.reference_status(self.run_nodes(self.annotation)), "unknown")
        self.target.update(id="PP4:defect_code:1", coupon="PP4", archive_path="PP4/workbook.xlsx")
        self.assertEqual(self.reference_status(self.run_nodes(self.annotation, self.target)), "unknown")

    def test_present_conflicts(self):
        for field, value in [("code", 2), ("coupon", "PP4"), ("archive_path", "other"), ("sha256", "b" * 64)]:
            with self.subTest(field=field):
                target = dict(self.target, **{field: value})
                self.assertEqual(self.reference_status(self.run_nodes(self.annotation, target)), "violation")

    def test_missing_metadata(self):
        for field in ("code", "coupon", "archive_path", "sha256", "sheet"):
            with self.subTest(field=field):
                target = dict(self.target)
                del target[field]
                self.assertEqual(self.reference_status(self.run_nodes(self.annotation, target)), "unknown")

    def test_version_always_unknown(self):
        for claim in (None, "1.0"):
            self.annotation["process_review_version"] = claim
            self.annotation["source_attribution"] = {"version": "2026"}
            result = self.run_nodes(self.annotation, self.target)
            self.assertEqual(result["results"][-1]["status"], "unknown")

    def test_empty_and_dictionary_only(self):
        for nodes in ([], [self.target]):
            result = self.run_nodes(*nodes)
            self.assertEqual(result["results"][0]["check_id"], "no_selected_annotation")
            self.assertEqual(result["results"][0]["status"], "unknown")

    def test_hash_and_byte_tampering(self):
        for field, value in (("evidence_sha256", "0" * 64), ("evidence_bytes", 0), ("status", "budget_error")):
            saved = envelope([chunk(self.annotation)])
            saved[field] = value
            result = check_evidence(saved)
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["results"], [])

    def test_duplicate_and_inconsistent_ids(self):
        saved = envelope([chunk(self.annotation)] * 2)
        self.assertEqual(check_evidence(saved)["status"], "error")
        saved = envelope([chunk(self.annotation)])
        saved["selected_chunk_ids"] = ["node:other"]
        self.assertEqual(check_evidence(saved)["status"], "error")
        malformed = chunk(self.annotation)
        malformed["node_id"] = "other"
        self.assertEqual(check_evidence(envelope([malformed]))["status"], "error")

    def test_malformed_text_and_structure(self):
        for text in ('{', '[]', '{"id":"PP3:10","id":"PP3:10"}',
                     '{"id":"PP3:10","code":NaN}', '{"id":"PP3:10","code":1e999}'):
            malformed = chunk(self.annotation)
            malformed["text"] = text
            self.assertEqual(check_evidence(envelope([malformed]))["status"], "error")
        for change in ({"dictionary_refs": None}, {"dictionary_refs": []}, {"dictionary_refs": {"defect": 1}},
                       {"values": []}, {"field_cells": []}):
            malformed = dict(self.annotation, **change)
            self.assertEqual(self.run_nodes(malformed)["status"], "error")

    def test_explicit_edge_checks(self):
        def run(edge, targets=True):
            selected = [chunk(self.annotation), chunk(edge, "edge")]
            if targets:
                selected.append(chunk(self.target))
            return check_evidence(envelope(selected))["results"][-1]["status"]
        self.assertEqual(run(self.edge), "pass")
        self.assertEqual(run(self.edge, targets=False), "unknown")
        for field, value in (("code", 2), ("field", "welding_setting"), ("relation_type", "welding_settings_code")):
            self.assertEqual(run(dict(self.edge, **{field: value})), "violation")
        for field, value in (("cell", "A99"), ("sha256", "b" * 64), ("target_excel_row", 99)):
            edge = copy.deepcopy(self.edge)
            edge["provenance"][field] = value
            self.assertEqual(run(edge), "violation")
        edge = copy.deepcopy(self.edge)
        edge["target"] = "PP4:defect_code:1"
        self.assertEqual(run(edge), "unknown")

    def test_caps_are_errors_never_successful_truncation(self):
        saved = envelope([chunk(self.annotation), chunk(self.target)])
        report = check_evidence(saved)
        size = len(canonical_bytes(report))
        self.assertEqual(check_evidence(saved, size), report)
        for cap in (size - 1, 1, 0, True):
            result = check_evidence(saved, cap)
            self.assertEqual(result["status"], "error")
            self.assertFalse(result["complete"])
            self.assertFalse(result["truncated"])
            self.assertEqual(result["results"], [])

    def test_invocation_has_no_io_software_guard_only(self):
        # Imported before patching; bounded invocation guard, not OS isolation.
        saved = envelope([chunk(self.annotation), chunk(self.target), chunk(self.edge, "edge")])
        targets = ("builtins.open", "io.open", "os.open", "pathlib.Path.open",
                   "socket.socket", "socket.create_connection", "urllib.request.urlopen")
        from contextlib import ExitStack
        with ExitStack() as stack:
            guards = [stack.enter_context(patch(t, side_effect=AssertionError("I/O forbidden"))) for t in targets]
            result = check_evidence(saved)
            for guard in guards:
                guard.assert_not_called()
        self.assertEqual(result["status"], "ok")

    def test_ignores_nonselected_payloads(self):
        saved = envelope([chunk(self.annotation)])
        saved["trace"] = {"arbitrary": object()}
        self.assertEqual(check_evidence(saved)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
