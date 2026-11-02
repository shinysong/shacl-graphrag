"""Lossless character slices for a pinned tokenizer; no retrieval/model calls."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

TOKENIZER_SHA256 = "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39"
TOKENIZER_VERSION = "0.22.1"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_children(corpus: dict, count_tokens, limit: int = 512) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= 512:
        raise ValueError("limit must be an integer in 1..512")
    chunks = corpus.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("nonempty chunks required")
    children, seen = [], set()
    for chunk in chunks:
        parent, text = chunk.get("chunk_id"), chunk.get("text")
        if not isinstance(parent, str) or not parent or parent in seen:
            raise ValueError("empty/duplicate/invalid parent ID")
        if not isinstance(text, str) or not text:
            raise ValueError("nonempty text required")
        seen.add(parent)
        parent_hash = sha(text.encode("utf-8"))
        pending, ordinal = [(0, len(text))], 0
        while pending:
            start, end = pending.pop()
            raw = text[start:end]
            search_text = f"passage: parent={parent}\n{raw}"
            count = count_tokens(search_text)
            if type(count) is not int or count < 1:
                raise ValueError("token counter returned invalid count")
            if count > limit:
                if end - start <= 1:
                    raise ValueError("single-character slice exceeds token limit")
                midpoint = (start + end) // 2
                pending.extend([(midpoint, end), (start, midpoint)])
                continue
            # Length-prefixed parent identity prevents ambiguous child IDs.
            child_id = f"{len(parent)}:{parent}:{ordinal}"
            children.append({"child_id": child_id, "parent_id": parent,
                             "parent_sha256": parent_hash, "ordinal": ordinal,
                             "start": start, "end": end, "text": raw,
                             "search_text": search_text, "token_count": count})
            ordinal += 1
    return children


def aggregate_parents(children: list[dict], scored_children: list[dict]) -> list[dict]:
    lookup = {c["child_id"]: c["parent_id"] for c in children}
    if len(lookup) != len(children):
        raise ValueError("duplicate child IDs in index")
    seen, groups = set(), {}
    for item in scored_children:
        child, score = item["child_id"], item["score"]
        if child not in lookup or child in seen:
            raise ValueError("unknown/duplicate scored child")
        if type(score) not in (int, float) or not math.isfinite(score):
            raise ValueError("finite numeric score required")
        seen.add(child)
        groups.setdefault(lookup[child], []).append((score, child))
    rows = []
    for parent, hits in groups.items():
        hits.sort(key=lambda pair: (-pair[0], pair[1]))
        rows.append({"parent_id": parent, "score": hits[0][0],
                     "contributing_child_ids": [child for _, child in hits]})
    return sorted(rows, key=lambda row: (-row["score"], row["parent_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        from tokenizers import Tokenizer
        if importlib.metadata.version("tokenizers") != TOKENIZER_VERSION:
            raise ValueError("tokenizer runtime version mismatch")
        raw_source, raw_tokenizer = args.source.read_bytes(), args.tokenizer.read_bytes()
        if sha(raw_tokenizer) != TOKENIZER_SHA256:
            raise ValueError("tokenizer hash mismatch")
        tokenizer = Tokenizer.from_str(raw_tokenizer.decode("utf-8"))
        tokenizer.no_truncation()
        tokenizer.no_padding()
        corpus = json.loads(raw_source)
        children = build_children(corpus, lambda text: len(tokenizer.encode(text).ids))
        raw_children = (json.dumps(children, ensure_ascii=False, indent=2) + "\n").encode()
        manifest = {"schema_version": "graphrag-search-slices-1",
                    "source_sha256": sha(raw_source), "tokenizer_sha256": sha(raw_tokenizer),
                    "tokenizers_version": TOKENIZER_VERSION,
                    "script_sha256": sha(Path(__file__).read_bytes()),
                    "protocol_sha256": sha(Path("research/graphrag-evidence-1/search-splitting-v1.md").read_bytes()),
                    "parent_count": len(corpus["chunks"]), "child_count": len(children),
                    "token_limit": 512, "maximum_tokens": max(c["token_count"] for c in children),
                    "children_sha256": sha(raw_children), "model_calls": 0,
                    "scope": "lossless preprocessing only; no retrieval efficacy"}
        (args.output / "children.json").write_bytes(raw_children)
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps(manifest, indent=2))
    except Exception as exc:
        (args.output / "failure.json").write_text(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
        raise


if __name__ == "__main__":
    main()
