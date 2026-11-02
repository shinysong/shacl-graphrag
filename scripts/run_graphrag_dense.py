"""A-only dense retrieval diagnostic; never reads reference answers."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import shutil
import time

from graphrag_dense import Encoder, file_hash, rank_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "children", "questions", "model", "tokenizer", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    questions, envelopes = [], []
    summary = {"scope": "A retrieval component only; consumed development", "status": "started",
               "paid_calls": 0, "generation_calls": 0}
    try:
        import numpy as np
        source = json.loads(args.source.read_text())
        children = json.loads(args.children.read_text())
        questions = json.loads(args.questions.read_text())["questions"]
        if len(questions) != 24 or len({q["question_id"] for q in questions}) != 24:
            raise ValueError("expected24 unique question IDs")
        if any(set(q) != {"question_id", "question"} or not all(isinstance(v, str) and v for v in q.values()) for q in questions):
            raise ValueError("only nonempty question_id/question allowed")
        if file_hash(args.source) != "900bb25d15bcb4dbab89076d3a1372d84762829dcd645bae7c17bc60b9693ac8":
            raise ValueError("source hash mismatch")
        if file_hash(args.children) != "274cf2d4d10e075f0664fc35d0e9bbe449c73c9e16a73985a9032e504e76a2eb":
            raise ValueError("search children hash mismatch")
        chunks = {c["chunk_id"]: c for c in source["chunks"]}
        if len(chunks) != 814 or len(children) != 1483:
            raise ValueError("corpus size mismatch")
        frozen = args.output / "frozen"
        frozen.mkdir()
        paths = [args.source, args.children, args.questions, Path(__file__),
                 Path("scripts/graphrag_dense.py"), Path("scripts/build_graphrag_search.py"),
                 Path("scripts/graphrag_expand.py"), Path("research/graphrag-evidence-1/dense-retrieval-v1.md")]
        manifest = {"files": {str(p): file_hash(p) for p in paths},
                    "configuration": {"child_k": 20, "parent_k": 8, "accounting_token_cap": 4096,
                                      "byte_cap": 64000, "batch_size": 2, "max_elapsed_seconds": 900}}
        for p in paths:
            shutil.copyfile(p, frozen / p.name)
        configuration_hash = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        manifest["configuration_sha256"] = configuration_hash
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
        encoder = Encoder(args.model, args.tokenizer)
        short = min(children, key=lambda c: c["token_count"])["search_text"]
        long = max(children, key=lambda c: c["token_count"])["search_text"]
        solo = encoder.encode([short])[0]
        padded = encoder.encode([short, long])[0]
        probe = {"short_tokens": encoder.count(short), "long_tokens": encoder.count(long),
                 "max_absolute_difference": float(np.max(np.abs(solo - padded))),
                 "agrees": bool(np.allclose(solo, padded, atol=1e-5, rtol=0))}
        (args.output / "padding-probe.json").write_text(json.dumps(probe, indent=2))
        if not probe["agrees"]:
            raise ValueError("padding invariance probe failed")
        with (args.output / "progress.jsonl").open("w") as log:
            def encode_all(texts, filename, phase):
                vectors = np.lib.format.open_memmap(args.output / filename, mode="w+", dtype=np.float32, shape=(len(texts), 384))
                vectors[:] = np.nan
                vectors.flush()
                for start in range(0, len(texts), 2):
                    if time.perf_counter() - started > 900:
                        raise TimeoutError("between-batch elapsed cap")
                    batch = texts[start:start+2]
                    vectors[start:start+len(batch)] = encoder.encode(batch)
                    vectors.flush()
                    log.write(json.dumps({"phase": phase, "completed": start+len(batch), "total": len(texts),
                                          "elapsed_seconds": time.perf_counter()-started}) + "\n")
                    log.flush()
                return vectors
            cv = encode_all([c["search_text"] for c in children], "child-vectors.npy", "children")
            qv = encode_all(["query: " + q["question"] for q in questions], "query-vectors.npy", "queries")
        for q, vector in zip(questions, qv):
            base = {"run_id": args.output.name, "question_id": q["question_id"], "arm": "A", "attempt_id": 1,
                    "source_sha256": file_hash(args.source), "configuration_sha256": configuration_hash,
                    "generation_executed": False}
            try:
                result = rank_pack(children, cv @ vector, chunks, encoder.count)
                base.update(result, error=None if result["status"] == "ok" else "no parent fits accounting budget")
                base.update(seed_chunk_ids=[p["parent_id"] for p in result["top_parents"]],
                            candidate_chunk_ids=[p["parent_id"] for p in result["top_parents"]])
            except Exception as exc:
                base.update(status="retrieval_error", error=f"{type(exc).__name__}: {exc}")
            envelopes.append(base)
        summary.update(status="completed", question_count=len(questions),
                       ok=sum(e["status"] == "ok" for e in envelopes),
                       failures=sum(e["status"] != "ok" for e in envelopes),
                       encoded_children=len(children), encoded_queries=len(questions), padding_probe=probe,
                       model_sha256=file_hash(args.model), tokenizer_sha256=file_hash(args.tokenizer),
                       child_vectors_sha256=file_hash(args.output / "child-vectors.npy"),
                       query_vectors_sha256=file_hash(args.output / "query-vectors.npy"))
    except Exception as exc:
        summary.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        envelopes = [{"question_id": q.get("question_id"), "arm": "A", "status": "retrieval_error",
                      "error": summary["error"], "generation_executed": False} for q in questions]
        summary.update(question_count=len(questions), ok=0, failures=len(envelopes))
        raise
    finally:
        (args.output / "retrieval.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in envelopes))
        summary.update(elapsed_seconds=time.perf_counter()-started,
                       process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
