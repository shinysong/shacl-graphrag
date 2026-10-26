"""Declared exact field equality after reviewed, unique snapshot linkage.

No approval, physical identity inference, normalization, or factual correction.
"""
from collections import Counter
from .linkage import audit_relationship, _key


def audit_field_consistency(project, contract, aliases=()):
    """contract adds equality_pairs and equality_status='confirmed'.

    Confirmation is a supplied assertion covering field pairs, not model inference.
    Snapshot digests are checked by the relationship auditor. Every comparison is
    scoped to imported records; agreement never means the inspection passed.
    """
    linkage = audit_relationship(project, contract, aliases)
    tables = {t['id']: t for t in project['tables']}
    source, target = tables[contract['source_table']], tables[contract['target_table']]
    pairs = contract.get('equality_pairs')
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 20:
        raise ValueError('Supply 1–20 declared equality field pairs.')
    for pair in pairs:
        if (not isinstance(pair, dict) or set(pair) != {'source_column', 'target_column'}
                or pair['source_column'] not in source['columns']
                or pair['target_column'] not in target['columns']):
            raise ValueError('Equality fields must exist in both table schemas.')
    results = []
    for link in linkage['results']:
        comparisons = []
        if contract.get('equality_status') != 'confirmed':
            status, reason = 'not_evaluated', 'equality_not_reviewed'
        elif link['status'] != 'linked':
            status, reason = 'not_evaluated', link['status']
        else:
            left = source['rows'][link['source_row'] - 1]
            right = target['rows'][link['exact_target_rows'][0] - 1]
            for pair in pairs:
                a, b = left.get(pair['source_column']), right.get(pair['target_column'])
                ka, kb = _key(a), _key(b)
                state = 'missing_evidence' if ka is None or kb is None else (
                    'agrees' if ka == kb else 'violates_declared_equality')
                comparisons.append({**pair, 'source_value': a, 'target_value': b, 'status': state})
            states = {c['status'] for c in comparisons}
            # An observed violation is retained even if another field is missing.
            status = ('violates_declared_equality' if 'violates_declared_equality' in states else
                      'missing_evidence' if 'missing_evidence' in states else 'agrees')
            reason = 'reviewed_exact_equality'
        results.append({'source_row': link['source_row'], 'target_rows': link['exact_target_rows'],
                        'linkage_status': link['status'], 'status': status,
                        'reason': reason, 'comparisons': comparisons})
    return {'schema_version': 1, 'contract': contract.copy(), 'linkage': linkage,
            'denominator': len(results), 'counts': dict(Counter(r['status'] for r in results)),
            'results': results,
            'scope': 'Declared exact equality on uniquely linked supplied snapshots; not inspection acceptance or external truth.'}
