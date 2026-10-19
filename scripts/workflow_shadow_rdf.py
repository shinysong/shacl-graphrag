"""Offline RDF counterpart to single-event-1; immutable, callable small-case check.

SHACL redundantly validates converted structure after shared JSON preflight. It
cannot discover omitted source evidence or establish semantic/external truth.
Coverage is supplied; no history, DB, OWL, model, or live enforcement. The Python
object API allocates serialized bytes before checking size, not memory isolation.
"""
from collections import deque
import hashlib

import pyshacl
from rdflib import BNode, Graph, Literal, Namespace, RDF, XSD

from scripts.workflow_shadow_impact import MAX_BYTES, canonical, envelope, validate

W = Namespace("urn:workflow-shadow:")
SHAPES = """
@prefix w: <urn:workflow-shadow:> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
w:NodeShape a sh:NodeShape ; sh:targetClass w:Node ;
  sh:property [ sh:path w:id ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path w:version ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] ;
  sh:property [ sh:path w:dependsOn ; sh:class w:Node ] .
"""


def encode(snapshot):
    """IDs and versions are literals, never executable query/IRI fragments."""
    graph = Graph()
    terms = {node["id"]: BNode() for node in snapshot["nodes"]}
    for node in snapshot["nodes"]:
        subject = terms[node["id"]]
        graph.add((subject, RDF.type, W.Node))
        graph.add((subject, W.id, Literal(node["id"], datatype=XSD.string)))
        graph.add((subject, W.version, Literal(node["version"], datatype=XSD.string)))
    for edge in snapshot["edges"]:
        graph.add((terms[edge["dependent"]], W.dependsOn, terms[edge["prerequisite"]]))
    return graph, terms


def result(payload, errors, digest=None, rows=None, executed=False, conforms=None):
    output = envelope(payload, errors, digest, rows)
    output.update(evaluator="rdf_pyshacl", actual_shacl_executed=executed,
                  shacl_conforms=conforms)
    return output


def evaluate(payload):
    """Same preflight contract; independent traversal using RDF graph.objects.

    actual_shacl_executed means the validator was invoked, including a raised
    exception; shacl_conforms is null unless a boolean result was returned.
    """
    try:
        if len(canonical(payload)) > MAX_BYTES:
            return result(payload, ["payload_byte_limit"])
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        return result(payload, ["invalid_json_value"])
    error = validate(payload)
    if error:
        return result(payload, [error])
    executed, conforms = False, None
    try:
        snapshot = payload["snapshot"]
        graph, terms = encode(snapshot)
        shapes = Graph().parse(data=SHAPES, format="turtle")
        executed = True
        conforms, _, _ = pyshacl.validate(graph, shacl_graph=shapes, inference="none",
                                         advanced=False, inplace=False)
        if type(conforms) is not bool:
            conforms = None
            return result(payload, ["shacl_result_unknown"], executed=True)
        if not conforms:
            return result(payload, ["shacl_nonconformance"], executed=True, conforms=False)
        ids = {term: identifier for identifier, term in terms.items()}
        target = terms[payload["change"]["node_id"]]
        rows = []
        for candidate in sorted(payload["candidates"]):
            start = terms[candidate]
            queue, visited, witness = deque([[start]]), {start}, []
            while queue:
                path = queue.popleft()
                if path[-1] == target:
                    witness = [ids[term] for term in path]
                    break
                for neighbor in sorted(graph.objects(path[-1], W.dependsOn), key=ids.__getitem__):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(path + [neighbor])
            if witness:
                impact, reason = "stale", "recorded_dependency_path"
            elif snapshot["coverage"] == "complete":
                impact, reason = "unaffected", "no_path_complete_coverage"
            else:
                impact, reason = "unknown", "no_path_partial_coverage"
            rows.append(dict(id=candidate, impact=impact, reasons=[reason], witness_path=witness))
        digest = hashlib.sha256(canonical(snapshot)).hexdigest()
        return result(payload, [], digest, rows, executed=True, conforms=True)
    except Exception:
        # Fail closed without exposing arbitrary exception details or partial rows.
        return result(payload, ["rdf_validation_or_execution_error"],
                      executed=executed, conforms=conforms)
