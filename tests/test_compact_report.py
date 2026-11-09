import copy
import hashlib
import json
import unittest
from unittest.mock import patch
from scripts.graphrag_compact_cells import canonical, RepresentationError
from scripts.graphrag_compact_pack import pack_compact, transmitted_chunks
from scripts.graphrag_compact_report import account_compact_report
from scripts.graphrag_input_contract import COVERAGE
from scripts.graphrag_message_pack import _measure


def source_chunk():
    return dict(chunk_id="node:x",node_id="x",chunk_type="node",
        text=canonical(dict(id="x",cells=[],header_rows=[])).decode())


def base():
    c=source_chunk()
    with patch("scripts.graphrag_compact_pack._index",return_value=({}, {}, {"node:x":c}, {}, {})):
        return pack_compact("q",["node:x"],{},lambda _:100)


def report():
    return dict(raw_conforms=True,results=[],applicable_bindings=0,
                coverage=COVERAGE,no_bindings_status="unknown")


class ReportTests(unittest.TestCase):
    def test_exact_evidence_and_no_mutation(self):
        b=base();before=canonical(b)
        result=account_compact_report("q",b,report(),lambda _:100)
        self.assertEqual(result["D"]["status"],"ok")
        self.assertEqual(canonical(result["C"]),before)
        self.assertEqual(canonical(b),before)
        dbody=json.loads(result["D"]["full"]["messages"][1]["content"])
        self.assertEqual(canonical(dbody["evidence"]),canonical(b["compact_selected_chunks"]))
        self.assertEqual(dbody["validation"],report())

    def test_report_budget_and_checker_failure(self):
        def count(text):
            return 1500 if json.loads(json.loads(text)[1]["content"])["validation"] is not None else 100
        self.assertEqual(account_compact_report("q",base(),report(),count)["D"]["status"],"report_budget_error")
        self.assertEqual(account_compact_report("q",base(),report(),count,"failed")["D"]["status"],"validation_execution_error")
        self.assertEqual(account_compact_report("q",base(),{},count)["D"]["status"],"validation_execution_error")

    def test_strict_envelope_rejects_rehashed_schema_change(self):
        for field in ["system","validation","extra"]:
            b=base()["base"];messages=copy.deepcopy(b["messages"])
            if field=="system":messages[0]["content"]="other"
            else:
                body=json.loads(messages[1]["content"])
                body["validation" if field=="validation" else "extra"]={}
                messages[1]["content"]=canonical(body).decode()
            raw=canonical(messages)
            b.update(messages=messages,serialized=raw.decode(),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            with self.subTest(field=field),self.assertRaises(RepresentationError):
                transmitted_chunks(b)

    def test_byte_boundary_without_token_pressure(self):
        c=source_chunk()
        parsed=json.loads(c["text"]);parsed["extra"]="x"*48000;c["text"]=canonical(parsed).decode()
        with patch("scripts.graphrag_compact_pack._index",return_value=({}, {}, {"node:x":c}, {}, {})):
            result=pack_compact("q",["node:x"],{},lambda _:100)
        self.assertEqual(result["status"],"evidence_budget_error")
        self.assertEqual(result["skipped_budget_ids"],["node:x"])

    def test_raw_fallback_forbidden(self):
        b=base();b["selected_chunks"][0]["text"]="{}"
        self.assertEqual(account_compact_report("q",b,report(),lambda _:100)["D"]["status"],"input_error")


if __name__=="__main__":
    unittest.main()
