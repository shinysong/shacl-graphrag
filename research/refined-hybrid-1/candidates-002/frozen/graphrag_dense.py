"""Pinned local CPU encoder and deterministic dense ranking/packing."""
import hashlib
import importlib.metadata
import math

from build_graphrag_search import aggregate_parents
from graphrag_expand import canonical


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for part in iter(lambda: f.read(1048576), b""):
            h.update(part)
    return h.hexdigest()


class Encoder:
    def __init__(self, model, tokenizer):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        for name, version in {"numpy": "2.3.4", "onnxruntime": "1.23.2", "tokenizers": "0.22.1"}.items():
            if importlib.metadata.version(name) != version:
                raise ValueError("runtime version mismatch")
        if file_hash(model) != "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665":
            raise ValueError("model hash mismatch")
        if file_hash(tokenizer) != "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39":
            raise ValueError("tokenizer hash mismatch")
        self.np = np
        self.tokenizer = Tokenizer.from_file(str(tokenizer))
        self.tokenizer.no_truncation()
        self.tokenizer.no_padding()
        self.pad = self.tokenizer.token_to_id("<pad>")
        if self.pad is None:
            raise ValueError("missing padding token")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        self.session = ort.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"])
        if self.session.get_providers() != ["CPUExecutionProvider"]:
            raise ValueError("unexpected provider")
        if {x.name for x in self.session.get_inputs()} != {"input_ids", "attention_mask", "token_type_ids"}:
            raise ValueError("unexpected model inputs")

    def count(self, text):
        return len(self.tokenizer.encode(text).ids)

    def encode(self, texts):
        np = self.np
        if not 1 <= len(texts) <= 2:
            raise ValueError("batch must have one or two inputs")
        encoded = [self.tokenizer.encode(x) for x in texts]
        if any(not 1 <= len(x.ids) <= 512 for x in encoded):
            raise ValueError("model input outside token limit")
        width = max(len(x.ids) for x in encoded)
        ids = np.full((len(texts), width), self.pad, dtype=np.int64)
        mask, types = np.zeros_like(ids), np.zeros_like(ids)
        for i, e in enumerate(encoded):
            ids[i, :len(e.ids)], mask[i, :len(e.ids)], types[i, :len(e.ids)] = e.ids, 1, e.type_ids
        hidden = self.session.run(["last_hidden_state"], {"input_ids": ids, "attention_mask": mask, "token_type_ids": types})[0]
        if hidden.shape != (len(texts), width, 384) or not np.isfinite(hidden).all():
            raise ValueError("invalid hidden states")
        pooled = (hidden * mask[..., None]).sum(axis=1) / mask.sum(axis=1)[:, None]
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        if not np.isfinite(norms).all() or (norms <= 0).any():
            raise ValueError("invalid norms")
        vectors = (pooled / norms).astype(np.float32)
        if not np.isfinite(vectors).all() or not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5, rtol=0):
            raise ValueError("invalid vectors")
        return vectors


def rank_pack(children, scores, chunks, count_tokens, child_k=20, parent_k=8,
              token_cap=4096, byte_cap=64000):
    if len(scores) != len(children) or len({c["child_id"] for c in children}) != len(children):
        raise ValueError("score/index mismatch")
    if any(type(x) is not int or x < 1 for x in (child_k, parent_k, token_cap, byte_cap)):
        raise ValueError("positive integer bounds required")
    hits = []
    for child, score in zip(children, scores):
        if isinstance(score, bool) or not math.isfinite(score):
            raise ValueError("invalid similarity")
        hits.append({"child_id": child["child_id"], "score": float(score)})
    hits.sort(key=lambda h: (-h["score"], h["child_id"]))
    hits = hits[:child_k]
    parents = aggregate_parents(children, hits)[:parent_k]
    selected, skipped = [], []
    for parent in parents:
        candidate = chunks[parent["parent_id"]]
        prospective = canonical(selected + [candidate])
        n = count_tokens(prospective.decode("utf-8"))
        if type(n) is not int or n < 1:
            raise ValueError("invalid accounting token count")
        if len(prospective) > byte_cap or n > token_cap:
            skipped.append(parent["parent_id"])
        else:
            selected.append(candidate)
    payload = canonical(selected)
    return {"status": "ok" if selected else "budget_error", "top_children": hits,
            "top_parents": parents, "skipped_budget_ids": skipped,
            "selected_chunk_ids": [c["chunk_id"] for c in selected], "selected_chunks": selected,
            "evidence_sha256": hashlib.sha256(payload).hexdigest(), "evidence_bytes": len(payload),
            "evidence_tokens": None, "accounting_tokenizer": "pinned-E5-not-generator",
            "accounting_tokens": count_tokens(payload.decode("utf-8"))}
