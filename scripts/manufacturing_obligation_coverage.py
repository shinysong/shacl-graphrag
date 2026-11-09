"""Inspect declared input obligations, never infer truth or repair answers."""
from scripts.manufacturing_answer_adapter import decode


def inspect_path(row, path):
    current = row
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return 'missing'
    if current is None:
        return 'explicit_null'
    if isinstance(current, (str, list, dict)) and not current:
        return 'empty'
    return 'present'


def coverage(saved, contract):
    result = {'backend': saved['backend'], 'question_id': saved['case_id'],
              'upstream_status': saved['status'], 'status': 'not_evaluated',
              'obligations': [], 'claim_scope': 'input availability under authored paths, not answer correctness'}
    if saved['status'] != 'completed':
        result['status'] = 'unsupported' if saved['status'] == 'unsupported' else 'upstream_failure'
        return result
    try:
        rows = [{k: decode(v) for k, v in row.items()} for row in saved['bindings']]
        for obligation in contract['obligations']:
            observations = [[inspect_path(row, p) for p in obligation['paths']] for row in rows]
            present = bool(rows) and all(all(s == 'present' for s in states) for states in observations)
            result['obligations'].append({'id': obligation['id'], 'label': obligation['label'],
                                          'input_available': present, 'observations': observations})
        result['status'] = 'inspected'
        result['available_count'] = sum(o['input_available'] for o in result['obligations'])
        result['declared_count'] = len(result['obligations'])
        # No all-complete flag: path presence does not establish scope, identity, or semantic correctness.
        return result
    except (ValueError, TypeError, KeyError) as exc:
        result['status'] = 'input_error'
        result['error'] = type(exc).__name__ + ':' + str(exc)
        return result
