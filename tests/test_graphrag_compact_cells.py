import copy
import unittest
from scripts.graphrag_compact_cells import canonical, encode, decode, RepresentationError


def node():
    cells = [dict(cell="A"+str(i), data_type="n", value=v, formula=None,
                  cached_value=v) for i,v in enumerate([None, True, 1, 1.0, -0.0, "단위", "=A1"])]
    record = dict(cells=cells, header_rows=[dict(excel_row=1, cells=copy.deepcopy(cells))],
                  values=[True, 1, -0.0], extra={"nested": ["원본", None]})
    return dict(chunk_id="node:n", chunk_type="node", node_id="n",
                text=canonical(record).decode())


class CompactTests(unittest.TestCase):
    def test_roundtrip_types_and_no_mutation(self):
        source = node()
        before = canonical(source)
        payload = encode(source)
        encoded_before = canonical(payload)
        restored = decode(payload)
        self.assertEqual(canonical(restored), before)
        self.assertEqual(canonical(source), before)
        self.assertEqual(canonical(payload), encoded_before)
        self.assertIn('-0.0', restored['text'])
        self.assertIn('true', restored['text'])

    def test_edge_and_empty(self):
        edge = dict(chunk_id="edge:e", chunk_type="edge", edge_id="e", text="exact raw text")
        self.assertEqual(decode(encode(edge)), edge)
        source=node()
        source["text"]=canonical(dict(cells=[],header_rows=[])).decode()
        self.assertEqual(decode(encode(source)),source)

    def test_reject_source(self):
        for text in ['{"cells":[],"cells":[],"header_rows":[]}',
                     '{"cells": [], "header_rows": []}',
                     '{"cells":[],"header_rows":[],"x":NaN}',
                     '{"cells":[{}],"header_rows":[]}']:
            with self.subTest(text=text), self.assertRaises(RepresentationError) as ctx:
                encode(dict(node(),text=text))
            self.assertEqual(ctx.exception.status,"unsupported_source_representation")

    def test_payload_structure(self):
        base=encode(node())
        bad=[]
        p=copy.deepcopy(base);p["projection_version"]="wrong";bad.append(p)
        p=copy.deepcopy(base);p["cell_fields"].reverse();bad.append(p)
        p=copy.deepcopy(base);p["record"]["cells"][0].pop();bad.append(p)
        p=copy.deepcopy(base);p["identity"]["text"]="injected";bad.append(p)
        p=copy.deepcopy(base);p["extra"]=1;bad.append(p)
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(RepresentationError) as ctx:
                decode(payload)
            self.assertEqual(ctx.exception.status,"compact_payload_failure")

    def test_integrity(self):
        payload=encode(node())
        payload["record"]["cells"][1][2]=1  # True must not compare equal to 1.
        with self.assertRaises(RepresentationError) as ctx:
            decode(payload)
        self.assertEqual(ctx.exception.status,"compact_integrity_failure")


if __name__ == "__main__":
    unittest.main()
