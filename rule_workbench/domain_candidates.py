"""Exact declared-domain lookup, not natural-language column interpretation."""
from collections import Counter, defaultdict
import hashlib

from scripts.profile_public_domains import profile


def find_domain_candidates(raw_csv, requests):
    """Verify pinned dictionary and retain all exact-name rows, never select one.

    requests: list of column_id, domain_name, optional declared_type (raw string).
    A declared type comparison is informational, never a compatibility judgment.
    """
    _, project = profile(raw_csv)
    if not isinstance(requests, list) or len(requests) > 1000:
        raise ValueError('Supply at most 1000 column requests.')
    seen = set()
    for request in requests:
        if (not isinstance(request, dict)
                or not {'column_id', 'domain_name'} <= set(request)
                or set(request) - {'column_id', 'domain_name', 'declared_type'}
                or any(not isinstance(request[k], str) or not request[k].strip()
                       for k in ['column_id', 'domain_name'])
                or ('declared_type' in request and
                    (not isinstance(request['declared_type'], str) or not request['declared_type'].strip()))):
            raise ValueError('Each request needs nonblank column_id/domain_name and optional nonblank declared_type.')
        if request['column_id'] in seen:
            raise ValueError('Duplicate column_id; use a table-qualified identifier.')
        seen.add(request['column_id'])
    index = defaultdict(list)
    digest = hashlib.sha256(raw_csv).hexdigest()
    for position, row in enumerate(project['tables'][0]['rows'], 1):
        index[row['공통표준도메인명']].append((position, row))
    results = []
    for request in requests:
        candidates = []
        for position, row in index.get(request['domain_name'], []):
            declared = request.get('declared_type')
            candidates.append({
                'snapshot_row_id': f'{digest}:{position}', 'source_record': position,
                'official_fields': dict(row),
                'type_comparison': 'not_supplied' if declared is None else (
                    'exact_string_agreement' if declared == row['데이터타입'] else 'different_string'),
            })
        results.append({'request': dict(request), 'status': (
            'not_found_in_snapshot' if not candidates else
            'ambiguous_name' if len(candidates) > 1 else 'single_candidate'),
            'approval_status': 'unreviewed', 'candidates': candidates})
    return {'schema_version': 1, 'source_sha256': digest,
            'counts': dict(Counter(r['status'] for r in results)), 'results': results,
            'scope': 'User-supplied domain names, exact lookup in pinned snapshot. No selected mapping, normalization, SQL type equivalence, generated rule or compliance judgment.'}
