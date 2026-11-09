"""Immutable compact C evidence plus scoped report; no source/checker calls."""
import copy
import hashlib
import json
from scripts.graphrag_compact_cells import canonical
from scripts.graphrag_compact_pack import transmitted_chunks
from scripts.graphrag_input_contract import prepare_bundle, ARMS
from scripts.graphrag_message_pack import _measure, BASE_TOKENS, BASE_BYTES


def account_compact_report(question,base,report,count_tokens,checker_status="ok"):
    output=dict(C=copy.deepcopy(base),D=dict(status="input_error",error=None,
                report=copy.deepcopy(report),full=None,increment_tokens=None,
                increment_bytes=None,evidence_sha256=None,compact_evidence_sha256=None,
                generator_ready=False,generation_executed=False))
    d=output["D"]
    try:
        if base.get("status")!="ok":
            d.update(status="upstream_error",error="C base unsuccessful")
            return output
        decoded=transmitted_chunks(base["base"])
        compact=json.loads(base["base"]["messages"][1]["content"])["evidence"]
        if (canonical(decoded)!=canonical(base["selected_chunks"]) or
                canonical(compact)!=canonical(base["compact_selected_chunks"]) or
                not decoded or len(decoded)>8):
            raise ValueError("selected evidence mismatch")
        envelope=dict(status="ok",question_id="accounting-only",selected_chunks=decoded,
                      selected_chunk_ids=base["selected_chunk_ids"],evidence_sha256=base["evidence_sha256"])
        if hashlib.sha256(canonical(compact)).hexdigest()!=base["compact_evidence_sha256"]:
            raise ValueError("compact evidence digest")
        measured=_measure(question,compact,count_tokens)
        if measured!=base["base"] or measured["tokens"]>BASE_TOKENS or measured["bytes"]>BASE_BYTES:
            raise ValueError("C accounting mismatch")
        d.update(evidence_sha256=base["evidence_sha256"],
                 compact_evidence_sha256=base["compact_evidence_sha256"])
    except Exception as exc:
        d.update(status="input_error",error=type(exc).__name__)
        return output
    if checker_status!="ok":
        d.update(status="validation_execution_error",error="checker failure retained")
        return output
    try:
        # Existing validator adapter only, not independent arm measurements.
        validated=prepare_bundle(dict(question_id="accounting-only",question=question),
                                 {a:envelope for a in ARMS},report)["D"]
        body=json.loads(validated[1]["content"])
        if canonical(body["evidence"])!=canonical(decoded):
            raise ValueError("validator evidence changed")
        body["evidence"]=compact
        messages=copy.deepcopy(base["base"]["messages"])
        messages[1]["content"]=canonical(body).decode()
    except Exception as exc:
        d.update(status="validation_execution_error",error=type(exc).__name__)
        return output
    try:
        raw=canonical(messages);tokens=count_tokens(raw.decode())
        if type(tokens) is not int or tokens<0:raise ValueError("invalid token count")
        d["full"]=dict(messages=messages,serialized=raw.decode(),tokens=tokens,bytes=len(raw),
                       sha256=hashlib.sha256(raw).hexdigest())
        d["increment_tokens"]=tokens-measured["tokens"]
        d["increment_bytes"]=len(raw)-measured["bytes"]
        fits=(tokens<=4096 and len(raw)<=64000 and
              d["increment_tokens"]<=1024 and d["increment_bytes"]<=16000)
        d.update(status="ok" if fits else "report_budget_error",
                 error=None if fits else "full or incremental report budget exceeded")
    except Exception as exc:
        d.update(status="accounting_error",error=type(exc).__name__)
    return output
