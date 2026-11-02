"""Evidence-only deterministic checks; execution success is not conformance.

No reader or corpus/scorer access exists here. This software boundary is not an
OS sandbox. Only ordered selected chunk payloads are parsed.
"""

import hashlib
import json

RULE_VERSION = "graphrag-evidence-check-1"
_RELATIONS = {"defect": "defect_code", "welding_setting": "welding_settings_code"}


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite JSON number")


def _compare(checks):
    conflicts = [name for name, left, right in checks
                 if left is not None and right is not None
                 and canonical_bytes(left) != canonical_bytes(right)]
    missing = [name for name, left, right in checks if left is None or right is None]
    if conflicts:
        return "violation", "conflicting " + ", ".join(conflicts)
    if missing:
        return "unknown", "missing " + ", ".join(missing)
    return "pass", "selected reference metadata agrees"


def _binding(annotation, target, field):
    if target is None:
        return "unknown", "declared target is not selected"
    checks = [(key, annotation.get(key), target.get(key))
              for key in ("coupon", "archive_path", "sha256")]
    checks += [("code", annotation.get("values", {}).get(field), target.get("code")),
               ("dictionary sheet", _RELATIONS.get(field), target.get("sheet"))]
    # Namespace is checked independently of coincidentally equal workbook values.
    for name, record in (("annotation", annotation), ("target", target)):
        checks.append((name + " namespace", record.get("coupon"), record["id"].split(":")[0]))
    return _compare(checks)


def _result(check_id, status, evidence_ids, reason):
    return dict(check_id=check_id, status=status, evidence_ids=evidence_ids, reason=reason)


def _parse(envelope):
    if not isinstance(envelope, dict) or envelope.get("status") != "ok":
        raise ValueError("retrieval envelope must have status ok")
    chunks = envelope.get("selected_chunks")
    ids = envelope.get("selected_chunk_ids")
    if not isinstance(chunks, list) or not isinstance(ids, list):
        raise ValueError("selected chunks and IDs must be lists")
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid or duplicate selected IDs")
    encoded = canonical_bytes(chunks)
    if hashlib.sha256(encoded).hexdigest() != envelope.get("evidence_sha256"):
        raise ValueError("evidence hash mismatch")
    if "evidence_bytes" in envelope and (type(envelope["evidence_bytes"]) is not int
                                         or envelope["evidence_bytes"] != len(encoded)):
        raise ValueError("evidence byte count mismatch")
    nodes, edges, actual = {}, [], []
    for chunk in chunks:
        if not isinstance(chunk, dict) or not isinstance(chunk.get("text"), str):
            raise ValueError("invalid chunk structure")
        kind = chunk.get("chunk_type")
        if kind not in ("node", "edge"):
            raise ValueError("unsupported chunk type")
        key = kind + "_id"
        identifier = chunk.get(key)
        if not isinstance(identifier, str) or not identifier or chunk.get("chunk_id") != kind + ":" + identifier:
            raise ValueError("chunk ID inconsistent with payload ID")
        data = json.loads(chunk["text"], object_pairs_hook=_pairs, parse_constant=_reject_constant)
        if not isinstance(data, dict) or data.get("id" if kind == "node" else "edge_id") != identifier:
            raise ValueError("chunk text ID mismatch")
        canonical_bytes(data)  # Reject overflow-to-infinity numbers, too.
        actual.append(chunk["chunk_id"])
        if kind == "node":
            if identifier in nodes:
                raise ValueError("duplicate node ID")
            refs = data.get("dictionary_refs")
            if "dictionary_refs" in data and (not isinstance(refs, dict) or any(
                    not isinstance(v, str) or not v for v in refs.values())):
                raise ValueError("malformed dictionary references")
            if "values" in data and not isinstance(data["values"], (dict, list)):
                raise ValueError("malformed node values")
            if "dictionary_refs" in data and not isinstance(data.get("values", {}), dict):
                raise ValueError("annotation values must be an object")
            if "field_cells" in data and not isinstance(data["field_cells"], dict):
                raise ValueError("malformed field cells")
            nodes[identifier] = data
        else:
            if any(k in data and (not isinstance(data[k], str) or not data[k])
                   for k in ("subject", "target", "field", "relation_type")):
                raise ValueError("malformed edge binding")
            if "provenance" in data and not isinstance(data["provenance"], dict):
                raise ValueError("malformed edge provenance")
            edges.append(data)
    if actual != ids:
        raise ValueError("selected IDs differ from ordered payload IDs")
    return nodes, edges


