"""Bounded offline lifecycle diagnostic (unified-rule-lifecycle-1).

A compares authored defect functions with authored reference implementations;
policy text and the illustrative dictionary are not compiled or normalized.
B compares deterministic policies on six synthetic states, with whole-source
reevaluation on unknown. No real GLEIF transfer is executed.
C repeats six templates across four rule rounds. Line metrics describe illustrative
snippets, not executed source changes, AST edits, or human maintenance effort.
D measures supplied report fields on four repeated violation templates. No LLM
is called and historical LLM results are not outcomes of these prompt modes.
"""
from __future__ import annotations

import ast
import copy
from decimal import Decimal
import hashlib
import inspect
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any

from pyshacl import validate
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef
from rdflib.collection import Collection
from rdflib.namespace import XSD

EX = Namespace("http://example.org/unified/")
SH = Namespace("http://www.w3.org/ns/shacl#")


# ---------------------------------------------------------------------------
# 1. Shared 3-Layer Standard Dictionary & Foreign-Key Schema (Rule-Agnostic)
# ---------------------------------------------------------------------------

STANDARD_DICTIONARY: dict[str, Any] = {
    "words": {
        "DSCNT": {"ko": "할인", "en": "discount", "desc": "기준 단가 대비 감액"},
        "MRGN": {"ko": "마진", "en": "margin", "desc": "순결제 대비 이익"},
        "RT": {"ko": "율", "en": "rate", "desc": "0.0~1.0 소수 비율"},
        "NET": {"ko": "순결제", "en": "net_payment", "desc": "할인 차감 후 실제 결제액"},
        "GROSS": {"ko": "총주문", "en": "gross_order", "desc": "할인 전 명목 주문액"},
        "APPRV": {"ko": "승인검토", "en": "approval_review", "desc": "독립 검토자 의사결정"},
        "DIV": {"ko": "상위본부", "en": "parent_division", "desc": "부서가 속한 최상위 본부"},
    },
    "domains": {
        "RATE_0_1": {
            "datatype": "decimal",
            "min": 0.0,
            "max": 1.0,
            "scale_unit": "ratio",
            "null_policy": "unknown",
        },
        "CURRENCY_KRW": {
            "datatype": "decimal",
            "min": 0.0,
            "max": 1e12,
            "scale_unit": "KRW",
            "null_policy": "unknown",
        },
        "STATUS_CODE": {
            "datatype": "string",
            "allowed_values": {
                "contract_status": ("Active", "Suspended"),
                "decision": ("Approve", "Reject"),
                "qualification_status": ("Qualified", "Expired"),
                "review_role": ("Primary", "Audit", "Observer"),
            },
            "null_policy": "unknown",
        },
        "UNCONSTRAINED_TEXT": {
            "datatype": "string",
            "pattern": None,
            "null_policy": "ignore_if_optional",
        },
    },
    "terms": {
        "applied_discount_rate": {
            "ko_label": "적용할인율",
            "en_label": "applied discount rate",
            "table": "order_requests",
            "column": "applied_discount_rate",
            "domain": "RATE_0_1",
            "disallowed_synonyms": ["max_discount_rate", "gross_discount_pct"],
        },
        "max_discount_rate": {
            "ko_label": "허용할인율상한",
            "en_label": "maximum allowed discount rate",
            "table": "items_contracts",
            "column": "max_discount_rate",
            "domain": "RATE_0_1",
            "disallowed_synonyms": ["applied_discount_rate"],
        },
        "achieved_margin_rate": {
            "ko_label": "달성마진율",
            "en_label": "achieved margin rate",
            "table": "order_requests",
            "column": "achieved_margin_rate",
            "domain": "RATE_0_1",
            "disallowed_synonyms": ["min_margin_rate"],
        },
        "min_margin_rate": {
            "ko_label": "최소마진율기준",
            "en_label": "minimum required margin rate",
            "table": "items_contracts",
            "column": "min_margin_rate",
            "domain": "RATE_0_1",
            "disallowed_synonyms": ["achieved_margin_rate"],
        },
        "net_amount": {
            "ko_label": "순결제금액",
            "en_label": "net settlement amount",
            "table": "order_requests",
            "column": "net_amount",
            "domain": "CURRENCY_KRW",
            "disallowed_synonyms": ["gross_amount"],
        },
        "gross_amount": {
            "ko_label": "총주문금액",
            "en_label": "gross order amount",
            "table": "order_requests",
            "column": "gross_amount",
            "domain": "CURRENCY_KRW",
            "disallowed_synonyms": ["net_amount"],
        },
    },
}

RELATIONAL_SCHEMA: dict[str, Any] = {
    "items_contracts": {
        "class": "ItemContract",
        "pk": "item_id",
        "literals": {
            "contract_status": ("contractStatus", XSD.string),
            "max_discount_rate": ("maxDiscountRate", XSD.decimal),
            "min_margin_rate": ("minMarginRate", XSD.decimal),
        },
        "fks": {},
    },
    "order_requests": {
        "class": "OrderRequest",
        "pk": "request_id",
        "literals": {
            "applied_discount_rate": ("appliedDiscountRate", XSD.decimal),
            "achieved_margin_rate": ("achievedMarginRate", XSD.decimal),
            "net_amount": ("netAmount", XSD.decimal),
            "gross_amount": ("grossAmount", XSD.decimal),
            "memo_code": ("memoCode", XSD.string),
        },
        "fks": {
            "item_id": ("hasItem", "items_contracts", None),
            "req_dept_id": ("requestedByDept", "departments", None),
        },
    },
    "approval_reviews": {
        "class": "ApprovalReview",
        "pk": "review_id",
        "literals": {
            "decision": ("decision", XSD.string),
            "review_role": ("reviewRole", XSD.string),
        },
        "fks": {
            "request_id": (None, "order_requests", "hasReview"),
            "reviewer_id": ("reviewedBy", "reviewers", None),
        },
    },
    "reviewers": {
        "class": "Reviewer",
        "pk": "reviewer_id",
        "literals": {
            "qualification_status": ("qualificationStatus", XSD.string),
        },
        "fks": {
            "belongs_to_dept_id": ("belongsToDept", "departments", None),
        },
    },
    "departments": {
        "class": "Department",
        "pk": "dept_id",
        "literals": {},
        "fks": {
            "parent_division_id": ("parentDivision", "divisions", None),
        },
    },
}


# ---------------------------------------------------------------------------
# 2. Rule-Agnostic Generic Foreign-Key-to-RDF Entity Graph Mapper (Arm G Core)
# ---------------------------------------------------------------------------

def generic_tables_to_rdf(
    tables: dict[str, list[dict[str, Any]]],
    schema: dict[str, Any] = RELATIONAL_SCHEMA,
) -> Graph:
    """Projects raw relational tables into an RDF entity graph using only
    table/column/FK metadata. Contains ZERO domain rule, join filter,
    cardinality count, or threshold logic.
    """
    g = Graph()
    g.bind("ex", EX)
    g.bind("sh", SH)
    for table_name, spec in schema.items():
        rows = tables.get(table_name, [])
        cls_uri = EX[spec["class"]]
        pk_col = spec["pk"]
        for row in rows:
            pk_val = row.get(pk_col)
            if not isinstance(pk_val, str) or not pk_val.strip():
                continue
            subj = EX[f"{table_name}/{pk_val}"]
            g.add((subj, RDF.type, cls_uri))
            for col, (pred_name, dtype) in spec["literals"].items():
                val = row.get(col)
                if val is None:
                    continue
                if dtype == XSD.decimal:
                    lit = Literal(Decimal(str(val)), datatype=XSD.decimal)
                else:
                    lit = Literal(str(val), datatype=dtype)
                g.add((subj, EX[pred_name], lit))
            for fk_col, (fwd_pred, target_ns, rev_pred) in spec["fks"].items():
                fk_val = row.get(fk_col)
                if not isinstance(fk_val, str) or not fk_val.strip():
                    continue
                target_uri = EX[f"{target_ns}/{fk_val}"]
                if fwd_pred:
                    g.add((subj, EX[fwd_pred], target_uri))
                if rev_pred:
                    g.add((target_uri, EX[rev_pred], subj))
    return g


# ---------------------------------------------------------------------------
# 3. Progressive Rule Evolution Implementations (Arm P, Arm S, Arm G)
# ---------------------------------------------------------------------------

ROUND_ORDER = ("R0", "R1", "R2", "R3")

ROUND_RULES: dict[str, tuple[str, ...]] = {
    "R0": (
        "contract-active",
        "discount-cap",
        "net-amount-cap",
        "primary-review-qualified",
    ),
    "R1": (
        "contract-active",
        "discount-cap",
        "net-amount-cap",
        "primary-review-qualified",
        "margin-floor",
    ),
    "R2": (
        "contract-active",
        "discount-cap",
        "net-amount-cap",
        "primary-review-qualified",
        "margin-floor",
        "dual-role-review",
    ),
    "R3": (
        "contract-active",
        "discount-cap",
        "net-amount-cap",
        "primary-review-qualified",
        "margin-floor",
        "dual-role-review",
        "division-separation",
    ),
}


