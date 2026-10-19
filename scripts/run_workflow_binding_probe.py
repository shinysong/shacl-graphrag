"""Offline authored approval-binding probe; not a benchmark or truth checker.

Both arms trust supplied dependency coverage and version identifiers. Preflight and
invalidation are shared infrastructure, not SHACL benefits. No ontology inference.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from time import perf_counter

from pyshacl import validate
from rdflib import RDF, BNode, Graph, Literal, Namespace
from rdflib.namespace import SH

EX = Namespace("urn:workflow-binding:")
BINDINGS = ("target_id", "target_version", "rule_version")


def result(status, reasons, executed):
    return {
        "status": status,
        "reason_codes": sorted(set(reasons)),
        "checker_executed": executed,
    }


def preflight(packet):
    """Validate the normalized JSON boundary; missing/null evidence is unknown.

    Unknown takes precedence over denial if evidence is missing/incomplete.
    Extra fields are rejected; unrelated changes belong to the separate change map.
    """
    missing = False
    invalid = False

    def obj(value, fields):
        nonlocal missing, invalid
        if value is None:
            missing = True
            return {}
        if not isinstance(value, dict):
            invalid = True
            return {}
        missing |= bool(set(fields) - value.keys())
        invalid |= bool(value.keys() - set(fields))
        return value

    def string(value):
        nonlocal missing, invalid
        if value is None:
            missing = True
        elif not isinstance(value, str) or not value.strip():
            invalid = True

    p = obj(packet, ("request", "approval", "dependencies", "approved", "complete"))
    for key in ("request", "approval"):
        binding = obj(p.get(key), BINDINGS)
        for field in BINDINGS:
            string(binding.get(field))
    deps = p.get("dependencies")
    if deps is None:
        missing = True
    elif not isinstance(deps, list):
        invalid = True
    else:
        for dep in deps:
            d = obj(dep, ("id", "approved_version", "current_version"))
            for field in ("id", "approved_version", "current_version"):
                string(d.get(field))
    for key in ("approved", "complete"):
        if p.get(key) is None:
            missing = True
        elif type(p[key]) is not bool:
            invalid = True
    reasons = []
    if invalid:
        reasons.append("schema_error")
    if missing:
        reasons.append("missing_evidence")
    if p.get("complete") is False:
        reasons.append("incomplete_evidence")
    return result("unknown", reasons, False) if reasons else None


def check_python(packet):
    early = preflight(packet)
    if early:
        return early
    reasons = []
    for field in BINDINGS:
        if packet["request"][field] != packet["approval"][field]:
            reasons.append(field + "_mismatch")
    if not packet["approved"]:
        reasons.append("approval_not_granted")
    versions = {}
    for dep in packet["dependencies"]:
        if dep["approved_version"] != dep["current_version"]:
            reasons.append("dependency_version_mismatch")
        pair = (dep["approved_version"], dep["current_version"])
        if dep["id"] in versions and versions[dep["id"]] != pair:
            reasons.append("conflicting_dependency_records")
        versions[dep["id"]] = pair
    return result(
        "deny" if reasons else "allow", reasons or ["contract_satisfied"], True
    )


def shapes_graph():
    """Actual SHACL constraints, independently evaluated against RDF evidence."""
    g = Graph()
    g.bind("ex", EX)
    g.bind("sh", SH)
    g.add((EX.ApprovalShape, RDF.type, SH.NodeShape))
    g.add((EX.ApprovalShape, SH.targetClass, EX.ApprovalEvidence))
    for field in BINDINGS:
        shape = EX[field + "Constraint"]
        g.add((EX.ApprovalShape, SH.property, shape))
        g.add((shape, SH.path, EX["request_" + field]))
        g.add((shape, SH.equals, EX["approval_" + field]))
        g.add((shape, SH.message, Literal(field + "_mismatch")))
    g.add((EX.ApprovalShape, SH.property, EX.ApprovedConstraint))
    g.add((EX.ApprovedConstraint, SH.path, EX.approved))
    g.add((EX.ApprovedConstraint, SH.hasValue, Literal(True)))
    g.add((EX.ApprovedConstraint, SH.message, Literal("approval_not_granted")))
    g.add((EX.DependencyShape, RDF.type, SH.NodeShape))
    g.add((EX.DependencyShape, SH.targetClass, EX.Dependency))
    g.add((EX.DependencyShape, SH.property, EX.VersionConstraint))
    g.add((EX.VersionConstraint, SH.path, EX.approved_version))
    g.add((EX.VersionConstraint, SH.equals, EX.current_version))
    g.add((EX.VersionConstraint, SH.message, Literal("dependency_version_mismatch")))
    g.add((EX.ApprovalShape, SH.sparql, EX.ConflictConstraint))
    g.add(
        (EX.ConflictConstraint, SH.message, Literal("conflicting_dependency_records"))
    )
    g.add(
        (
            EX.ConflictConstraint,
            SH.select,
            Literal("""
