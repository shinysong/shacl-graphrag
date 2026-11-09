"""Fixed saved candidate prefixes and selections, not a new retrieval run."""
import hashlib
import json
from pathlib import Path
from tokenizers import Tokenizer
from scripts.graphrag_compact_cells import canonical, encode, decode_serialized
from scripts.graphrag_message_pack import _measure, BASE_TOKENS, BASE_BYTES

OUT=Path("research/answer-evidence-1/compact-message-diagnostic-001")
PATHS=dict(source="research/graphrag-evidence-1/source-corpus-v1.json",
           rows="research/answer-evidence-1/anchor-on-001/rows.jsonl",
           prior_manifest="research/answer-evidence-1/anchor-on-001/manifest.json",
           tokenizer="_workspace/graphrag-cycle3/sources/e5-tokenizer.json",
           codec="scripts/graphrag_compact_cells.py",
           packer="scripts/graphrag_message_pack.py",
           messages="scripts/graphrag_input_contract.py",
           parse="scripts/graphrag_check.py",
           lock="uv.lock",
           diagnostic=__file__)


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    results=[]
    summary=dict(planned=96,processed=0,failed=0,unprocessed=96,generator_ready=False,
                 scope="saved A1/B/C/E selected sets and candidate prefixes, E5 surrogate only")
    try:
        hashes={k:hashlib.sha256(Path(p).read_bytes()).hexdigest() for k,p in PATHS.items()}
        (OUT/"manifest.json").write_bytes(canonical(dict(paths=PATHS,hashes=hashes)))
        old=json.loads(Path(PATHS["prior_manifest"]).read_bytes())
        for k in ["source","tokenizer","packer","messages","parse","lock"]:
            if hashes[k]!=old["hashes"][k]:raise ValueError("historical input hash mismatch:"+k)
        source=json.loads(Path(PATHS["source"]).read_bytes())
        chunks={c["chunk_id"]:c for c in source["chunks"]}
        rows=[json.loads(s) for s in Path(PATHS["rows"]).read_text().splitlines()]
        by={(r["question_id"],r["arm"]):r for r in rows}
        if len(by)!=120 or len(rows)!=120:raise ValueError("unexpected source rows")
        qids=sorted({r["question_id"] for r in rows})
        if len(qids)!=24 or set(by)!={(q,a) for q in qids for a in ["A1","B","C","D","E"]}:
            raise ValueError("unexpected row universe")
        tok=Tokenizer.from_file(PATHS["tokenizer"]);tok.no_padding();tok.no_truncation()
        count=lambda text:len(tok.encode(text).ids)
        def pair(question,ids):
            raw=[chunks[cid] for cid in ids]
            compact=[encode(c) for c in raw]
            if [canonical(decode_serialized(canonical(c))) for c in compact]!=[canonical(c) for c in raw]:
                raise ValueError("representation mismatch")
            measured={}
            for label,evidence in [("raw",raw),("compact",compact)]:
                m=_measure(question,evidence,count)
                measured[label]=dict(tokens=m["tokens"],bytes=m["bytes"],sha256=m["sha256"],
                                     fits=m["tokens"]<=BASE_TOKENS and m["bytes"]<=BASE_BYTES)
            return dict(chunk_ids=ids,**measured)
        for q in qids:
            for arm in ["A1","B","C","E"]:
                result=dict(question_id=q,arm=arm,status="error")
                try:
                    r=by[q,arm]["result"]
                    if r["status"]!="ok":raise ValueError("upstream failure")
                    messages=r["base"]["messages"]
                    question=json.loads(messages[1]["content"])["question"]
                    ids=r["candidate_chunk_ids"]
                    if len(ids)>8 or len(set(ids))!=len(ids):raise ValueError("candidate policy")
                    selected=r["selected_chunk_ids"]
                    if [chunks[cid] for cid in selected]!=r["selected_chunks"]:raise ValueError("saved source mismatch")
                    selection=pair(question,selected)
                    if any(selection["raw"][k]!=r["base"][k] for k in ["tokens","bytes","sha256"]):
                        raise ValueError("raw replay mismatch")
                    prefixes=[pair(question,ids[:n]) for n in range(len(ids)+1)]
                    result.update(status="ok",saved_selection=selection,candidate_prefixes=prefixes,
                                  candidate_chunk_ids=ids)
                except Exception as exc:
                    result["error"]=type(exc).__name__+": "+str(exc)
                results.append(result)
                (OUT/"rows.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in results))
        stable=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==hashes[k] for k,p in PATHS.items())
        if not stable:raise ValueError("input changed")
        ok=[r for r in results if r["status"]=="ok"]
        summary.update(input_hashes_stable=True,ok=len(ok),by_arm={})
        for arm in ["A1","B","C","E"]:
            rs=[r for r in ok if r["arm"]==arm]
            summary["by_arm"][arm]=dict(rows=len(rs),
                raw_selected_tokens=sum(r["saved_selection"]["raw"]["tokens"] for r in rs),
                compact_selected_tokens=sum(r["saved_selection"]["compact"]["tokens"] for r in rs),
                compact_selected_over_cap=sum(not r["saved_selection"]["compact"]["fits"] for r in rs),
                full_candidate_raw_fits=sum(r["candidate_prefixes"][-1]["raw"]["fits"] for r in rs),
                full_candidate_compact_fits=sum(r["candidate_prefixes"][-1]["compact"]["fits"] for r in rs))
    except Exception as exc:
        summary["error"]=type(exc).__name__+": "+str(exc)
    finally:
        summary.update(processed=len(results),unprocessed=96-len(results),
                       failed=sum(r["status"]!="ok" for r in results))
        (OUT/"summary.json").write_bytes(canonical(summary))
        print(json.dumps(summary))
    return 0 if summary.get("ok")==96 and not summary.get("error") else 1


if __name__=="__main__":
    raise SystemExit(main())