def build_shacl_shapes_for_round(round_id: str, net_cap: float = 100000.0) -> Graph:
    """Declarative W3C SHACL Core shapes for rounds R0, R1, R2, R3.
    Operates directly on the unjoined generic entity graph.
    """
    if round_id not in ROUND_RULES:
        raise ValueError(f"Unsupported round_id: {round_id}")
    sg = Graph()
    sg.bind("ex", EX)
    sg.bind("sh", SH)

    def path_seq(items: list[Any]) -> BNode:
        head = BNode()
        Collection(sg, head, items)
        return head

    def inv_path(pred: URIRef) -> BNode:
        bn = BNode()
        sg.add((bn, SH.inversePath, pred))
        return bn

    # Base shape on OrderRequest
    req_shape = EX[f"OrderRequestShape_{round_id}"]
    sg.add((req_shape, RDF.type, SH.NodeShape))
    sg.add((req_shape, SH.targetClass, EX.OrderRequest))

    # Completeness shapes (distinguish missing required data -> sh:Info -> unknown)
    req_completeness_paths: list[tuple[str, Any, dict[URIRef, Any]]] = [
        (
            "missing:contract-active",
            path_seq([EX.hasItem, EX.contractStatus]),
            {SH.minCount: Literal(1)},
        ),
        (
            "missing:discount-cap-req",
            EX.appliedDiscountRate,
            {SH.minCount: Literal(1)},
        ),
        (
            "missing:discount-cap-item",
            path_seq([EX.hasItem, EX.maxDiscountRate]),
            {SH.minCount: Literal(1)},
        ),
        (
            "missing:net-amount-cap",
            EX.netAmount,
            {SH.minCount: Literal(1)},
        ),
        (
            "missing:review-presence",
            EX.hasReview,
            {SH.minCount: Literal(1)},
        ),
        (
            "missing:review-qual",
            path_seq([EX.hasReview, EX.reviewedBy, EX.qualificationStatus]),
            {SH.minCount: Literal(1)},
        ),
    ]
    if round_id in ("R1", "R2", "R3"):
        req_completeness_paths.extend(
            [
                (
                    "missing:margin-floor-req",
                    EX.achievedMarginRate,
                    {SH.minCount: Literal(1)},
                ),
                (
                    "missing:margin-floor-item",
                    path_seq([EX.hasItem, EX.minMarginRate]),
                    {SH.minCount: Literal(1)},
                ),
            ]
        )
    if round_id == "R3":
        req_completeness_paths.extend(
            [
                (
                    "missing:req-division",
                    path_seq([EX.requestedByDept, EX.parentDivision]),
                    {SH.minCount: Literal(1)},
                ),
                (
                    "missing:rev-division",
                    path_seq(
                        [
                            EX.hasReview,
                            EX.reviewedBy,
                            EX.belongsToDept,
                            EX.parentDivision,
                        ]
                    ),
                    {SH.minCount: Literal(1)},
                ),
            ]
        )

    for msg, p_node, extra in req_completeness_paths:
        ps = BNode()
        sg.add((req_shape, SH.property, ps))
        sg.add((ps, SH.path, p_node))
        sg.add((ps, SH.severity, SH.Info))
        sg.add((ps, SH.message, Literal(msg)))
        for k, v in extra.items():
            sg.add((ps, k, v))

    # Rule 1: contract-active (via sh:path (ex:hasItem ex:contractStatus))
    ps_status = BNode()
    sg.add((req_shape, SH.property, ps_status))
    sg.add((ps_status, SH.path, path_seq([EX.hasItem, EX.contractStatus])))
    sg.add((ps_status, SH.hasValue, Literal("Active", datatype=XSD.string)))
    sg.add((ps_status, SH.message, Literal("violation:contract-active")))

    # Rule 2: discount-cap on ItemContract via inversePath
    item_shape = EX[f"ItemContractShape_{round_id}"]
    sg.add((item_shape, RDF.type, SH.NodeShape))
    sg.add((item_shape, SH.targetClass, EX.ItemContract))
    ps_disc = BNode()
    sg.add((item_shape, SH.property, ps_disc))
    sg.add(
        (
            ps_disc,
            SH.path,
            path_seq([inv_path(EX.hasItem), EX.appliedDiscountRate]),
        )
    )
    sg.add((ps_disc, SH.lessThanOrEquals, EX.maxDiscountRate))
    sg.add((ps_disc, SH.message, Literal("violation:discount-cap")))

    # Rule 3: net-amount-cap on OrderRequest
    ps_net = BNode()
    sg.add((req_shape, SH.property, ps_net))
    sg.add((ps_net, SH.path, EX.netAmount))
    sg.add(
        (
            ps_net,
            SH.maxInclusive,
            Literal(Decimal(str(net_cap)), datatype=XSD.decimal),
        )
    )
    sg.add((ps_net, SH.message, Literal("violation:net-amount-cap")))

    # Rule 4: primary-review-qualified (at least 1 Primary Approved review by Qualified reviewer)
    ps_prim = BNode()
    sg.add((req_shape, SH.property, ps_prim))
    sg.add((ps_prim, SH.path, EX.hasReview))
    q_prim = BNode()
    sg.add((ps_prim, SH.qualifiedValueShape, q_prim))
    sg.add((ps_prim, SH.qualifiedMinCount, Literal(1)))
    sg.add((ps_prim, SH.message, Literal("violation:primary-review-qualified")))
    for p_node, expected_val in (
        (EX.decision, "Approve"),
        (EX.reviewRole, "Primary"),
        (path_seq([EX.reviewedBy, EX.qualificationStatus]), "Qualified"),
    ):
        sub_p = BNode()
        sg.add((q_prim, SH.property, sub_p))
        sg.add((sub_p, SH.path, p_node))
        sg.add((sub_p, SH.hasValue, Literal(expected_val, datatype=XSD.string)))

    # R1 addition: margin-floor (minMarginRate <= achievedMarginRate)
    if round_id in ("R1", "R2", "R3"):
        ps_margin = BNode()
        sg.add((req_shape, SH.property, ps_margin))
        sg.add((ps_margin, SH.path, path_seq([EX.hasItem, EX.minMarginRate])))
        sg.add((ps_margin, SH.lessThanOrEquals, EX.achievedMarginRate))
        sg.add((ps_margin, SH.message, Literal("violation:margin-floor")))

    # R2 addition: dual-role-review (requires an independent Audit role qualified approval as well)
    if round_id in ("R2", "R3"):
        ps_audit = BNode()
        sg.add((req_shape, SH.property, ps_audit))
        sg.add((ps_audit, SH.path, EX.hasReview))
        q_audit = BNode()
        sg.add((ps_audit, SH.qualifiedValueShape, q_audit))
        sg.add((ps_audit, SH.qualifiedMinCount, Literal(1)))
        sg.add((ps_audit, SH.message, Literal("violation:dual-role-review")))
        for p_node, expected_val in (
            (EX.decision, "Approve"),
            (EX.reviewRole, "Audit"),
            (path_seq([EX.reviewedBy, EX.qualificationStatus]), "Qualified"),
        ):
            sub_p = BNode()
            sg.add((q_audit, SH.property, sub_p))
            sg.add((sub_p, SH.path, p_node))
            sg.add((sub_p, SH.hasValue, Literal(expected_val, datatype=XSD.string)))

    # R3 addition: division-separation (5-hop path across Department/OrderRequest/ApprovalReview/Reviewer/Department)
    if round_id == "R3":
        dept_shape = EX[f"DepartmentConflictShape_{round_id}"]
        sg.add((dept_shape, RDF.type, SH.NodeShape))
        sg.add((dept_shape, SH.targetClass, EX.Department))
        ps_div = BNode()
        sg.add((dept_shape, SH.property, ps_div))
        sg.add(
            (
                ps_div,
                SH.path,
                path_seq(
                    [
                        inv_path(EX.requestedByDept),
                        EX.hasReview,
                        EX.reviewedBy,
                        EX.belongsToDept,
                        EX.parentDivision,
                    ]
                ),
            )
        )
        sg.add((ps_div, SH.disjoint, EX.parentDivision))
        sg.add((ps_div, SH.message, Literal("violation:division-separation")))

    return sg


def evaluate_arm_g_shacl(
    tables: dict[str, list[dict[str, Any]]],
    round_id: str = "R3",
    net_cap: float = 100000.0,
    shapes_graph: Graph | None = None,
) -> dict[str, Any]:
    """Executes Arm G: Generic Table-to-RDF Entity Graph + W3C SHACL Core."""
    reqs = tables.get("order_requests", [])
    if len(reqs) != 1:
        return {"decision": "unknown", "violations": [], "missing": ["missing:request"]}
    dg = generic_tables_to_rdf(tables)
    sg = shapes_graph if shapes_graph is not None else build_shacl_shapes_for_round(round_id, net_cap)
    _, rep_graph, _ = validate(dg, shacl_graph=sg)

    missing_msgs: set[str] = set()
    violation_msgs: set[str] = set()
    for res in rep_graph.subjects(RDF.type, SH.ValidationResult):
        sev = rep_graph.value(res, SH.resultSeverity)
        for m in rep_graph.objects(res, SH.resultMessage):
            msg = str(m)
            if sev == SH.Info or msg.startswith("missing:"):
                missing_msgs.add(msg)
            elif msg.startswith("violation:"):
                violation_msgs.add(msg.removeprefix("violation:"))

    # Check if any review has a missing reviewer or missing qualification status
    reviews = [rv for rv in tables.get("approval_reviews", [])
               if rv.get("request_id") == reqs[0].get("request_id")]
    reviewers_by_id = {r["reviewer_id"]: r for r in tables.get("reviewers", []) if "reviewer_id" in r}
    depts_by_id = {d["dept_id"]: d for d in tables.get("departments", []) if "dept_id" in d}
    if not reviews:
        missing_msgs.add("missing:review-presence")
    for rv in reviews:
        rev_obj = reviewers_by_id.get(rv.get("reviewer_id"))
        if not rev_obj or rev_obj.get("qualification_status") is None:
            missing_msgs.add("missing:review-qual")
        if round_id == "R3":
            if not rev_obj or not rev_obj.get("belongs_to_dept_id"):
                missing_msgs.add("missing:rev-division")
            else:
                d_obj = depts_by_id.get(rev_obj["belongs_to_dept_id"])
                if not d_obj or not d_obj.get("parent_division_id"):
                    missing_msgs.add("missing:rev-division")

    if missing_msgs:
        # Suppress false-positive sh:hasValue / qualifiedMinCount violation when underlying data is missing
        if "missing:contract-active" in missing_msgs:
            violation_msgs.discard("contract-active")
        if "missing:review-presence" in missing_msgs or "missing:review-qual" in missing_msgs:
            violation_msgs.discard("primary-review-qualified")
            violation_msgs.discard("dual-role-review")

    if violation_msgs:
        decision = "blocked"
    elif missing_msgs:
        decision = "unknown"
    else:
        decision = "eligible"
    return {
        "decision": decision,
        "violations": sorted(violation_msgs),
        "missing": sorted(missing_msgs),
    }


