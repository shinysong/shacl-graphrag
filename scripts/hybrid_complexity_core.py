"""Bounded synthetic release decisions; evaluator truth never enters runtime checks.

No claim of real manufacturing correctness: this is an explicitly supplied policy.
RDF is a field projection, SHACL-SPARQL evaluates policy independently of Python.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import re
from datetime import date

from pyshacl import validate
from rdflib import RDF, XSD, BNode, Graph, Literal, Namespace
from rdflib.namespace import SH

EX = Namespace("https://example.org/hybrid/")
ATOMS = ("path", "permitted", "dates", "certificate")
VARIANTS = (
    "clean",
    "known_violation",
    "metadata_violation",
    "source_missing",
    "conforming_false_fact",
)


def _opaque(value):
    return "r" + hashlib.sha256(value.encode()).hexdigest()[:16]


def _uri(value):
    return EX[value]


def _prefix(depth):
    """A fixed-length walk through normalized link records, not inferred truth."""
    return " ".join(
        f"?n{i} ex:outgoing ?l{i} . ?l{i} ex:to ?n{i + 1} ." for i in range(depth)
    )


def _start(c):
    return f"BIND(<{_uri(c['subject_id'])}> AS ?n0)"


def _rules(c):
    """Independent executable SPARQL predicates for known failure/unknown."""
    d = c["depth"]
    start = _start(c)
    whole = _prefix(d)
    root = f"<{_uri(c['trusted_root_id'])}>"
    rules = [
        ("path_missing", "path", "unknown", f"{start} FILTER NOT EXISTS {{ {whole} }}"),
        ("path_wrong_root", "path", "fail", f"{start} {whole} FILTER(?n{d} != {root})"),
    ]
    if c["load"] == "basic":
        return rules
    # Nodes reached by every available prefix are relevant, including partial paths.
    nodes = " UNION ".join(
        "{ " + start + " " + _prefix(i) + f" BIND(?n{i} AS ?node) }}"
        for i in range(d + 1)
    )
    links = " UNION ".join(
        "{ " + start + " " + _prefix(i + 1) + f" BIND(?l{i} AS ?record) }}"
        for i in range(d)
    )
    cert = f"?cert ex:subject <{_uri(c['subject_id'])}> ."
    today = f'"{c["as_of"]}"^^xsd:date'
    rules += [
        (
            "node_metadata_missing",
            "permitted",
            "unknown",
            f"{{ {nodes} }} FILTER NOT EXISTS {{ ?node ex:permitted ?p ; ex:business_class ?k }}",
        ),
        (
            "node_not_permitted",
            "permitted",
            "fail",
            f"{{ {nodes} }} ?node ex:permitted ?p . FILTER(?p = false)",
        ),
        (
            "node_wrong_class",
            "permitted",
            "fail",
            f'{{ {nodes} }} ?node ex:business_class ?k . FILTER((?node = <{_uri(c["subject_id"])}> && ?k != "Release") || (?node != <{_uri(c["subject_id"])}> && ?k != "Organization"))',
        ),
        (
            "record_dates_missing",
            "dates",
            "unknown",
            f"{{ {{ {links} }} UNION {{ {cert} BIND(?cert AS ?record) }} }} FILTER NOT EXISTS {{ ?record ex:valid_from ?a ; ex:valid_to ?b }}",
        ),
        (
            "record_dates_invalid",
            "dates",
            "fail",
            f"{{ {{ {links} }} UNION {{ {cert} BIND(?cert AS ?record) }} }} OPTIONAL {{ ?record ex:valid_from ?a }} OPTIONAL {{ ?record ex:valid_to ?b }} FILTER((BOUND(?a) && ?a > {today}) || (BOUND(?b) && ?b < {today}) || (BOUND(?a) && BOUND(?b) && ?a > ?b))",
        ),
        (
            "certificate_missing",
            "certificate",
            "unknown",
            f"FILTER NOT EXISTS {{ {cert} }}",
        ),
        (
            "certificate_metadata_missing",
            "certificate",
            "unknown",
            f"{cert} FILTER NOT EXISTS {{ ?cert ex:issuer ?i ; ex:status ?s }}",
        ),
        (
            "certificate_unauthorized",
            "certificate",
            "fail",
            f"{cert} ?cert ex:issuer ?i . FILTER(?i != <{_uri(c['authorized_issuer_id'])}>)",
        ),
        (
            "certificate_not_current",
            "certificate",
            "fail",
            f'{cert} ?cert ex:status ?s . FILTER(?s != "current")',
        ),
    ]
    return rules


def _query(body):
    return (
        "PREFIX ex: <https://example.org/hybrid/>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\nSELECT $this WHERE { "
        + body
        + " }"
    )


def formal_contract(c):
    return [
        {"id": i, "atom": a, "severity": s, "select": _query(q)}
        for i, a, s, q in _rules(c)
    ]


def generate_cases():
    cases, truth = [], {}
    for depth, load, distractors, variant, seed in itertools.product(
        (1, 2, 4), ("basic", "full"), (0, 8), VARIANTS, (11, 29)
    ):
        # IDs do not reveal variant or factors; records differ only in declared intervention.
        cohort = f"{depth}:{load}:{distractors}:{seed}"
        rid = lambda label, seed=seed: _opaque(str(seed) + ":" + label)
        nodes = [rid(f"node:{i}") for i in range(depth + 1)]
        c = {
            "kind": "manufacturing_release",
            "depth": depth,
            "load": load,
            "subject_id": nodes[0],
            "trusted_root_id": nodes[-1],
            "as_of": "2026-10-01",
            "authorized_issuer_id": rid("issuer"),
        }
        c["text"] = (
            f"Decide release {nodes[0]} as of {c['as_of']}. Follow exactly {depth} directed links; "
            f"the terminal entity must equal trusted root {nodes[-1]}. A missing link is unknown. "
            "A complete path ending elsewhere fails. "
            + (
                "Additionally every reached entity must be permitted, with business_class Release for the subject and Organization otherwise. "
                "Every traversed link and subject certificate must have inclusive valid_from/valid_to enclosing the as-of date. "
                f"A subject certificate must have issuer {c['authorized_issuer_id']} and status current. "
                "Missing required records or fields are unknown; an observed contrary value fails. "
                if load == "full"
                else "No metadata or certificate constraints apply. "
            )
            + "Any known failure means deny, otherwise any unknown means abstain, otherwise allow. Ignore unrelated records and descriptive names/notes."
        )
        c["formal_query"] = {
            "template": "release_v1",
            "parameters": {
                key: c[key]
                for key in (
                    "depth",
                    "load",
                    "subject_id",
                    "trusted_root_id",
                    "as_of",
                    "authorized_issuer_id",
                )
            },
        }
        records = [
            {
                "id": n,
                "kind": "entity",
                "business_class": "Release" if i == 0 else "Organization",
                "permitted": True,
                "name": f"Manufacturing unit {i}",
                "notes": "Synthetic administrative description; not decision evidence.",
            }
            for i, n in enumerate(nodes)
        ]
        links = [
            {
                "id": rid(f"link:{i}"),
                "kind": "link",
                "from": nodes[i],
                "to": nodes[i + 1],
                "valid_from": "2026-01-01",
                "valid_to": "2026-12-31",
            }
            for i in range(depth)
        ]
        records += links
        records.append(
            {
                "id": rid("cert"),
                "kind": "certificate",
                "subject": nodes[0],
                "issuer": c["authorized_issuer_id"],
                "status": "current",
                "valid_from": "2026-01-01",
                "valid_to": "2026-12-31",
            }
        )
        for i in range(distractors):
            records.append(
                {
                    "id": rid(f"distractor:{i}"),
                    "kind": "entity",
                    "business_class": "Organization",
                    "permitted": False,
                    "name": f"Unrelated vendor {i}",
                    "notes": "Not connected to the questioned release. Administrative note.",
                }
            )
        original = copy.deepcopy(records)
        if variant == "known_violation":
            links[-1]["to"] = rid("untrusted-root")
            original = copy.deepcopy(records)
        elif variant == "metadata_violation":
            if seed == 11:
                next(r for r in records if r["id"] == nodes[1])["permitted"] = False
            else:
                next(r for r in records if r["kind"] == "certificate")["valid_to"] = (
                    "2026-09-30"
                )
            original = copy.deepcopy(records)
        elif variant == "source_missing":
            records.remove(links[-1])
        elif variant == "conforming_false_fact":
            # Runtime source asserts the clean chain. A separate synthetic original
            # world has a different terminal edge; it is NEVER supplied to checks.
            next(r for r in original if r["id"] == links[-1]["id"])["to"] = rid(
                "untrusted-root"
            )
        case_id = _opaque(cohort + ":" + variant)
        case = {
            "id": case_id,
            "question": f"May release {nodes[0]} be approved under the supplied policy?",
            "contract": c,
            "records": records,
        }
        cases.append(case)
        truth[case_id] = {
            "depth": depth,
            "constraint_load": load,
            "distractors": distractors,
            "seed": seed,
            "variant": variant,
            "expected_decision": {
                "known_violation": "deny",
                "source_missing": "abstain",
                "metadata_violation": "deny" if load == "full" else "allow",
            }.get(variant, "allow"),
            "original_truth_decision": "deny"
            if variant in ("known_violation", "conforming_false_fact")
            or (variant == "metadata_violation" and load == "full")
            else "allow",
            "original_records": original,
        }
    return cases, truth


def _validate_case(case):
    if set(case) != {"id", "question", "contract", "records"}:
        raise ValueError("Runtime accepts only id, question, contract and records")
    c = case["contract"]
    if (
        c["kind"] != "manufacturing_release"
        or c["depth"] not in (1, 2, 4)
        or c["load"] not in ("basic", "full")
    ):
        raise ValueError("Unsupported bounded contract")
    expected_parameters = {
        key: c[key]
        for key in (
            "depth",
            "load",
            "subject_id",
            "trusted_root_id",
            "as_of",
            "authorized_issuer_id",
        )
    }
    if c["formal_query"] != {
        "template": "release_v1",
        "parameters": expected_parameters,
    }:
        raise ValueError(
            "Formal query and human-readable contract parameters must agree"
        )
    date.fromisoformat(c["as_of"])
    ids, sources, subjects = set(), set(), set()
    for r in case["records"]:
        for field in ("id", "from", "to", "subject", "issuer"):
            if field in r and not re.fullmatch(r"[A-Za-z0-9_-]+", r[field]):
                raise ValueError("Identifiers must be URI-safe opaque strings")
        if r["id"] in ids:
            raise ValueError("Duplicate record ID")
        ids.add(r["id"])
        if r["kind"] not in ("entity", "link", "certificate"):
            raise ValueError("Unsupported record kind")
        allowed = {"id", "kind", "name", "notes"} | {
            "entity": {"business_class", "permitted"},
            "link": {"from", "to", "valid_from", "valid_to"},
            "certificate": {"subject", "issuer", "status", "valid_from", "valid_to"},
        }[r["kind"]]
        if set(r) - allowed:
            raise ValueError("Field is not part of the normalized record schema")
        if r["kind"] == "link":
            if r["from"] in sources:
                raise ValueError(
                    "Contract requires at most one outgoing link per entity"
                )
            sources.add(r["from"])
        if r["kind"] == "certificate":
            if r["subject"] in subjects:
                raise ValueError(
                    "Contract requires at most one certificate per subject"
                )
            subjects.add(r["subject"])
        if "permitted" in r and type(r["permitted"]) is not bool:
            raise ValueError("permitted must be boolean")
        for key in ("valid_from", "valid_to"):
            if key in r and date.fromisoformat(r[key]).isoformat() != r[key]:
                raise ValueError("Dates must use YYYY-MM-DD")


def _result(c, issues, evidence):
    issues = sorted(issues, key=lambda v: v["id"])
    atoms = {}
    for atom in ATOMS:
        statuses = {i["severity"] for i in issues if i["atom"] == atom}
        atoms[atom] = (
            "not_applicable"
            if atom != "path" and c["load"] == "basic"
            else "fail"
            if "fail" in statuses
            else "unknown"
            if statuses
            else "pass"
        )
    decision = (
        "deny"
        if "fail" in atoms.values()
        else "abstain"
        if "unknown" in atoms.values()
        else "allow"
    )
    return {
        "decision": decision,
        "atoms": atoms,
        "issues": issues,
        "evidence_ids": sorted(set(evidence)),
    }


def check_python(case):
    _validate_case(case)
    c, records = case["contract"], case["records"]
    by_id = {r["id"]: r for r in records}
    outgoing = {r["from"]: r for r in records if r["kind"] == "link"}
    nodes, links, issues = [c["subject_id"]], [], []

    def issue(i, a, s):
        item = {"id": i, "atom": a, "severity": s}
        if item not in issues:
            issues.append(item)

    for _ in range(c["depth"]):
        link = outgoing.get(nodes[-1])
        if link is None:
            issue("path_missing", "path", "unknown")
            break
        links.append(link)
        nodes.append(link["to"])
    if len(links) == c["depth"] and nodes[-1] != c["trusted_root_id"]:
        issue("path_wrong_root", "path", "fail")
    certs = [
        r
        for r in records
        if r["kind"] == "certificate" and r["subject"] == c["subject_id"]
    ]
    if c["load"] == "full":
        for node in nodes:
            r = by_id.get(node, {})
            if "permitted" not in r or "business_class" not in r:
                issue("node_metadata_missing", "permitted", "unknown")
            if r.get("permitted") is False:
                issue("node_not_permitted", "permitted", "fail")
            if "business_class" in r and r["business_class"] != (
                "Release" if node == c["subject_id"] else "Organization"
            ):
                issue("node_wrong_class", "permitted", "fail")
        for r in links + certs:
            if "valid_from" not in r or "valid_to" not in r:
                issue("record_dates_missing", "dates", "unknown")
            if ("valid_from" in r and r["valid_from"] > c["as_of"]) or (
                "valid_to" in r and r["valid_to"] < c["as_of"]
            ):
                issue("record_dates_invalid", "dates", "fail")
        if not certs:
            issue("certificate_missing", "certificate", "unknown")
        for r in certs:
            if "issuer" not in r or "status" not in r:
                issue("certificate_metadata_missing", "certificate", "unknown")
            if "issuer" in r and r["issuer"] != c["authorized_issuer_id"]:
                issue("certificate_unauthorized", "certificate", "fail")
            if "status" in r and r["status"] != "current":
                issue("certificate_not_current", "certificate", "fail")
    evidence = [n for n in nodes if n in by_id] + [r["id"] for r in links]
    if c["load"] == "full":
        evidence += [r["id"] for r in certs]
    return _result(c, issues, evidence)


def project_rdf(case):
    _validate_case(case)
    g = Graph()
    g.bind("ex", EX)
    for r in case["records"]:
        node = _uri(r["id"])
        g.add((node, RDF.type, EX[r["kind"]]))
        g.add((node, EX.record_id, Literal(r["id"])))
        for key in (
            "from",
            "to",
            "subject",
            "issuer",
            "permitted",
            "business_class",
            "valid_from",
            "valid_to",
            "status",
        ):
            if key not in r:
                continue
            value = (
                _uri(r[key])
                if key in ("from", "to", "subject", "issuer")
                else Literal(r[key], datatype=XSD.date)
                if key in ("valid_from", "valid_to")
                else Literal(r[key])
            )
            g.add((node, EX[key], value))
        if r["kind"] == "link":
            g.add((_uri(r["from"]), EX.outgoing, node))
    return g


def check_shacl(case):
    g = project_rdf(case)
    c = case["contract"]
    shapes = Graph()
    shapes.bind("ex", EX)
    shapes.bind("sh", SH)
    for ident, atom, severity, body in _rules(c):
        shape, constraint = EX[ident], BNode()
        shapes.add((shape, RDF.type, SH.NodeShape))
        shapes.add((shape, SH.targetNode, _uri(c["subject_id"])))
        shapes.add(
            (shape, SH.severity, SH.Warning if severity == "unknown" else SH.Violation)
        )
        shapes.add((shape, SH.sparql, constraint))
        shapes.add((constraint, SH.select, Literal(_query(body))))
        shapes.add((constraint, SH.message, Literal(ident)))
    conforms, report, _ = validate(
        g, shacl_graph=shapes, advanced=True, allow_warnings=True
    )
    rule_meta = {i: (a, s) for i, a, s, _ in _rules(c)}
    issues = []
    for result in report.subjects(RDF.type, SH.ValidationResult):
        ident = str(report.value(result, SH.resultMessage))
        atom, severity = rule_meta[ident]
        issue = {"id": ident, "atom": atom, "severity": severity}
        if issue not in issues:
            issues.append(issue)
    evidence = []
    for i in range(c["depth"] + 1):
        for row in g.query(
            "PREFIX ex: <https://example.org/hybrid/> SELECT ?id WHERE { "
            + _start(c)
            + " "
            + _prefix(i)
            + f" ?n{i} ex:record_id ?id . }}"
        ):
            evidence.append(str(row.id))
        if i:
            for row in g.query(
                "PREFIX ex: <https://example.org/hybrid/> SELECT ?id WHERE { "
                + _start(c)
                + " "
                + _prefix(i)
                + f" ?l{i - 1} ex:record_id ?id . }}"
            ):
                evidence.append(str(row.id))
    if c["load"] == "full":
        for row in g.query(
            f"PREFIX ex: <https://example.org/hybrid/> SELECT ?id WHERE {{ ?r ex:subject <{_uri(c['subject_id'])}> ; ex:record_id ?id }}"
        ):
            evidence.append(str(row.id))
    result = _result(c, issues, evidence)
    result.update(
        conforms=bool(conforms),
        rdf_turtle=g.serialize(format="turtle"),
        shapes_turtle=shapes.serialize(format="turtle"),
        report_turtle=report.serialize(format="turtle"),
    )
    return result


def projection_stats(case):
    graph = project_rdf(case)
    return {
        "source_json_bytes": len(
            json.dumps(case["records"], ensure_ascii=False, sort_keys=True).encode()
        ),
        "rdf_turtle_bytes": len(graph.serialize(format="turtle").encode()),
        "record_count": len(case["records"]),
        "triple_count": len(graph),
        "source_field_count": sum(len(r) for r in case["records"]),
        "projected_field_count": sum(
            sum(
                k
                in {
                    "id",
                    "kind",
                    "from",
                    "to",
                    "subject",
                    "issuer",
                    "permitted",
                    "business_class",
                    "valid_from",
                    "valid_to",
                    "status",
                }
                for k in r
            )
            for r in case["records"]
        ),
        "omitted_descriptive_field_count": sum(
            sum(k in {"name", "notes"} for k in r) for r in case["records"]
        ),
    }
