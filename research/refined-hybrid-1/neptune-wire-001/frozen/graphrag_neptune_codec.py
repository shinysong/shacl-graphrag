"""Offline Neptune Database openCypher wire codec; no transport, auth or AWS calls."""
import json
import re
from urllib.parse import urlencode

QUERY = ('MATCH (s:Evidence {run:$run})-[r:SOURCE_REL {run:$run}]->(t:Evidence {run:$run}) '
         'WHERE s.id IN $starts RETURN s.id AS subject,r.id AS edge_id,t.id AS target,'
         'r.chunk_id AS chunk_id,r.payload AS payload ORDER BY subject,edge_id')
FIELDS = {'subject', 'edge_id', 'target', 'chunk_id', 'payload'}
MAX_BYTES = 4 * 1024 * 1024


def outgoing_request(namespace, starts):
    if not isinstance(namespace, str) or not re.fullmatch(r'[a-z0-9-]{1,80}', namespace):
        raise ValueError('invalid namespace')
    if not isinstance(starts, list) or len(starts) > 328 or any(not isinstance(x, str) or not x or len(x) > 1024 for x in starts):
        raise ValueError('invalid frontier')
    parameters = json.dumps({'run': namespace, 'starts': sorted(set(starts))}, ensure_ascii=False, separators=(',', ':'))
    return {'method': 'POST', 'path': '/openCypher',
            'headers': {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'},
            'body': urlencode({'query': QUERY, 'parameters': parameters}).encode('ascii')}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def outgoing_response(status, raw, starts):
    # Validate caller frontier even when the response is empty. No silent fallback.
    outgoing_request('validation-only', starts)
    if type(status) is not int or status != 200:
        raise ValueError('non-success HTTP status')
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('invalid response size/type')
    body = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    if not isinstance(body, dict) or set(body) != {'results'} or not isinstance(body['results'], list):
        raise ValueError('unexpected Neptune result envelope')
    rows = body['results']
    if len(rows) > 486:
        raise ValueError('response exceeds bounded source edge count')
    seen = set()
    previous = None
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS or any(not isinstance(v, str) or not v for v in row.values()):
            raise ValueError('unexpected projection fields')
        key = row['subject'], row['edge_id']
        if row['subject'] not in starts or row['edge_id'] in seen or (previous is not None and key <= previous):
            raise ValueError('unexpected frontier, duplicate or unordered edge')
        seen.add(row['edge_id'])
        previous = key
        edge = json.loads(row['payload'], object_pairs_hook=_unique_object)
        if not isinstance(edge, dict) or any(edge.get(k) != row[k] for k in ('subject', 'edge_id', 'target')):
            raise ValueError('payload identity mismatch')
        if row['chunk_id'] != 'edge:' + row['edge_id']:
            raise ValueError('chunk identity mismatch')
    return rows
