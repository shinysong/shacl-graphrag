"""Common base-message packing only; no report, retrieval or model execution."""
import copy
import hashlib
from scripts.graphrag_expand import _index
from scripts.graphrag_check import canonical_bytes
from scripts.graphrag_input_contract import SYSTEM

BASE_TOKENS = 3072
BASE_BYTES = 48000


def base_messages(question, evidence):
    return [{'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': canonical_bytes(
                dict(question=question, evidence=evidence, validation=None)).decode('utf-8')}]


def _measure(question, evidence, count_tokens):
    messages = base_messages(question, evidence)
    raw = canonical_bytes(messages)
    tokens = count_tokens(raw.decode('utf-8'))
    if type(tokens) is not int or tokens < 0:
        raise ValueError('token count must be nonnegative integer')
    return dict(messages=messages, serialized=raw.decode('utf-8'), tokens=tokens,
                bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def pack_base(question, candidate_ids, source, count_tokens, upstream_status='ok'):
    """Candidate order supplied externally; at most eight; preserve source chunks."""
    result = dict(status='input_error', error=None, candidate_chunk_ids=[],
        selected_chunk_ids=[], selected_chunks=[], skipped_budget_ids=[],
        evidence_sha256=None, base=None, generator_ready=False, generation_executed=False,
        token_cap=BASE_TOKENS, byte_cap=BASE_BYTES)
    if upstream_status != 'ok':
        result.update(status='upstream_error', error='upstream failure retained')
        return result
    try:
        if not isinstance(question, str) or not question:
            raise ValueError('nonempty question required')
        if (not isinstance(candidate_ids, list) or len(candidate_ids) > 8
                or any(not isinstance(cid, str) or not cid for cid in candidate_ids)
                or len(candidate_ids) != len(set(candidate_ids))):
            raise ValueError('expected at most eight unique candidate IDs')
        _, _, chunks, _, _ = _index(source)
        if any(cid not in chunks for cid in candidate_ids):
            raise ValueError('unknown candidate identity')
        result['candidate_chunk_ids'] = list(candidate_ids)
        selected, skipped = [], []
        measured = _measure(question, selected, count_tokens)
        if measured['tokens'] > BASE_TOKENS or measured['bytes'] > BASE_BYTES:
            result.update(status='overhead_budget_error', error='empty-message overhead exceeds cap',
                          base=measured, evidence_sha256=hashlib.sha256(canonical_bytes([])).hexdigest())
            return result
        for cid in candidate_ids:
            tentative = selected + [copy.deepcopy(chunks[cid])]
            candidate = _measure(question, tentative, count_tokens)
            if candidate['tokens'] > BASE_TOKENS or candidate['bytes'] > BASE_BYTES:
                skipped.append(cid)
            else:
                selected, measured = tentative, candidate
        result.update(status='ok' if selected else 'evidence_budget_error',
            error=None if selected else 'no candidate fits',
            selected_chunk_ids=[c['chunk_id'] for c in selected], selected_chunks=selected,
            skipped_budget_ids=skipped, base=measured,
            evidence_sha256=hashlib.sha256(canonical_bytes(selected)).hexdigest())
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, AttributeError) as exc:
        # Do not expose partial selections when input/accounting fails mid-loop.
        result.update(status='input_error', error=type(exc).__name__, selected_chunk_ids=[],
                      selected_chunks=[], skipped_budget_ids=[], base=None, evidence_sha256=None)
    return result
