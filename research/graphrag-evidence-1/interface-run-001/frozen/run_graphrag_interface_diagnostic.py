#!/usr/bin/env python3
"""Run source-seeded offline interface checks; never call a retriever or LLM."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from graphrag_expand import expand
from graphrag_check import check_evidence


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("research/graphrag-evidence-1/source-corpus-v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    files = [args.source, Path(__file__), Path(__file__).with_name("graphrag_expand.py"),
             Path(__file__).with_name("graphrag_check.py"),
             Path("research/graphrag-evidence-1/offline-interface-v1.md"), Path("uv.lock")]
    frozen = args.output / "frozen"
    frozen.mkdir()
    hashes = {}
    for path in files:
        hashes[str(path)] = digest(path.read_bytes())
        shutil.copyfile(path, frozen / path.name)
    corpus = json.loads(args.source.read_text())
    configuration = {"max_depth": 1, "max_candidates": 32, "max_evidence_bytes": 64000}
    seeds = sorted("node:" + n["node_id"] for n in corpus["nodes"] if n["node_type"] == "annotation")
    if len(seeds) != 243 or len(set(seeds)) != 243:
        raise ValueError("This fixed diagnostic requires 243 unique consumed-source annotation seeds")
    manifest = {"schema_version": "graphrag-interface-diagnostic-1", "source_hashes": hashes,
                "configuration": configuration, "max_report_bytes": 32000,
                "seed_chunk_ids": seeds, "planned_pairs": len(seeds),
                "scope": "Consumed-source supplied-seed software diagnostic; no B retrieval, embedding, generator or SHACL engine.",
                "unmeasured": ["A_vector_rag", "B_hybrid_rag", "C_end_to_end", "D_end_to_end", "E_end_to_end"]}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    summary = {"attempted_pairs": 0, "retrieval_failures": 0, "parity_matches": 0,
               "parity_mismatches": 0, "checker_errors": 0, "evidence_mutations": 0,
               "checker_results": {}, "new_model_calls": 0, "scope": manifest["scope"]}
    with (args.output / "outputs.jsonl").open("x") as out:
        for seed in seeds:
            summary["attempted_pairs"] += 1
            record = {"seed_chunk_id": seed, "envelopes": {}}
            for backend in ["adjacency", "sqlite"]:
                try:
                    record["envelopes"][backend] = expand(corpus, [seed], backend=backend, **configuration)
                except Exception as exc:
                    record["envelopes"][backend] = {"status": "unhandled_error", "error": f"{type(exc).__name__}: {exc}"}
            a, b = record["envelopes"]["adjacency"], record["envelopes"]["sqlite"]
            ok = a.get("status") == b.get("status") == "ok"
            summary["retrieval_failures"] += sum(e.get("status") != "ok" for e in [a, b])
            record["parity"] = ok and a["selected_chunks"] == b["selected_chunks"] and a["evidence_sha256"] == b["evidence_sha256"]
            summary["parity_matches" if record["parity"] else "parity_mismatches"] += 1
            before = dump(a)
            try:
                report = check_evidence(a, max_report_bytes=32000)
            except Exception as exc:
                report = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            record["checker_report"] = report
            record["checker_input_unchanged"] = before == dump(a)
            summary["evidence_mutations"] += not record["checker_input_unchanged"]
            summary["checker_errors"] += report.get("status") != "ok"
            for result in report.get("results", []):
                key = result["status"]
                summary["checker_results"][key] = summary["checker_results"].get(key, 0) + 1
            out.write(dump(record) + "\n")
            out.flush()
    summary["inputs_unchanged"] = all(digest(Path(path).read_bytes()) == h for path, h in hashes.items())
    summary["software_success"] = (summary["attempted_pairs"] == len(seeds) and
        not any(summary[k] for k in ["retrieval_failures", "parity_mismatches", "checker_errors", "evidence_mutations"]) and
        summary["inputs_unchanged"])
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if summary["software_success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
