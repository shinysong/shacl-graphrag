"""Model-selected source pointers. Matching a pointer is not claim verification."""
from copy import deepcopy


def catalog(sources):
    """Use the same source entry IDs as generation, with hash-bound locators."""
    result = {}
    for source in sources:
        base = {'file': source['name'], 'sha256': source['sha256']}
        if source['kind'] == 'table':
            for column in source['headers']:
                result[f'map:{source["name"]}:{column}'] = {**base, 'column': column}
        else:
            for paragraph in source['paragraphs']:
                result[f'policy:{source["name"]}:{paragraph["paragraph"]}'] = {
                    **base, **{k: paragraph[k] for k in ('paragraph', 'line_start', 'line_end')}}
    return result


def resolve(ids, sources):
    if (not isinstance(ids, list) or len(ids) > 8 or
            any(not isinstance(v, str) for v in ids) or len(set(ids)) != len(ids)):
        raise ValueError('Evidence must contain at most 8 unique source entry IDs')
    available = catalog(sources)
    if any(v not in available for v in ids):
        raise ValueError('Evidence entry does not exist in this source snapshot')
    return [{'entry_id': v, **deepcopy(available[v])} for v in ids]


def validate(refs, sources):
    if not isinstance(refs, list) or any(not isinstance(v, dict) for v in refs):
        raise ValueError('Invalid proposal evidence locators')
    expected = resolve([v.get('entry_id') for v in refs], sources)
    # Exact serialized locators reject booleans masquerading as integer positions.
    import json
    if json.dumps(refs, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError('Proposal evidence locator does not match source snapshot')
