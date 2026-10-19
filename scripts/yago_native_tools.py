"""Bounded local YAGO tools, with no scorer access or question-intent repair.

The caller supplies pinned source, original shape bytes and trusted taxonomy.
Workers disable networking; this is an application guard, not an OS sandbox.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

MEMORY_BYTES = 512 * 1024 * 1024
MAX_TRIPLES = 100
MAX_OUTPUT_BYTES = 128 * 1024
MAX_INPUT_BYTES = 4 * 1024 * 1024


def _text(value):
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _call(operation, **arguments):
    timeout = 10 if operation == "query" else 30
    limits = {
        "timeout_seconds": timeout,
        "memory_bytes": MEMORY_BYTES,
        "max_triples": MAX_TRIPLES,
        "max_output_bytes": MAX_OUTPUT_BYTES,
    }
    payload = json.dumps(dict(operation=operation, **arguments)).encode()
    if len(payload) > MAX_INPUT_BYTES:
        return {"status": "error", "error_type": "input_limit", "limits": limits}
    try:
        worker = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, _ = worker.communicate(payload, timeout=timeout)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.communicate()
            return {"status": "error", "error_type": "timeout", "limits": limits}
        except BaseException:
            worker.kill()
            worker.communicate()
            raise
        if worker.returncode:
            return {
                "status": "error",
                "error_type": "worker_resource_or_process_failure",
                "limits": limits,
            }
        if len(stdout) > MAX_OUTPUT_BYTES:
            return {
                "status": "error",
                "error_type": "output_limit",
                "truncated": True,
                "limits": limits,
            }
        result = json.loads(stdout)
        result["limits"] = limits
        return result
    except (OSError, ValueError) as exc:
        return {"status": "error", "error_type": type(exc).__name__, "limits": limits}


def query(source_turtle: str | bytes, query: str) -> dict:
    """SELECT exactly ?s ?p ?o; rows and evidence contain only source triples.

    Terms are N3, retaining URI/literal distinctions, datatypes and language.
    No CONSTRUCT or ASK. Wrong predicates can produce an ordinary empty result.
    Any non-source/unbound binding rejects the returned result, without repair.
    Explicit LIMIT and all successful results retain unknown completeness.
    """
    return _call("query", source_turtle=_text(source_turtle), query=query)


def validate_evidence(
    evidence_turtle: str | bytes,
    shapes_turtle: str | bytes,
    taxonomy_turtle: str | bytes,
    subject_iri: str,
) -> dict:
    """Actual original SHACL validation, with run_yago_pilot.inspect filtering.

    Evaluate all shapes first (no pySHACL focus_nodes restriction); then retain
    report results focused on subject or its retrieved schema:birthPlace objects.
    This preserves nested literal datatype checks. Empty/absent/untyped subjects
    are unknown. Pass concerns applicable evidence only, never completeness or
    truth. Missing source and omitted retrieval cannot be distinguished here.
    """
    return _call(
        "validate",
        evidence_turtle=_text(evidence_turtle),
        shapes_turtle=_text(shapes_turtle),
        taxonomy_turtle=_text(taxonomy_turtle),
        subject_iri=subject_iri,
    )


def _query(source_turtle, query):
    import rdflib
    from ontology_tools import _prepare, _walk
    from rdflib import Graph

    rdflib.NORMALIZE_LITERALS = False
    prepared = _prepare(query)
    if prepared.algebra.name != "SelectQuery":
        raise ValueError("Only SELECT ?s ?p ?o is supported")
    graph = Graph().parse(data=source_turtle, format="turtle")
    result = graph.query(prepared)
    if {str(v) for v in result.vars} != {"s", "p", "o"} or len(result.vars) != 3:
        raise ValueError("SELECT must project exactly s, p, o")
    response = {
        "status": "ok",
        "rows": [],
        "evidence_turtle": "",
        "truncated": False,
        "cap_reasons": [],
        "completeness": "unknown",
        "explicit_limit": any(
            n.name == "Slice" and "length" in n for n in _walk(prepared.algebra)
        ),
    }
    for index, row in enumerate(result):
        if index >= MAX_TRIPLES:
            response["truncated"] = True
            response["cap_reasons"].append("row_limit")
            break
        terms = tuple(row[v] for v in ("s", "p", "o"))
        if None in terms or terms not in graph:
            raise ValueError("Returned binding is not an actual source triple")
        binding = dict(zip(("s", "p", "o"), (v.n3() for v in terms)))
        line = " ".join(binding[v] for v in ("s", "p", "o")) + " .\n"
        response["rows"].append(binding)
        response["evidence_turtle"] += line
        # Leave room for flags and parent-added resource metadata; never cut a term.
        if len(json.dumps(response).encode()) > MAX_OUTPUT_BYTES - 2048:
            response["rows"].pop()
            response["evidence_turtle"] = response["evidence_turtle"][: -len(line)]
            response["truncated"] = True
            response["cap_reasons"].append("output_limit")
            break
    response["triple_count"] = len(
        {tuple(row[v] for v in ("s", "p", "o")) for row in response["rows"]}
    )
    return response


def _validate(evidence_turtle, shapes_turtle, taxonomy_turtle, subject_iri):
    import rdflib
    from rdflib import RDF, RDFS, SH, Graph, URIRef
    from run_yago_pilot import inspect

    rdflib.NORMALIZE_LITERALS = False
    graph = Graph().parse(data=evidence_turtle, format="turtle")
    shapes = Graph().parse(data=shapes_turtle, format="turtle")
    taxonomy = Graph().parse(data=taxonomy_turtle, format="turtle")
    subject = URIRef(subject_iri)
    response = {
        "status": "unknown",
        "conforms": None,
        "completeness": "unknown",
        "issues": [],
        "truncated": False,
        "checked_scope": "subject and retrieved birthPlace objects; post-validation report filtering",
        "limitations": [
            "Conformance does not establish complete retrieval, question applicability or truth.",
            "Source absence and retrieval omission are unresolved.",
        ],
    }
    executable = {
        SH.sparql,
        SH.js,
        SH.rule,
        SH.target,
        SH.select,
        SH.ask,
        SH.construct,
        SH.jsFunctionName,
        SH.jsLibrary,
        SH.jsLibraryURL,
    }
    if any(p in executable for g in (shapes, taxonomy, graph) for _, p, _ in g):
        response["reason"] = "executable_shapes_unsupported"
        return response
    if not len(graph) or not any(graph.triples((subject, None, None))):
        response["reason"] = "empty_evidence" if not len(graph) else "absent_subject"
        return response
    hierarchy = taxonomy + shapes
    classes = set()
    for cls in graph.objects(subject, RDF.type):
        classes.update(hierarchy.transitive_objects(cls, RDFS.subClassOf))
    implicit = set(shapes.subjects(RDF.type, SH.NodeShape)) & set(
        shapes.subjects(RDF.type, RDFS.Class)
    )
    applicable = bool(classes & (implicit | set(shapes.objects(None, SH.targetClass))))
    applicable |= (None, SH.targetNode, subject) in shapes
    if not applicable:
        response["reason"] = "no_applicable_subject_shape"
        return response
    conforms, _, issues, elapsed = inspect(graph, shapes, taxonomy, subject)
    response.update(
        status="pass" if conforms else "fail",
        conforms=conforms,
        issues=issues[:MAX_TRIPLES],
        truncated=len(issues) > MAX_TRIPLES,
        elapsed_ms=elapsed,
    )
    return response


def _worker():
    import resource
    import socket

    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))

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
        if operation == "query":
            resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        result = {"query": _query, "validate": _validate}[operation](**args)
    except Exception as exc:  # noqa: BLE001 - serialize failed tool attempts
        result = {
            "status": "error",
            "error_type": type(exc).__name__,
            "message": str(exc)[:1000],
        }
    serialized = json.dumps(result)
    if len(serialized.encode()) > MAX_OUTPUT_BYTES:
        serialized = json.dumps(
            {"status": "error", "error_type": "output_limit", "truncated": True}
        )
    sys.stdout.write(serialized)


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    _worker()
