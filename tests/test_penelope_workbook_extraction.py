"""Miniature workbook tests; no network or existing source files required."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import openpyxl

SPEC = importlib.util.spec_from_file_location("extract_penelope", Path(__file__).resolve().parents[1] / "scripts/extract_penelope_workbooks.py")
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "manifest.json"

    def workbook(self, coupon="PP3", mutate=None, cached=False):
        book = openpyxl.Workbook()
        book.remove(book.active)
        for name, headers in extractor.DICTIONARY_HEADERS.items():
            sheet = book.create_sheet(name)
            for header in headers:
                sheet.append(header)
        book["defect_code"].append([1, "Porosity"])
        book["welding_settings_code"].append([1, 27, 450, None, None, 1.6, None, 48])
        sheet = book.create_sheet(coupon)
        sheet.append(extractor.ANNOTATION_HEADERS)
        sheet.append([1, 1, 2, "=50+80", 120, 100, 200])
        if mutate:
            mutate(book)
        relative = f"ZENODO_Penelope/{coupon}/2. ndt_data/defects_xlocation.xlsx"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        book.save(path)
        book.close()
        if cached:
            raw = path.read_bytes()
            output = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(output, "w") as target:
                for info in source.infolist():
                    content = source.read(info.filename)
                    if info.filename == "xl/worksheets/sheet3.xml":
                        tree = ET.fromstring(content)
                        ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                        tree.find(".//s:c[@r='D2']/s:v", ns).text = "130"
                        content = ET.tostring(tree)
                    target.writestr(info, content)
            path.write_bytes(output.getvalue())
        return {"coupon": coupon, "archive_path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def write_manifest(self, files):
        # Deliberately false legacy derived data must never supply extracted values.
        self.manifest.write_text(json.dumps({"files": files, "rows": [{"value": "FAKE"}],
            "dictionaries": "FAKE", "formulas": "FAKE", "design": "FAKE",
            "source": {"title": "Source title", "license": "CC-BY-4.0", "changes": "FAKE"}}))

    def test_cells_cache_namespaces_and_source_preservation(self):
        files = [self.workbook(cached=True), self.workbook("PP4")]
        self.write_manifest(files)
        before = {f["archive_path"]: (self.root / f["archive_path"]).read_bytes() for f in files}
        result = extractor.extract(self.manifest, [self.root])
        a, b = result["workbooks"]
        self.assertEqual(result["schema_version"], "penelope-workbook-extract-1")
        self.assertEqual(a["records"][0]["values"]["x_init_mm"], 130)
        self.assertIsNone(b["records"][0]["values"]["x_init_mm"])
        self.assertEqual(a["records"][0]["field_cells"]["x_init_mm"], "D2")
        self.assertEqual(a["records"][0]["dictionary_refs"]["defect"], "PP3:defect_code:1")
        self.assertEqual(b["records"][0]["dictionary_refs"]["defect"], "PP4:defect_code:1")
        cell = b["sheets"]["PP4"]["rows"][1]["cells"][3]
        self.assertEqual(cell["formula"], "=50+80")
        self.assertIsNone(cell["cached_value"])
        self.assertIs(type(a["records"][0]["values"]["sample_init"]), int)
        self.assertIsNone(a["dictionaries"]["welding_settings_code"][0]["values"][3])
        self.assertNotIn("FAKE", json.dumps(result))
        self.assertEqual(before, {key: (self.root / key).read_bytes() for key in before})

    def test_invalid_schema_duplicates_and_unresolved_references(self):
        mutations = [
            (lambda w: setattr(w["PP3"]["A1"], "value", "wrong"), "headers"),
            (lambda w: w["defect_code"].append([1, "duplicate"]), "Duplicate"),
            (lambda w: setattr(w["PP3"]["B2"], "value", 2), "Unresolved"),
            (lambda w: setattr(w["PP3"]["C2"], "value", "2"), "integer"),
            (lambda w: w.create_sheet("extra"), "sheet schema"),
        ]
        for mutation, error in mutations:
            with self.subTest(error=error):
                self.write_manifest([self.workbook(mutate=mutation)])
                with self.assertRaisesRegex(ValueError, error):
                    extractor.extract(self.manifest, [self.root])

    def test_hash_missing_inventory_and_ambiguous_sources(self):
        item = self.workbook()
        self.write_manifest([{**item, "sha256": "0" * 64}])
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            extractor.extract(self.manifest, [self.root])
        self.write_manifest([item])
        with self.assertRaisesRegex(ValueError, "found 0"):
            extractor.extract(self.manifest, [self.root / "missing"])
        other = self.root / "other"
        duplicate = other / item["archive_path"]
        duplicate.parent.mkdir(parents=True)
        duplicate.write_bytes((self.root / item["archive_path"]).read_bytes())
        with self.assertRaisesRegex(ValueError, "found 2"):
            extractor.extract(self.manifest, [self.root, other])
        self.write_manifest([item, item])
        with self.assertRaisesRegex(ValueError, "duplicate coupon"):
            extractor.extract(self.manifest, [self.root])

    def test_cli_exclusive_output_and_no_failed_export(self):
        item = self.workbook()
        self.write_manifest([item])
        output = self.root / "export.json"
        args = ["--source-root", str(self.root), "--manifest", str(self.manifest), "--output", str(output)]
        extractor.main(args)
        initial = output.read_bytes()
        with self.assertRaises(FileExistsError):
            extractor.main(args)
        self.assertEqual(output.read_bytes(), initial)
        args[-1] = str(self.root / item["archive_path"])
        with self.assertRaises(FileExistsError):
            extractor.main(args)
        args[-1] = str(self.root / "failed.json")
        self.write_manifest([{**item, "sha256": "0" * 64}])
        with self.assertRaises(ValueError):
            extractor.main(args)
        self.assertFalse(Path(args[-1]).exists())


if __name__ == "__main__":
    unittest.main()
