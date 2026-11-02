"""Pinned nine-input CPU smoke; not a retrieval or answer-quality evaluation."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import resource
import time


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("model", "tokenizer", "inputs", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"scope": "nine-input CPU execution smoke only", "status": "started"}
    started = time.perf_counter()
    try:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        expected = {"numpy": "2.3.4", "onnxruntime": "1.23.2", "tokenizers": "0.22.1"}
        versions = {name: importlib.metadata.version(name) for name in expected}
        if versions != expected:
            raise ValueError("runtime version mismatch")
        model_hash, tokenizer_hash = digest(args.model), digest(args.tokenizer)
        if model_hash != "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665":
            raise ValueError("model hash mismatch")
        if tokenizer_hash != "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39":
            raise ValueError("tokenizer hash mismatch")
        raw_inputs = args.inputs.read_bytes()
        packet = json.loads(raw_inputs)
        items = packet["inputs"]
        if len(items) != 9 or items[0]["text"] != items[-1]["text"]:
            raise ValueError("expected eight inputs plus repeat of first")
        if len({x["id"] for x in items}) != 9:
            raise ValueError("duplicate input IDs")
        tokenizer = Tokenizer.from_file(str(args.tokenizer))
        tokenizer.no_truncation()
        tokenizer.no_padding()
        pad_id = tokenizer.token_to_id("<pad>")
        if pad_id is None:
            raise ValueError("missing pad token")
        encoded = [tokenizer.encode(x["text"]) for x in items]
        if any(not 1 <= len(x.ids) <= 512 for x in encoded):
            raise ValueError("input outside token limit")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        load_started = time.perf_counter()
        session = ort.InferenceSession(str(args.model), sess_options=options,
                                       providers=["CPUExecutionProvider"])
        load_seconds = time.perf_counter() - load_started
        if session.get_providers() != ["CPUExecutionProvider"]:
            raise ValueError("unexpected execution provider")
        input_names = [x.name for x in session.get_inputs()]
        if set(input_names) != {"input_ids", "attention_mask"}:
            raise ValueError("unexpected ONNX inputs")
        outputs, batches = [], []
        for start in range(0, 9, 2):
            batch = encoded[start:start + 2]
            width = max(len(x.ids) for x in batch)
            ids = np.full((len(batch), width), pad_id, dtype=np.int64)
            mask = np.zeros_like(ids)
            for i, enc in enumerate(batch):
                ids[i, :len(enc.ids)] = enc.ids
                mask[i, :len(enc.ids)] = 1
            before = time.perf_counter()
            hidden = session.run(["last_hidden_state"], {"input_ids": ids, "attention_mask": mask})[0]
            if hidden.shape != (len(batch), width, 384) or not np.isfinite(hidden).all():
                raise ValueError("invalid hidden states")
            pooled = (hidden * mask[..., None]).sum(axis=1) / mask.sum(axis=1)[:, None]
            norm = np.linalg.norm(pooled, axis=1, keepdims=True)
            if not np.isfinite(norm).all() or (norm <= 0).any():
                raise ValueError("invalid pooled norms")
            outputs.append((pooled / norm).astype(np.float32))
            batches.append({"start": start, "size": len(batch), "padded_tokens": width,
                            "seconds": time.perf_counter() - before})
        vectors = np.concatenate(outputs)
        norms = np.linalg.norm(vectors, axis=1)
        checks = {"shape": list(vectors.shape) == [9, 384],
                  "finite": bool(np.isfinite(vectors).all()),
                  "unit_norms": bool(np.allclose(norms, 1, atol=1e-5, rtol=0)),
                  "repeat_agrees": bool(np.allclose(vectors[0], vectors[-1], atol=1e-5, rtol=0))}
        np.save(args.output / "embeddings.npy", vectors, allow_pickle=False)
        (args.output / "inputs.json").write_bytes(raw_inputs)
        result.update(status="passed" if all(checks.values()) else "failed_checks",
                      versions=versions, providers=session.get_providers(), checks=checks,
                      model_sha256=model_hash, tokenizer_sha256=tokenizer_hash,
                      input_sha256=hashlib.sha256(raw_inputs).hexdigest(),
                      source_children_sha256=packet["source_children_sha256"],
                      script_sha256=digest(__file__),
                      protocol_sha256=digest("research/graphrag-evidence-1/cpu-smoke-v1.md"),
                      embeddings_sha256=digest(args.output / "embeddings.npy"),
                      lengths=[len(x.ids) for x in encoded], norms=norms.tolist(),
                      maximum_repeat_difference=float(np.max(np.abs(vectors[0] - vectors[-1]))),
                      input_metadata=[{"name": x.name, "shape": x.shape, "type": x.type} for x in session.get_inputs()],
                      output_metadata=[{"name": x.name, "shape": x.shape, "type": x.type} for x in session.get_outputs()],
                      load_seconds=load_seconds, batches=batches, paid_calls=0)
        if not all(checks.values()):
            raise ValueError("smoke check failed")
    except Exception as exc:
        result.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        result.update(total_process_observed_seconds=time.perf_counter() - started,
                      process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        (args.output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
