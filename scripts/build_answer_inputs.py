"""Freeze source-only answer messages; no model client or reference access."""
import hashlib
import json
from pathlib import Path
from scripts.graphrag_check import canonical_bytes, _parse

ROOT=Path("research/answer-evidence-1")
OUT=ROOT/"answer-inputs-001"
PATHS=dict(design=ROOT/"answer-comparison-freeze-v1.json",
           schema=ROOT/"answer-schema-v1.json",system=ROOT/"answer-system-v1.txt",
           rows=ROOT/"anchor-on-001/rows.jsonl",
           source=Path("research/graphrag-evidence-1/source-corpus-v1.json"),
           questions=Path("research/graphrag-evidence-1/development-questions.json"),
           prior_manifest=ROOT/"anchor-on-001/manifest.json",
           parser=Path("scripts/graphrag_check.py"),builder=Path(__file__))
ARMS=("B","C","D")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    results=[]
    summary=dict(planned=72,processed=0,unprocessed=72,failed=0,
                 generator_ready=False,generation_executed=False,paid_calls=0)
    try:
        hashes={k:digest(p.read_bytes()) for k,p in PATHS.items()}
        frozen=OUT/"frozen";frozen.mkdir()
        for k,p in PATHS.items():(frozen/(k+"-"+p.name)).write_bytes(p.read_bytes())
        (OUT/"input-hashes.json").write_bytes(canonical_bytes(dict(paths={k:str(p) for k,p in PATHS.items()},hashes=hashes)))
        design=json.loads(PATHS["design"].read_bytes())
        for p,h in design["source_variant"]["frozen_paths"].items():
            if digest(Path(p).read_bytes())!=h:raise ValueError("design binding mismatch")
        prior=json.loads(PATHS["prior_manifest"].read_bytes())
        for key in ["source","questions"]:
            if hashes[key]!=prior["hashes"][key]:raise ValueError("source/question mismatch")
        source=json.loads(PATHS["source"].read_bytes())
        source_chunks={c["chunk_id"]:c for c in source["chunks"]}
        questions=json.loads(PATHS["questions"].read_bytes())["questions"]
        qmap={q["question_id"]:q["question"] for q in questions}
        if len(qmap)!=24 or len(questions)!=24:raise ValueError("question universe")
        rows=[json.loads(s) for s in PATHS["rows"].read_text().splitlines()]
        by={(r["question_id"],r["arm"]):r for r in rows}
        if len(rows)!=120 or set(by)!={(q,a) for q in qmap for a in ("A1","B","C","D","E")}:
            raise ValueError("source rows universe")
        schema=json.loads(PATHS["schema"].read_bytes())
        system=PATHS["system"].read_text().strip()+"\n\nJSON schema:\n"+canonical_bytes(schema).decode()
        planned=sorted([(q,a) for q in qmap for a in ARMS],
                       key=lambda k:digest(("answer-order-v1|"+k[0]+"|"+k[1]).encode()))
        (OUT/"planned.json").write_bytes(canonical_bytes([dict(episode_id=q+"-"+a,question_id=q,arm=a) for q,a in planned]))
        for q,a in planned:
            item=dict(episode_id=q+"-"+a,question_id=q,arm=a,status="preparation_error")
            try:
                r=by[q,a]["result"]
                if r["status"]!="ok":raise ValueError("upstream failure")
                env=dict(status="ok",selected_chunks=r["selected_chunks"],
                         selected_chunk_ids=r["selected_chunk_ids"],evidence_sha256=r["evidence_sha256"])
                _parse(env)
                if any(canonical_bytes(c)!=canonical_bytes(source_chunks[c["chunk_id"]]) for c in env["selected_chunks"]):
                    raise ValueError("source-exact mismatch")
                saved=r["full"] if a=="D" else r["base"]
                if digest(canonical_bytes(saved["messages"]))!=saved["sha256"] or canonical_bytes(saved["messages"]).decode()!=saved["serialized"]:
                    raise ValueError("saved message digest")
                body=json.loads(saved["messages"][1]["content"])
                if set(body)!={"question","evidence","validation"} or body["question"]!=qmap[q] or canonical_bytes(body["evidence"])!=canonical_bytes(env["selected_chunks"]):
                    raise ValueError("saved body mismatch")
                if a!="D" and body["validation"] is not None:raise ValueError("unexpected report")
                if a=="D":
                    c=by[q,"C"]["result"]
                    if canonical_bytes(body["evidence"])!=canonical_bytes(c["selected_chunks"]) or canonical_bytes(body["validation"])!=canonical_bytes(r["report"]):
                        raise ValueError("D differs from C/report")
                messages=[dict(role="system",content=system),dict(role="user",content=canonical_bytes(body).decode())]
                raw=canonical_bytes(messages)
                item.update(status="prepared_not_admitted",messages=messages,
                            message_sha256=digest(raw),serialized_bytes=len(raw),
                            selected_chunk_ids=env["selected_chunk_ids"],evidence_sha256=env["evidence_sha256"],
                            model_id=None,provider=None,actual_input_tokens=None,
                            output_reserve=None,admission="pending",generation_executed=False)
            except Exception as exc:item["error"]=type(exc).__name__+": "+str(exc)
            results.append(item)
            (OUT/"episodes.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in results))
        if any(digest(p.read_bytes())!=hashes[k] for k,p in PATHS.items()):
            raise ValueError("inputs changed")
        summary.update(prepared=sum(x["status"]=="prepared_not_admitted" for x in results),
                       input_hashes_stable=True,
                       max_serialized_bytes=max((x.get("serialized_bytes",0) for x in results),default=0))
    except Exception as exc:summary["error"]=type(exc).__name__+": "+str(exc)
    finally:
        summary.update(processed=len(results),unprocessed=72-len(results),
                       failed=sum(x["status"]!="prepared_not_admitted" for x in results))
        (OUT/"summary.json").write_bytes(canonical_bytes(summary));print(json.dumps(summary))
    return 0 if summary.get("prepared")==72 and not summary.get("error") else 1


if __name__=="__main__":raise SystemExit(main())
