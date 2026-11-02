#!/usr/bin/env python3
"""Offline JSON/RDF matched validation of consumed PENELOPE annotations.

The adapter binds extracted codes to coupon-scoped expected references. SHACL
checks this binding and supplied classes, not spreadsheet authenticity or truth.
Input is the bounded extractor schema; arbitrary JSON schema validation is outside scope.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import traceback
from datetime import UTC, datetime
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from urllib.parse import quote

from pyshacl import validate
from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import SH

P = Namespace("https://example.org/penelope/validation/")
BASE = "https://example.org/penelope/source/"
SHAPES = (
    Path(__file__).resolve().parents[1]
    / "research/actionable-evidence-1/source-validation/shapes.ttl"
)
FIELDS = (
    "defect",
    "welding_setting",
    "bead",
    "x_init_mm",
    "x_end_mm",
    "sample_init",
    "sample_end",
)
REFS = {
    "defect": ("defect_code", P.DefectCode),
    "welding_setting": ("welding_settings_code", P.SettingCode),
}
PAIRS = (("x_init_mm", "x_end_mm"), ("sample_init", "sample_end"))


def uri(*parts):
    return URIRef(BASE + "/".join(quote(str(p), safe="") for p in parts))


def annotation_uri(record):
    return uri(record["coupon"], record["sheet"], record["excel_row"])


def reference_uri(ref):
    return uri("codebook", ref)


def literal(value):
    if type(value) is float and math.isfinite(value):
        return Literal(Decimal(str(value)), datatype=XSD.decimal)
    if isinstance(value, (dict, list)):
        return Literal(json.dumps(value, sort_keys=True), datatype=XSD.string)
    return Literal(value)


def project(source):
    graph = Graph()
    graph.bind("p", P)
    seen = set()
    for workbook in source["workbooks"]:
        for sheet, cls in (
            ("defect_code", P.DefectCode),
            ("welding_settings_code", P.SettingCode),
        ):
            for entry in workbook["dictionaries"][sheet]:
                # Class follows the actual dictionary sheet, never the reference label.
                node = reference_uri(entry["id"])
                graph.add((node, RDF.type, cls))
                graph.add((node, P.sourceFileSha256, Literal(workbook["sha256"])))
                graph.add((node, P.archiveMember, Literal(workbook["archive_path"])))
                graph.add((node, P.sheet, Literal(entry["sheet"])))
                graph.add((node, P.excelRow, Literal(entry["excel_row"])))
                graph.add((node, P.sourceCode, literal(entry["code"])))
                graph.add((node, P.codeCell, Literal(f"A{entry['excel_row']}")))
                graph.add(
                    (node, P.sourceValuesJSON, Literal(json.dumps(entry["values"])))
                )
        for record in workbook["records"]:
            node = annotation_uri(record)
            if node in seen:
                raise ValueError(f"duplicate annotation URI: {node}")
            seen.add(node)
            graph.add((node, RDF.type, P.Annotation))
            for key, value in {
                "annotationId": record["id"],
                "sourceFileSha256": workbook["sha256"],
                "archiveMember": record["archive_path"],
                "sheet": record["sheet"],
                "excelRow": record["excel_row"],
            }.items():
                graph.add((node, P[key], Literal(value)))
            for field in FIELDS:
                cell = uri(
                    record["coupon"], record["sheet"], record["field_cells"][field]
                )
                graph.add((node, P["cell_" + field], cell))
                graph.add((cell, P.cellAddress, Literal(record["field_cells"][field])))
                graph.add((cell, P.sourceFileSha256, Literal(workbook["sha256"])))
                value = record["values"].get(field)
                if field in REFS:
                    ref = record.get("dictionary_refs", {}).get(field)
                    if ref is not None:
                        graph.add((node, P[field], reference_uri(ref)))
                    if value is not None:
                        sheet = REFS[field][0]
                        graph.add(
                            (
                                node,
                                P["expected_" + field],
                                reference_uri(f"{record['coupon']}:{sheet}:{value}"),
                            )
                        )
                elif value is not None:
                    graph.add((node, P[field], literal(value)))
    return graph


def python_checks(source):
    """Independent JSON checks: no RDF, SHACL, or SHACL result consultation."""
    failures = set()
    for workbook in source["workbooks"]:
        memberships = {
            sheet: {entry["id"] for entry in entries}
            for sheet, entries in workbook["dictionaries"].items()
        }
        for record in workbook["records"]:
            values = record["values"]
            for field in FIELDS:
                value = values.get(field)
                if field in ("defect", "welding_setting"):
                    sheet = (
                        "defect_code" if field == "defect" else "welding_settings_code"
                    )
                    ref = record.get("dictionary_refs", {}).get(field)
                    if ref is None:
                        failures.add((record["id"], field, "required"))
                    expected = (
                        None if value is None else f"{record['coupon']}:{sheet}:{value}"
                    )
                    if ref != expected or (
                        ref is not None and ref not in memberships[sheet]
                    ):
                        failures.add((record["id"], field, "reference"))
                elif value is None:
                    failures.add((record["id"], field, "required"))
                elif not (
                    type(value) is int
                    or (
                        field.endswith("_mm")
                        and type(value) is float
                        and math.isfinite(value)
                    )
                ):
                    failures.add((record["id"], field, "type"))
            for start, end in (
                ("x_init_mm", "x_end_mm"),
                ("sample_init", "sample_end"),
            ):
                a, b = values.get(start), values.get(end)
                allowed = (int, float) if start.endswith("_mm") else (int,)
                if (
                    type(a) in allowed
                    and type(b) in allowed
                    and math.isfinite(a)
                    and math.isfinite(b)
                    and a > b
                ):
                    failures.add((record["id"], start, "order"))
    return failures


def shacl_checks(graph, shapes=None):
    shapes = shapes if shapes is not None else Graph().parse(SHAPES)
    conforms, report, readable = validate(
        graph,
        shacl_graph=shapes,
        inference="none",
        advanced=False,
        js=False,
        meta_shacl=True,
        abort_on_first=False,
        inplace=False,
    )
    normalized = set()
    components = {
        SH.MinCountConstraintComponent: "required",
        SH.MaxCountConstraintComponent: "required",
        SH.DatatypeConstraintComponent: "type",
        SH.NodeKindConstraintComponent: "reference",
        SH.ClassConstraintComponent: "reference",
        SH.EqualsConstraintComponent: "reference",
        SH.OrConstraintComponent: "type",
    }
    for result in report.subjects(RDF.type, SH.ValidationResult):
        focus = report.value(result, SH.focusNode)
        annotation_id = graph.value(focus, P.annotationId)
        shape = report.value(result, SH.sourceShape)
        field = shapes.value(shape, P.normalizedField)
        if field is not None:
            kind = str(shapes.value(shape, P.normalizedKind))
        else:
            path = report.value(result, SH.resultPath)
            field = str(path).removeprefix(str(P))
            kind = components[report.value(result, SH.sourceConstraintComponent)]
        if annotation_id is None or str(field) not in FIELDS:
            raise ValueError(f"unrecognized SHACL report row: {result}")
        normalized.add((str(annotation_id), str(field), kind))
    return bool(conforms), normalized, report, str(readable)


def rows(failures):
    return [
        dict(zip(("annotation_id", "field", "kind"), row)) for row in sorted(failures)
    ]


def requests(source, failures):
    output = []
    for workbook in source["workbooks"]:
        for record in workbook["records"]:
            for rid, field, kind in sorted(failures):
                if rid != record["id"]:
                    continue
                fields = [field]
                if kind == "order":
                    fields.append(dict(PAIRS)[field])
                output.append(
                    {
                        "annotation_id": rid,
                        "kind": kind,
                        "action": "request_evidence"
                        if kind == "required"
                        else "request_source_confirmation",
                        "origin": "researcher-authored workflow request; not source-issued instruction",
                        "archive_member": record["archive_path"],
                        "source_file_sha256": workbook["sha256"],
                        "sheet": record["sheet"],
                        "excel_row": record["excel_row"],
                        "fields": {
                            f: {
                                "value": record["values"].get(f),
                                "cell": record["field_cells"][f],
                            }
                            for f in fields
                        },
                        "instruction": "Obtain or confirm the cited source evidence; no automatic value change or physical action.",
                    }
                )
    return output


def save_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    out = args.output_dir
    try:
        inputs = {
            "input.json": args.input,
            "validator.py": Path(__file__),
            "shapes.ttl": SHAPES,
            "contract.md": SHAPES.with_name("contract.md"),
            "uv.lock": Path(__file__).resolve().parents[1] / "uv.lock",
        }
        hashes = {}
        for name, path in inputs.items():
            payload = path.read_bytes()
            (out / name).write_bytes(payload)
            hashes[name] = hashlib.sha256(payload).hexdigest()
        save_json(
            out / "manifest.json",
            {
                "schema_version": "penelope-source-validation-1",
                "hashes": hashes,
                "versions": {name: version(name) for name in ("rdflib", "pyshacl")},
                "python": platform.python_version(),
                "inference": "none",
                "advanced": False,
                "created_at_utc": datetime.now(UTC).isoformat(),
                "input_path": str(args.input),
                "scope": "Consumed-source software demonstration; not a new efficacy cohort.",
            },
        )
        source = json.loads((out / "input.json").read_text())
        if source.get("schema_version") != "penelope-workbook-extract-1":
            raise ValueError("unsupported source schema_version")
        graph = project(source)
        graph.serialize(out / "data.ttl", format="turtle")
        conforms, actual, report, readable = shacl_checks(
            graph, Graph().parse(out / "shapes.ttl")
        )
        report.serialize(out / "report.ttl", format="turtle")
        (out / "report.txt").write_text(readable)
        expected = python_checks(source)
        save_json(out / "python-violations.json", rows(expected))
        save_json(out / "shacl-violations.json", rows(actual))
        statuses = []
        for workbook in source["workbooks"]:
            for record in workbook["records"]:
                py = {r for r in expected if r[0] == record["id"]}
                sh = {r for r in actual if r[0] == record["id"]}
                statuses.append(
                    {
                        "annotation_id": record["id"],
                        "python_conforms": not py,
                        "shacl_conforms": not sh,
                        "violation_set_parity": py == sh,
                    }
                )
        save_json(out / "records.json", statuses)
        save_json(out / "requests.json", requests(source, actual))
        summary = {
            "source_attribution": source["source_attribution"],
            "input_bytes_unchanged": hashlib.sha256(args.input.read_bytes()).hexdigest()
            == hashes["input.json"],
            "annotation_count": len(statuses),
            "shacl_conforms": conforms,
            "normalized_violation_count": len(actual),
            "raw_report_row_count": len(
                set(report.subjects(RDF.type, SH.ValidationResult))
            ),
            "violation_set_parity": expected == actual,
            "conforming_records": sum(s["shacl_conforms"] for s in statuses),
            "interpretation": "No detected violation is not physical correctness. Parity is not mapping or source truth. Ascending intervals are researcher-declared; no measured-settings, repair or release approval claim.",
        }
        save_json(out / "summary.json", summary)
        print(json.dumps(summary, ensure_ascii=False))
        return 0 if expected == actual else 2
    except Exception:
        (out / "failure.txt").write_text(traceback.format_exc())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
