#!/usr/bin/env python3
"""Read-only single replacement against a frozen snapshot, protocol single-event-1.

No event history, ledger, replay, sequencing, updated snapshot, or live enforcement.
Stale means a recorded binding needs recheck, not factual falsity or denial.
Hashes preserve list order: they identify serialized snapshots, not canonical graphs.
"""
from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import sys

MAX_BYTES = 128 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def candidate_ids(payload):
    if type(payload) is not dict or type(payload.get("candidates")) is not list:
        return []
    return sorted({x for x in payload["candidates"] if type(x) is str and x})


def envelope(payload, errors, snapshot_hash=None, results=None):
    return {
        "protocol": "workflow-shadow-single-event-1",
        "status": "invalid" if errors else "evaluated",
        "snapshot_hash": snapshot_hash,
        "candidate_results": results if results is not None else [
            {"id": x, "impact": "unknown", "reasons": list(errors), "witness_path": []}
            for x in candidate_ids(payload)
        ],
        "errors": errors, "evaluator": "python_reference",
        "actual_shacl_executed": False,
    }


def fields(value, expected):
    return type(value) is dict and set(value) == set(expected.split())


def string(value):
    return type(value) is str and bool(value)


def validate(payload):
    if not fields(payload, "snapshot candidates change"):
        return "invalid_payload_fields"
    snapshot, candidates, change = (payload[k] for k in ("snapshot", "candidates", "change"))
    if not fields(snapshot, "nodes edges coverage"):
        return "invalid_snapshot_fields"
    nodes, edges, coverage = (snapshot[k] for k in ("nodes", "edges", "coverage"))
    if type(coverage) is not str or coverage not in ("complete", "partial"):
        return "invalid_coverage"
    if type(nodes) is not list or len(nodes) > 100:
        return "invalid_nodes_or_bound"
    versions = {}
    for node in nodes:
        if not fields(node, "id version") or not all(string(v) for v in node.values()):
            return "invalid_node"
        if node["id"] in versions:
            return "duplicate_node_id"
        versions[node["id"]] = node["version"]
    if type(edges) is not list or len(edges) > 200:
        return "invalid_edges_or_bound"
    for edge in edges:
        if not fields(edge, "dependent prerequisite") or not all(string(v) for v in edge.values()):
            return "invalid_edge"
        if any(v not in versions for v in edge.values()):
            return "missing_edge_endpoint"
    if type(candidates) is not list or len(candidates) > 100:
        return "invalid_candidates_or_bound"
    if not all(string(x) for x in candidates):
        return "invalid_candidate"
    if len(set(candidates)) != len(candidates):
        return "duplicate_candidate"
    if any(x not in versions for x in candidates):
        return "unknown_candidate"
    if not fields(change, "node_id old_version new_version") or not all(string(v) for v in change.values()):
        return "invalid_change"
    if change["old_version"] == change["new_version"]:
        return "unchanged_version"
    if change["node_id"] not in versions:
        return "unknown_change_target"
    if versions[change["node_id"]] != change["old_version"]:
        return "version_conflict"
    return None


def evaluate(payload):
    """Return an explicit result; never mutate input or consult external state."""
    try:
        if len(canonical(payload)) > MAX_BYTES:
            return envelope(payload, ["payload_byte_limit"])
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        return envelope(payload, ["invalid_json_value"])
    error = validate(payload)
    if error:
        return envelope(payload, [error])
    snapshot = payload["snapshot"]
    adjacency = {n["id"]: set() for n in snapshot["nodes"]}
    for edge in snapshot["edges"]:
        adjacency[edge["dependent"]].add(edge["prerequisite"])
    target = payload["change"]["node_id"]
    results = []
    for candidate in sorted(payload["candidates"]):
        queue, visited, witness = deque([[candidate]]), {candidate}, []
        while queue:
            path = queue.popleft()
            if path[-1] == target:
                witness = path
                break
            for neighbor in sorted(adjacency[path[-1]]):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        if witness:
            impact, reason = "stale", "recorded_dependency_path"
        elif snapshot["coverage"] == "complete":
            impact, reason = "unaffected", "no_path_complete_coverage"
        else:
            impact, reason = "unknown", "no_path_partial_coverage"
        results.append({"id": candidate, "impact": impact, "reasons": [reason],
                        "witness_path": witness})
    digest = hashlib.sha256(canonical(snapshot)).hexdigest()
    return envelope(payload, [], digest, results)


def read_input(path):
    """Bound raw bytes before parsing; reject duplicate keys and nonfinite JSON."""
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        return envelope(None, ["payload_byte_limit"])
    errors = []

    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                errors.append("duplicate_json_key")
            obj[key] = value
        return obj

    def constant(value):
        errors.append("nonfinite_json_constant")
        return None

    try:
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                             parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError):
        return envelope(None, ["malformed_json"])
    return envelope(payload, sorted(set(errors))) if errors else evaluate(payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = read_input(args.input)
    except OSError:
        result = envelope(None, ["input_read_error"])
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=True, indent=2, allow_nan=False)
            stream.write("\n")
    except OSError as exc:
        print(f"Output refused: {exc}", file=sys.stderr)
        return 2
    return 0 if result["status"] == "evaluated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