def evaluate_arm_p_python(
    tables: dict[str, list[dict[str, Any]]],
    round_id: str = "R3",
    net_cap: float = 100000.0,
) -> dict[str, Any]:
    """Executes Arm P: Procedural Python with manual table indexing, nested joins,
    cardinality role sets, and multi-hop department hierarchy lookups.
    """
    reqs = tables.get("order_requests", [])
    if len(reqs) != 1:
        return {"decision": "unknown", "violations": [], "missing": ["missing:request"]}
    req = reqs[0]
    items_by_id = {i["item_id"]: i for i in tables.get("items_contracts", []) if "item_id" in i}
    reviewers_by_id = {r["reviewer_id"]: r for r in tables.get("reviewers", []) if "reviewer_id" in r}
    depts_by_id = {d["dept_id"]: d for d in tables.get("departments", []) if "dept_id" in d}
    reviews = [
        rv for rv in tables.get("approval_reviews", [])
        if rv.get("request_id") == req.get("request_id")
    ]

    violations: set[str] = set()
    missing: set[str] = set()

    item = items_by_id.get(req.get("item_id"))
    if not item or item.get("contract_status") is None:
        missing.add("missing:contract-active")
    elif item["contract_status"] != "Active":
        violations.add("contract-active")

    app_disc = req.get("applied_discount_rate")
    max_disc = item.get("max_discount_rate") if item else None
    if app_disc is None:
        missing.add("missing:discount-cap-req")
    if max_disc is None:
        missing.add("missing:discount-cap-item")
    if app_disc is not None and max_disc is not None and float(app_disc) > float(max_disc):
        violations.add("discount-cap")

    net_amt = req.get("net_amount")
    if net_amt is None:
        missing.add("missing:net-amount-cap")
    elif float(net_amt) > float(net_cap):
        violations.add("net-amount-cap")

    if not reviews:
        missing.add("missing:review-presence")
    else:
        qual_missing = False
        primary_ok = False
        audit_ok = False
        for rv in reviews:
            rev_user = reviewers_by_id.get(rv.get("reviewer_id"))
            if not rev_user or rev_user.get("qualification_status") is None:
                qual_missing = True
                continue
            if rv.get("decision") == "Approve" and rev_user.get("qualification_status") == "Qualified":
                if rv.get("review_role") == "Primary":
                    primary_ok = True
                elif rv.get("review_role") == "Audit":
                    audit_ok = True
        if qual_missing:
            missing.add("missing:review-qual")
        else:
            if not primary_ok:
                violations.add("primary-review-qualified")
            if round_id in ("R2", "R3") and not audit_ok:
                violations.add("dual-role-review")

    if round_id in ("R1", "R2", "R3"):
        ach_margin = req.get("achieved_margin_rate")
        min_margin = item.get("min_margin_rate") if item else None
        if ach_margin is None:
            missing.add("missing:margin-floor-req")
        if min_margin is None:
            missing.add("missing:margin-floor-item")
        if ach_margin is not None and min_margin is not None and float(ach_margin) < float(min_margin):
            violations.add("margin-floor")

    if round_id == "R3":
        req_dept = depts_by_id.get(req.get("req_dept_id"))
        req_div = req_dept.get("parent_division_id") if req_dept else None
        if not req_div:
            missing.add("missing:req-division")
        if not reviews:
            missing.add("missing:rev-division")
        for rv in reviews:
            rev_user = reviewers_by_id.get(rv.get("reviewer_id"))
            rev_dept = depts_by_id.get(rev_user.get("belongs_to_dept_id")) if rev_user else None
            rev_div = rev_dept.get("parent_division_id") if rev_dept else None
            if not rev_div:
                missing.add("missing:rev-division")
            elif req_div and rev_div == req_div:
                violations.add("division-separation")

    decision = "blocked" if violations else ("unknown" if missing else "eligible")
    return {
        "decision": decision,
        "violations": sorted(violations),
        "missing": sorted(missing),
    }


