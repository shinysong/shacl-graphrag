#!/usr/bin/env python3
"""Build source-only chunks and explicit same-workbook codebook links (offline)."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

DEFAULT_SOURCE = Path("research/actionable-evidence-1/source/workbook-extraction-v1.json")
RELATIONS = {"defect": "defect_code", "welding_setting": "welding_settings_code"}


def serialized(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def code_key(value):
    require(type(value) is int, f"Expected integer dictionary code, got {value!r}")
    return value


def build_corpus(source, *, source_sha256, builder_sha256):
    """Validate extracted source, then serialize it without interpretation or repair."""
    require(source["schema_version"] == "penelope-workbook-extract-1", "Unsupported source schema")
    nodes, edges, inventories = [], [], []
    node_ids, coupons, archives = set(), set(), set()
    duplicate_groups = {}

    def add_node(kind, payload):
        node_id = payload["id"]
        require(node_id not in node_ids, f"Duplicate node ID: {node_id}")
        node_ids.add(node_id)
        nodes.append({"node_id": node_id, "node_type": kind, "source": payload,
                      "text": serialized(payload)})

    for workbook in source["workbooks"]:
        coupon = workbook["coupon"]
        require(coupon not in coupons, f"Duplicate workbook namespace: {coupon}")
        require(workbook["archive_path"] not in archives, "Duplicate workbook archive path")
        coupons.add(coupon)
        archives.add(workbook["archive_path"])
        provenance = {k: workbook[k] for k in ("coupon", "archive_path", "sha256")}
        rows = {}
        headers = {}
        for sheet, content in workbook["sheets"].items():
            rows[sheet] = {}
            for row in content["rows"]:
                number = row["excel_row"]
                require(number not in rows[sheet], f"Duplicate row: {coupon}/{sheet}/{number}")
                cells = row["cells"]
                require(len({c["cell"] for c in cells}) == len(cells), "Duplicate cell coordinate")
                rows[sheet][number] = row
            headers[sheet] = [r for r in content["rows"] if r["excel_row"] <= content["header_row_count"]]

        def raw_row(sheet, number):
            require(sheet in rows and number in rows[sheet], f"Missing raw row: {coupon}/{sheet}/{number}")
            return rows[sheet][number]

        lookup = {}
        hashes = {}
        require(set(workbook["dictionaries"]) == set(RELATIONS.values()), "Unexpected dictionary scope")
        for relation in RELATIONS.values():
            lookup[relation] = {}
            entries = workbook["dictionaries"][relation]
            for entry in entries:
                code = code_key(entry["code"])
                require(code not in lookup[relation], f"Duplicate code: {coupon}/{relation}/{code}")
                expected_id = f"{coupon}:{relation}:{code}"
                require(entry["id"] == expected_id and entry["sheet"] == relation,
                        f"Dictionary code/ID/scope inconsistency: {entry['id']}")
                raw = raw_row(relation, entry["excel_row"])
                require(serialized(entry["values"]) == serialized([c["value"] for c in raw["cells"]]),
                        f"Dictionary/raw values mismatch: {expected_id}")
                require(serialized(entry["values"][0]) == serialized(code), "Dictionary code/value mismatch")
                lookup[relation][code] = entry
                payload = {**copy.deepcopy(entry), **provenance, "cells": copy.deepcopy(raw["cells"]),
                           "header_rows": copy.deepcopy(headers[relation])}
                add_node("dictionary", payload)
            # Hash content without workbook-local IDs so repeated codebooks are visible.
            content = {"header_rows": headers[relation],
                       "rows": [raw_row(relation, e["excel_row"]) for e in sorted(entries, key=lambda e: e["code"])]}
            hashes[relation] = sha256(serialized(content).encode("utf-8"))
            duplicate_groups.setdefault((relation, hashes[relation]), []).append(coupon)

        for record in workbook["records"]:
            require(record["coupon"] == coupon and record["archive_path"] == workbook["archive_path"]
                    and record["sheet"] == coupon and record["id"] == f"{coupon}:{record['excel_row']}",
                    f"Annotation namespace/provenance inconsistency: {record['id']}")
            raw = raw_row(record["sheet"], record["excel_row"])
            cells = {c["cell"]: c for c in raw["cells"]}
            require(set(record["field_cells"]) == set(record["values"]), "Field/cell mapping mismatch")
            require(len(set(record["field_cells"].values())) == len(record["field_cells"]), "Duplicate field cell")
            for field, value in record["values"].items():
                cell = record["field_cells"][field]
                require(cell in cells and serialized(cells[cell]["value"]) == serialized(value),
                        f"Annotation/raw values mismatch: {record['id']}/{field}")
            require(set(record["dictionary_refs"]) == set(RELATIONS), "Missing or unexpected dictionary references")
            add_node("annotation", {**copy.deepcopy(record), "sha256": workbook["sha256"],
                                     "cells": copy.deepcopy(raw["cells"]),
                                     "header_rows": copy.deepcopy(headers[record["sheet"]])})
            for field, relation in RELATIONS.items():
                # Raw cell value drives lookup; saved reference is only a cross-check.
                code = code_key(cells[record["field_cells"][field]]["value"])
                require(code in lookup[relation], f"Missing dictionary target: {coupon}/{relation}/{code}")
                target = lookup[relation][code]
                require(record["dictionary_refs"][field] == target["id"],
                        f"Wrong namespace or dictionary reference: {record['id']}/{field}")
                edge_id = f"{record['id']}|{field}|{target['id']}"
                edge = {"edge_id": edge_id, "subject": record["id"], "field": field,
                        "relation_type": relation, "target": target["id"], "code": code,
                        "provenance": {**provenance, "sheet": record["sheet"],
                                       "cell": record["field_cells"][field],
                                       "target_sheet": target["sheet"], "target_excel_row": target["excel_row"]}}
                edges.append(edge)
        inventories.append({**provenance, "annotation_nodes": len(workbook["records"]),
                            "dictionary_nodes": sum(len(v) for v in lookup.values()),
                            "dictionary_reference_edges": 2 * len(workbook["records"]),
                            "codebook_content_sha256": hashes})

    nodes.sort(key=lambda n: n["node_id"])
    edges.sort(key=lambda e: e["edge_id"])
    chunks = [{"chunk_id": "node:" + n["node_id"], "chunk_type": "node", "node_id": n["node_id"],
               "text": n["text"]} for n in nodes]
    chunks.extend({"chunk_id": "edge:" + e["edge_id"], "chunk_type": "edge", "edge_id": e["edge_id"],
                   "text": serialized(e)} for e in edges)
    return {"schema_version": "graphrag-source-corpus-1",
            "source_attribution": copy.deepcopy(source["source_attribution"]),
            "derivation": {"source_sha256": source_sha256, "builder_sha256": builder_sha256,
                           "manifest_sha256": source["manifest_sha256"],
                           "source_schema_version": source["schema_version"],
                           "source_extraction": copy.deepcopy(source["extraction"]),
                           "license": source["source_attribution"]["extract_license"],
                           "change_note": "Derived source serialization and same-workbook codebook links; no inferred workflow links or answer summaries.",
                           "cohort_note": "Consumed real development source; not fresh evaluation."},
            "inventory": {"annotation_nodes": sum(n["node_type"] == "annotation" for n in nodes),
                          "dictionary_nodes": sum(n["node_type"] == "dictionary" for n in nodes),
                          "nodes": len(nodes), "edges": len(edges), "chunks": len(chunks),
                          "workbooks": sorted(inventories, key=lambda w: w["coupon"]),
                          "duplicate_codebooks": [{"relation_type": r, "content_sha256": h, "coupons": sorted(cs)}
                                                  for (r, h), cs in sorted(duplicate_groups.items()) if len(cs) > 1],
                          "duplicate_note": "Identical codebooks retain separate workbook namespaces; no deduplication."},
            "nodes": nodes, "edges": edges, "chunks": chunks}


def write_corpus(source_path, output_path):
    source_bytes = Path(source_path).read_bytes()
    corpus = build_corpus(json.loads(source_bytes), source_sha256=sha256(source_bytes),
                          builder_sha256=sha256(Path(__file__).read_bytes()))
    data = (json.dumps(corpus, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    with Path(output_path).open("xb") as output:
        output.write(data)
    return corpus["inventory"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        inventory = write_corpus(args.source, args.output)
    except (ValueError, KeyError, TypeError, IndexError, OSError) as exc:
        parser.exit(1, f"Corpus build failed: {exc}\n")
    print(serialized(inventory))


if __name__ == "__main__":
    main()
