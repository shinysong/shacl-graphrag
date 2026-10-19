"""Offline supplied-role presence only; never approval, identity, or truth validation."""

import pyshacl
from rdflib import RDF, BNode, Graph, Literal, Namespace
from rdflib.collection import Collection
from rdflib.namespace import SH

POLICY_V1 = {"version": "v1", "base_roles": ["methods", "implementation"],
             "conditional_roles": []}
POLICY_V2 = {"version": "v2", "base_roles": ["methods", "implementation"],
             "conditional_roles": [{"field": "data_change", "equals": True,
                                    "role": "data-steward"}]}
EX = Namespace("urn:offline-required-roles:")


def _roles(value):
    return (type(value) is list and len(value) <= 20
            and all(type(r) is str and 0 < len(r) <= 80 and r.strip() == r
                    for r in value) and len(set(value)) == len(value))


def _payload_ok(payload):
    return (type(payload) is dict
            and set(payload) == {"data_change", "completed_roles", "coverage"}
            and (payload["data_change"] is None or type(payload["data_change"]) is bool)
            and _roles(payload["completed_roles"])
            and type(payload["coverage"]) is str
            and payload["coverage"] in ("complete", "partial"))


def _policy_ok(policy):
    if not (type(policy) is dict
            and set(policy) == {"version", "base_roles", "conditional_roles"}
            and type(policy["version"]) is str and policy["version"] in ("v1", "v2")
            and _roles(policy["base_roles"])
            and type(policy["conditional_roles"]) is list
            and len(policy["conditional_roles"]) <= 20):
        return False
    seen = set()
    for rule in policy["conditional_roles"]:
        if not (type(rule) is dict and set(rule) == {"field", "equals", "role"}
                and rule["field"] == "data_change" and rule["equals"] is True
                and _roles([rule["role"]]) and rule["role"] not in seen):
            return False
        seen.add(rule["role"])
    return True


def _result(decision, reason, *, status="evaluated", executed=False, conforms=None):
    return {"status": status, "decision": decision, "reason": reason,
            "actual_shacl_executed": executed, "shacl_conforms": conforms}


def _invalid():
    return _result("unknown", "invalid_input_or_policy", status="invalid")


def _finish(present, coverage, **metadata):
    if present:
        return _result("satisfied", "required_roles_witnessed", **metadata)
    if coverage == "complete":
        return _result("missing", "required_roles_not_witnessed", **metadata)
    return _result("unknown", "partial_role_evidence", **metadata)


def evaluate_coded(payload, version):
    """Explicit v1/v2 business logic; does not read declarative policies."""
    if not _payload_ok(payload) or type(version) is not str or version not in ("v1", "v2"):
        return _invalid()
    if version == "v2" and payload["data_change"] is None:
        return _result("unknown", "unknown_condition")
    completed = payload["completed_roles"]
    present = "methods" in completed and "implementation" in completed
    if version == "v2" and payload["data_change"]:
        present = present and "data-steward" in completed
    return _finish(present, payload["coverage"])


def _preflight(payload, policy):
    if not _payload_ok(payload) or not _policy_ok(policy):
        return _invalid()
    if policy["conditional_roles"] and payload["data_change"] is None:
        return _result("unknown", "unknown_condition")
    return None


def evaluate_json(payload, policy):
    """Interpret the bounded grammar, independently of coded role names."""
    early = _preflight(payload, policy)
    if early is not None:
        return early
    required = list(policy["base_roles"])
    for rule in policy["conditional_roles"]:
        if payload[rule["field"]] is rule["equals"]:
            required.append(rule["role"])
    return _finish(all(role in payload["completed_roles"] for role in required),
                   payload["coverage"])


def _has_value(graph, shape, path, value):
    prop = BNode()
    graph.add((shape, SH.property, prop))
    graph.add((prop, SH.path, path))
    graph.add((prop, SH.hasValue, Literal(value)))


def evaluate_rdf(payload, policy):
    """Compile policy into actual SHACL; membership is decided by pySHACL."""
    early = _preflight(payload, policy)
    if early is not None:
        return early
    invoked = False
    try:
        data, shapes = Graph(), Graph()
        for role in payload["completed_roles"]:
            data.add((EX.record, EX.completed_role, Literal(role)))
        if payload["data_change"] is not None:
            data.add((EX.record, EX.data_change, Literal(payload["data_change"])))
        root = EX.RequiredRoles
        shapes.add((root, RDF.type, SH.NodeShape))
        shapes.add((root, SH.targetNode, EX.record))
        for role in policy["base_roles"]:
            _has_value(shapes, root, EX.completed_role, role)
        for rule in policy["conditional_roles"]:
            condition, inactive, witnessed, choices = (BNode() for _ in range(4))
            shapes.add((root, SH.node, condition))
            shapes.add((condition, SH["or"], choices))
            Collection(shapes, choices, [inactive, witnessed])
            _has_value(shapes, inactive, EX.data_change, False)
            _has_value(shapes, witnessed, EX.completed_role, rule["role"])
        invoked = True
        conforms, _, report = pyshacl.validate(data, shacl_graph=shapes,
                                              inference="none", advanced=False)
        if type(conforms) is not bool:
            raise ValueError("validator returned no Boolean conformance")
        result = _finish(conforms, payload["coverage"], executed=True, conforms=conforms)
        result["report_text"] = str(report)[:4000]
        return result
    except Exception as exc:  # noqa: BLE001 - validator failures must remain unknown
        return _result("unknown", "shacl_exception:" + type(exc).__name__,
                       executed=invoked)
