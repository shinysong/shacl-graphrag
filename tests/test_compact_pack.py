import copy
import json
import unittest
from unittest.mock import patch
from scripts.graphrag_compact_cells import canonical, RepresentationError
from scripts.graphrag_compact_pack import pack_compact, transmitted_chunks


def chunk(cid):
    record=dict(cells=[dict(cell="A1",data_type="n",value=1,formula=None,cached_value=None)],
                header_rows=[])
    return dict(chunk_id=cid,chunk_type="node",node_id=cid,text=canonical(record).decode())


def count(text):
    messages=json.loads(text);body=json.loads(messages[1]["content"])
    ids=[p["identity"]["chunk_id"] for p in body["evidence"]]
    return 4000 if "large" in ids else 100+len(ids)*500


class PackTests(unittest.TestCase):
    def call(self,ids,chunks=None,counter=count):
        chunks=chunks or {cid:chunk(cid) for cid in ids}
        with patch("scripts.graphrag_compact_pack._index",return_value=({}, {}, chunks, {}, {})):
            return pack_compact("question",ids,{},counter)

    def test_skip_large_keep_later_and_transmitted_only(self):
        r=self.call(["a","large","b"])
        self.assertEqual(r["status"],"ok")
        self.assertEqual(r["selected_chunk_ids"],["a","b"])
        self.assertEqual(r["skipped_budget_ids"],["large"])
        self.assertEqual(canonical(transmitted_chunks(r["base"])),canonical(r["selected_chunks"]))
        # The reader does not accept a corpus/raw fallback argument.
        self.assertNotEqual(r["evidence_sha256"],r["compact_evidence_sha256"])

    def test_late_invalid_discards_whole_episode(self):
        chunks={"a":chunk("a"),"bad":chunk("bad")}
        chunks["bad"]["text"]="{}"
        r=self.call(["a","bad"],chunks)
        self.assertEqual(r["status"],"unsupported_source_representation")
        self.assertEqual(r["candidate_chunk_ids"],["a","bad"])
        self.assertEqual(r["selected_chunks"],[])
        self.assertIsNone(r["base"])

    def test_accounting_failure_discards_partial(self):
        def bad(text):
            if len(json.loads(json.loads(text)[1]["content"])["evidence"])==2:
                return True
            return count(text)
        r=self.call(["a","b"],counter=bad)
        self.assertEqual(r["status"],"input_error")
        self.assertEqual(r["selected_chunk_ids"],[])
        self.assertIsNone(r["base"])

    def test_upstream_and_empty_overhead(self):
        self.assertEqual(pack_compact("q",["a"],{},count,"failed")["status"],"upstream_error")
        self.assertEqual(self.call(["a"],counter=lambda _:4000)["status"],"overhead_budget_error")
        self.assertEqual(self.call([])["status"],"evidence_budget_error")

    def test_message_tamper(self):
        r=self.call(["a"]);base=copy.deepcopy(r["base"])
        base["serialized"]=base["serialized"].replace("question","different")
        with self.assertRaises(RepresentationError):
            transmitted_chunks(base)


if __name__=="__main__":
    unittest.main()
