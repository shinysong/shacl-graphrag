"""Source integrity tests; these are software checks, not retrieval measurements."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("graphrag_corpus", ROOT / "scripts/build_graphrag_corpus.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((ROOT / builder.DEFAULT_SOURCE).read_bytes())

    def build(self, source=None):
        return builder.build_corpus(source or self.source, source_sha256="source-test", builder_sha256="builder-test")

    def test_inventory_and_same_workbook_edges(self):
        corpus = self.build()
        self.assertEqual((corpus["inventory"]["annotation_nodes"], corpus["inventory"]["dictionary_nodes"],
                          len(corpus["edges"]), len(corpus["chunks"])), (243, 85, 486, 814))
        nodes = {n["node_id"]: n for n in corpus["nodes"]}
        chunks = {c["chunk_id"]: c for c in corpus["chunks"]}
        for edge in corpus["edges"]:
            subject, target = nodes[edge["subject"]]["source"], nodes[edge["target"]]["source"]
            self.assertEqual(subject["archive_path"], target["archive_path"])
            self.assertEqual(subject["values"][edge["field"]], target["values"][0])
            self.assertEqual(json.loads(chunks["edge:" + edge["edge_id"]]["text"]), edge)
        self.assertEqual(len(corpus["inventory"]["duplicate_codebooks"]), 2)
        self.assertTrue(all(len(group["coupons"]) == 5 for group in corpus["inventory"]["duplicate_codebooks"]))

    def test_wrong_namespace_reference_rejected(self):
        source = copy.deepcopy(self.source)
        source["workbooks"][0]["records"][0]["dictionary_refs"]["defect"] = "PP4:defect_code:2"
        with self.assertRaisesRegex(ValueError, "Wrong namespace"):
            self.build(source)

    def test_missing_target_rejected(self):
        source = copy.deepcopy(self.source)
        entries = source["workbooks"][0]["dictionaries"]["defect_code"]
        entries[:] = [e for e in entries if e["code"] != 2]
        with self.assertRaisesRegex(ValueError, "Missing dictionary target"):
            self.build(source)

    def test_duplicate_code_rejected(self):
        source = copy.deepcopy(self.source)
        entries = source["workbooks"][0]["dictionaries"]["defect_code"]
        entries.append(copy.deepcopy(entries[0]))
        with self.assertRaisesRegex(ValueError, "Duplicate code"):
            self.build(source)

    def test_dictionary_id_inconsistency_rejected(self):
        source = copy.deepcopy(self.source)
        source["workbooks"][0]["dictionaries"]["defect_code"][0]["id"] = "PP3:defect_code:9"
        with self.assertRaisesRegex(ValueError, "code/ID/scope"):
            self.build(source)

    def test_raw_value_disagreement_rejected_even_with_consistent_saved_reference(self):
        source = copy.deepcopy(self.source)
        record = source["workbooks"][0]["records"][0]
        record["values"]["defect"] = 3
        record["dictionary_refs"]["defect"] = "PP3:defect_code:3"
        with self.assertRaisesRegex(ValueError, "Annotation/raw values mismatch"):
            self.build(source)

    def test_null_numeric_headers_and_attribution_preserved(self):
        corpus = self.build()
        node = next(n for n in corpus["nodes"] if n["node_id"] == "PP3:welding_settings_code:1")
        payload = json.loads(node["text"])
        self.assertEqual(payload["values"], [1, 27, 450, None, None, 1.6, None, 48])
        self.assertIs(type(payload["values"][1]), int)
        self.assertIs(type(payload["values"][5]), float)
        expected = self.source["workbooks"][0]["sheets"]["welding_settings_code"]["rows"][:2]
        self.assertEqual(payload["header_rows"], expected)
        self.assertEqual(corpus["source_attribution"], self.source["source_attribution"])
        self.assertEqual(payload["sha256"], self.source["workbooks"][0]["sha256"])

    def test_deterministic_bytes_and_exclusive_write(self):
        # Tiny valid input exercises the actual writer without generating the public corpus.
        source = copy.deepcopy(self.source)
        source["workbooks"] = source["workbooks"][:1]
        source["workbooks"][0]["records"] = source["workbooks"][0]["records"][:1]
        logs = ROOT / "_workspace/graphrag-cycle1/builder-tests"
        logs.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=logs) as directory:
            directory = Path(directory)
            input_path = directory / "input.json"
            input_path.write_text(json.dumps(source), encoding="utf-8")
            first, second = directory / "first.json", directory / "second.json"
            builder.write_corpus(input_path, first)
            builder.write_corpus(input_path, second)
            before = first.read_bytes()
            self.assertEqual(before, second.read_bytes())
            with self.assertRaises(FileExistsError):
                builder.write_corpus(input_path, first)
            self.assertEqual(before, first.read_bytes())
            self.assertEqual(json.loads(before)["derivation"]["source_sha256"], builder.sha256(input_path.read_bytes()))


if __name__ == "__main__":
    unittest.main()
