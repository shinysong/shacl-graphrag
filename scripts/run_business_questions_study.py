#!/usr/bin/env python3
"""Bounded synthetic business workflows; no external factual validation or model calls."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import time
from pathlib import Path

from rdflib import RDF, Graph, Literal, Namespace

PROTOCOL = "business-questions-1"
ARMS = ("raw_lookup", "typed_json", "typed_rdf")
ASOF = "2026-10-12"
KINDS = {
    "M1": ("bom",),
    "M2": ("candidate",),
    "M3": ("change", "dependency"),
    "F1": ("relationship", "exception"),
    "F2": ("relationship", "exception"),
    "F3": ("entity", "relationship", "exception"),
}
NS = Namespace("urn:business-questions:")


def answer(status, value=None, ids=()):
    return {"status": status, "value": value, "evidence_ids": sorted(set(ids))}


def current(r, asof):
    return (
        r.get("status") == "ACTIVE"
        and r.get("start", "9999") <= asof <= r.get("end", "")
        and (
            r["kind"] not in ("relationship", "exception")
            or r.get("snapshot_date") == asof
        )
        and (r["kind"] != "relationship" or r.get("registration_status") == "PUBLISHED")
    )


def select_json(packet):
    return [
        {k: v for k, v in r.items() if v is not None}
        for r in packet["observed_records"]
        if r["kind"] in KINDS[packet["task"]]
    ]


def select_rdf(packet):
    """Actual SPARQL selection by typed record kind, retaining every literal field."""
    graph = Graph()
    for r in packet["observed_records"]:
        subject = NS["record/" + r["id"]]
        graph.add((subject, RDF.type, NS[r["kind"]]))
        for key, value in r.items():
            if value is not None:
                graph.add((subject, NS[key], Literal(value)))
    types = " ".join("<" + str(NS[k]) + ">" for k in KINDS[packet["task"]])
    query = f"SELECT ?s ?p ?v WHERE {{ VALUES ?kind {{ {types} }} ?s a ?kind ; ?p ?v . FILTER(isLiteral(?v)) }}"
    records = {}
    for subject, predicate, value in graph.query(query):
        records.setdefault(str(subject), {})[str(predicate)[len(str(NS)) :]] = (
            value.toPython()
        )
    return sorted(records.values(), key=lambda r: r["id"])


def decide(packet, records):
    task, policy, asof = packet["task"], packet["internal_policy"], packet["asof"]
    if task == "M1":
        if not policy.get("complete_bom"):
            return answer("unknown")
        directions = packet["published_schema"].get("bom_relations", {})
        edges, invalid = [], []
        for r in records:
            if not current(r, asof):
                continue
            direction = directions.get(r.get("relation"))
            if direction not in ("parent_child", "child_parent"):
                invalid.append(r["id"])
                continue
            parent, child = r["subject"], r["object"]
            if direction == "child_parent":
                parent, child = child, parent
            edges.append((parent, child, r))
        if invalid:
            return answer("unknown", ids=invalid)
        seen, ids = {policy["part"]}, set()
        while True:
            old = len(seen)
            for parent, child, r in edges:
                if child in seen:
                    seen.add(parent)
                    ids.add(r["id"])
            if len(seen) == old:
                break
        products = sorted(set(policy["products"]) & seen)
        # Conflicting explicit positive/negative inclusion records are not repaired.
        for parent, child, r in edges:
            if child in seen and r.get("included") is False:
                return answer("conflict", ids=ids)
        return answer("known", products, ids)
    if task == "M2":
        rows = [
            r
            for r in records
            if r.get("candidate") == policy["candidate"] and current(r, asof)
        ]
        if not rows:
            return answer("unknown")
        if (
            len(
                {
                    (
                        r.get("tolerance"),
                        r.get("unit"),
                        r.get("certificate"),
                        r.get("compatibility"),
                    )
                    for r in rows
                }
            )
            > 1
        ):
            return answer("conflict", ids=[r["id"] for r in rows])
        r = rows[0]
        factors = {"mm": 1.0, "um": 0.001}
        if r.get("unit") not in factors or any(
            r.get(k) is None for k in ("tolerance", "certificate", "compatibility")
        ):
            return answer("unknown", ids=[r["id"]])
        ok = (
            r["tolerance"] * factors[r["unit"]] <= policy["max_tolerance_mm"]
            and r["certificate"] in policy["approved_certificates"]
            and r["compatibility"] == policy["compatibility"]
        )
        return answer("eligible" if ok else "blocked", ids=[r["id"] for r in rows])
    if task == "M3":
        if not policy.get("complete_dependencies"):
            return answer("unknown")
        changes = [r for r in records if r["kind"] == "change" and current(r, asof)]
        deps = [r for r in records if r["kind"] == "dependency" and current(r, asof)]
        if any(r.get("field") not in policy["known_fields"] for r in changes):
            return answer("unknown", ids=[r["id"] for r in changes])
        items, ids = set(), set()
        for change in changes:
            relevant = [r for r in deps if r["field"] == change["field"]]
            for dep in relevant:
                if dep.get("required") is True:
                    items.add(dep["workitem"])
                    ids.update((change["id"], dep["id"]))
                    if any(
                        other["workitem"] == dep["workitem"]
                        and other.get("required") is False
                        for other in relevant
                    ):
                        return answer(
                            "conflict", ids=[change["id"]] + [r["id"] for r in relevant]
                        )
        return answer("known", sorted(items), ids)
    if task in ("F1", "F2"):
        role = "DIRECT_ACCOUNTING" if task == "F1" else "ULTIMATE_ACCOUNTING"
        subjects = [policy["entity"]] if task == "F1" else policy["entities"]
        parents, ids = [], []
        for entity in subjects:
            rows = [
                r
                for r in records
                if r["kind"] == "relationship"
                and r.get("subject") == entity
                and r.get("relation") == role
                and current(r, asof)
            ]
            exceptions = [
                r
                for r in records
                if r["kind"] == "exception"
                and r.get("subject") == entity
                and r.get("relation") == role
                and current(r, asof)
            ]
            if rows and exceptions:
                return answer("conflict", ids=[r["id"] for r in rows + exceptions])
            values = sorted({r["object"] for r in rows})
            ids.extend(r["id"] for r in rows)
            if len(values) > 1:
                return answer("conflict", ids=ids)
            if not values:
                exceptions = [
                    r
                    for r in records
                    if r["kind"] == "exception"
                    and r.get("subject") == entity
                    and r.get("relation") == role
                    and current(r, asof)
                ]
                return answer(
                    "reported_exception" if exceptions else "unknown",
                    ids=[r["id"] for r in exceptions],
                )
            parents.append(values[0])
        return answer(
            "known", parents[0] if task == "F1" else parents[0] == parents[1], ids
        )
    if task == "F3":
        entities = [
            r
            for r in records
            if r["kind"] == "entity" and r.get("entity") == policy["entity"]
        ]
        if not entities:
            return answer("incomplete")
        ids = [r["id"] for r in entities]
        if (
            len(
                {
                    (r.get("legal_status"), r.get("registration_status"))
                    for r in entities
                }
            )
            > 1
        ):
            return answer("review_required", ids=ids)
        e = entities[0]
        if e.get("snapshot_date") != asof:
            return answer("incomplete", ids=ids)
        if e.get("legal_status") is None or e.get("registration_status") is None:
            return answer("incomplete", ids=ids)
        if e["legal_status"] != "ACTIVE" or e["registration_status"] != "ISSUED":
            return answer("review_required", ids=ids)
        rels = [
            r
            for r in records
            if r["kind"] == "relationship"
            and r.get("subject") == policy["entity"]
            and r.get("relation") == "DIRECT_ACCOUNTING"
            and current(r, asof)
        ]
        if not rels:
            exceptions = [
                r
                for r in records
                if r["kind"] == "exception"
                and r.get("subject") == policy["entity"]
                and r.get("relation") == "DIRECT_ACCOUNTING"
                and current(r, asof)
            ]
            return answer("incomplete", ids=ids + [r["id"] for r in exceptions])
        exceptions = [
            r
            for r in records
            if r["kind"] == "exception"
            and r.get("subject") == policy["entity"]
            and r.get("relation") == "DIRECT_ACCOUNTING"
            and current(r, asof)
        ]
        return answer(
            "review_required"
            if len({r["object"] for r in rels}) > 1 or exceptions
            else "review_ready",
            ids=ids + [r["id"] for r in rels + exceptions],
        )
    raise ValueError(task)


def raw_lookup(packet):
    """Deliberately weak ablation: literal lookup without time/role/unit/dependency guards."""
    records, task, p = (
        packet["observed_records"],
        packet["task"],
        packet["internal_policy"],
    )
    if task == "M1":
        rows = [r for r in records if r.get("object") == p["part"]]
        return answer(
            "known", sorted({r["subject"] for r in rows}), [r["id"] for r in rows]
        )
    if task == "M2":
        rows = [r for r in records if r.get("candidate") == p["candidate"]]
        if not rows:
            return answer("unknown")
        r = rows[0]
        return answer(
            "eligible"
            if r.get("tolerance", 999) <= p["max_tolerance_mm"]
            else "blocked",
            ids=[r["id"]],
        )
    if task == "M3":
        rows = [r for r in records if r["kind"] == "dependency"]
        return answer(
            "known", sorted({r["workitem"] for r in rows}), [r["id"] for r in rows]
        )
    if task in ("F1", "F2"):
        subjects = [p["entity"]] if task == "F1" else p["entities"]
        rows = [
            next((r for r in records if r.get("subject") == s and "object" in r), None)
            for s in subjects
        ]
        if any(r is None for r in rows):
            return answer("unknown")
        return answer(
            "known",
            rows[0]["object"]
            if task == "F1"
            else rows[0]["object"] == rows[1]["object"],
            [r["id"] for r in rows],
        )
    rows = [r for r in records if r["kind"] == "entity"]
    return answer(
        "review_ready"
        if rows and rows[0].get("legal_status") == "ACTIVE"
        else "review_required",
        ids=[r["id"] for r in rows],
    )


def rec(id, kind, **fields):
    base = {
        "id": id,
        "kind": kind,
        "status": "ACTIVE",
        "start": "2026-01-01",
        "end": "2026-12-31",
    }
    if kind in ("relationship", "exception", "entity"):
        base["snapshot_date"] = ASOF
    if kind == "relationship":
        base["registration_status"] = "PUBLISHED"
    return base | fields


def make_cases():
    """Explicit expected outputs are fixture declarations, never runtime-derived labels."""
    cases = []

    def add(task, scenario, records, policy, expected, schema=None):
        packet = {
            "task": task,
            "question": QUESTIONS[task],
            "asof": ASOF,
            "observed_records": records,
            "published_schema": schema or {},
            "internal_policy": policy,
        }
        cases.append(
            {
                "case_id": f"{task}-{len([c for c in cases if c['packet']['task'] == task]) + 1}",
                "scenario": scenario,
                "packet": packet,
                "expected": expected,
            }
        )

    bom = lambda id, s, o, relation="contains", **kw: rec(
        id, "bom", subject=s, object=o, relation=relation, **kw
    )
    mp = {
        "part": "part-A",
        "products": ["product-X", "product-Y"],
        "complete_bom": True,
    }
    schema = {"bom_relations": {"contains": "parent_child", "part_of": "child_parent"}}
    add(
        "M1",
        "transitive_alias_success",
        [
            bom("b1", "part-A", "assembly", "part_of"),
            bom("b2", "product-X", "assembly"),
        ],
        mp,
        answer("known", ["product-X"], ["b1", "b2"]),
        schema,
    )
    add(
        "M1",
        "complete_negative",
        [bom("b1", "product-X", "part-B")],
        mp,
        answer("known", []),
        schema,
    )
    add(
        "M1",
        "missing_evidence",
        [],
        dict(mp, complete_bom=False),
        answer("unknown"),
        schema,
    )
    add(
        "M1",
        "conflicting_inclusion",
        [
            bom("b1", "product-X", "part-A", included=True),
            bom("b2", "product-X", "part-A", included=False),
        ],
        mp,
        answer("conflict", ids=["b1", "b2"]),
        schema,
    )
    retired = bom("b1", "product-X", "part-A")
    retired["status"] = "RETIRED"
    add("M1", "retired_edge", [retired], mp, answer("known", []), schema)
    add(
        "M1",
        "undeclared_relation",
        [bom("b1", "product-X", "part-A", "supplied_by")],
        mp,
        answer("unknown", ids=["b1"]),
        schema,
    )
    cp = {
        "candidate": "replacement-A",
        "max_tolerance_mm": 0.1,
        "approved_certificates": ["cert-A"],
        "compatibility": "interface-A",
    }
    candidate = lambda **kw: rec(
        "c1",
        "candidate",
        candidate="replacement-A",
        **{
            "tolerance": 50,
            "unit": "um",
            "certificate": "cert-A",
            "compatibility": "interface-A",
        }
        | kw,
    )
    add(
        "M2",
        "equivalent_unit_success",
        [candidate()],
        cp,
        answer("eligible", ids=["c1"]),
    )
    add(
        "M2",
        "explicit_policy_failure",
        [candidate(certificate="cert-B")],
        cp,
        answer("blocked", ids=["c1"]),
    )
    add(
        "M2",
        "missing_certificate",
        [candidate(certificate=None)],
        cp,
        answer("unknown", ids=["c1"]),
    )
    c2 = candidate(tolerance=200)
    c2["id"] = "c2"
    add(
        "M2",
        "conflicting_measurement",
        [candidate(), c2],
        cp,
        answer("conflict", ids=["c1", "c2"]),
    )
    c = candidate()
    c["end"] = "2025-12-31"
    add("M2", "expired_certificate_record", [c], cp, answer("unknown"))
    add(
        "M2",
        "undeclared_unit",
        [candidate(unit="mil")],
        cp,
        answer("unknown", ids=["c1"]),
    )
    dp = {
        "complete_dependencies": True,
        "known_fields": [
            "spec.tolerance",
            "certificate.validity",
            "bom.member",
            "display.color",
        ],
    }
    deps = [
        rec(
            "d1",
            "dependency",
            field="spec.tolerance",
            workitem="fit-review",
            required=True,
        ),
        rec(
            "d2",
            "dependency",
            field="certificate.validity",
            workitem="certificate-review",
            required=True,
        ),
        rec(
            "d3",
            "dependency",
            field="bom.member",
            workitem="assembly-review",
            required=True,
        ),
    ]
    ch = lambda field: rec("h1", "change", field=field)
    add(
        "M3",
        "dependency_scoped_success",
        [ch("spec.tolerance")] + deps,
        dp,
        answer("known", ["fit-review"], ["h1", "d1"]),
    )
    add(
        "M3", "irrelevant_change", [ch("display.color")] + deps, dp, answer("known", [])
    )
    add(
        "M3",
        "missing_dependency_declaration",
        [ch("bom.member")],
        dict(dp, complete_dependencies=False),
        answer("unknown"),
    )
    d4 = rec(
        "d4",
        "dependency",
        field="certificate.validity",
        workitem="certificate-review",
        required=False,
    )
    add(
        "M3",
        "conflicting_dependencies",
        [ch("certificate.validity")] + deps + [d4],
        dp,
        answer("conflict", ids=["h1", "d2", "d4"]),
    )
    h = ch("bom.member")
    h["status"] = "RETIRED"
    add("M3", "retired_change", [h] + deps, dp, answer("known", []))
    add(
        "M3",
        "unmapped_field",
        [ch("certificate.expiry_alias")] + deps,
        dp,
        answer("unknown", ids=["h1"]),
    )
    rel = lambda id, s, o, role="DIRECT_ACCOUNTING": rec(
        id, "relationship", subject=s, object=o, relation=role
    )
    fp = {"entity": "LEI-A"}
    add(
        "F1",
        "direct_parent",
        [rel("r1", "LEI-A", "LEI-P")],
        fp,
        answer("known", "LEI-P", ["r1"]),
    )
    ex = rec(
        "x1",
        "exception",
        subject="LEI-A",
        relation="DIRECT_ACCOUNTING",
        reason="NATURAL_PERSONS",
    )
    add("F1", "reported_exception", [ex], fp, answer("reported_exception", ids=["x1"]))
    add("F1", "missing_parent", [], fp, answer("unknown"))
    add(
        "F1",
        "conflicting_parents",
        [rel("r1", "LEI-A", "LEI-P"), rel("r2", "LEI-A", "LEI-Q")],
        fp,
        answer("conflict", ids=["r1", "r2"]),
    )
    old = rel("r1", "LEI-A", "LEI-P")
    old["end"] = "2026-10-11"
    add("F1", "expired_parent", [old], fp, answer("unknown"))
    add(
        "F1",
        "fund_manager_role",
        [rel("r1", "LEI-A", "LEI-P", "FUND_MANAGER")],
        fp,
        answer("unknown"),
    )
    gp = {"entities": ["LEI-A", "LEI-B"]}
    ult = lambda id, s, o: rel(id, s, o, "ULTIMATE_ACCOUNTING")
    add(
        "F2",
        "same_group",
        [ult("r1", "LEI-A", "LEI-P"), ult("r2", "LEI-B", "LEI-P")],
        gp,
        answer("known", True, ["r1", "r2"]),
    )
    add(
        "F2",
        "different_explicit_groups",
        [ult("r1", "LEI-A", "LEI-P"), ult("r2", "LEI-B", "LEI-Q")],
        gp,
        answer("known", False, ["r1", "r2"]),
    )
    add(
        "F2",
        "missing_second_parent",
        [ult("r1", "LEI-A", "LEI-P")],
        gp,
        answer("unknown"),
    )
    add(
        "F2",
        "conflicting_ultimate",
        [
            ult("r1", "LEI-A", "LEI-P"),
            ult("r2", "LEI-A", "LEI-Q"),
            ult("r3", "LEI-B", "LEI-P"),
        ],
        gp,
        answer("conflict", ids=["r1", "r2"]),
    )
    old = ult("r2", "LEI-B", "LEI-P")
    old["end"] = "2026-10-11"
    add(
        "F2",
        "expired_second_parent",
        [ult("r1", "LEI-A", "LEI-P"), old],
        gp,
        answer("unknown"),
    )
    add(
        "F2",
        "shared_fund_manager",
        [
            rel("r1", "LEI-A", "LEI-P", "FUND_MANAGER"),
            rel("r2", "LEI-B", "LEI-P", "FUND_MANAGER"),
        ],
        gp,
        answer("unknown"),
    )
    entity = lambda **kw: rec(
        "e1",
        "entity",
        entity="LEI-A",
        **({"legal_status": "ACTIVE", "registration_status": "ISSUED"} | kw),
    )
    add(
        "F3",
        "complete_internal_review",
        [entity(), rel("r1", "LEI-A", "LEI-P")],
        fp,
        answer("review_ready", ids=["e1", "r1"]),
    )
    add(
        "F3",
        "lapsed_registration",
        [entity(registration_status="LAPSED"), rel("r1", "LEI-A", "LEI-P")],
        fp,
        answer("review_required", ids=["e1"]),
    )
    add(
        "F3",
        "exception_without_parent",
        [entity(), ex],
        fp,
        answer("incomplete", ids=["e1", "x1"]),
    )
    add(
        "F3",
        "conflicting_reports",
        [entity(), rel("r1", "LEI-A", "LEI-P"), rel("r2", "LEI-A", "LEI-Q")],
        fp,
        answer("review_required", ids=["e1", "r1", "r2"]),
    )
    old = rel("r1", "LEI-A", "LEI-P")
    old["end"] = "2026-10-11"
    add(
        "F3",
        "stale_relationship",
        [entity(), old],
        fp,
        answer("incomplete", ids=["e1"]),
    )
    add(
        "F3",
        "status_namespace_swap",
        [
            entity(legal_status="ISSUED", registration_status="ACTIVE"),
            rel("r1", "LEI-A", "LEI-P"),
        ],
        fp,
        answer("review_required", ids=["e1"]),
    )
    return cases


QUESTIONS = {
    "M1": "Which listed products are potentially affected by the declared part change?",
    "M2": "Is the replacement eligible under the declared tolerance, certificate and compatibility policy?",
    "M3": "Which declared work items require revalidation after the recorded field change?",
    "F1": "What is the reported direct accounting parent at the reference date?",
    "F2": "Do both entities report the same explicit ultimate accounting parent?",
    "F3": "Is relationship evidence ready under the declared internal review rule?",
}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def run(output, timeout_seconds=300):
    start = time.monotonic()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "protocol": PROTOCOL,
        "status": "running",
        "planned_cases": 36,
        "planned_rows": 108,
        "synthetic_only": True,
        "arms": ARMS,
        "timeout_seconds": timeout_seconds,
    }
    write_json(output / "manifest.json", manifest)
    try:
        source = output / "source"
        source.mkdir()
        for path in (
            Path(__file__),
            Path(__file__).parents[1] / "tests/test_business_questions_study.py",
        ):
            if path.exists():
                shutil.copy2(path, source / path.name)
        cases = make_cases()
        assert len(cases) == 36 and all(
            sum(c["packet"]["task"] == task for c in cases) == 6 for task in KINDS
        )
        write_json(output / "cases.json", cases)
        write_json(
            output / "runtime_packets.json",
            [{"case_id": c["case_id"], "packet": c["packet"]} for c in cases],
        )
        count = 0
        with (output / "rows.jsonl").open("x") as sink:
            for case in cases:
                for arm in ARMS:
                    if time.monotonic() - start > timeout_seconds:
                        raise TimeoutError("Internal wall-clock budget exhausted")
                    packet = copy.deepcopy(case["packet"])
                    row = {
                        "case_id": case["case_id"],
                        "task": packet["task"],
                        "arm": arm,
                    }
                    try:
                        result = (
                            raw_lookup(packet)
                            if arm == "raw_lookup"
                            else decide(
                                packet,
                                select_json(packet)
                                if arm == "typed_json"
                                else select_rdf(packet),
                            )
                        )
                        expected = case["expected"]
                        row.update(
                            answer=result,
                            decision_correct=(result["status"], result["value"])
                            == (expected["status"], expected["value"]),
                            evidence_correct=result["evidence_ids"]
                            == expected["evidence_ids"],
                        )
                    except Exception as exc:  # noqa: BLE001 - preserve individual failed attempts
                        row.update(error_type=type(exc).__name__, error=str(exc))
                    sink.write(json.dumps(row) + "\n")
                    sink.flush()
                    count += 1
        manifest.update(status="completed", completed_rows=count)
    except BaseException as exc:
        manifest.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        manifest["elapsed_seconds"] = time.monotonic() - start
        manifest["sha256"] = {
            str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.rglob("*"))
            if p.is_file() and p.name != "manifest.json"
        }
        write_json(output / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300)
    args = parser.parse_args()
    if not 0 < args.timeout_seconds <= 300:
        parser.error("timeout must be positive and at most 300 seconds")
    print(json.dumps(run(args.output, args.timeout_seconds), indent=2))
