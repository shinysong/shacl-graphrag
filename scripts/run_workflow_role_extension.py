"""Offline authored dependency-registration extension, not live role gating."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from scripts import workflow_shadow_impact as python_arm
from scripts import workflow_shadow_rdf as rdf_arm

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs/experiments/records/20261015-workflow-shadow-single.json"
REQUEST, REVIEW = "data-steward-request", "data-steward-review"


def build_cases(record):
    """Copy the consumed projection; author no real requests or reviews."""
    baseline = copy.deepcopy(record["cases"][0]["input"])
    if record["cases"][0]["id"] != "packet_replacement":
        raise ValueError("Expected frozen packet_replacement first")
    added = copy.deepcopy(baseline)
    added["snapshot"]["nodes"].extend(
        {"id": name, "version": "authored-v1"} for name in (REQUEST, REVIEW))
    added["snapshot"]["edges"].extend([
        {"dependent": REVIEW, "prerequisite": REQUEST},
        {"dependent": REQUEST, "prerequisite": "packet"}])
    added["candidates"].append(REVIEW)
    omitted = copy.deepcopy(added)
    omitted["snapshot"]["edges"].pop()
    methods = copy.deepcopy(added)
    methods["change"] = copy.deepcopy(next(
        c["input"]["change"] for c in record["cases"]
        if c["id"] == "methods_request_replacement"))
    return [{"id": name, "input": payload} for name, payload in (
        ("baseline", baseline), ("added_role", added),
        ("omitted_link", omitted), ("methods_change", methods))]


def score(case_id, output):
    """Authored external status expectations, never passed to evaluators."""
    original = {"methods-review": "stale", "implementation-review": "stale"}
    expected = {
        "baseline": original,
        "added_role": {**original, REVIEW: "stale"},
        "omitted_link": {**original, REVIEW: "unknown"},
        "methods_change": {"methods-review": "stale",
                           "implementation-review": "unknown", REVIEW: "unknown"},
    }[case_id]
    actual = {row["id"]: row["impact"] for row in output["candidate_results"]}
    return {"authored_expected_status": expected,
            "status_map_matches": actual == expected,
            "matching_candidate_count": sum(actual.get(k) == v for k, v in expected.items()),
            "expected_candidate_count": len(expected)}


def run(record_path):
    record_path = Path(record_path)
    paths = [record_path, Path(python_arm.__file__), Path(rdf_arm.__file__), Path(__file__)]
    sources = {}
    for path in paths:
        raw = path.read_bytes()
        label = str(path.resolve().relative_to(ROOT)) if path.resolve().is_relative_to(ROOT) else str(path)
        sources[label] = {"sha256": hashlib.sha256(raw).hexdigest(),
                          "bytes": len(raw), "lines": len(raw.splitlines())}
    record = json.loads(record_path.read_bytes())
    cases = build_cases(record)
    totals = {}
    for name, evaluator in (("python", python_arm.evaluate), ("rdf", rdf_arm.evaluate)):
        totals[name] = {"evaluations": 0, "candidate_outputs": 0,
                        "actual_shacl_invocations": 0, "shacl_conformed": 0}
        for case in cases:
            before = copy.deepcopy(case["input"])
            output = evaluator(case["input"])
            case.setdefault("arms", {})[name] = {
                "output": output, "score": score(case["id"], output),
                "input_unchanged": before == case["input"]}
            totals[name]["evaluations"] += 1
            totals[name]["candidate_outputs"] += len(output["candidate_results"])
            totals[name]["actual_shacl_invocations"] += int(output["actual_shacl_executed"])
            totals[name]["shacl_conformed"] += int(output.get("shacl_conforms") is True)
    return {
        "protocol": "workflow-role-extension-1", "cases": cases, "arm_counts": totals,
        "source_manifest": sources,
        "setup_size_interpretation": "File bytes and lines describe existing evaluator and runner setup; not labor or maintenance time.",
        "mapping_edits": {"added_nodes": 2, "added_edges": 2, "added_candidates": 1,
                          "omission_control_removed_edges": 1, "evaluator_source_edits": 0},
        "scope": "Authored hypothetical dependency registration on a consumed real projection. No real reviews/data added or source versions updated. No automated role selection or authorization rule; role gating is NOT implemented.",
        "limitations": ["Coverage remains supplied and partial in every case.",
                        "Status agreement is with authored expectations, not external truth.",
                        "SHACL checks converted structure, not source completeness.",
                        "No maintenance labor, RDF superiority, or independent benchmark claim."],
        "paid_calls": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=RECORD)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.record)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
