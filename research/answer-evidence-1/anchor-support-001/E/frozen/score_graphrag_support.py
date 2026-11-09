"""OFFLINE ONLY: source-bound evidence support; no retrieval or answer repair."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def bound(annotation, target, field):
    return (annotation.get("dictionary_refs", {}).get(field) == target.get("id")
            and all(annotation.get(k) is not None and annotation[k] == target.get(k)
                    for k in ("coupon", "archive_path", "sha256"))
            and annotation.get("values", {}).get(field) == target.get("code"))


def score(source, references, outputs):
    chunks = {c["chunk_id"]: c for c in source["chunks"]}
    if len(chunks) != len(source["chunks"]):
        raise ValueError("duplicate source chunk IDs")
    nodes = {c["node_id"]: json.loads(c["text"]) for c in chunks.values() if c["chunk_type"] == "node"}
    refs = references["references"]
    ids = [r["question_id"] for r in refs]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("empty/duplicate reference IDs")
    observed = {}
    for row in outputs:
        qid = row["question_id"]
        if qid not in ids or qid in observed:
            raise ValueError("extra/duplicate output ID")
        observed[qid] = row
    # Reject invalid definitions before producing any metric.
    for ref in refs:
        state, sets, field = ref["evidence_state"], ref["admissible_node_sets"], ref["required_link_field"]
        if state == "absent_from_supplied_bundle":
            if sets:
                raise ValueError("absent reference has support sets")
        elif state == "present_in_supplied_bundle":
            if not sets or ref["target_record"] not in nodes:
                raise ValueError("present reference missing support")
            for group in sets:
                if not group or len(set(group)) != len(group) or ref["target_record"] not in group or any(n not in nodes for n in group):
                    raise ValueError("invalid admissible nodes")
                if field is not None:
                    target = nodes[ref["target_record"]].get("dictionary_refs", {}).get(field)
                    if target not in group or not bound(nodes[ref["target_record"]], nodes[target], field):
                        raise ValueError("reference binding mismatch")
        else:
            raise ValueError("unknown reference evidence state")
    results = []
    for ref in refs:
        present = ref["evidence_state"] == "present_in_supplied_bundle"
        result = {"question_id": ref["question_id"], "task": ref["task"],
                  "evidence_state": ref["evidence_state"], "complete_support": False if present else None,
                  "node_coverage": 0.0 if present else None, "answer_accuracy": None,
                  "reason": None, "retrieval_state": None}
        row = observed.get(ref["question_id"])
        if row is None:
            result.update(retrieval_state="missing_output", reason="no saved envelope")
        elif row.get("status") != "ok":
            result.update(retrieval_state="retrieval_failure", reason=row.get("error"))
        else:
            try:
                selected = row["selected_chunks"]
                selected_ids = [c["chunk_id"] for c in selected]
                raw = canonical(selected)
                if (len(set(selected_ids)) != len(selected_ids) or selected_ids != row["selected_chunk_ids"]
                        or hashlib.sha256(raw).hexdigest() != row["evidence_sha256"]
                        or len(raw) != row["evidence_bytes"]
                        or any(c != chunks.get(c["chunk_id"]) for c in selected)):
                    raise ValueError("evidence identity/hash/source mismatch")
                selected_nodes = {c["node_id"] for c in selected if c["chunk_type"] == "node"}
                result["retrieval_state"] = "valid_saved_evidence"
                if not present:
                    result["reason"] = "reference absence is bundle-scoped; no answer to score"
                else:
                    groups = ref["admissible_node_sets"]
                    result["node_coverage"] = max(len(set(g) & selected_nodes) / len(g) for g in groups)
                    # Binding was validated in source; selected chunks must be source-exact.
                    result["complete_support"] = any(set(g) <= selected_nodes for g in groups)
                    result["missing_node_sets"] = [sorted(set(g) - selected_nodes) for g in groups]
                    result["reason"] = "complete frozen support" if result["complete_support"] else "required source nodes not selected"
            except (KeyError, TypeError, ValueError) as exc:
                result.update(retrieval_state="invalid_evidence", reason=str(exc))
        results.append(result)
    present_rows = [r for r in results if r["evidence_state"] == "present_in_supplied_bundle"]
    summary = {"reference_questions": len(refs), "saved_envelopes": len(outputs),
               "source_present": len(present_rows), "complete_support": sum(r["complete_support"] for r in present_rows),
               "source_absent_separate": len(results)-len(present_rows),
               "retrieval_state_counts": {s: sum(r["retrieval_state"] == s for r in results)
                                          for s in sorted({r["retrieval_state"] for r in results})},
               "by_present_task": {task: {"denominator": sum(r["task"] == task for r in present_rows),
                                          "complete": sum(r["task"] == task and r["complete_support"] for r in present_rows)}
                                   for task in sorted({r["task"] for r in present_rows})},
               "answer_accuracy": None, "scope": "authored support contracts on consumed development; no external truth"}
    return {"summary": summary, "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "references", "retrieval", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    files = [args.source, args.references, args.retrieval, Path(__file__),
             Path("research/graphrag-evidence-1/support-scoring-v1.md")]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    frozen = args.output / "frozen"
    frozen.mkdir()
    for p in files:
        shutil.copyfile(p, frozen / p.name)
    (args.output / "manifest.json").write_text(json.dumps(hashes, indent=2))
    try:
        result = score(json.loads(args.source.read_text()), json.loads(args.references.read_text()),
                       [json.loads(line) for line in args.retrieval.read_text().splitlines()])
        if any(hashlib.sha256(p.read_bytes()).hexdigest() != hashes[str(p)] for p in files):
            raise ValueError("input changed during scoring")
        (args.output / "scores.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result["summary"], indent=2))
    except Exception as exc:
        (args.output / "failure.json").write_text(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
        raise


if __name__ == "__main__":
    main()
