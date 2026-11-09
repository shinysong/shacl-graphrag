"""Compact common-budget packing; no gold, retrieval, or model execution."""
import copy
import hashlib
import json
from scripts.graphrag_expand import _index
from scripts.graphrag_compact_cells import (
    canonical, encode, decode_serialized, RepresentationError, _pairs, _constant)
from scripts.graphrag_message_pack import _measure, BASE_TOKENS, BASE_BYTES


def transmitted_chunks(base):
    """Strict base-only envelope; no corpus lookup or report acceptance."""
    try:
        from scripts.graphrag_input_contract import SYSTEM
        if type(base) is not dict or set(base)!={"messages","serialized","tokens","bytes","sha256"}:
            raise ValueError("measurement fields")
        if type(base["serialized"]) is not str:
            raise ValueError("serialized text required")
        messages=json.loads(base["serialized"],object_pairs_hook=_pairs,parse_constant=_constant)
        raw=canonical(messages)
        if raw.decode()!=base["serialized"] or raw!=canonical(base["messages"]):
            raise RepresentationError("compact_integrity_failure","message mismatch")
        if (hashlib.sha256(raw).hexdigest()!=base["sha256"] or
                type(base["bytes"]) is not int or base["bytes"]!=len(raw)):
            raise RepresentationError("compact_integrity_failure","message digest/bytes mismatch")
        if type(base["tokens"]) is not int or base["tokens"]<0:
            raise ValueError("invalid token metadata")
        if (type(messages) is not list or len(messages)!=2 or
                any(type(m) is not dict or set(m)!={"role","content"} for m in messages) or
                messages[0]!={"role":"system","content":SYSTEM} or messages[1]["role"]!="user"):
            raise ValueError("base message schema")
        body=json.loads(messages[1]["content"],object_pairs_hook=_pairs,parse_constant=_constant)
        if (type(body) is not dict or set(body)!={"question","evidence","validation"} or
                type(body["question"]) is not str or not body["question"] or
                body["validation"] is not None or type(body["evidence"]) is not list or
                canonical(body).decode()!=messages[1]["content"]):
            raise ValueError("base body schema")
        return [decode_serialized(canonical(p)) for p in body["evidence"]]
    except RepresentationError:
        raise
    except (ValueError,TypeError,KeyError,IndexError,UnicodeError,RecursionError) as exc:
        raise RepresentationError("compact_payload_failure",str(exc)) from exc


def pack_compact(question,candidate_ids,source,count_tokens,upstream_status="ok"):
    result=dict(status="input_error",error=None,candidate_chunk_ids=[],
                selected_chunk_ids=[],selected_chunks=[],compact_selected_chunks=[],
                skipped_budget_ids=[],evidence_sha256=None,compact_evidence_sha256=None,
                base=None,generator_ready=False,generation_executed=False,
                token_cap=BASE_TOKENS,byte_cap=BASE_BYTES)
    if upstream_status!="ok":
        result.update(status="upstream_error",error="upstream failure retained")
        return result
    stage="input_error"
    try:
        if type(question) is not str or not question:
            raise ValueError("nonempty question required")
        if (type(candidate_ids) is not list or len(candidate_ids)>8 or
            any(type(cid) is not str or not cid for cid in candidate_ids) or
            len(set(candidate_ids))!=len(candidate_ids)):
            raise ValueError("at most eight unique candidate IDs required")
        result["candidate_chunk_ids"]=list(candidate_ids)
        stage="source_integrity_failure"
        _,_,chunks,_,_=_index(source)
        if any(cid not in chunks for cid in candidate_ids):
            raise ValueError("unknown source chunk")
        # Validate all candidates first: an invalid late candidate cannot be
        # silently omitted even when preceding candidates fill the budget.
        encoded={cid:encode(chunks[cid]) for cid in candidate_ids}
        stage="input_error"
        selected=[];skipped=[]
        measured=_measure(question,[],count_tokens)
        if measured["tokens"]>BASE_TOKENS or measured["bytes"]>BASE_BYTES:
            result.update(status="overhead_budget_error",error="empty overhead exceeds cap",base=measured)
            return result
        for cid in candidate_ids:
            tentative=selected+[cid]
            m=_measure(question,[encoded[x] for x in tentative],count_tokens)
            if m["tokens"]>BASE_TOKENS or m["bytes"]>BASE_BYTES:
                skipped.append(cid)
            else:
                selected=tentative;measured=m
        compact=[copy.deepcopy(encoded[cid]) for cid in selected]
        raw=[copy.deepcopy(chunks[cid]) for cid in selected]
        decoded=transmitted_chunks(measured)
        if canonical(decoded)!=canonical(raw):
            raise RepresentationError("compact_integrity_failure","decoded source mismatch")
        result.update(status="ok" if selected else "evidence_budget_error",
                      error=None if selected else "no candidate fits",
                      selected_chunk_ids=selected,selected_chunks=raw,
                      compact_selected_chunks=compact,skipped_budget_ids=skipped,base=measured,
                      evidence_sha256=hashlib.sha256(canonical(raw)).hexdigest(),
                      compact_evidence_sha256=hashlib.sha256(canonical(compact)).hexdigest())
    except (ValueError,TypeError,KeyError,UnicodeError,RecursionError,AttributeError) as exc:
        result.update(status=getattr(exc,"status",stage),error=type(exc).__name__,
                      selected_chunk_ids=[],selected_chunks=[],compact_selected_chunks=[],
                      skipped_budget_ids=[],base=None,evidence_sha256=None,
                      compact_evidence_sha256=None)
    return result
