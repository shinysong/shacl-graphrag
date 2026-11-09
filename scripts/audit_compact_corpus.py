"""Offline representation audit; no questions, gold, tokenization or selection."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
from scripts.graphrag_compact_cells import canonical, encode, decode_serialized

SOURCE = Path("research/graphrag-evidence-1/source-corpus-v1.json")
SOURCE_HASH = "900bb25d15bcb4dbab89076d3a1372d84762829dcd645bae7c17bc60b9693ac8"


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    out=Path(args.out)
    out.mkdir(parents=True,exist_ok=False)
    paths=[SOURCE,Path(__file__),Path("scripts/graphrag_compact_cells.py"),
           Path("research/answer-evidence-1/compact-cell-contract-v1.json"),
           Path("tests/test_compact_boundary.py"),Path("tests/test_graphrag_compact_cells.py")]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (out/"input-hashes.json").write_bytes(canonical(hashes))
    if hashes[str(SOURCE)] != SOURCE_HASH:
        (out/"summary.json").write_bytes(canonical(dict(status="source_integrity_failure")))
        return 1
    source=json.loads(SOURCE.read_bytes())
    chunks=source["chunks"]
    rows=[]
    for index,chunk in enumerate(chunks):
        row=dict(index=index,chunk_id=chunk.get("chunk_id"),chunk_type=chunk.get("chunk_type"))
        try:
            before=canonical(chunk)
            encoded=canonical(encode(chunk))
            restored=canonical(decode_serialized(encoded))
            if restored != before or canonical(chunk) != before:
                raise ValueError("roundtrip or mutation mismatch")
            row.update(status="ok",raw_bytes=len(before),compact_bytes=len(encoded),
                       raw_sha256=hashlib.sha256(before).hexdigest(),
                       compact_sha256=hashlib.sha256(encoded).hexdigest())
        except Exception as exc:
            row.update(status=getattr(exc,"status","audit_failure"),error=type(exc).__name__,
                       detail=str(exc))
        rows.append(row)
    stable=all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[str(p)] for p in paths)
    failed=sum(r["status"]!="ok" for r in rows)
    summary=dict(status="ok" if stable and not failed else "failed",
                 planned=len(chunks),processed=len(rows),failed=failed,unprocessed=len(chunks)-len(rows),
                 passed=len(rows)-failed,input_hashes_stable=stable,python=platform.python_version(),
                 by_type={k:sum(r["chunk_type"]==k for r in rows) for k in ["node","edge"]},
                 raw_bytes=sum(r.get("raw_bytes",0) for r in rows),
                 compact_bytes=sum(r.get("compact_bytes",0) for r in rows),
                 byte_totals_scope="successful chunks only, includes wrappers; not messages/tokens",
                 qa_executed=False)
    (out/"rows.json").write_bytes(canonical(rows))
    (out/"summary.json").write_bytes(canonical(summary))
    print(json.dumps(summary))
    return 0 if summary["status"]=="ok" else 1


if __name__=="__main__":
    raise SystemExit(main())
