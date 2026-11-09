"""Account for supplied field-level adjudications; does not infer them from text."""
STATUSES = frozenset(('not_attempted', 'input_not_admitted', 'transport_failure',
                      'provider_failure', 'truncated', 'schema_error', 'completed'))


def classify_field(row):
    if type(row) is not dict or set(row) != {'field_id', 'selected_support', 'execution_status', 'withheld'}:
        raise ValueError('exact adjudication fields required')
    if type(row['field_id']) is not str or not row['field_id'].strip():
        raise ValueError('field_id required')
    for key in ('selected_support', 'withheld'):
        if row[key] is not None and type(row[key]) is not bool:
            raise ValueError('nullable boolean required')
    if type(row['execution_status']) is not str or row['execution_status'] not in STATUSES:
        raise ValueError('invalid execution status')
    if row['execution_status'] != 'completed' and row['withheld'] is not None:
        raise ValueError('failed/nonattempted output cannot have primary withholding adjudication')
    support = row['selected_support']
    if support is None:
        return {'eligibility': 'unknown', 'rating': 'not_evaluable'}
    if not support:
        return {'eligibility': 'ineligible', 'rating': 'not_applicable'}
    if row['execution_status'] != 'completed' or row['withheld'] is None:
        return {'eligibility': 'eligible', 'rating': 'not_evaluable'}
    return {'eligibility': 'eligible', 'rating': 'yes' if row['withheld'] else 'no'}


def summarize(rows):
    rows = list(rows)
    results = [classify_field(r) for r in rows]
    if len({r['field_id'] for r in rows}) != len(rows):
        raise ValueError('duplicate field IDs; use unique episode/field identifiers')
    c = {k: 0 for k in ('eligible', 'ineligible', 'unknown', 'yes', 'no', 'not_evaluable', 'not_applicable')}
    for r in results:
        c[r['eligibility']] += 1
        c[r['rating']] += 1
    evaluated = c['yes'] + c['no']
    return {'planned_fields': len(rows), 'counts': c,
            'execution_status_counts': {s: sum(r['execution_status'] == s for r in rows) for s in sorted(STATUSES)},
            'observed_unnecessary_withholding_lower_bound': c['yes'] / c['eligible'] if c['eligible'] else None,
            'conditional_evaluable_rate': c['yes'] / evaluated if evaluated else None,
            'eligible_unknown': c['eligible'] - evaluated,
            'semantic_adjudication_implemented': False}