PREFIX ex: <urn:workflow-binding:>
SELECT $this WHERE {
  $this ex:dependency ?a, ?b .
  ?a ex:id ?id ; ex:approved_version ?av ; ex:current_version ?ac .
  ?b ex:id ?id ; ex:approved_version ?bv ; ex:current_version ?bc .
  FILTER (?av != ?bv || ?ac != ?bc)
}"""),
        )
    )
    return g


def evidence_graph(packet):
    g = Graph()
    root = EX.evidence
    g.add((root, RDF.type, EX.ApprovalEvidence))
    for key in ("request", "approval"):
        for field in BINDINGS:
            g.add((root, EX[key + "_" + field], Literal(packet[key][field])))
    g.add((root, EX.approved, Literal(packet["approved"])))
    g.add((root, EX.complete, Literal(packet["complete"])))
    for dep in packet["dependencies"]:
        node = BNode()  # Preserve duplicate records, including conflicting pairs.
        g.add((root, EX.dependency, node))
        g.add((node, RDF.type, EX.Dependency))
        for field, value in dep.items():
            g.add((node, EX[field], Literal(value)))
    return g


def check_shacl(packet):
    early = preflight(packet)
    if early:
        return early
    conforms, report, _ = validate(
        evidence_graph(packet),
        shacl_graph=shapes_graph(),
        inference="none",
        advanced=False,
        abort_on_first=False,
    )
    reasons = [str(message) for message in report.objects(None, SH.resultMessage)]
    if not conforms and not reasons:
        raise RuntimeError("SHACL violation without a reason code")
    return result(
        "allow" if conforms else "deny", reasons or ["contract_satisfied"], True
    )


def invalidation_set(declared_dependencies, changed_ids):
    """Shared explicit reverse-membership baseline; no inferred/transitive edges."""
    changed = set(changed_ids)
    return sorted(
        key for key, deps in declared_dependencies.items() if changed.intersection(deps)
    )


def authored_cases():
    base = {
        "request": {
            "target_id": "product-A",
            "target_version": "v1",
            "rule_version": "r1",
        },
        "approval": {
            "target_id": "product-A",
            "target_version": "v1",
            "rule_version": "r1",
        },
        "dependencies": [
            {"id": "part-A", "approved_version": "v1", "current_version": "v1"}
        ],
        "approved": True,
        "complete": True,
    }
    cases = []

    def add(name, expected, modify=lambda p: None, changed=()):
        p = deepcopy(base)
        modify(p)
        cases.append(
            {
                "name": name,
                "input": p,
                "expected_status": expected,
                "changed_ids": list(changed),
            }
        )

    add("valid", "allow")
    for field in BINDINGS:
        add(
            field + "_mismatch",
            "deny",
            lambda p, f=field: p["approval"].update({f: "other"}),
        )
    add(
        "dependency_change",
        "deny",
        lambda p: p["dependencies"][0].update(current_version="v2"),
        ("part-A",),
    )
    add("unrelated_change", "allow", changed=("unrelated-part",))
    add("missing_data", "unknown", lambda p: p["approval"].pop("target_version"))
    add("revoked_approval", "deny", lambda p: p.update(approved=False))
    add(
        "multiple_dependency_mismatch",
        "deny",
        lambda p: p.update(
            dependencies=[
                {"id": x, "approved_version": "v1", "current_version": "v2"}
                for x in ("part-A", "part-B")
            ]
        ),
    )
    add(
        "duplicate_identical_dependencies",
        "allow",
        lambda p: p["dependencies"].append(deepcopy(p["dependencies"][0])),
    )
    add(
        "conflicting_duplicate_dependencies",
        "deny",
        lambda p: p["dependencies"].append(
            {"id": "part-A", "approved_version": "v2", "current_version": "v2"}
        ),
    )
    add(
        "explicit_complete_empty_dependencies",
        "allow",
        lambda p: p.update(dependencies=[]),
    )
    return cases


def run_probe():
    rows = []
    for case in authored_cases():
        for arm, checker in (
            ("python_json", check_python),
            ("rdflib_pyshacl", check_shacl),
        ):
            start = perf_counter()
            outcome = checker(case["input"])  # Expectations never enter either checker.
            elapsed = perf_counter() - start
            rows.append(
                {
                    "case": case["name"],
                    "arm": arm,
                    **outcome,
                    "elapsed_seconds": elapsed,
                    "expected_status": case["expected_status"],
                    "status_agrees": outcome["status"] == case["expected_status"],
                }
            )
    return {
        "protocol": "workflow-binding-probe-1",
        "scope": "12 authored synthetic feasibility cases; 24 checks; not a benchmark",
        "timing_scope": "single in-process calls including preflight, graph construction and validation; descriptive only",
        "limitations": [
            "Supplied normalized identities, versions and completeness are trusted.",
            "No hidden-omission detection, external truth, natural-language interpretation, database, LLM or ontology inference.",
            "Shared preflight and declared-dependency invalidation are baseline infrastructure.",
        ],
        "cases": authored_cases(),
        "rows": rows,
        "invalidation_examples": {
            "declared_dependencies": {
                "approval-A": ["part-A"],
                "approval-B": ["part-B"],
            },
            "part_A_changed": invalidation_set(
                {"approval-A": ["part-A"], "approval-B": ["part-B"]}, ["part-A"]
            ),
            "unrelated_changed": invalidation_set(
                {"approval-A": ["part-A"]}, ["unrelated-part"]
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSON exclusively to a new explicit path; otherwise print JSON",
    )
    args = parser.parse_args()
    output = run_probe()
    serialized = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(serialized)
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
