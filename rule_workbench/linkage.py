"""Explicit relationship coverage audit; matches are not factual validation.

No fuzzy matching, LLM calls, automatic repair, or business approval. Alias
suggestions remain candidates even when only one target is suggested.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json

from .core import validate_project


def table_digest(table):
    """Bind reviewed mappings to an exact table snapshot, including provenance."""
    return hashlib.sha256(json.dumps(table, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def _key(value):
    # Preserve leading zeros, spaces, case and scalar type. No inferred coercion.
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return (type(value).__name__, str(value))


def audit_relationship(project, contract, aliases=()):
    """Audit one reviewed column relation without changing data or rules.

    contract: id, source_table/column, target_table/column, status,
    source_digest, target_digest. A confirmed mapping needs both snapshot
    digests. Target completeness is an explicit caller declaration, not a
    discovery; missing declaration, truncated or redacted data stay unknown.
    aliases: {source_value, target_value, evidence}; these NEVER establish links.
    """
    validate_project(project)
    tables = {t['id']: t for t in project['tables']}
    source = tables.get(contract.get('source_table'))
    target = tables.get(contract.get('target_table'))
    if (source is None or target is None
            or contract.get('source_column') not in source['columns']
            or contract.get('target_column') not in target['columns']):
        raise ValueError('A relationship needs existing source/target tables and columns.')
    alias_index = defaultdict(list)
    alias_sizes = {}
    for alias in aliases:
        if not isinstance(alias, dict) or not isinstance(alias.get('evidence'), str) or not alias['evidence'].strip():
            raise ValueError('Alias candidates need a nonempty evidence reference.')
        a, b = _key(alias.get('source_value')), _key(alias.get('target_value'))
        if a is None or b is None:
            raise ValueError('Alias candidates need nonempty source and target keys.')
        alias_index[a].append((b, alias['evidence']))
        # Upper bound for one serialized candidate (max table row is 5,000).
        alias_sizes[alias['evidence']] = len(json.dumps(
            {'target_row': 5000, 'evidence': alias['evidence']}, ensure_ascii=False).encode()) + 2
    index = defaultdict(list)
    for position, row in enumerate(target['rows'], 1):
        key = _key(row.get(contract['target_column']))
        if key is not None:
            index[key].append(position)
    provenance = target['source']
    complete = (provenance.get('complete') is True
                and not provenance.get('truncated') and not provenance.get('redacted')
                and not provenance.get('data_omitted'))
    blocked = None
    if contract.get('status') != 'confirmed':
        blocked = 'not_reviewed'
    elif (contract.get('source_digest') != table_digest(source)
          or contract.get('target_digest') != table_digest(target)):
        blocked = 'stale_mapping'
    results = []
    evidence_count = 0
    evidence_bytes = 0
    for position, row in enumerate(source['rows'], 1):
        value = row.get(contract['source_column'])
        key = _key(value)
        exact = index.get(key, []) if key is not None else []
        evidence_count += len(exact) + sum(len(index.get(suggested, []))
                                         for suggested, _ in alias_index.get(key, []))
        if evidence_count > 50_000:
            raise ValueError('연결 근거가 50,000개를 넘습니다. 입력 자료를 나누어 검사하세요.')
        evidence_bytes += len(exact) * 6 + sum(
            len(index.get(suggested, [])) * alias_sizes[evidence]
            for suggested, evidence in alias_index.get(key, []))
        if evidence_bytes > 2_000_000:
            raise ValueError('연결 근거의 펼친 크기가 2MB를 넘습니다. 근거 문구나 입력 자료를 줄이세요.')
        candidates = []
        for suggested, evidence in alias_index.get(key, []):
            candidates.extend({'target_row': r, 'evidence': evidence}
                              for r in index.get(suggested, []))
        if blocked:
            status = blocked
        elif key is None:
            status = 'missing_key'
        elif len(exact) > 1:
            status = 'ambiguous'
        elif not complete:
            status = 'unknown_target_scope'
        elif exact:
            status = 'linked'
        elif candidates:
            status = 'candidate_only'
        else:
            status = 'unmatched_in_snapshot'
        results.append({'source_row': position, 'value': value, 'status': status,
                        'exact_target_rows': list(exact), 'alias_candidates': candidates})
    return {'relationship_id': contract.get('id'), 'source_table': source['id'],
            'target_table': target['id'], 'target_complete_declared': complete,
            'source_truncated': bool(source['source'].get('truncated')),
            'source_redacted': bool(source['source'].get('redacted') or source['source'].get('data_omitted')),
            'source_digest': table_digest(source), 'target_digest': table_digest(target),
            'denominator': len(source['rows']), 'counts': dict(Counter(r['status'] for r in results)),
            'results': results,
            'scope': 'Coverage of imported rows under a supplied column mapping, not semantic identity or business validity.'}
