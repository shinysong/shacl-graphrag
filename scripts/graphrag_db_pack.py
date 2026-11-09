"""Selected B evidence to bounded relation candidates and ordered evidence packing.

No question, reference, answer or file reader is accepted by this interface.
"""
import copy
import hashlib
from scripts.graphrag_db_expand import canonical, expand


def relation_pack(source, envelope, count_tokens, backend='neo4j', db=None):
    """Fixed one-hop policy; fail closed on inconsistent selected B evidence."""
    empty = canonical([])
    result = dict(status='retrieval_error', error=None, backend=backend,
                  seed_chunk_ids=[], candidate_chunk_ids=[], eligible_chunk_ids=[],
                  selected_chunk_ids=[], selected_chunks=[], skipped_budget_ids=[],
                  evidence_sha256=hashlib.sha256(empty).hexdigest(), evidence_bytes=2,
                  evidence_tokens=None, accounting_tokens=None,
                  accounting_tokenizer='pinned-E5-not-generator', trace=[],
                  configuration=dict(max_depth=1, max_candidates=32,
                                     intermediate_byte_cap=64000, parent_k=8,
                                     token_cap=4096, byte_cap=64000))
    try:
        if envelope.get('status') != 'ok':
            raise ValueError('upstream failure retained')
        chunks = {c['chunk_id']: c for c in source['chunks']}
        if len(chunks) != len(source['chunks']):
            raise ValueError('duplicate source chunks')
        selected = envelope['selected_chunks']
        ids = [c['chunk_id'] for c in selected]
        raw = canonical(selected)
        if (not ids or len(ids) > 8 or len(set(ids)) != len(ids)
                or ids != envelope['selected_chunk_ids']
                or ids != envelope['seed_chunk_ids']
                or any(c != chunks.get(c['chunk_id']) for c in selected)
                or len(raw) != envelope['evidence_bytes']
                or hashlib.sha256(raw).hexdigest() != envelope['evidence_sha256']):
            raise ValueError('invalid B evidence identity')
        n = count_tokens(raw.decode())
        if type(n) is not int or n < 1 or n > 4096 or len(raw) > 64000:
            raise ValueError('invalid B evidence budget')
        result['seed_chunk_ids'] = list(ids)
        expanded = expand(source, ids, backend=backend, max_depth=1,
                          max_candidates=32, max_evidence_bytes=64000, db=db)
        result['candidate_chunk_ids'] = expanded['candidate_chunk_ids']
        result['trace'] = expanded['trace']
        if expanded['status'] != 'ok':
            result.update(status=expanded['status'], error=expanded['error'])
            return result
        eligible = expanded['selected_chunks'][:8]
        result['eligible_chunk_ids'] = [c['chunk_id'] for c in eligible]
        packed = []
        for chunk in eligible:
            payload = canonical(packed + [chunk])
            n = count_tokens(payload.decode())
            if type(n) is not int or n < 1:
                raise ValueError('invalid accounting token count')
            if n > 4096 or len(payload) > 64000:
                result['skipped_budget_ids'].append(chunk['chunk_id'])
            else:
                packed.append(copy.deepcopy(chunk))
        raw = canonical(packed)
        n = count_tokens(raw.decode())
        if type(n) is not int or not 1 <= n <= 4096 or len(raw) > 64000:
            raise ValueError('invalid final accounting count')
        result.update(status='ok' if packed else 'budget_error',
                      error=None if packed else 'no candidate fits budget',
                      selected_chunks=packed, selected_chunk_ids=[c['chunk_id'] for c in packed],
                      evidence_sha256=hashlib.sha256(raw).hexdigest(), evidence_bytes=len(raw),
                      accounting_tokens=n)
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError) as exc:
        result.update(status='retrieval_error', error=f'{type(exc).__name__}: {exc}')
    return result
