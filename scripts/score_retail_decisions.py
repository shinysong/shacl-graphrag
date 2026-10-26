"""Offline scorer only: reference labels never enter runtime policy evaluation."""
from collections import Counter

REFERENCE = {'pass', 'violation', 'unknown'}
PREDICTION = REFERENCE | {'error'}

def indexed(rows, allowed):
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Records must be objects')
        k = (row.get('row_id'), row.get('policy'))
        if any(not isinstance(v, str) or not v.strip() for v in k):
            raise ValueError('row_id and policy must be nonblank strings')
        if k in result:
            raise ValueError('Duplicate row/policy')
        status = row.get('status')
        if not isinstance(status, str) or status not in allowed:
            raise ValueError('Unsupported status')
        result[k] = status
    return result

def ratio(n, d):
    return n / d if d else None

def summarize(pairs):
    matrix = Counter(pairs)
    n = len(pairs)
    known = sum(g != 'unknown' for g, p in pairs)
    decided = sum(p in {'pass', 'violation'} for g, p in pairs)
    known_decided = sum(g != 'unknown' and p in {'pass', 'violation'} for g, p in pairs)
    tp = matrix['violation','violation']
    fp = matrix['pass','violation']
    fn = sum(matrix['violation',p] for p in ('pass','unknown','error','missing_output'))
    errors = fp + matrix['violation','pass']
    unknown_refs = n - known
    unsupported = matrix['unknown','pass'] + matrix['unknown','violation']
    return {
        'n': n, 'known_reference_n': known,
        'confusion': {g: {p: matrix[g,p] for p in ('pass','violation','unknown','error','missing_output')} for g in ('pass','violation','unknown')},
        'violation_tp': tp, 'violation_fp': fp, 'violation_fn': fn,
        'violation_precision_known_refs': ratio(tp,tp+fp),
        'violation_recall_known_refs': ratio(tp,tp+fn),
        'violation_f1_known_refs': ratio(2*tp,2*tp+fp+fn),
        'coverage_all': ratio(decided,n),
        'coverage_known_refs': ratio(known_decided,known),
        'selective_error_known_refs': ratio(errors,known_decided),
        'false_pass_n': matrix['violation','pass'],
        'unnecessary_abstention_known_refs_n': sum(matrix[g,'unknown'] for g in ('pass','violation')),
        'unsupported_decision_unknown_refs_n': unsupported,
        'unsupported_decision_unknown_refs_rate': ratio(unsupported,unknown_refs),
        'runtime_error_n': sum(matrix[g,'error'] for g in REFERENCE),
        'missing_output_n': sum(matrix[g,'missing_output'] for g in REFERENCE),
        'abstention_n': sum(matrix[g,'unknown'] for g in REFERENCE),
    }

def score(reference_rows, prediction_rows):
    refs = indexed(reference_rows, REFERENCE)
    preds = indexed(prediction_rows, PREDICTION)
    if preds.keys() - refs.keys():
        raise ValueError('Prediction contains an unexpected row/policy')
    by_policy = {}
    pairs = []
    for k, gold in refs.items():
        pair = (gold, preds.get(k, 'missing_output'))
        pairs.append(pair)
        by_policy.setdefault(k[1], []).append(pair)
    return {'overall': summarize(pairs), 'by_policy': {k:summarize(v) for k,v in sorted(by_policy.items())},
            'notes': ['Missing/error/abstention on reference violation counts as missed detection.',
                      'Unknown references excluded from binary metrics; unsupported decisions counted separately.',
                      'No human time, cost, confidence interval or external business truth inferred.']}