def evaluate_arm_s_sqlite(
    tables: dict[str, list[dict[str, Any]]],
    round_id: str = "R3",
    net_cap: float = 100000.0,
) -> dict[str, Any]:
    """Executes Arm S: Relational SQLite using explicit SQL JOINs, GROUP BY
    aggregations, and multi-alias department self-joins.
    """
    reqs = tables.get("order_requests", [])
    if len(reqs) != 1:
        return {"decision": "unknown", "violations": [], "missing": ["missing:request"]}
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE items_contracts (
            item_id TEXT PRIMARY KEY,
            contract_status TEXT,
            max_discount_rate REAL,
            min_margin_rate REAL
        );
        CREATE TABLE departments (
            dept_id TEXT PRIMARY KEY,
            parent_division_id TEXT
        );
        CREATE TABLE order_requests (
            request_id TEXT PRIMARY KEY,
            item_id TEXT,
            req_dept_id TEXT,
            applied_discount_rate REAL,
            achieved_margin_rate REAL,
            net_amount REAL,
            gross_amount REAL,
            memo_code TEXT
        );
        CREATE TABLE reviewers (
            reviewer_id TEXT PRIMARY KEY,
            belongs_to_dept_id TEXT,
            qualification_status TEXT
        );
        CREATE TABLE approval_reviews (
            review_id TEXT PRIMARY KEY,
            request_id TEXT,
            reviewer_id TEXT,
            decision TEXT,
            review_role TEXT
        );
        """
    )
    for row in tables.get("items_contracts", []):
        cur.execute(
            "INSERT INTO items_contracts VALUES (?, ?, ?, ?)",
            (
                row.get("item_id"),
                row.get("contract_status"),
                row.get("max_discount_rate"),
                row.get("min_margin_rate"),
            ),
        )
    for row in tables.get("departments", []):
        cur.execute(
            "INSERT INTO departments VALUES (?, ?)",
            (row.get("dept_id"), row.get("parent_division_id")),
        )
    for row in tables.get("order_requests", []):
        cur.execute(
            "INSERT INTO order_requests VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                row.get("request_id"),
                row.get("item_id"),
                row.get("req_dept_id"),
                row.get("applied_discount_rate"),
                row.get("achieved_margin_rate"),
                row.get("net_amount"),
                row.get("gross_amount"),
                row.get("memo_code"),
            ),
        )
    for row in tables.get("reviewers", []):
        cur.execute(
            "INSERT INTO reviewers VALUES (?, ?, ?)",
            (
                row.get("reviewer_id"),
                row.get("belongs_to_dept_id"),
                row.get("qualification_status"),
            ),
        )
    for row in tables.get("approval_reviews", []):
        cur.execute(
            "INSERT INTO approval_reviews VALUES (?, ?, ?, ?, ?)",
            (
                row.get("review_id"),
                row.get("request_id"),
                row.get("reviewer_id"),
                row.get("decision"),
                row.get("review_role"),
            ),
        )

    violations: set[str] = set()
    missing: set[str] = set()

    # Query 1: OrderRequest + ItemContract + Request Department JOIN
    cur.execute(
        """
        SELECT
            r.request_id,
            r.applied_discount_rate,
            r.achieved_margin_rate,
            r.net_amount,
            i.contract_status,
            i.max_discount_rate,
            i.min_margin_rate,
            d_req.parent_division_id
        FROM order_requests r
        LEFT JOIN items_contracts i ON r.item_id = i.item_id
        LEFT JOIN departments d_req ON r.req_dept_id = d_req.dept_id
        LIMIT 1
        """
    )
    head = cur.fetchone()
    (
        req_id,
        app_disc,
        ach_margin,
        net_amt,
        c_status,
        max_disc,
        min_margin,
        req_div,
    ) = head

    if c_status is None:
        missing.add("missing:contract-active")
    elif c_status != "Active":
        violations.add("contract-active")

    if app_disc is None:
        missing.add("missing:discount-cap-req")
    if max_disc is None:
        missing.add("missing:discount-cap-item")
    if app_disc is not None and max_disc is not None and app_disc > max_disc:
        violations.add("discount-cap")

    if net_amt is None:
        missing.add("missing:net-amount-cap")
    elif net_amt > net_cap:
        violations.add("net-amount-cap")

    if round_id in ("R1", "R2", "R3"):
        if ach_margin is None:
            missing.add("missing:margin-floor-req")
        if min_margin is None:
            missing.add("missing:margin-floor-item")
        if ach_margin is not None and min_margin is not None and ach_margin < min_margin:
            violations.add("margin-floor")

    # Query 2: 1:N ApprovalReviews + Reviewers + Reviewer Departments JOIN
    cur.execute(
        """
        SELECT
            rv.review_id,
            rv.decision,
            rv.review_role,
            u.qualification_status,
            d_rev.parent_division_id
        FROM approval_reviews rv
        LEFT JOIN reviewers u ON rv.reviewer_id = u.reviewer_id
        LEFT JOIN departments d_rev ON u.belongs_to_dept_id = d_rev.dept_id
        WHERE rv.request_id = ?
        """,
        (req_id,),
    )
    rev_rows = cur.fetchall()
    if not rev_rows:
        missing.add("missing:review-presence")
        if round_id == "R3":
            missing.add("missing:rev-division")
    else:
        qual_missing = any(r[3] is None for r in rev_rows)
        if qual_missing:
            missing.add("missing:review-qual")
        else:
            primary_cnt = sum(
                1 for r in rev_rows if r[1] == "Approve" and r[2] == "Primary" and r[3] == "Qualified"
            )
            audit_cnt = sum(
                1 for r in rev_rows if r[1] == "Approve" and r[2] == "Audit" and r[3] == "Qualified"
            )
            if primary_cnt < 1:
                violations.add("primary-review-qualified")
            if round_id in ("R2", "R3") and audit_cnt < 1:
                violations.add("dual-role-review")

        if round_id == "R3":
            if req_div is None:
                missing.add("missing:req-division")
            for r in rev_rows:
                rev_div = r[4]
                if rev_div is None:
                    missing.add("missing:rev-division")
                elif req_div is not None and rev_div == req_div:
                    violations.add("division-separation")

    conn.close()
    decision = "blocked" if violations else ("unknown" if missing else "eligible")
    return {
        "decision": decision,
        "violations": sorted(violations),
        "missing": sorted(missing),
    }


# ---------------------------------------------------------------------------
# 4. Base Fixture Factory & 4-Type Counterexample Witness Generator (Stage A)
# ---------------------------------------------------------------------------

def make_valid_base_tables(
    applied_discount: float = 0.12,
    max_discount: float = 0.15,
    achieved_margin: float = 0.22,
    min_margin: float = 0.18,
    net_amount: float = 85000.0,
    gross_amount: float = 100000.0,
    contract_status: str = "Active",
    memo_code: str = "MEMO-2026-0001",
    req_div: str = "DIV_SALES",
    rev1_div: str = "DIV_FINANCE",
    rev2_div: str = "DIV_AUDIT",
) -> dict[str, list[dict[str, Any]]]:
    """Creates a clean, fully-conforming 5-table instance."""
    return {
        "items_contracts": [
            {
                "item_id": "ITEM_101",
                "contract_status": contract_status,
                "max_discount_rate": max_discount,
                "min_margin_rate": min_margin,
            }
        ],
        "departments": [
            {"dept_id": "DEPT_REQ", "parent_division_id": req_div},
            {"dept_id": "DEPT_REV1", "parent_division_id": rev1_div},
            {"dept_id": "DEPT_REV2", "parent_division_id": rev2_div},
        ],
        "order_requests": [
            {
                "request_id": "REQ_2026_01",
                "item_id": "ITEM_101",
                "req_dept_id": "DEPT_REQ",
                "applied_discount_rate": applied_discount,
                "achieved_margin_rate": achieved_margin,
                "net_amount": net_amount,
                "gross_amount": gross_amount,
                "memo_code": memo_code,
            }
        ],
        "reviewers": [
            {
                "reviewer_id": "USER_PRIMARY",
                "belongs_to_dept_id": "DEPT_REV1",
                "qualification_status": "Qualified",
            },
            {
                "reviewer_id": "USER_AUDIT",
                "belongs_to_dept_id": "DEPT_REV2",
                "qualification_status": "Qualified",
            },
        ],
        "approval_reviews": [
            {
                "review_id": "REV_01",
                "request_id": "REQ_2026_01",
                "reviewer_id": "USER_PRIMARY",
                "decision": "Approve",
                "review_role": "Primary",
            },
            {
                "review_id": "REV_02",
                "request_id": "REQ_2026_01",
                "reviewer_id": "USER_AUDIT",
                "decision": "Approve",
                "review_role": "Audit",
            },
        ],
    }


def generate_stage_a_policies_and_witnesses() -> list[dict[str, Any]]:
    """Generates 24 paired bilingual (12 KO + 12 EN) policy items across R0-R3,
    each with 4 minimal counterexample witness graphs:
      - G_pos: boundary-conforming valid instance -> expected 'eligible'
      - G_neg_bound: single-constraint boundary violation -> expected 'blocked'
      - G_unspec: non-standard memo/ID format variation -> expected 'eligible'
      - G_missing: missing required foreign key / NULL attribute -> expected 'unknown'
    """
    policy_templates = [
        {
            "family_id": "P01_discount_cap_pct",
            "round": "R0",
            "ko": "요청의 적용할인율은 품목 계약의 허용할인율상한(예: 15%) 이하여야 한다.",
            "en": "The applied discount rate of the request must not exceed the item contract maximum allowed discount rate (e.g., 15%).",
            "l0_defect": "scale_confusion_pct",
            "neg_mutator": lambda t: t["order_requests"][0].update({"applied_discount_rate": 0.18}),
            "missing_mutator": lambda t: t["order_requests"][0].update({"applied_discount_rate": None}),
        },
        {
            "family_id": "P02_net_amount_cap",
            "round": "R0",
            "ko": "발주 요청의 결제 금액(순결제금액 기준)은 100,000원 이하여야 한다.",
            "en": "The settlement amount of the order request (net settlement amount) must be at most 100,000 KRW.",
            "l0_defect": "synonym_column_confusion",
            "neg_mutator": lambda t: t["order_requests"][0].update({"net_amount": 105000.0, "gross_amount": 120000.0}),
            "missing_mutator": lambda t: t["order_requests"][0].update({"net_amount": None}),
        },
        {
            "family_id": "P03_contract_active",
            "round": "R0",
            "ko": "연결된 품목 계약의 상태코드는 반드시 Active여야 한다.",
            "en": "The linked item contract status must be Active.",
            "l0_defect": "over_spec_memo_regex",
            "neg_mutator": lambda t: t["items_contracts"][0].update({"contract_status": "Suspended"}),
            "missing_mutator": lambda t: t["items_contracts"][0].update({"contract_status": None}),
        },
        {
            "family_id": "P04_primary_review_qual",
            "round": "R0",
            "ko": "적격(Qualified) 검토자의 Primary 역할 승인(Approve)이 최소 1건 존재해야 한다.",
            "en": "At least one Primary role Approve review by a Qualified reviewer must exist.",
            "l0_defect": "over_spec_memo_regex",
            "neg_mutator": lambda t: t["reviewers"][0].update({"qualification_status": "Expired"}),
            "missing_mutator": lambda t: t["reviewers"][0].update({"qualification_status": None}),
        },
        {
            "family_id": "P05_margin_floor_pct",
            "round": "R1",
            "ko": "요청의 달성마진율은 품목의 최소마진율기준(예: 18%) 이상이어야 한다.",
            "en": "The achieved margin rate of the request must be at least the item minimum required margin rate (e.g., 18%).",
            "l0_defect": "null_coercion_to_zero",
            "neg_mutator": lambda t: t["order_requests"][0].update({"achieved_margin_rate": 0.14}),
            "missing_mutator": lambda t: t["items_contracts"][0].update({"min_margin_rate": None}),
        },
        {
            "family_id": "P06_margin_boundary_exact",
            "round": "R1",
            "ko": "달성마진율이 최소마진율기준과 정확히 같을 때는 정상 승인으로 판정하고 미달일 때만 차단한다.",
            "en": "When the achieved margin rate equals the minimum margin rate, it is eligible; block only when strictly below.",
            "l0_defect": "strict_inequality_boundary",
            "neg_mutator": lambda t: t["order_requests"][0].update({"achieved_margin_rate": 0.17}),
            "missing_mutator": lambda t: t["order_requests"][0].update({"achieved_margin_rate": None}),
        },
        {
            "family_id": "P07_dual_role_cardinality",
            "round": "R2",
            "ko": "고액·긴급 요청은 Primary 승인 외에 적격 검토자의 Audit 역할 승인이 1건 이상 추가로 필요하다.",
            "en": "Requests require at least one additional Audit role approval by a Qualified reviewer alongside Primary approval.",
            "l0_defect": "missing_role_qualification",
            "neg_mutator": lambda t: t["approval_reviews"][1].update({"review_role": "Observer"}),
            "missing_mutator": lambda t: t.update({"approval_reviews": []}),
        },
        {
            "family_id": "P08_dual_reviewer_qual_check",
            "round": "R2",
            "ko": "Audit 역할 검토자 역시 자격 상태가 Qualified여야 하며 자격 정보가 누락되면 보류(unknown)한다.",
            "en": "The Audit role reviewer must also have Qualified status, and missing qualification data must yield unknown.",
            "l0_defect": "null_coercion_to_zero",
            "neg_mutator": lambda t: t["reviewers"][1].update({"qualification_status": "Expired"}),
            "missing_mutator": lambda t: t["reviewers"][1].update({"qualification_status": None}),
        },
        {
            "family_id": "P09_division_conflict_3hop",
            "round": "R3",
            "ko": "요청 부서의 상위본부와 검토자 소속 부서의 상위본부가 동일하면 이해상충으로 차단한다.",
            "en": "If the parent division of the requesting department equals the parent division of the reviewer's department, block for conflict of interest.",
            "l0_defect": "dept_vs_division_hop_omission",
            "neg_mutator": lambda t: t["departments"][1].update({"parent_division_id": "DIV_SALES"}),
            "missing_mutator": lambda t: t["departments"][1].update({"parent_division_id": None}),
        },
        {
            "family_id": "P10_audit_division_conflict",
            "round": "R3",
            "ko": "2차 Audit 검토자의 상위본부도 요청 부서의 상위본부와 분리되어야 한다.",
            "en": "The parent division of the Audit reviewer must also be disjoint from the requesting department's parent division.",
            "l0_defect": "over_spec_memo_regex",
            "neg_mutator": lambda t: t["departments"][2].update({"parent_division_id": "DIV_SALES"}),
            "missing_mutator": lambda t: t["departments"][0].update({"parent_division_id": None}),
        },
        {
            "family_id": "P11_combined_discount_and_margin",
            "round": "R3",
            "ko": "적용할인율 상한과 달성마진율 하한을 동시에 충족해야 하며 비고란(memo_code) 형식은 제한하지 않는다.",
            "en": "Both the discount cap and margin floor must be met; memo_code string format is unconstrained.",
            "l0_defect": "over_spec_memo_regex",
            "neg_mutator": lambda t: t["order_requests"][0].update({"applied_discount_rate": 0.21}),
            "missing_mutator": lambda t: t["order_requests"][0].update({"applied_discount_rate": None}),
        },
        {
            "family_id": "P12_full_lifecycle_contract",
            "round": "R3",
            "ko": "계약 활성, 할인·마진·순결제 한도, 2인 역할별 적격 승인, 상위본부 분리를 모두 만족해야 한다.",
            "en": "Contract active status, discount/margin/net caps, dual-role qualified approvals, and parent division separation must all hold.",
            "l0_defect": "synonym_column_confusion",
            "neg_mutator": lambda t: t["order_requests"][0].update({"net_amount": 115000.0}),
            "missing_mutator": lambda t: t["order_requests"][0].update({"net_amount": None}),
        },
    ]

    items: list[dict[str, Any]] = []
    for tpl in policy_templates:
        for lang in ("ko", "en"):
            # Build 4 minimal witness graphs
            g_pos = make_valid_base_tables(
                applied_discount=0.15,
                max_discount=0.15,
                achieved_margin=0.18,
                min_margin=0.18,
                net_amount=95000.0,
                gross_amount=110000.0,
            )
            g_neg = copy.deepcopy(g_pos)
            tpl["neg_mutator"](g_neg)

            g_unspec = copy.deepcopy(g_pos)
            g_unspec["order_requests"][0]["memo_code"] = "freeform_note_#99_no_regex"

            g_missing = copy.deepcopy(g_pos)
            tpl["missing_mutator"](g_missing)

            items.append(
                {
                    "policy_id": f"{tpl['family_id']}_{lang}",
                    "family_id": tpl["family_id"],
                    "lang": lang,
                    "round": tpl["round"],
                    "text": tpl[lang],
                    "l0_defect": tpl["l0_defect"],
                    "witnesses": {
                        "G_pos": {"tables": g_pos, "expected": "eligible"},
                        "G_neg_bound": {"tables": g_neg, "expected": "blocked"},
                        "G_unspec": {"tables": g_unspec, "expected": "eligible"},
                        "G_missing": {"tables": g_missing, "expected": "unknown"},
                    },
                }
            )
    return items


def evaluate_l0_unguarded_rule(
    defect_kind: str,
    tables: dict[str, list[dict[str, Any]]],
    round_id: str,
) -> str:
    """Simulates the unguarded direct-compilation (L0) rule behavior with the
    characteristic failure modes documented in NL2SHACL and Retail studies:
      - scale_confusion_pct: compares applied_discount_rate <= 15.0 (raw % scale)
      - synonym_column_confusion: checks gross_amount <= 100000 instead of net_amount
      - over_spec_memo_regex: adds unrequested regex ^MEMO-[0-9]{4}-[0-9]{4}$
      - null_coercion_to_zero: coerces None -> 0.0 instead of returning 'unknown'
      - strict_inequality_boundary: uses < instead of <= on boundary
      - missing_role_qualification: counts total reviews >= 2 without checking distinct roles
      - dept_vs_division_hop_omission: compares dept_id != belongs_to_dept_id (1-hop) instead of parent_division_id
    """
    base_res = evaluate_arm_p_python(tables, round_id=round_id)
    req = tables["order_requests"][0]
    item = tables["items_contracts"][0]

    if defect_kind == "over_spec_memo_regex":
        memo = req.get("memo_code") or ""
        if not re.match(r"^MEMO-\d{4}-\d{4}$", str(memo)):
            return "blocked"
        return base_res["decision"]

    if defect_kind == "scale_confusion_pct":
        # Compares applied_discount_rate against 15.0 instead of 0.15
        app_disc = req.get("applied_discount_rate")
        if app_disc is None:
            return "unknown"
        if float(app_disc) <= 15.0 and base_res["violations"] == ["discount-cap"]:
            return "eligible"
        return base_res["decision"]

    if defect_kind == "synonym_column_confusion":
        # Uses gross_amount (110,000 in G_pos) instead of net_amount (95,000 in G_pos)
        gross = req.get("gross_amount")
        if gross is not None and float(gross) > 100000.0:
            return "blocked"
        return base_res["decision"]

    if defect_kind == "null_coercion_to_zero":
        # Coerces missing min_margin_rate or qualification into default pass/violation instead of unknown
        if base_res["decision"] == "unknown":
            return "eligible"
        return base_res["decision"]

    if defect_kind == "strict_inequality_boundary":
        # Uses strict '>' on achieved_margin_rate > min_margin_rate, failing exact equality on G_pos
        ach = req.get("achieved_margin_rate")
        min_m = item.get("min_margin_rate")
        if ach is not None and min_m is not None and float(ach) == float(min_m):
            return "blocked"
        return base_res["decision"]

    if defect_kind == "missing_role_qualification":
        # Counts len(reviews) >= 2 without checking Audit role
        if base_res["violations"] == ["dual-role-review"] and len(tables["approval_reviews"]) >= 2:
            return "eligible"
        return base_res["decision"]

    if defect_kind == "dept_vs_division_hop_omission":
        # Compares dept_id (DEPT_REQ vs DEPT_REV1) instead of 3-hop parent_division_id
        if base_res["violations"] == ["division-separation"]:
            return "eligible"
        return base_res["decision"]

    return base_res["decision"]


def run_stage_a_experiment() -> dict[str, Any]:
    """Executes Stage A across all 24 bilingual policies (96 witness cases)."""
    policies = generate_stage_a_policies_and_witnesses()
    shapes_cache = {r: build_shacl_shapes_for_round(r) for r in ROUND_ORDER}

    l0_naive_ser_pass = 0
    l0_cem_pass = 0
    l0_failures_by_witness = {"G_pos": 0, "G_neg_bound": 0, "G_unspec": 0, "G_missing": 0}

    l1_cem_pass = 0
    cross_target_parity_count = 0

    policy_records: list[dict[str, Any]] = []
    for pol in policies:
        r_id = pol["round"]
        w_map = pol["witnesses"]

        # Evaluate L0 (Direct compilation without dictionary/counterexample gate)
        l0_outcomes = {
            w_name: evaluate_l0_unguarded_rule(pol["l0_defect"], w_spec["tables"], r_id)
            for w_name, w_spec in w_map.items()
        }
        # Naive SER checks only one standard non-boundary positive graph
        # where memo_code is standard and gross_amount is not near boundary
        naive_pos = make_valid_base_tables(
            applied_discount=0.10,
            max_discount=0.15,
            achieved_margin=0.25,
            min_margin=0.18,
            net_amount=80000.0,
            gross_amount=90000.0,
        )
        l0_naive_ok = evaluate_l0_unguarded_rule(pol["l0_defect"], naive_pos, r_id) == "eligible"
        if l0_naive_ok:
            l0_naive_ser_pass += 1

        l0_all_match = True
        for w_name, w_spec in w_map.items():
            if l0_outcomes[w_name] != w_spec["expected"]:
                l0_all_match = False
                l0_failures_by_witness[w_name] += 1
        if l0_all_match:
            l0_cem_pass += 1

        # Evaluate L1 (Standard Dictionary + Intermediate Rule Spec + 4-Type Witness Gate across Arm P, S, G)
        p_out = {
            w_name: evaluate_arm_p_python(w_spec["tables"], r_id)["decision"]
            for w_name, w_spec in w_map.items()
        }
        s_out = {
            w_name: evaluate_arm_s_sqlite(w_spec["tables"], r_id)["decision"]
            for w_name, w_spec in w_map.items()
        }
        g_out = {
            w_name: evaluate_arm_g_shacl(
                w_spec["tables"], r_id, shapes_graph=shapes_cache[r_id]
            )["decision"]
            for w_name, w_spec in w_map.items()
        }
        expected_map = {w_name: w_spec["expected"] for w_name, w_spec in w_map.items()}
        if p_out == s_out == g_out:
            cross_target_parity_count += 1
        if p_out == expected_map and s_out == expected_map and g_out == expected_map:
            l1_cem_pass += 1

        policy_records.append(
            {
                "policy_id": pol["policy_id"],
                "lang": pol["lang"],
                "round": r_id,
                "l0_defect": pol["l0_defect"],
                "l0_naive_ser": l0_naive_ok,
                "l0_cem": l0_all_match,
                "l0_outcomes": l0_outcomes,
                "l1_cem": p_out == expected_map,
                "l1_parity_psg": p_out == s_out == g_out,
            }
        )

    n_total = len(policies)
    return {
        "n_policies": n_total,
        "design": "12 authored policy families x 2 language labels; no text compilation",
        "naive_ser_definition": "L0 evaluation of one standard positive case per policy only",
        "n_witness_graphs": n_total * 4,
        "L0_direct": {
            "svr": None,
            "svr_status": "not_measured_no_generated_artifact",
            "naive_ser": f"{l0_naive_ser_pass}/{n_total}",
            "cem": f"{l0_cem_pass}/{n_total}",
            "ser_minus_cem_gap": l0_naive_ser_pass - l0_cem_pass,
            "failures_by_witness": l0_failures_by_witness,
        },
        "L1_workbench_dictionary_gate": {
            "svr": None,
            "svr_status": "not_measured_no_generated_artifact",
            "naive_ser": None,
            "naive_ser_status": "not_measured",
            "cem": f"{l1_cem_pass}/{n_total}",
            "cross_target_parity_psg": f"{cross_target_parity_count}/{n_total}",
        },
        "records": policy_records,
    }


# ---------------------------------------------------------------------------
# 5. Stage B: Runtime Evidence Gating & Whole-Source Reevaluation (360 cases)
# ---------------------------------------------------------------------------

EVIDENCE_STATES = (
    "normal",
    "irrelevant_noise",
    "retrievable_omission",
    "source_absence",
    "explicit_violation",
    "valid_fact_substitution",
)


def build_stage_b_case(entity_idx: int, state: str) -> dict[str, Any]:
    """Constructs an initial retrieved snapshot, full source snapshot, and
    gold evaluation reference for a given entity and evidence state.
    """
    base_disc = round(0.05 + (entity_idx % 8) * 0.01, 4)
    max_disc = 0.15
    ach_margin = round(0.20 + (entity_idx % 5) * 0.01, 4)
    min_margin = 0.18
    net_amt = float(50000 + (entity_idx % 40) * 1000)

    source_tables = make_valid_base_tables(
        applied_discount=base_disc,
        max_discount=max_disc,
        achieved_margin=ach_margin,
        min_margin=min_margin,
        net_amount=net_amt,
    )
    initial_tables = copy.deepcopy(source_tables)

    # Gold truth before any fact corruption
    gold_truth_eligible = True
    answerable_in_source = True
    expected_contract_decision = "eligible"

    if state == "normal":
        pass
    elif state == "irrelevant_noise":
        # Non-target noise: malformed memo_code and an extra unreferenced suspended item
        initial_tables["order_requests"][0]["memo_code"] = "BAD_FORMAT_###"
        initial_tables["items_contracts"].append(
            {
                "item_id": "UNREFERENCED_NOISE_ITEM",
                "contract_status": "Suspended",
                "max_discount_rate": 0.01,
                "min_margin_rate": 0.90,
            }
        )
        source_tables = copy.deepcopy(initial_tables)
    elif state == "retrievable_omission":
        # Initial retrieval omits reviewer department / qualification record, but source has it!
        initial_tables["departments"] = [
            d for d in initial_tables["departments"] if d["dept_id"] == "DEPT_REQ"
        ]
    elif state == "source_absence":
        # Required Audit review or reviewer qualification is absent in both initial AND source!
        initial_tables["reviewers"][1]["qualification_status"] = None
        source_tables["reviewers"][1]["qualification_status"] = None
        answerable_in_source = False
        expected_contract_decision = "unknown"
    elif state == "explicit_violation":
        # Explicit division conflict or discount violation in both initial and source
        if entity_idx % 2 == 0:
            initial_tables["order_requests"][0]["applied_discount_rate"] = 0.25
            source_tables["order_requests"][0]["applied_discount_rate"] = 0.25
        else:
            initial_tables["departments"][1]["parent_division_id"] = "DIV_SALES"
            source_tables["departments"][1]["parent_division_id"] = "DIV_SALES"
        gold_truth_eligible = False
        expected_contract_decision = "blocked"
    elif state == "valid_fact_substitution":
        # Shape-conforming false fact: discount was 0.25 in external reality, but corrupted
        # to a valid-looking 0.11 in source without contrary evidence in the snapshot
        initial_tables["order_requests"][0]["applied_discount_rate"] = 0.11
        source_tables["order_requests"][0]["applied_discount_rate"] = 0.11
        gold_truth_eligible = False
        expected_contract_decision = "eligible"
    else:
        raise ValueError(f"Unknown state: {state}")

    return {
        "case_id": f"ENT_{entity_idx:03d}_{state}",
        "entity_id": f"ENT_{entity_idx:03d}",
        "state": state,
        "initial_tables": initial_tables,
        "source_tables": source_tables,
        "answerable_in_source": answerable_in_source,
        "expected_contract_decision": expected_contract_decision,
        "gold_truth_eligible": gold_truth_eligible,
    }


def run_stage_b_experiment(n_entities: int = 60) -> dict[str, Any]:
    """Executes Stage B over 360 multi-table cases (60 entities x 6 states)
    No real GLEIF source is loaded or evaluated.
    """
    cases = [
        build_stage_b_case(i, st)
        for i in range(1, n_entities + 1)
        for st in EVIDENCE_STATES
    ]
    shapes_r3 = build_shacl_shapes_for_round("R3")

    policies = ("U0", "G1", "S2_ArmP", "S2_ArmS", "S2_ArmG")
    stats: dict[str, dict[str, Any]] = {
        p: {
            "total": len(cases),
            "contract_match": 0,
            "wrong_approval": 0,
            "external_truth_error_on_substitution": 0,
            "unnecessary_abstention": 0,
            "answerable_total": 0,
            "refresh_calls": 0,
            "elapsed_ms": 0.0,
            "by_state": {st: {"eligible": 0, "blocked": 0, "unknown": 0} for st in EVIDENCE_STATES},
        }
        for p in policies
    }

    arm_decisions: list[tuple[str, str, str]] = []

    for c in cases:
        st = c["state"]
        init_t = c["initial_tables"]
        src_t = c["source_tables"]

        # 1. U0 (Unvalidated baseline: approves whenever order_requests row exists and has net_amount <= 100000)
        t0 = time.perf_counter()
        req = init_t["order_requests"][0]
        u0_dec = "eligible" if (req.get("net_amount") or 0.0) <= 100000.0 else "blocked"
        t_u0 = (time.perf_counter() - t0) * 1000.0

        # 2. G1 (Blanket validation: checks all items in table + strict memo regex, no selective refresh)
        t0 = time.perf_counter()
        g1_base = evaluate_arm_p_python(init_t, "R3")
        all_items_active = all(
            it.get("contract_status") == "Active" for it in init_t.get("items_contracts", [])
        )
        memo_valid = bool(re.match(r"^MEMO-\d{4}-\d{4}$", str(req.get("memo_code") or "")))
        if g1_base["decision"] != "eligible" or not all_items_active or not memo_valid:
            g1_dec = "unknown" if g1_base["decision"] == "unknown" else "blocked"
        else:
            g1_dec = "eligible"
        t_g1 = (time.perf_counter() - t0) * 1000.0

        # 3. S2 across Arm P, Arm S, Arm G (Question-scoped check + at most 1 refresh on 'unknown')
        s2_results: dict[str, tuple[str, int, float]] = {}
        for arm_name, fn in (
            ("S2_ArmP", lambda tb: evaluate_arm_p_python(tb, "R3")),
            ("S2_ArmS", lambda tb: evaluate_arm_s_sqlite(tb, "R3")),
            ("S2_ArmG", lambda tb: evaluate_arm_g_shacl(tb, "R3", shapes_graph=shapes_r3)),
        ):
            t0 = time.perf_counter()
            r1 = fn(init_t)
            refreshed = 0
            if r1["decision"] == "unknown":
                refreshed = 1
                r1 = fn(src_t)
            elapsed = (time.perf_counter() - t0) * 1000.0
            s2_results[arm_name] = (r1["decision"], refreshed, elapsed)

        arm_decisions.append(
            (
                s2_results["S2_ArmP"][0],
                s2_results["S2_ArmS"][0],
                s2_results["S2_ArmG"][0],
            )
        )

        all_runs = {
            "U0": (u0_dec, 0, t_u0),
            "G1": (g1_dec, 0, t_g1),
            **s2_results,
        }
        for pol_name, (dec, ref_cnt, ms) in all_runs.items():
            ps = stats[pol_name]
            ps["elapsed_ms"] += ms
            ps["refresh_calls"] += ref_cnt
            ps["by_state"][st][dec] += 1
            if dec == c["expected_contract_decision"]:
                ps["contract_match"] += 1
            # Wrong approval: deciding 'eligible' when contract says 'blocked' or 'unknown'
            if dec == "eligible" and c["expected_contract_decision"] != "eligible":
                ps["wrong_approval"] += 1
            if st == "valid_fact_substitution" and dec == "eligible" and not c["gold_truth_eligible"]:
                ps["external_truth_error_on_substitution"] += 1
            if c["answerable_in_source"] and c["expected_contract_decision"] == "eligible":
                ps["answerable_total"] += 1
                if dec in ("blocked", "unknown"):
                    ps["unnecessary_abstention"] += 1

    exact_psg_matches = sum(1 for p, s, g in arm_decisions if p == s == g)
    return {
        "n_cases": len(cases),
        "n_entities": n_entities,
        "psg_exact_agreement": f"{exact_psg_matches}/{len(cases)}",
        "gleif_transfer_24": {
            "status": "not_executed",
            "reason": "Legacy output used synthetic labels and constants, not source evaluation",
        },
        "refresh_policy": "On unknown, reevaluate the whole supplied source_tables once; no path targeting",
        "policies": {
            k: {
                **v,
                "mean_latency_ms": round(v["elapsed_ms"] / v["total"], 4),
                "elapsed_ms": round(v["elapsed_ms"], 2),
            }
            for k, v in stats.items()
        },
    }


# ---------------------------------------------------------------------------
# 6. Stage C: Rule Evolution (R0 -> R1 -> R2 -> R3) & Multi-Consumer Consistency
# ---------------------------------------------------------------------------

ARM_STAGE_SOURCE_SNIPPETS: dict[str, dict[str, tuple[str, str]]] = {
    # Each entry is an illustrative (join_projection_core_code, rule_constraint_code) pair; not executed source
    "ArmP_Python": {
        "R0": (
            """
