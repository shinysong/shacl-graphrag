"""Account a scoped report against an immutable C base; no checker/source calls."""
import copy
import hashlib
from scripts.graphrag_check import canonical_bytes, _parse
from scripts.graphrag_input_contract import prepare_bundle, ARMS
from scripts.graphrag_message_pack import _measure, BASE_TOKENS, BASE_BYTES


def account_report(question, base, report, count_tokens, checker_status='ok'):
    """Return preserved C and separate D result; E is external and never touched."""
    output = dict(C=copy.deepcopy(base), D=dict(status='input_error', error=None,
        report=copy.deepcopy(report), full=None, increment_tokens=None, increment_bytes=None,
        evidence_sha256=None, generator_ready=False, generation_executed=False))
    d = output['D']
    try:
        if base.get('status') != 'ok':
            d.update(status='upstream_error', error='C base unsuccessful')
            return output
        envelope = dict(status='ok', question_id='accounting-only',
            selected_chunks=base['selected_chunks'], selected_chunk_ids=base['selected_chunk_ids'],
            evidence_sha256=base['evidence_sha256'])
        _parse(envelope)
        measured = _measure(question, base['selected_chunks'], count_tokens)
        if (not base['selected_chunks'] or len(base['selected_chunks']) > 8
                or measured != base['base'] or measured['tokens'] > BASE_TOKENS
                or measured['bytes'] > BASE_BYTES):
            raise ValueError('C base identity/accounting mismatch')
        d['evidence_sha256'] = base['evidence_sha256']
    except Exception as exc:
        d.update(status='input_error', error=type(exc).__name__)
        return output
    if checker_status != 'ok':
        d.update(status='validation_execution_error', error='checker failure retained')
        return output
    try:
        # Reuse existing report schema/citation checks. These copies are an internal
        # validator adapter, NOT measured A/B/E results or a backend parity claim.
        messages = prepare_bundle(dict(question_id='accounting-only',question=question),
                                  {arm: envelope for arm in ARMS}, report)['D']
    except Exception as exc:
        d.update(status='validation_execution_error', error=type(exc).__name__)
        return output
    try:
        raw = canonical_bytes(messages)
        tokens = count_tokens(raw.decode('utf-8'))
        if type(tokens) is not int or tokens < 0:
            raise ValueError('invalid token count')
        d['full'] = dict(messages=messages, serialized=raw.decode('utf-8'),tokens=tokens,
                        bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        d['increment_tokens'] = tokens - measured['tokens']
        d['increment_bytes'] = len(raw) - measured['bytes']
        fits = (tokens <= 4096 and len(raw) <= 64000
                and d['increment_tokens'] <= 1024 and d['increment_bytes'] <= 16000)
        d.update(status='ok' if fits else 'report_budget_error',
                 error=None if fits else 'full or incremental report budget exceeded')
    except Exception as exc:
        d.update(status='accounting_error',error=type(exc).__name__)
    return output
