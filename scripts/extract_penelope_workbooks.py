#!/usr/bin/env python3
"""Extract pinned, cached PENELOPE workbooks; never calculate or repair values.

Requires openpyxl. Source roots contain the manifest's archive-relative paths.
Only file inventory/hashes and attribution are read from the old audit manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re

import openpyxl

SCHEMA_VERSION = "penelope-workbook-extract-1"
ANNOTATION_FIELDS = ("defect", "welding_setting", "bead", "x_init_mm", "x_end_mm", "sample_init", "sample_end")
ANNOTATION_HEADERS = ["defect", "welding_setting", "bead", "x_init [mm]", "x_end [mm]", "x_init [# sample]", "x_end [# sample]"]
DICTIONARY_HEADERS = {
    "defect_code": [["Code", "Defect"]],
    "welding_settings_code": [
        ["Code", "welding settings", None, None, None, None, None, None],
        [None, "Vdc (V)", "Idc (A)", "Vac (V)", "Iac (A)", "wfs (dc)", "wfs (ac)", "ts (cm/min)"],
    ],
}
ATTRIBUTION_KEYS = ("title", "doi", "authors", "version", "url", "license", "license_url", "metadata_url", "metadata_sha256", "extract_license")


def scalar(value):
    if value is None or type(value) in (str, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError(f"Unsupported cell value: {value!r}")


def integer(value, locator):
    if type(value) is not int:
        raise ValueError(f"Expected integer code at {locator}: {value!r}")
    return value


def numeric(value, locator):
    if value is not None and type(value) not in (int, float):
        raise ValueError(f"Expected number or null at {locator}: {value!r}")


def extract_workbook(raw, coupon, archive_path, digest):
    formula_book = openpyxl.load_workbook(io.BytesIO(raw), data_only=False)
    cached_book = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    try:
        expected = {**DICTIONARY_HEADERS, coupon: [ANNOTATION_HEADERS]}
        if set(formula_book.sheetnames) != set(expected):
            raise ValueError(f"Unexpected sheet schema for {coupon}: {formula_book.sheetnames}")
        sheets = {}
        dictionaries = {}
        records = []
        for name, headers in expected.items():
            sheet, cache = formula_book[name], cached_book[name]
            width = len(headers[0])
            if sheet.max_column != width or sheet.max_row < len(headers):
                raise ValueError(f"Unexpected dimensions for {coupon}:{name}")
            actual_headers = [[sheet.cell(r, c).value for c in range(1, width + 1)] for r in range(1, len(headers) + 1)]
            if actual_headers != headers:
                raise ValueError(f"Unexpected headers for {coupon}:{name}")
            rows = []
            entries = []
            seen_codes = set()
            for row_number in range(1, sheet.max_row + 1):
                cells = []
                for column in range(1, width + 1):
                    cell = sheet.cell(row_number, column)
                    is_formula = cell.data_type == "f"
                    value = scalar(cache.cell(row_number, column).value if is_formula else cell.value)
                    cells.append({"cell": cell.coordinate, "value": value,
                                  "formula": scalar(cell.value) if is_formula else None,
                                  "cached_value": value if is_formula else None,
                                  "data_type": cell.data_type})
                rows.append({"excel_row": row_number, "cells": cells})
                if row_number <= len(headers) or all(c["value"] is None and c["formula"] is None for c in cells):
                    continue
                values = [c["value"] for c in cells]
                locator = f"{coupon}:{name}:{row_number}"
                if name != coupon:
                    code = integer(values[0], locator)
                    if code in seen_codes:
                        raise ValueError(f"Duplicate dictionary code at {locator}: {code}")
                    seen_codes.add(code)
                    if name == "defect_code":
                        if not isinstance(values[1], str) or not values[1]:
                            raise ValueError(f"Expected defect label at {locator}")
                    else:
                        for value in values[1:]:
                            numeric(value, locator)
                    entries.append({"id": f"{coupon}:{name}:{code}", "code": code,
                                    "sheet": name, "excel_row": row_number, "values": values})
                else:
                    for value in values[:3]:
                        integer(value, locator)
                    for value in values[3:]:
                        numeric(value, locator)
                    records.append({"id": f"{coupon}:{row_number}", "coupon": coupon,
                                    "archive_path": archive_path, "sheet": name,
                                    "excel_row": row_number, "cell_range": f"A{row_number}:G{row_number}",
                                    "values": dict(zip(ANNOTATION_FIELDS, values)),
                                    "field_cells": dict(zip(ANNOTATION_FIELDS, (c["cell"] for c in cells))),
                                    "dictionary_refs": {
                                        "defect": f"{coupon}:defect_code:{values[0]}",
                                        "welding_setting": f"{coupon}:welding_settings_code:{values[1]}",
                                    }})
            sheets[name] = {"max_row": sheet.max_row, "max_column": width,
                            "header_row_count": len(headers), "rows": rows}
            if name != coupon:
                dictionaries[name] = entries
        ids = {entry["id"] for entries in dictionaries.values() for entry in entries}
        for record in records:
            if not set(record["dictionary_refs"].values()) <= ids:
                raise ValueError(f"Unresolved dictionary reference at {record['id']}")
        return {"coupon": coupon, "archive_path": archive_path, "sha256": digest,
                "sheets": sheets, "dictionaries": dictionaries, "records": records}
    finally:
        formula_book.close()
        cached_book.close()


def extract(manifest_path, source_roots):
    manifest_bytes = Path(manifest_path).read_bytes()
    manifest = json.loads(manifest_bytes)
    inventory = manifest["files"]
    if not isinstance(inventory, list) or not inventory:
        raise ValueError("Manifest must have a nonempty files inventory")
    workbooks, seen = [], set()
    for item in inventory:
        coupon, archive_path, digest = item["coupon"], item["archive_path"], item["sha256"]
        if not re.fullmatch(r"PP[3-7]", coupon) or coupon in seen:
            raise ValueError(f"Unsupported or duplicate coupon: {coupon}")
        seen.add(coupon)
        relative = PurePosixPath(archive_path)
        if archive_path != f"ZENODO_Penelope/{coupon}/2. ndt_data/defects_xlocation.xlsx":
            raise ValueError(f"Unexpected archive path: {archive_path}")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"Invalid SHA-256 for {coupon}")
        candidates = sorted({(Path(root) / relative).resolve() for root in source_roots if (Path(root) / relative).is_file()})
        if len(candidates) != 1:
            raise ValueError(f"Expected exactly one source for {coupon}, found {len(candidates)}")
        raw = candidates[0].read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"SHA-256 mismatch for {coupon}")
        workbooks.append(extract_workbook(raw, coupon, archive_path, digest))
    source = manifest.get("source", {})
    return {"schema_version": SCHEMA_VERSION,
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "source_attribution": {key: source[key] for key in ATTRIBUTION_KEYS if key in source},
            "extraction": {"library": "openpyxl", "library_version": openpyxl.__version__,
                           "formula_policy": "Preserve formula text and saved cache; never evaluate. Missing cache is null.",
                           "row_policy": "Preserve every cell in sheet dimensions; omit wholly empty rows from typed records.",
                           "scope": "Workbook transcription and code references only; no design mapping or physical decision."},
            "workbooks": workbooks}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, action="append", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    # lexists semantics also reject dangling symlinks. Exclusive creation handles races.
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError(f"Refusing existing output: {args.output}")
    result = extract(args.manifest, args.source_root)
    encoded = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with args.output.open("x", encoding="utf-8") as handle:
        handle.write(encoded)


if __name__ == "__main__":
    main()