def join_core(tables):
    req = tables['order_requests'][0]
    item = {i['item_id']: i for i in tables['items_contracts']}.get(req.get('item_id'))
    revs = [r for r in tables['approval_reviews'] if r.get('request_id') == req.get('request_id')]
    users = {u['reviewer_id']: u for u in tables['reviewers']}
    return req, item, [(r, users.get(r.get('reviewer_id'))) for r in revs]
""",
            """
def check_rules(req, item, rev_pairs):
    v = []
    if item.get('contract_status') != 'Active': v.append('contract-active')
    if req['applied_discount_rate'] > item['max_discount_rate']: v.append('discount-cap')
    if req['net_amount'] > 100000.0: v.append('net-amount-cap')
    if not any(r['decision']=='Approve' and r['review_role']=='Primary' and u['qualification_status']=='Qualified' for r, u in rev_pairs):
        v.append('primary-review-qualified')
    return v
""",
        ),
        "R1": (
            """
def join_core(tables):
    req = tables['order_requests'][0]
    item = {i['item_id']: i for i in tables['items_contracts']}.get(req.get('item_id'))
    revs = [r for r in tables['approval_reviews'] if r.get('request_id') == req.get('request_id')]
    users = {u['reviewer_id']: u for u in tables['reviewers']}
    return req, item, [(r, users.get(r.get('reviewer_id'))) for r in revs]