def check_evidence(envelope, max_report_bytes=32000):
    """Return all generic checks or an error, without modifying the envelope.

    An error receipt may exceed a pathologically tiny caller cap. It contains no
    successful or truncated check results; callers must not treat it as a report.
    """
    digest = envelope.get("evidence_sha256") if isinstance(envelope, dict) else None
    if not isinstance(digest, str) or len(digest) != 64:
        digest = None
    report = dict(evidence_sha256=digest, rule_version=RULE_VERSION, results=[],
                  status="error", complete=False, truncated=False, error=None)
    try:
        if type(max_report_bytes) is not int or max_report_bytes < 1:
            raise ValueError("max_report_bytes must be a positive integer")
        nodes, edges = _parse(envelope)
        results = []
        annotations = {i: n for i, n in nodes.items()
                       if "dictionary_refs" in n or isinstance(n.get("values"), dict)}
        for identifier, annotation in annotations.items():
            refs = annotation.get("dictionary_refs") or {}
            if not refs:
                results.append(_result(identifier + ":dictionary_refs", "unknown",
                                       ["node:" + identifier], "no declared dictionary references"))
            for field, target_id in sorted(refs.items()):
                target = nodes.get(target_id)
                status, reason = _binding(annotation, target, field)
                evidence = ["node:" + identifier] + (["node:" + target_id] if target else [])
                results.append(_result(identifier + ":dictionary_ref:" + field, status, evidence, reason))
            results.append(_result(identifier + ":process_review_version", "unknown",
                                   ["node:" + identifier], "process review version applicability is unsupported"))
        if not annotations:
            results.append(_result("no_selected_annotation", "unknown", [], "no selected annotation"))
        for edge in edges:
            subject, target = nodes.get(edge.get("subject")), nodes.get(edge.get("target"))
            evidence = ["edge:" + edge["edge_id"]]
            evidence += ["node:" + n["id"] for n in (subject, target) if n is not None]
            if subject is None or target is None:
                status, reason = "unknown", "edge endpoint not selected or not declared"
            elif subject["id"] not in annotations:
                status, reason = "violation", "edge subject is not an annotation"
            else:
                field = edge.get("field")
                provenance = edge.get("provenance", {})
                checks = [("edge identity", edge["edge_id"], "|".join((edge["subject"], field, edge["target"])) if field is not None else None),
                          ("reference binding", subject.get("dictionary_refs", {}).get(field), edge.get("target")),
                          ("field", field, next((f for f, r in _RELATIONS.items() if r == edge.get("relation_type")), None)),
                          ("relation", edge.get("relation_type"), target.get("sheet")),
                          ("source code", edge.get("code"), subject.get("values", {}).get(field)),
                          ("target code", edge.get("code"), target.get("code"))]
                checks += [("provenance " + k, provenance.get(k), subject.get(k))
                           for k in ("coupon", "archive_path", "sha256", "sheet")]
                checks += [("provenance cell", provenance.get("cell"), subject.get("field_cells", {}).get(field)),
                           ("target sheet", provenance.get("target_sheet"), target.get("sheet")),
                           ("target row", provenance.get("target_excel_row"), target.get("excel_row"))]
                status, reason = _compare(checks)
                binding_status, binding_reason = _binding(subject, target, field)
                if binding_status == "violation" or (binding_status == "unknown" and status == "pass"):
                    status, reason = binding_status, binding_reason
            results.append(_result("edge_binding:" + edge["edge_id"], status, evidence, reason))
        report.update(status="ok", complete=True, results=results)
        if len(canonical_bytes(report)) > max_report_bytes:
            raise ValueError("report byte cap exceeded")
    except (ValueError, TypeError, KeyError, RecursionError, UnicodeError) as exc:
        report.update(status="error", complete=False, results=[], error=str(exc))
    return report
