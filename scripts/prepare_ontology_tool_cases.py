#!/usr/bin/env python3
"""Authored, consumed synthetic development cases; runtime and scorer exports are separate."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path

from rdflib import RDF, Graph, Literal, Namespace

NS = Namespace("urn:business-questions:")
ASOF = "2026-10-12"
PROTOCOL = "llm-ontology-tools-1"
KINDS = {
    "bom": ["subject", "object", "relation"],
    "candidate": ["candidate", "tolerance", "unit", "certificate", "compatibility"],
    "change": ["field"],
    "dependency": ["field", "workitem", "required"],
    "entity": ["entity", "legal_status", "registration_status", "snapshot_date"],
    "relationship": [
        "subject",
        "object",
        "relation",
        "registration_status",
        "snapshot_date",
    ],
    "exception": ["subject", "relation", "reason", "snapshot_date"],
}
PHYSICAL_SCHEMA = {
    "namespace": str(NS),
    "record_subject": "urn:business-questions:record/{id}",
    "layout": "Each record has rdf:type bq:<kind>. All field values are literals. Join identifier strings, not record IRIs. Missing fields have no triple.",
    "types": KINDS,
    "common_fields": ["id", "kind", "status", "start", "end"],
    "dates": "ISO YYYY-MM-DD strings; windows include both endpoints.",
    "numeric_fields": ["tolerance"],
    "boolean_fields": ["included", "required"],
    "roles": {
        "DIRECT_ACCOUNTING": "direct accounting parent",
        "ULTIMATE_ACCOUNTING": "ultimate accounting parent",
        "FUND_MANAGER": "fund manager",
        "contains": "subject contains object",
        "part_of": "subject is part of object",
    },
    "other_fields": {
        "status": "record activity",
        "registration_status": "registration/publication status",
        "legal_status": "entity legal status",
        "snapshot_date": "snapshot date",
        "field": "changed or dependent field identifier",
        "included": "explicit inclusion assertion; absence means positive inclusion",
    },
}
PUBLIC_POLICIES = {
    "version": "authored-business-policy-1",
    "current": "Use ACTIVE records whose inclusive start/end window contains the question date. Finance records also require snapshot_date equal to that date.",
    "impact": {
        "part": "part-A",
        "products": ["product-X", "product-Y"],
        "rule": "Follow current BOM membership transitively from part to containing products, reversing part_of edges. Return only listed products. Incomplete BOM scope yields unknown; contradictory inclusion yields conflict.",
    },
    "replacement": {
        "candidate": "replacement-A",
        "max_tolerance_mm": 0.1,
        "approved_certificates": ["cert-A"],
        "compatibility": "interface-A",
        "rule": "All requirements must hold in current candidate evidence. Missing required evidence or no current record yields unknown; disagreeing current measurements yield conflict. This is declared toy eligibility, not engineering approval.",
    },
    "rechecks": {
        "known_fields": [
            "spec.tolerance",
            "certificate.validity",
            "bom.member",
            "display.color",
        ],
        "rule": "Join current change field to current dependency field; include required=true workitems only. Conflicting required flags yield conflict. Incomplete dependency scope or an unmapped field yields unknown.",
    },
    "reported_parent": "For reported facts use current accounting relationships even when registration_status is LAPSED; disclose LAPSED as a caveat. Multiple distinct parents or a matching exception plus relationship yield conflict. A matching exception without a parent yields reported_exception; absent matching evidence yields unknown. FUND_MANAGER does not establish an accounting parent.",
    "same_ultimate": "Compare explicit ULTIMATE_ACCOUNTING parents for LEI-A and LEI-B only if both are established; missing one yields unknown, not false.",
    "internal_review": "For LEI-A require a current snapshot entity with legal_status ACTIVE and registration_status ISSUED, and a unique current DIRECT_ACCOUNTING relationship with registration_status PUBLISHED. Entity status failure or conflicting reports yields review_required. Missing entity fields or eligible direct evidence yields incomplete; an exception alone cannot complete review. Otherwise review_ready. LAPSED relationships may still be reported facts.",
}
ONTOLOGY = {
    "definitions": {
        "bom": "A membership assertion, not supplier identity.",
        "candidate": "A replacement measurement and certificate claim.",
        "change": "A recorded field change.",
        "dependency": "A field-to-revalidation-workitem rule.",
        "entity": "Entity legal and registration statuses in separate namespaces.",
        "relationship": "A reported role-specific relationship, not beneficial ownership.",
        "exception": "A reporting exception for a specific role, not a named parent.",
    },
    "inverse_roles": {"contains": "part_of"},
    "role_distinctions": "DIRECT_ACCOUNTING is immediate consolidation; ULTIMATE_ACCOUNTING is explicit ultimate consolidation; FUND_MANAGER is a separate service role. None may substitute for another.",
    "units": {
        "mm": {"dimension": "length", "factor_to_mm": 1},
        "um": {"dimension": "length", "factor_to_mm": 0.001},
    },
    "status_distinctions": "ACTIVE legal/relationship status, ISSUED entity registration and PUBLISHED relationship registration are distinct properties and vocabularies. LAPSED registration does not negate a recorded relationship.",
    "limits": "Definitions organize the disclosed policy package. They cannot establish external truth, hidden completeness, or independently verify question interpretation.",
}
ONTOLOGY["roles"] = {
    "impact_membership": {"required_constants": {str(NS.kind): "bom"}},
    "replacement_conditions": {"required_constants": {str(NS.kind): "candidate"}},
    "changed_field": {"required_constants": {str(NS.kind): "change"}},
    "revalidation_dependency": {"required_constants": {str(NS.kind): "dependency"}},
    "direct_accounting_parent": {
        "required_constants": {
            str(NS.kind): "relationship",
            str(NS.relation): "DIRECT_ACCOUNTING",
        }
    },
    "ultimate_accounting_parent": {
        "required_constants": {
            str(NS.kind): "relationship",
            str(NS.relation): "ULTIMATE_ACCOUNTING",
        }
    },
    "entity_review_status": {"required_constants": {str(NS.kind): "entity"}},
    "reporting_exception": {"required_constants": {str(NS.kind): "exception"}},
}
ONTOLOGY["allowed_predicates"] = sorted(
    {str(NS[field]) for fields in KINDS.values() for field in fields}
    | {str(NS[field]) for field in ["id", "kind", "status", "start", "end", "included"]}
    | {str(RDF.type)}
)
ANSWER_CONTRACT = {
    "fields": ["status", "value", "evidence_ids", "caveats"],
    "statuses": [
        "known",
        "eligible",
        "blocked",
        "unknown",
        "conflict",
        "review_ready",
        "review_required",
        "incomplete",
        "reported_exception",
    ],
    "value": "Parent identifier, boolean same-parent comparison, sorted product/workitem list, or null for other statuses.",
    "evidence_ids": "List of bq:id strings supporting the answer; do not use record IRIs.",
    "caveats": "List of short strings; explicitly include LAPSED if relying on LAPSED registration.",
    "clarification": "A clarification request ends the episode unresolved; no scripted answer or automatic completion follows.",
    "instruction": "Return explicit JSON with all four fields. Choose the workflow from the natural-language question; sources may contain unrelated evidence.",
}
QUESTIONS = {
    "M1": "As of 2026-10-12, which of product-X and product-Y are potentially affected by a change to part-A under the published BOM policy?",
    "M2": "As of 2026-10-12, is replacement-A eligible under the published 0.1 mm tolerance, cert-A certificate and interface-A compatibility requirements?",
    "M3": "As of 2026-10-12, which work items require revalidation for the recorded changes under the published dependency policy?",
    "F1": "As of 2026-10-12, what direct accounting parent does LEI-A report? Report facts with registration caveats, without substituting the internal-review eligibility rule.",
    "F2": "As of 2026-10-12, do LEI-A and LEI-B report the same explicit ultimate accounting parent under the published reported-fact policy?",
    "F3": "As of 2026-10-12, is LEI-A ready for internal relationship review under the published ACTIVE/ISSUED entity and PUBLISHED direct-accounting relationship policy?",
}


def shapes_turtle():
    """Shared structural requirements; conformance does not establish task truth."""
    parts = [
        "@prefix bq: <urn:business-questions:> .",
        "@prefix sh: <http://www.w3.org/ns/shacl#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
    ]
    for kind, fields in KINDS.items():
        properties = []
        for field in ["id", "kind", "status", "start", "end"] + fields:
            datatype = "boolean" if field == "required" else "string"
            constraint = (
                "sh:nodeKind sh:Literal"
                if field == "tolerance"
                else f"sh:datatype xsd:{datatype}"
            )
            properties.append(
                f"sh:property [ sh:path bq:{field}; sh:minCount 1; sh:maxCount 1; {constraint} ]"
            )
        if kind == "candidate":
            properties.append('sh:property [ sh:path bq:unit; sh:in ("mm" "um") ]')
        parts.append(
            f"bq:{kind}Shape a sh:NodeShape; sh:targetClass bq:{kind}; "
            + "; ".join(properties)
            + " ."
        )
    return "\n".join(parts) + "\n"


def _expected(status, value=None, ids=(), caveats=()):
    return {
        "status": status,
        "value": value,
        "evidence_ids": sorted(ids),
        "required_caveat_terms": list(caveats),
    }


def build_cases():
    """References below are explicit authored declarations, never validator output."""
    spec = importlib.util.spec_from_file_location(
        "business_seed", Path(__file__).with_name("run_business_questions_study.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seeds = {
        (c["packet"]["task"], c["scenario"]): c["packet"] for c in module.make_cases()
    }
    declarations = [
        (
            "M1",
            "transitive_alias_success",
            _expected("known", ["product-X"], ["b1", "b2"]),
        ),
        ("M1", "missing_evidence", _expected("unknown")),
        ("M1", "conflicting_inclusion", _expected("conflict", ids=["b1", "b2"])),
        ("M2", "equivalent_unit_success", _expected("eligible", ids=["c1"])),
        ("M2", "missing_certificate", _expected("unknown", ids=["c1"])),
        ("M2", "explicit_policy_failure", _expected("blocked", ids=["c1"])),
        (
            "M3",
            "dependency_scoped_success",
            _expected("known", ["fit-review"], ["h1", "d1"]),
        ),
        ("M3", "missing_dependency_declaration", _expected("unknown")),
        (
            "M3",
            "conflicting_dependencies",
            _expected("conflict", ids=["h1", "d2", "d4"]),
        ),
        ("F1", "direct_parent", _expected("known", "LEI-P", ["r1"])),
        (
            "F1",
            "lapsed_reported_parent",
            _expected("known", "LEI-P", ["r1"], ["LAPSED"]),
        ),
        ("F1", "fund_manager_role", _expected("unknown")),
        ("F2", "same_group", _expected("known", True, ["r1", "r2"])),
        ("F2", "expired_second_parent", _expected("unknown")),
        ("F2", "conflicting_ultimate", _expected("conflict", ids=["r1", "r2"])),
        ("F3", "complete_internal_review", _expected("review_ready", ids=["e1", "r1"])),
        ("F3", "stale_relationship", _expected("incomplete", ids=["e1"])),
        ("F3", "status_namespace_swap", _expected("review_required", ids=["e1"])),
    ]
    cases = []
    for number, (family, scenario, expected) in enumerate(declarations, 1):
        seed_name = (
            "direct_parent" if scenario == "lapsed_reported_parent" else scenario
        )
        packet = copy.deepcopy(seeds[(family, seed_name)])
        if scenario == "lapsed_reported_parent":
            packet["observed_records"][0]["registration_status"] = "LAPSED"
        graph = Graph()
        graph.bind("bq", NS)
        for record in packet["observed_records"]:
            subject = NS["record/" + record["id"]]
            graph.add((subject, RDF.type, NS[record["kind"]]))
            for key, value in record.items():
                if value is not None:
                    graph.add((subject, NS[key], Literal(value)))
        runtime = {
            "question": QUESTIONS[family],
            "source_turtle": graph.serialize(format="turtle"),
            "physical_schema": copy.deepcopy(PHYSICAL_SCHEMA),
            "public_policies": copy.deepcopy(PUBLIC_POLICIES),
            "ontology": copy.deepcopy(ONTOLOGY),
            "shapes_turtle": shapes_turtle(),
            "scope_metadata": {
                "snapshot_date": ASOF,
                "complete_bom": packet["internal_policy"].get("complete_bom", True),
                "complete_dependencies": packet["internal_policy"].get(
                    "complete_dependencies", True
                ),
                "source_scope": "Authored bounded snapshot only; omitted fields are source absence, not retrieval omission. No global completeness or external truth claim.",
                "provenance": "Consumed synthetic business-questions-1 development fixtures; no actual GLEIF records; toy manufacturing semantics.",
            },
            "answer_contract": copy.deepcopy(ANSWER_CONTRACT),
        }
        cases.append(
            {
                "case_id": f"case{number:02d}",
                "family": family,
                "scenario": scenario,
                "runtime": runtime,
                "expected": expected,
            }
        )
    return cases


def export_cases(destination):
    """Physically separate scorer data; neither it nor routing metadata is a prompt."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "runtime").mkdir()
    (destination / "scorer").mkdir()
    cases = build_cases()
    for case in cases:
        (destination / "runtime" / f"{case['case_id']}.json").write_text(
            json.dumps(case["runtime"], indent=2) + "\n"
        )
    scorer = [{k: v for k, v in case.items() if k != "runtime"} for case in cases]
    (destination / "scorer" / "references.json").write_text(
        json.dumps(scorer, indent=2) + "\n"
    )
    return cases


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    export_cases(parser.parse_args().output)