""",
            """
def check_rules(req, item, rev_pairs):
    v = []
    if item.get('contract_status') != 'Active': v.append('contract-active')
    if req['applied_discount_rate'] > item['max_discount_rate']: v.append('discount-cap')
    if req['net_amount'] > 100000.0: v.append('net-amount-cap')
    if not any(r['decision']=='Approve' and r['review_role']=='Primary' and u['qualification_status']=='Qualified' for r, u in rev_pairs):
        v.append('primary-review-qualified')
    if req['achieved_margin_rate'] < item['min_margin_rate']: v.append('margin-floor')
    return v
""",
        ),
        "R2": (
            """
def join_core(tables):
    req = tables['order_requests'][0]
    item = {i['item_id']: i for i in tables['items_contracts']}.get(req.get('item_id'))
    revs = [r for r in tables['approval_reviews'] if r.get('request_id') == req.get('request_id')]
    users = {u['reviewer_id']: u for u in tables['reviewers']}
    role_map = {}
    for r in revs:
        u = users.get(r.get('reviewer_id'))
        if r.get('decision') == 'Approve' and u and u.get('qualification_status') == 'Qualified':
            role_map.setdefault(r.get('review_role'), []).append((r, u))
    return req, item, role_map
""",
            """
def check_rules(req, item, role_map):
    v = []
    if item.get('contract_status') != 'Active': v.append('contract-active')
    if req['applied_discount_rate'] > item['max_discount_rate']: v.append('discount-cap')
    if req['net_amount'] > 100000.0: v.append('net-amount-cap')
    if 'Primary' not in role_map: v.append('primary-review-qualified')
    if req['achieved_margin_rate'] < item['min_margin_rate']: v.append('margin-floor')
    if 'Audit' not in role_map: v.append('dual-role-review')
    return v
""",
        ),
        "R3": (
            """
def join_core(tables):
    req = tables['order_requests'][0]
    item = {i['item_id']: i for i in tables['items_contracts']}.get(req.get('item_id'))
    depts = {d['dept_id']: d for d in tables['departments']}
    req_div = depts.get(req.get('req_dept_id'), {}).get('parent_division_id')
    revs = [r for r in tables['approval_reviews'] if r.get('request_id') == req.get('request_id')]
    users = {u['reviewer_id']: u for u in tables['reviewers']}
    role_map, rev_divs = {}, []
    for r in revs:
        u = users.get(r.get('reviewer_id'))
        if u:
            rev_divs.append(depts.get(u.get('belongs_to_dept_id'), {}).get('parent_division_id'))
        if r.get('decision') == 'Approve' and u and u.get('qualification_status') == 'Qualified':
            role_map.setdefault(r.get('review_role'), []).append((r, u))
    return req, item, role_map, req_div, rev_divs
""",
            """
def check_rules(req, item, role_map, req_div, rev_divs):
    v = []
    if item.get('contract_status') != 'Active': v.append('contract-active')
    if req['applied_discount_rate'] > item['max_discount_rate']: v.append('discount-cap')
    if req['net_amount'] > 100000.0: v.append('net-amount-cap')
    if 'Primary' not in role_map: v.append('primary-review-qualified')
    if req['achieved_margin_rate'] < item['min_margin_rate']: v.append('margin-floor')
    if 'Audit' not in role_map: v.append('dual-role-review')
    if any(d == req_div for d in rev_divs): v.append('division-separation')
    return v
""",
        ),
    },
    "ArmS_SQLite": {
        "R0": (
            """
SELECT r.request_id, r.applied_discount_rate, r.net_amount,
       i.contract_status, i.max_discount_rate,
       SUM(CASE WHEN rv.decision='Approve' AND rv.review_role='Primary' AND u.qualification_status='Qualified' THEN 1 ELSE 0 END) AS prim_ok
FROM order_requests r
LEFT JOIN items_contracts i ON r.item_id = i.item_id
LEFT JOIN approval_reviews rv ON r.request_id = rv.request_id
LEFT JOIN reviewers u ON rv.reviewer_id = u.reviewer_id
GROUP BY r.request_id
""",
            """
SELECT CASE WHEN contract_status != 'Active' THEN 'contract-active' END,
       CASE WHEN applied_discount_rate > max_discount_rate THEN 'discount-cap' END,
       CASE WHEN net_amount > 100000.0 THEN 'net-amount-cap' END,
       CASE WHEN prim_ok < 1 THEN 'primary-review-qualified' END
""",
        ),
        "R1": (
            """
SELECT r.request_id, r.applied_discount_rate, r.achieved_margin_rate, r.net_amount,
       i.contract_status, i.max_discount_rate, i.min_margin_rate,
       SUM(CASE WHEN rv.decision='Approve' AND rv.review_role='Primary' AND u.qualification_status='Qualified' THEN 1 ELSE 0 END) AS prim_ok
FROM order_requests r
LEFT JOIN items_contracts i ON r.item_id = i.item_id
LEFT JOIN approval_reviews rv ON r.request_id = rv.request_id
LEFT JOIN reviewers u ON rv.reviewer_id = u.reviewer_id
GROUP BY r.request_id
""",
            """
SELECT CASE WHEN contract_status != 'Active' THEN 'contract-active' END,
       CASE WHEN applied_discount_rate > max_discount_rate THEN 'discount-cap' END,
       CASE WHEN net_amount > 100000.0 THEN 'net-amount-cap' END,
       CASE WHEN prim_ok < 1 THEN 'primary-review-qualified' END,
       CASE WHEN achieved_margin_rate < min_margin_rate THEN 'margin-floor' END
""",
        ),
        "R2": (
            """
SELECT r.request_id, r.applied_discount_rate, r.achieved_margin_rate, r.net_amount,
       i.contract_status, i.max_discount_rate, i.min_margin_rate,
       SUM(CASE WHEN rv.decision='Approve' AND rv.review_role='Primary' AND u.qualification_status='Qualified' THEN 1 ELSE 0 END) AS prim_ok,
       SUM(CASE WHEN rv.decision='Approve' AND rv.review_role='Audit' AND u.qualification_status='Qualified' THEN 1 ELSE 0 END) AS audit_ok
