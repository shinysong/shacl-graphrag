"""Bounded local RDF tools; checks establish declared contracts, never question truth.

Only supplied Turtle strings are parsed. Workers have no query-selected file paths,
network calls are disabled, and OS address-space/deadline limits bound execution.
These are bounded application guards, not a general hostile-code sandbox.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 5
MEMORY_BYTES = 512 * 1024 * 1024
MAX_ROWS = 100
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 128 * 1024
NS = "urn:business-questions:"
LIMITS = {
    "timeout_seconds": TIMEOUT_SECONDS,
    "memory_bytes": MEMORY_BYTES,
    "max_rows": MAX_ROWS,
}


def _call(operation, **arguments):
    payload = json.dumps({"operation": operation, **arguments})
    if len(payload.encode()) > MAX_INPUT_BYTES:
        return {"status": "error", "error_type": "input_limit", "limits": LIMITS}
    try:
        worker = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, _ = worker.communicate(payload.encode(), timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.communicate()
            return {"status": "error", "error_type": "timeout", "limits": LIMITS}
        except BaseException:
            worker.kill()
            worker.communicate()
            raise
        if worker.returncode:
            return {
                "status": "error",
                "error_type": "worker_resource_or_process_failure",
                "limits": LIMITS,
            }
        result = json.loads(stdout)
        result["limits"] = LIMITS
        return result
    except (OSError, ValueError) as exc:
        return {"status": "error", "error_type": type(exc).__name__, "limits": LIMITS}


def execute_query(turtle: str, query: str) -> dict:
    """Execute local SELECT/ASK. Explicit LIMIT never certifies source completeness."""
    return _call("query", turtle=turtle, query=query)


def check_query_contract(query: str, interpretation: dict, ontology: dict) -> dict:
    """Check positive basic-pattern constants against a published role contract.

    ontology.roles[interpretation.role].required_constants maps predicate IRIs to
    literal strings. Optional allowed_predicates constrains vocabulary. Unsupported
    algebra (including FILTER/path/UNION) is unknown, never a semantic pass.
    No evaluator intent, expected answer or reference record is accepted here.
    """
    return _call(
        "contract", query=query, interpretation=interpretation, ontology=ontology
    )


def check_evidence(turtle: str, record_ids: list[str], shapes_turtle: str) -> dict:
    """Run pySHACL on outgoing triples of selected flat records, without inference."""
    return _call(
        "evidence", turtle=turtle, record_ids=record_ids, shapes_turtle=shapes_turtle
    )


def _walk(value):
    from rdflib.plugins.sparql.parserutils import CompValue

    if isinstance(value, CompValue):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _walk(item)


def _prepare(query):
    from rdflib.plugins.sparql import prepareQuery
    from rdflib.plugins.sparql.parser import parseQuery

    parsed = parseQuery(query)
    root = parsed[1]
    if root.name not in {"SelectQuery", "AskQuery"}:
        raise ValueError("only local SELECT and ASK are allowed")
    for node in _walk(root):
        if node.name in {"ServiceGraphPattern", "DatasetClause", "Function"}:
            raise ValueError("SERVICE, FROM and extension functions are disabled")
    return prepareQuery(query)


def _query(turtle, query):
    from rdflib import Graph, URIRef

    prepared = _prepare(query)
    graph = Graph().parse(data=turtle, format="turtle")
    explicit_limit = any(
        n.name == "Slice" and "length" in n for n in _walk(prepared.algebra)
    )
    result = graph.query(prepared)
    response = {
        "status": "ok",
        "rows": [],
        "boolean": None,
        "source_ids": [],
        "truncated": False,
        "explicit_limit": explicit_limit,
        "completeness": "unknown",
        "completeness_note": "LIMIT, projection and query selection cannot establish complete source coverage.",
    }
    if result.type == "ASK":
        response["boolean"] = bool(result.askAnswer)
        return response
    ids = set()
    known_ids = {str(value) for value in graph.objects(None, URIRef(NS + "id"))}
    for index, row in enumerate(result):
        if index >= MAX_ROWS:
            response["truncated"] = True
            break
        binding = {}
        for variable, value in row.asdict().items():
            string = str(value)
            if len(string) > 4096:
                response["truncated"] = True
                string = string[:4096]
            binding[str(variable)] = string
            if str(value) in known_ids:
                ids.add(str(value))
            for identifier in graph.objects(value, URIRef(NS + "id")):
                ids.add(str(identifier))
        response["rows"].append(binding)
    response["source_ids"] = sorted(ids)
    return response


def _contract(query, interpretation, ontology):
    from rdflib import Literal, URIRef
    from rdflib.paths import Path as RDFPath

    prepared = _prepare(query)
    nodes = list(_walk(prepared.algebra))
    response = {
        "status": "unknown",
        "checked_scope": "positive BGP role constants and declared predicate vocabulary only",
        "rule_ids": [],
        "witnesses": [],
        "limitations": [
            "Model interpretation may be wrong; natural-language intent is not verified.",
            "Date, unit, domain/range, completeness and external truth are not verified.",
        ],
    }
    unsupported = sorted(
        {n.name for n in nodes}
        - {"SelectQuery", "AskQuery", "Project", "BGP", "Distinct", "Reduced", "Slice"}
    )
    triples = [t for n in nodes if n.name == "BGP" for t in n.triples]
    if unsupported or any(isinstance(p, RDFPath) for _, p, _ in triples):
        response["unsupported_constructs"] = unsupported or ["property_path"]
        return response
    role = interpretation.get("role")
    contract = ontology.get("roles", {}).get(role)
    if not isinstance(contract, dict) or not contract.get("required_constants"):
        response["reason"] = (
            "No supported published role contract for declared interpretation."
        )
        return response
    if any(not isinstance(p, URIRef) for _, p, _ in triples):
        response["reason"] = "Variable predicates are unsupported."
        return response
    allowed = ontology.get("allowed_predicates")
    if allowed is not None:
        response["rule_ids"].append("declared-predicate-vocabulary")
        for _, predicate, _ in triples:
            if str(predicate) not in allowed:
                response["witnesses"].append(
                    {"predicate": str(predicate), "finding": "undeclared_predicate"}
                )
    # Every required constant must constrain the SAME record variable/subject.
    subjects = {subject for subject, _, _ in triples}
    matches = set(subjects)
    for predicate, constant in contract["required_constants"].items():
        response["rule_ids"].append("role-constant:" + predicate)
        matches &= {
            subject
            for subject, p, obj in triples
            if str(p) == predicate
            and isinstance(obj, Literal)
            and str(obj) == str(constant)
        }
    if not matches:
        response["witnesses"].append(
            {"finding": "required_role_constants_not_jointly_bound", "role": role}
        )
    response["status"] = "fail" if response["witnesses"] else "pass"
    return response


def _evidence(turtle, record_ids, shapes_turtle):
    from pyshacl import validate
    from rdflib import Graph, Literal, URIRef

    graph = Graph().parse(data=turtle, format="turtle")
    shapes = Graph().parse(data=shapes_turtle, format="turtle")
    sh = "http://www.w3.org/ns/shacl#"
    # Published shapes must remain local and declarative; do not run embedded code.
    forbidden = {
        sh + x
        for x in (
            "sparql",
            "js",
            "jsFunctionName",
            "rule",
            "nodeValidator",
            "select",
            "ask",
        )
    }
    if any(str(p) in forbidden for _, p, _ in shapes):
        return {
            "status": "unknown",
            "conforms": None,
            "coverage": "unknown",
            "reason": "Executable shapes are unsupported.",
        }
    selected = Graph()
    missing = []
    found = []
    for identifier in sorted(set(record_ids)):
        subjects = list(graph.subjects(URIRef(NS + "id"), Literal(identifier)))
        if not subjects:
            missing.append(identifier)
        else:
            found.append(identifier)
        for subject in subjects:
            for triple in graph.triples((subject, None, None)):
                selected.add(triple)
    conforms, report, _ = validate(
        selected,
        shacl_graph=shapes,
        inference="none",
        advanced=False,
        js=False,
        do_owl_imports=False,
        meta_shacl=False,
    )
    results = []
    for result in report.subjects(URIRef(sh + "resultSeverity"), None):
        item = {}
        for key in (
            "focusNode",
            "resultPath",
            "sourceShape",
            "sourceConstraintComponent",
            "resultMessage",
        ):
            item[key] = [
                str(v)[:4096] for v in report.objects(result, URIRef(sh + key))
            ]
        results.append(item)
        if len(results) >= MAX_ROWS:
            break
    targets = set(shapes.objects(None, URIRef(sh + "targetClass")))
    from rdflib import RDF

    applicable = bool(
        set(selected.objects(None, RDF.type)) & targets
        or any(
            s in set(selected.subjects())
            for s in shapes.objects(None, URIRef(sh + "targetNode"))
        )
    )
    return {
        "status": "fail"
        if not conforms
        else ("unknown" if missing or not applicable else "pass"),
        "conforms": bool(conforms),
        "coverage": "unknown",
        "source_ids": found,
        "missing_record_ids": missing,
        "results": results,
        "checked_scope": "outgoing triples of selected flat records; published SHACL only",
        "limitations": [
            "Missing properties are not factual falsity.",
            "Source versus retrieval omission is not resolved.",
            "Conformance does not certify factual truth or question applicability.",
        ],
    }


def _worker():
    import resource
    import socket

    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))

    def denied(*args, **kwargs):
        raise PermissionError("network disabled")

    class DisabledSocket(socket.socket):
        def __new__(cls, *args, **kwargs):
            raise PermissionError("network disabled")

    socket.socket = DisabledSocket
    socket.create_connection = denied
    socket.getaddrinfo = denied
    try:
        args = json.loads(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
        operation = args.pop("operation")
        result = {"query": _query, "contract": _contract, "evidence": _evidence}[
            operation
        ](**args)
    except Exception as exc:  # noqa: BLE001 - serialize all worker failures without losing calls
        result = {
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc)[:1000],
        }
    serialized = json.dumps(result)
    if len(serialized.encode()) > MAX_OUTPUT_BYTES:
        serialized = json.dumps({"status": "error", "error_type": "output_limit"})
    sys.stdout.write(serialized)


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    _worker()
