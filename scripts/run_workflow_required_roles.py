"""Run predeclared authored policy-change cases; no live approvals or model calls."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from scripts import workflow_required_roles as rules

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "research/operations/designs/workflow-required-roles.json"


def run():
    design = json.loads(DESIGN.read_text())
    policy_paths = {v: DESIGN.with_name("workflow-required-roles-" + v + ".json")
                    for v in ("v1", "v2")}
    policies = {v: json.loads(p.read_text()) for v, p in policy_paths.items()}
    rows = []
    for case in design["cases"]:
        for version, policy in policies.items():
            for arm in ("coded", "json", "rdf"):
                payload, selected = copy.deepcopy(case["input"]), copy.deepcopy(policy)
                output = (rules.evaluate_coded(payload, version) if arm == "coded" else
                          getattr(rules, "evaluate_" + arm)(payload, selected))
                rows.append({"case": case["id"], "policy_version": version, "arm": arm,
                             "input": case["input"], "output": output,
                             "inputs_unchanged": payload == case["input"] and selected == policy,
                             "external_score": {"authored_expected": case["authored_expected"][version],
                                                "matches": output["decision"] == case["authored_expected"][version]}})
    paths = [DESIGN, *policy_paths.values(), Path(__file__), Path(rules.__file__),
             ROOT / "tests/test_workflow_required_roles.py"]
    sources = {str(p.relative_to(ROOT)): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
               "bytes": p.stat().st_size, "lines": len(p.read_bytes().splitlines())} for p in paths}
    return {"protocol": design["protocol"], "scope": design["scope"], "policies": policies,
            "rows": rows, "source_manifest": sources, "limitations": design["limits"],
            "footprint_interpretation": "Static setup sizes, not measured maintenance effort. Both coded versions coexist.",
            "paid_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