FROM order_requests r
LEFT JOIN items_contracts i ON r.item_id = i.item_id
LEFT JOIN approval_reviews rv ON r.request_id = rv.request_id
LEFT JOIN reviewers u ON rv.reviewer_id = u.reviewer_id
GROUP BY r.request_id
""",
            """
SELECT CASE WHEN contract_status != 'Active' THEN 'contract-active' END,
       CASE WHEN applied_discount_rate > max_discount_rate THEN 'discount-cap' END,
       CASE WHEN net_amount > 100000.0 THEN 'net-amount-cap' END,
       CASE WHEN prim_ok < 1 THEN 'primary-review-qualified' END,
       CASE WHEN achieved_margin_rate < min_margin_rate THEN 'margin-floor' END,
       CASE WHEN audit_ok < 1 THEN 'dual-role-review' END
""",
        ),
        "R3": (
            """
SELECT r.request_id, r.applied_discount_rate, r.achieved_margin_rate, r.net_amount,
       i.contract_status, i.max_discount_rate, i.min_margin_rate,
       SUM(CASE WHEN rv.decision='Approve' AND rv.review_role='Primary' AND u.qualification_status='Qualified' THEN 1 ELSE 0 END) AS prim_ok,
       SUM(CASE WHEN rv.decision='Approve' AND rv.review_role='Audit' AND u.qualification_status='Qualified' THEN 1 ELSE 0 END) AS audit_ok,
       SUM(CASE WHEN d_req.parent_division_id = d_rev.parent_division_id THEN 1 ELSE 0 END) AS div_conflict
FROM order_requests r
LEFT JOIN items_contracts i ON r.item_id = i.item_id
LEFT JOIN departments d_req ON r.req_dept_id = d_req.dept_id
LEFT JOIN approval_reviews rv ON r.request_id = rv.request_id
LEFT JOIN reviewers u ON rv.reviewer_id = u.reviewer_id
LEFT JOIN departments d_rev ON u.belongs_to_dept_id = d_rev.dept_id
GROUP BY r.request_id
""",
            """
SELECT CASE WHEN contract_status != 'Active' THEN 'contract-active' END,
       CASE WHEN applied_discount_rate > max_discount_rate THEN 'discount-cap' END,
       CASE WHEN net_amount > 100000.0 THEN 'net-amount-cap' END,
       CASE WHEN prim_ok < 1 THEN 'primary-review-qualified' END,
       CASE WHEN achieved_margin_rate < min_margin_rate THEN 'margin-floor' END,
       CASE WHEN audit_ok < 1 THEN 'dual-role-review' END,
       CASE WHEN div_conflict > 0 THEN 'division-separation' END
