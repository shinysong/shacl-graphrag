import copy
import json
import unittest
from scripts.graphrag_compact_cells import (
    canonical, encode, decode_serialized, RepresentationError)


def fixture():
    cell=dict(cell="C2",data_type="f",value="=A1+1",formula="=A1+1",cached_value=42)
    record=dict(cells=[cell],header_rows=[dict(row=1,cells=[
        dict(cell="C1",data_type="s",value="電流(A)",formula=None,cached_value=None)])],
        meta=dict(number=-0.0))
    return dict(chunk_id="node:x",chunk_type="node",node_id="x",text=canonical(record).decode())


class BoundaryTests(unittest.TestCase):
    def test_formula_cache_header(self):
        source=fixture()
        payload=canonical(encode(source))
        self.assertEqual(canonical(decode_serialized(payload)),canonical(source))
        self.assertEqual(canonical(decode_serialized(payload.decode())),canonical(source))

    def test_duplicate_and_nonfinite_transport(self):
        for raw in [b'{"projection_version":"a","projection_version":"b"}',
                    b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":NaN}',
                    b'{"x":1e999}',b'\xff', b'[]']:
            with self.subTest(raw=raw),self.assertRaises(RepresentationError) as ctx:
                decode_serialized(raw)
            self.assertEqual(ctx.exception.status,"compact_payload_failure")

    def test_header_and_cell_rejections(self):
        for mutation in ["extra","missing","header_object","header_cells"]:
            source=fixture();r=json.loads(source["text"])
            if mutation=="extra":r["cells"][0]["extra"]=1
            if mutation=="missing":del r["cells"][0]["formula"]
            if mutation=="header_object":r["header_rows"]=[[]]
            if mutation=="header_cells":r["header_rows"][0]["cells"]={}
            source["text"]=canonical(r).decode()
            with self.subTest(mutation=mutation),self.assertRaises(RepresentationError):
                encode(source)

    def test_invalid_edge_and_nested_transport(self):
        edge=dict(chunk_id="edge:e",chunk_type="edge",edge_id="e",text="raw")
        p=encode(edge);p["raw_chunk"]["unexpected"]=1
        with self.assertRaises(RepresentationError):
            decode_serialized(canonical(p))
        p=encode(fixture())
        raw=canonical(p).decode().replace('"meta":{"number":-0.0}',
                                         '"meta":{"number":-0.0,"number":0}')
        self.assertNotEqual(raw,canonical(p).decode())
        with self.assertRaises(RepresentationError):
            decode_serialized(raw)


if __name__=="__main__":
    unittest.main()
