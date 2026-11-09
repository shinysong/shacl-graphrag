"""Common proposed QA message contract. Accounting is not model execution."""
import hashlib
from scripts.graphrag_check import _parse, canonical_bytes

ARMS = ('A1', 'B', 'C', 'D', 'E')
COVERAGE = 'selected declared dictionary references only; no question applicability, edge provenance or process-rule checks'
SYSTEM = ('Answer only from the supplied evidence. Cite chunk IDs and source locations. '
          'Distinguish recorded values, derived conclusions, and missing evidence. '
          'Do not invent missing facts. A validation report, when supplied, concerns only its stated scope; '
          'conformance does not establish truth, completeness, or question applicability. '
          'No applicable checks is not a positive validation. '
          'Return JSON with answer, evidence_ids, and limitations. '
          'If evidence is insufficient, state that explicitly.')


def prepare_bundle(question, envelopes, report):
    if set(envelopes) != set(ARMS):
        raise ValueError('exact five-arm universe required')
    if not isinstance(question.get('question'), str) or not question['question']:
        raise ValueError('question text required')
    for envelope in envelopes.values():
        _parse(envelope)
        if envelope['question_id'] != question['question_id']:
            raise ValueError('question mismatch')
    for arm in ('D', 'E'):
        if envelopes[arm]['selected_chunks'] != envelopes['C']['selected_chunks']:
            raise ValueError('C/D/E evidence mismatch')
    expected = {'raw_conforms', 'results', 'applicable_bindings', 'coverage', 'no_bindings_status'}
    if not isinstance(report, dict) or set(report) != expected:
        raise ValueError('complete compact report required')
    if type(report['raw_conforms']) is not bool or not isinstance(report['results'], list):
        raise ValueError('invalid report types')
    if type(report['applicable_bindings']) is not int or report['applicable_bindings'] != len(report['results']):
        raise ValueError('invalid binding count')
    if report['coverage'] != COVERAGE:
        raise ValueError('unexpected report scope')
    if report['no_bindings_status'] != ('unknown' if not report['results'] else None):
        raise ValueError('invalid no-bindings status')
    check_ids = set()
    for check in report['results']:
        if not isinstance(check, dict) or set(check) != {'check_id','status','missing','conflicts','evidence_ids'}:
            raise ValueError('invalid check fields')
        if not isinstance(check['check_id'], str) or not check['check_id'] or check['check_id'] in check_ids:
            raise ValueError('invalid check ID')
        check_ids.add(check['check_id'])
        for field in ('missing','conflicts','evidence_ids'):
            values = check[field]
            if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values) or len(values) != len(set(values)):
                raise ValueError('invalid check list')
        if not check['evidence_ids'] or not set(check['evidence_ids']).issubset(envelopes['C']['selected_chunk_ids']):
            raise ValueError('unselected report citation')
        status = 'violation' if check['conflicts'] else 'unknown' if check['missing'] else 'pass'
        if check['status'] != status:
            raise ValueError('inconsistent operational status')
    messages = {}
    for arm in ARMS:
        user = {'question': question['question'], 'evidence': envelopes[arm]['selected_chunks'],
                'validation': report if arm == 'D' else None}
        messages[arm] = [{'role': 'system', 'content': SYSTEM},
                         {'role': 'user', 'content': canonical_bytes(user).decode()}]
    return messages


def account_bundle(messages, count_serialized_tokens, token_cap=4096, byte_cap=64000):
    # This deliberately does not expose a generator-ready mode: service chat framing
    # and model tokenizer accounting require a separate verified integration.
    if set(messages) != set(ARMS) or type(token_cap) is not int or token_cap < 1 or type(byte_cap) is not int or byte_cap < 1:
        raise ValueError('invalid arms or limits')
    result = {}
    for arm in ARMS:
        raw = canonical_bytes(messages[arm])
        tokens = count_serialized_tokens(raw.decode())
        if type(tokens) is not int or tokens < 0:
            raise ValueError('invalid token count')
        result[arm] = {'tokens': tokens, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                       'within_accounting_cap': tokens <= token_cap and len(raw) <= byte_cap}
    return {'arms': result, 'all_arms_within_accounting_cap': all(x['within_accounting_cap'] for x in result.values()),
            'generator_ready': False, 'generation_executed': False,
            'scope': 'serialized proposed messages only; actual chat framing and generator tokenizer unverified',
            'token_cap': token_cap, 'byte_cap': byte_cap}