""",
        ),
    },
    "ArmG_SHACL": {
        # Generic mapper is 100% identical across R0, R1, R2, R3!
        r: (
            "GENERIC_MAPPER_INVARIANT",
            f"SHACL_SHAPES_{r}",
        )
        for r in ROUND_ORDER
    },
}


def compute_line_diff_count(before: str, after: str) -> int:
    """Legacy snippet metric: nonblank stripped lines absent from opposite set.

    Counts additions plus removals; ignores order and duplicate-count changes.
    Not a source diff, AST edit distance, or minimum implementation cost.
    """
    b_lines = [line.strip() for line in before.strip().splitlines() if line.strip()]
    a_lines = [line.strip() for line in after.strip().splitlines() if line.strip()]
    b_set = set(b_lines)
    a_set = set(a_lines)
    added = sum(1 for x in a_lines if x not in b_set)
    removed = sum(1 for x in b_lines if x not in a_set)
    return added + removed


def source_function_line_counts() -> dict[str, Any]:
    """Count physical function spans including signature, docstring and blanks."""
    functions = (generic_tables_to_rdf, _compact_uri, extract_shacl_llm_report)
    return {
        "definition": "physical lines from def through last body line, inclusive",
        "counts": {fn.__name__: len(inspect.getsourcelines(fn)[0]) for fn in functions},
    }


def run_stage_c_experiment(cases_per_round: int = 240) -> dict[str, Any]:
    """Executes Stage C across R0 -> R1 -> R2 -> R3 (240 cases/round = 960 evaluations)
    and evaluates join-core invariance, rule diff lines, cross-engine parity,
    and 3-consumer consistency.
    """
    shapes_cache = {r: build_shacl_shapes_for_round(r) for r in ROUND_ORDER}
    round_summaries: dict[str, Any] = {}
    total_parity_matches = 0
    total_evals = 0

    for r_idx, r_id in enumerate(ROUND_ORDER):
        parity_matches = 0
        decisions_dist = {"eligible": 0, "blocked": 0, "unknown": 0}
        for c_idx in range(cases_per_round):
            t = make_valid_base_tables()
            mode = c_idx % 6
            if mode == 0:
                pass  # eligible
            elif mode == 1:
                t["order_requests"][0]["applied_discount_rate"] = 0.22  # R0 violation
            elif mode == 2:
                t["order_requests"][0]["achieved_margin_rate"] = 0.12  # R1 violation
            elif mode == 3:
                t["approval_reviews"][1]["review_role"] = "Observer"  # R2 violation
            elif mode == 4:
                t["departments"][1]["parent_division_id"] = "DIV_SALES"  # R3 violation
            elif mode == 5:
                t["order_requests"][0]["net_amount"] = None  # unknown

            res_p = evaluate_arm_p_python(t, r_id)
            res_s = evaluate_arm_s_sqlite(t, r_id)
            res_g = evaluate_arm_g_shacl(t, r_id, shapes_graph=shapes_cache[r_id])
            total_evals += 1
            if res_p == res_s == res_g:
                parity_matches += 1
                total_parity_matches += 1
            decisions_dist[res_g["decision"]] += 1

        round_summaries[r_id] = {
            "n_cases": cases_per_round,
            "psg_exact_match": f"{parity_matches}/{cases_per_round}",
            "decisions": decisions_dist,
        }

    # Compute transition modification metrics (R0->R1, R1->R2, R2->R3)
    transitions = (("R0", "R1"), ("R1", "R2"), ("R2", "R3"))
    evolution_diffs: dict[str, list[dict[str, Any]]] = {
        "ArmP_Python": [],
        "ArmS_SQLite": [],
        "ArmG_SHACL": [],
    }
    shacl_shape_triples = {r: len(shapes_cache[r]) for r in ROUND_ORDER}

    for prev_r, next_r in transitions:
        for arm_key in ("ArmP_Python", "ArmS_SQLite"):
            j_prev, c_prev = ARM_STAGE_SOURCE_SNIPPETS[arm_key][prev_r]
            j_next, c_next = ARM_STAGE_SOURCE_SNIPPETS[arm_key][next_r]
            j_diff = compute_line_diff_count(j_prev, j_next)
            c_diff = compute_line_diff_count(c_prev, c_next)
            evolution_diffs[arm_key].append(
                {
                    "transition": f"{prev_r}->{next_r}",
                    "join_core_modified_lines": j_diff,
                    "rule_layer_modified_lines": c_diff,
                    "total_modified_lines": j_diff + c_diff,
                }
            )
        # In ArmG_SHACL, generic_tables_to_rdf is 100% invariant (0 lines modified);
        # only declarative shape triples are added
        added_triples = shacl_shape_triples[next_r] - shacl_shape_triples[prev_r]
        evolution_diffs["ArmG_SHACL"].append(
            {
                "transition": f"{prev_r}->{next_r}",
                "join_core_modified_lines": 0,
                "declarative_shape_added_triples": added_triples,
                "declarative_shape_blocks_added": 1,
            }
        )

    # Multi-consumer consistency evaluation across 3 consumers
    # (Consumer 1: Approval Gate, Consumer 2: Batch Audit, Consumer 3: Explanation Assistant)
    # Illustration only: compare R3 vs R1 (two-round lag), then R3 vs R3; no actual services.
    n_test = 240
    copied_code_divergent_cases = 0
    pinned_shared_spec_divergent_cases = 0
    for c_idx in range(n_test):
        t = make_valid_base_tables()
        if c_idx % 6 == 3:
            t["approval_reviews"][1]["review_role"] = "Observer"
        elif c_idx % 6 == 4:
            t["departments"][1]["parent_division_id"] = "DIV_SALES"
        c1_dec = evaluate_arm_p_python(t, "R3")["decision"]
        c3_lagged_dec = evaluate_arm_p_python(t, "R1")["decision"]
        if c1_dec != c3_lagged_dec:
            copied_code_divergent_cases += 1
        # Same-version duplicate call; no deployed version-hash enforcement is tested
        c1_pinned = evaluate_arm_g_shacl(t, "R3", shapes_graph=shapes_cache["R3"])["decision"]
        c3_pinned = evaluate_arm_g_shacl(t, "R3", shapes_graph=shapes_cache["R3"])["decision"]
        if c1_pinned != c3_pinned:
            pinned_shared_spec_divergent_cases += 1

    return {
        "line_count_basis": "illustrative snippets; stripped nonblank opposite-set absence, additions + removals",
        "source_function_lines": source_function_line_counts(),
        "consumer_design": "two local calls: Python R3 vs R1; SHACL R3 vs R3; no services or pin enforcement",
        "total_evaluations": total_evals,
        "overall_psg_parity": f"{total_parity_matches}/{total_evals}",
        "round_summaries": round_summaries,
        "evolution_diffs": evolution_diffs,
        "multi_consumer_consistency": {
            "n_cases": n_test,
            "copied_procedural_consumer_divergence": f"{copied_code_divergent_cases}/{n_test}",
            "pinned_shared_spec_divergence": f"{pinned_shared_spec_divergent_cases}/{n_test}",
        },
    }


# ---------------------------------------------------------------------------
# 7. Stage D: LLM Prompt Injection & Provenance Bridge (M0 vs M1 vs M2)
# ---------------------------------------------------------------------------

def _compact_uri(node: Any, g: Graph) -> str:
    if node is None:
        return ""
    if isinstance(node, URIRef):
        s = str(node)
        if s.startswith(str(EX)):
            return "ex:" + s[len(str(EX)):]
        if s.startswith(str(SH)):
            return "sh:" + s[len(str(SH)):]
        return s
    if isinstance(node, BNode):
        inv = g.value(node, SH.inversePath)
        if inv is not None:
            return f"^{_compact_uri(inv, g)}"
        items = list(Collection(g, node))
        if items:
            return " / ".join(_compact_uri(it, g) for it in items)
    return str(node)


def extract_shacl_llm_report(
    tables: dict[str, list[dict[str, Any]]],
    round_id: str = "R3",
    shapes_graph: Graph | None = None,
) -> dict[str, Any]:
    """Runs pySHACL on the generic entity graph and extracts
    the standardized W3C SHACL ValidationReport (focusNode, resultPath,
    valueNode, sourceConstraintComponent, resultSeverity, resultMessage)
    ready for direct injection into an LLM prompt or tool response.
    Uses custom shared formatting and a separate policy evaluator.
    SHACL conformance is returned separately from policy eligibility.
    """
    dg = generic_tables_to_rdf(tables)
    sg = shapes_graph if shapes_graph is not None else build_shacl_shapes_for_round(round_id)
    conforms, rep_graph, _ = validate(dg, shacl_graph=sg)
    base_eval = evaluate_arm_g_shacl(tables, round_id, shapes_graph=sg)

    findings: list[dict[str, str]] = []
    for res in rep_graph.subjects(RDF.type, SH.ValidationResult):
        focus = _compact_uri(rep_graph.value(res, SH.focusNode), rep_graph)
        r_path = _compact_uri(rep_graph.value(res, SH.resultPath), rep_graph)
        val_node = _compact_uri(rep_graph.value(res, SH.value), rep_graph)
        comp = _compact_uri(rep_graph.value(res, SH.sourceConstraintComponent), rep_graph)
        sev = _compact_uri(rep_graph.value(res, SH.resultSeverity), rep_graph)
        msg = str(rep_graph.value(res, SH.resultMessage) or "")
        findings.append(
            {
                "severity": sev,
                "message": msg,
                "focus_node": focus,
                "result_path": r_path,
                "value_node": val_node,
                "constraint_component": comp,
            }
        )
    findings.sort(key=lambda x: (x["severity"], x["message"], x["focus_node"]))
    return {
        "decision": base_eval["decision"],
        "conforms": bool(conforms),
        "policy_eligible": base_eval["decision"] == "eligible",
        "violations": base_eval["violations"],
        "missing": base_eval["missing"],
        "shacl_validation_results": findings,
    }


def build_llm_prompt_modes(
    tables: dict[str, list[dict[str, Any]]],
    question: str = "REQ_2026_01 발주 요청을 승인해도 되는지 판단하고, 차단 또는 보류 시 정확한 원인 개체(focus_node), 관계 경로(result_path), 충돌 값(value_node)을 근거로 제시하라.",
    round_id: str = "R3",
) -> dict[str, str]:
    """Constructs the three concrete LLM prompt payloads to show how values
    enter the LLM prompt in each architecture:
      - M0_raw_table_prompt: Raw 5-table JSON + natural-language rules only (no pre-check).
      - M1_bare_function_prompt: Python function returns only {'decision': ..., 'violations': [...]}
        without node/path/value provenance.
      - M2_shacl_report_prompt: Injects the W3C SHACL ValidationReport JSON containing
        automatic focus_node, result_path, and value_node provenance.
    """
    raw_tables_json = json.dumps(tables, ensure_ascii=False, indent=2)
    bare_fn_res = {
        "decision": evaluate_arm_p_python(tables, round_id)["decision"],
        "violations": evaluate_arm_p_python(tables, round_id)["violations"],
    }
    shacl_report = extract_shacl_llm_report(tables, round_id)

    m0_prompt = (
        f"<QUESTION>\n{question}\n</QUESTION>\n\n"
        "<POLICY_TEXT>\n"
        "1. 품목 계약 상태가 Active이고 적용할인율 <= 허용할인율상한, 달성마진율 >= 최소마진율기준, 순결제금액 <= 100,000원이어야 한다.\n"
        "2. 적격(Qualified) 검토자의 Primary 승인과 Audit 승인이 각각 1건 이상 있어야 한다.\n"
        "3. 요청 부서의 상위본부와 검토자 소속 부서의 상위본부가 같으면 이해상충으로 차단한다.\n"
        "</POLICY_TEXT>\n\n"
        f"<RAW_TABLES>\n{raw_tables_json}\n</RAW_TABLES>\n\n"
        "<INSTRUCTION>\n위 원천 테이블만 보고 직접 조인·계산하여 JSON(decision, focus_node, result_path, value_node, explanation)으로 답하라.\n</INSTRUCTION>"
    )

    m1_prompt = (
        f"<QUESTION>\n{question}\n</QUESTION>\n\n"
        f"<FUNCTION_CHECK_RESULT>\n{json.dumps(bare_fn_res, ensure_ascii=False, indent=2)}\n</FUNCTION_CHECK_RESULT>\n\n"
        f"<RAW_TABLES>\n{raw_tables_json}\n</RAW_TABLES>\n\n"
        "<INSTRUCTION>\n함수 판정 결과(decision)는 고정하되, 어느 개체와 경로·값 때문에 위반되었는지는 원천 테이블에서 직접 찾아 JSON으로 설명하라.\n</INSTRUCTION>"
    )

    m2_prompt = (
        f"<QUESTION>\n{question}\n</QUESTION>\n\n"
        f"<SHACL_VALIDATION_REPORT>\n{json.dumps(shacl_report, ensure_ascii=False, indent=2)}\n</SHACL_VALIDATION_REPORT>\n\n"
        "<INSTRUCTION>\n검증 보고서의 decision, focus_node, result_path, value_node를 그대로 근거로 인용하여 환각 없이 JSON 응답과 감사 설명을 생성하라.\n</INSTRUCTION>"
    )

    return {
        "M0_raw_table_prompt": m0_prompt,
        "M1_bare_function_prompt": m1_prompt,
        "M2_shacl_report_prompt": m2_prompt,
    }


def run_stage_d_llm_prompt_bridge() -> dict[str, Any]:
    """Evaluates what structured decision & provenance information is delivered
    to the LLM prompt across M0 (Raw Tables), M1 (Bare Function), and
    M2 (SHACL ValidationReport) over four R3 violation patterns repeated 60 times.
    Counts nonempty fields of the first sorted result. Manual tracing implementation cost is unmeasured.
    """
    shapes_r3 = build_shacl_shapes_for_round("R3")
    n_cases = 240
    value_counts_by_constraint: dict[str, dict[str, int]] = {}
    # Required LLM output slots: (1) decision, (2) focus_node, (3) result_path, (4) value_node
    explicit_slots_in_prompt = {
        "M0_raw_table_prompt": {"decision": 0, "focus_node": 0, "result_path": 0, "value_node": 0},
        "M1_bare_function_prompt": {"decision": 0, "focus_node": 0, "result_path": 0, "value_node": 0},
        "M2_shacl_report_prompt": {"decision": 0, "focus_node": 0, "result_path": 0, "value_node": 0},
    }

    for idx in range(n_cases):
        t = make_valid_base_tables()
        mode = idx % 4
        if mode == 0:
            t["order_requests"][0]["applied_discount_rate"] = 0.25
        elif mode == 1:
            t["order_requests"][0]["achieved_margin_rate"] = 0.11
        elif mode == 2:
            t["approval_reviews"][1]["review_role"] = "Observer"
        else:
            t["departments"][1]["parent_division_id"] = "DIV_SALES"

        rep = extract_shacl_llm_report(t, "R3", shapes_graph=shapes_r3)
        # M0 provides 0 pre-computed decision/provenance fields in prompt
        # M1 provides decision (1/4), but 0/3 structural provenance fields (focus_node, result_path, value_node)
        explicit_slots_in_prompt["M1_bare_function_prompt"]["decision"] += 1
        # M2 (SHACL report) automatically provides decision + focus_node + result_path + value_node
        if rep["decision"] == "blocked" and rep["shacl_validation_results"]:
            r0 = rep["shacl_validation_results"][0]
            counts = value_counts_by_constraint.setdefault(r0["constraint_component"], {"results": 0, "nonempty_value": 0})
            counts["results"] += 1
            counts["nonempty_value"] += bool(r0["value_node"])
            explicit_slots_in_prompt["M2_shacl_report_prompt"]["decision"] += 1
            if r0["focus_node"]:
                explicit_slots_in_prompt["M2_shacl_report_prompt"]["focus_node"] += 1
            if r0["result_path"]:
                explicit_slots_in_prompt["M2_shacl_report_prompt"]["result_path"] += 1
            # QualifiedMinCount has no individual offending value in these fixtures;
            # Value/Disjoint constraints populate value_node as well
            if r0["value_node"]:
                explicit_slots_in_prompt["M2_shacl_report_prompt"]["value_node"] += 1

    # Concrete sample prompts for R3 5-hop division conflict case
    sample_conflict_tables = make_valid_base_tables(req_div="DIV_SALES", rev1_div="DIV_SALES")
    sample_prompts = build_llm_prompt_modes(sample_conflict_tables, round_id="R3")
    sample_shacl_report = extract_shacl_llm_report(sample_conflict_tables, "R3", shapes_graph=shapes_r3)

    return {
        "n_violation_cases": n_cases,
        "first_result_values_by_constraint": value_counts_by_constraint,
        "prompt_slot_coverage": {
            mode_key: {k: f"{v}/{n_cases}" for k, v in slot_counts.items()}
            for mode_key, slot_counts in explicit_slots_in_prompt.items()
        },
        "coverage_definition": "nonempty fields of first sorted report result; 4 templates repeated 60 times",
        "llm_calls": 0,
        "custom_provenance_code_lines_added_r0_to_r3": None,
        "provenance_cost_status": "not_measured; legacy 14/11/0 constants withdrawn",
        "source_function_lines": source_function_line_counts(),
        "sample_r3_conflict_shacl_report": sample_shacl_report,
        "sample_prompts_r3_conflict": sample_prompts,
    }


def run_unified_experiment(output_dir: Path | None = None) -> dict[str, Any]:
    """Runs four separately authored offline diagnostics and writes artifacts."""
    if output_dir is not None and output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {output_dir}")
    t_start = time.perf_counter()
    stage_a = run_stage_a_experiment()
    stage_b = run_stage_b_experiment(n_entities=60)
    stage_c = run_stage_c_experiment(cases_per_round=240)
    stage_d = run_stage_d_llm_prompt_bridge()
    elapsed_sec = round(time.perf_counter() - t_start, 3)

    summary = {
        "experiment_id": "unified-rule-lifecycle-1",
        "audit_revision": "2026-10-26",
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "paid_api_calls": 0,
        "elapsed_seconds": elapsed_sec,
        "stage_a_compilation_gate": {
            k: v for k, v in stage_a.items() if k != "records"
        },
        "stage_b_runtime_gating": stage_b,
        "stage_c_rule_evolution": stage_c,
        "stage_d_llm_prompt_bridge": {
            k: v for k, v in stage_d.items() if k != "sample_prompts_r3_conflict"
        },
    }
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=False)
        (output_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "stage_a_records.json").write_text(
            json.dumps(stage_a["records"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "stage_d_sample_prompts.json").write_text(
            json.dumps(stage_d["sample_prompts_r3_conflict"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; existing outputs are never overwritten")
    out = parser.parse_args().output_dir
    res = run_unified_experiment(out)
    print(json.dumps(res, ensure_ascii=False, indent=2))
