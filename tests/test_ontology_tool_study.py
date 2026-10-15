import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_ontology_tool_study as s
from scripts.prepare_ontology_tool_cases import build_cases


def call(name, args):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "tc",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


class Fake:
    def __init__(self, messages):
        self.responses = iter(messages)
        self.inputs = []

    def generate(self, messages, specs, path):
        self.inputs.append(json.loads(json.dumps(messages)))
        return next(self.responses), {"usage": {"cost": 0}}


class StudyTests(unittest.TestCase):
    def test_model_driven_query_and_final_trace(self):
        runtime = build_cases()[9]["runtime"]
        q = 'PREFIX b: <urn:business-questions:> SELECT ?id ?parent WHERE { ?r b:id ?id; b:relation "DIRECT_ACCOUNTING"; b:object ?parent }'
        answer = {
            "status": "known",
            "value": "LEI-P",
            "evidence_ids": ["r1"],
            "caveats": [],
            "interpretation": {"role": "direct_accounting_parent"},
        }
        gateway = Fake(
            [
                call("finish", answer),
                call("query", {"query": q, "interpretation": answer["interpretation"]}),
                call("finish", answer),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "e"
            result = s.episode(runtime, "A", "case10-A", gateway, path)
            self.assertEqual(result["answer"], answer)
            self.assertEqual(result["counts"]["model_calls"], 3)
            self.assertIn("r1", result["source_ids_retrieved"])
            self.assertNotIn("ontology", json.loads(gateway.inputs[0][1]["content"]))
            self.assertIn("QueryBeforeFinishRequired", json.dumps(gateway.inputs[1]))
            rows = [
                json.loads(x) for x in (path / "events.jsonl").read_text().splitlines()
            ]
            self.assertTrue(
                all(
                    b["parent_event_id"] == a["event_id"]
                    for a, b in zip(rows, rows[1:])
                )
            )
            self.assertEqual(len({x["event_id"] for x in rows}), len(rows))

    def test_checks_cannot_fetch_unretrieved_evidence(self):
        gateway = Fake([call("check_evidence", {"record_ids": ["r1"]})] * 6)
        with tempfile.TemporaryDirectory() as tmp:
            result = s.episode(
                build_cases()[9]["runtime"], "C", "case10-C", gateway, Path(tmp) / "e"
            )
            self.assertEqual(result["status"], "model_turn_budget_exhausted")
            self.assertIn(
                "EvidenceNotPreviouslyRetrieved", json.dumps(gateway.inputs[1])
            )

    def test_failed_transport_preserves_episode(self):
        gateway = Fake([])
        with patch.object(
            gateway, "generate", side_effect=s.BudgetStop("UnresolvedCost")
        ):
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "e"
                with self.assertRaises(s.BudgetStop):
                    s.episode(build_cases()[0]["runtime"], "B", "e", gateway, p)
                self.assertEqual(
                    json.loads((p / "result.json").read_text())["status"], "failed"
                )

    def test_reservations_never_refunded_and_cap_is_hard(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = s.Gateway.__new__(s.Gateway)
            g.output = Path(tmp) / "run"
            g.ledger = Path(tmp) / "ledger.json"
            self.assertEqual(g.reserve(0.8), 0)
            with self.assertRaises(s.BudgetStop):
                g.reserve(0.8)
            d = json.loads(g.ledger.read_text())
            self.assertEqual(d["attempts"], 1)
            self.assertEqual(d["reserved_usd"], 0.8)
            d["reserved_usd"] = float("nan")
            g.ledger.write_text(json.dumps(d))
            with self.assertRaises(s.BudgetStop):
                g.reserve(0.01)

    def test_runtime_rejects_reference_fields(self):
        runtime = build_cases()[0]["runtime"]
        runtime["expected"] = {"status": "known"}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                s.episode(runtime, "C", "e", Fake([]), Path(tmp) / "e")

    def test_unavailable_tools_stay_unavailable(self):
        gateway = Fake(
            [call("check_query_contract", {"query": "ASK {}", "interpretation": {}})]
            * 6
        )
        with tempfile.TemporaryDirectory() as tmp:
            s.episode(build_cases()[0]["runtime"], "B", "e", gateway, Path(tmp) / "e")
            self.assertIn("UnavailableTool", json.dumps(gateway.inputs[1]))


if __name__ == "__main__":
    unittest.main()
