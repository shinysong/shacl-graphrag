"""Pure source-dictionary outgoing relation expansion; no file/network readers."""
import copy
import hashlib
import json
import sqlite3


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _identifier(value):
    if not isinstance(value, str) or not value:
        raise ValueError('identifiers must be nonempty strings')
    return value


def _index(corpus):
    """Reject ambiguous or dangling source representations before traversal."""
    canonical(corpus)
    nodes, edges, chunks = {}, {}, {}
    for key in ('nodes', 'edges', 'chunks'):
        if not isinstance(corpus[key], list):
            raise ValueError(f'{key} must be a list')
    for node in corpus['nodes']:
        nid = _identifier(node['node_id'])
        if nid in nodes:
            raise ValueError(f'duplicate node: {nid}')
        nodes[nid] = node
    for edge in corpus['edges']:
        eid = _identifier(edge['edge_id'])
        if eid in edges:
            raise ValueError(f'duplicate edge: {eid}')
        for endpoint in ('subject', 'target'):
            if _identifier(edge[endpoint]) not in nodes:
                raise ValueError(f'missing edge {endpoint}: {eid}')
        edges[eid] = edge
    node_chunks, edge_chunks = {}, {}
    for chunk in corpus['chunks']:
        cid = _identifier(chunk['chunk_id'])
        if cid in chunks:
            raise ValueError(f'duplicate chunk: {cid}')
        if not isinstance(chunk['text'], str):
            raise ValueError(f'invalid chunk text: {cid}')
        payload = json.loads(chunk['text'])
        if not isinstance(payload, dict):
            raise ValueError(f'chunk text must encode an object: {cid}')
        canonical(payload)
        if chunk['chunk_type'] == 'node':
            nid = _identifier(chunk['node_id'])
            if nid not in nodes or nid in node_chunks:
                raise ValueError(f'unknown or duplicate node chunk: {cid}')
            node = nodes[nid]
            if chunk['text'] != node['text']:
                raise ValueError(f'node text mismatch: {cid}')
            if 'source' in node and canonical(payload) != canonical(node['source']):
                raise ValueError(f'node source mismatch: {cid}')
            node_chunks[nid] = cid
        elif chunk['chunk_type'] == 'edge':
            eid = _identifier(chunk['edge_id'])
            if eid not in edges or eid in edge_chunks:
                raise ValueError(f'unknown or duplicate edge chunk: {cid}')
            if canonical(payload) != canonical(edges[eid]):
                raise ValueError(f'edge text mismatch: {cid}')
            edge_chunks[eid] = cid
        else:
            raise ValueError(f'unknown chunk type: {cid}')
        chunks[cid] = chunk
    if set(nodes) != set(node_chunks) or set(edges) != set(edge_chunks):
        raise ValueError('source node or edge has no chunk')
    return nodes, edges, chunks, node_chunks, edge_chunks


def _adjacency(edges, starts, depth, add, node_chunks, edge_chunks, trace):
    outgoing = {}
    for eid, edge in edges.items():
        outgoing.setdefault(edge['subject'], []).append(eid)
    visited = set(starts)
    frontier = set(starts)
    for level in range(1, depth + 1):
        trace.append({'depth': level, 'frontier': sorted(frontier)})
        following = set()
        for subject in sorted(frontier):
            for eid in sorted(outgoing.get(subject, [])):
                target = edges[eid]['target']
                add(edge_chunks[eid])
                add(node_chunks[target])
                if target not in visited:
                    visited.add(target)
                    following.add(target)
        frontier = following
        if not frontier:
            break


def _sqlite(edges, starts, depth, add, node_chunks, edge_chunks, trace):
    """Independent frontier/visited storage and ordering in SQLite memory tables."""
    db = sqlite3.connect(':memory:')
    try:
        db.executescript('''
            CREATE TABLE edges (id TEXT PRIMARY KEY, subject TEXT, target TEXT);
            CREATE INDEX outgoing ON edges(subject, id);
            CREATE TABLE seen (id TEXT PRIMARY KEY);
            CREATE TABLE frontier (id TEXT PRIMARY KEY);
            CREATE TABLE following (id TEXT PRIMARY KEY);
        ''')
        db.executemany('INSERT INTO edges VALUES (?, ?, ?)',
                       [(eid, e['subject'], e['target']) for eid, e in edges.items()])
        db.executemany('INSERT OR IGNORE INTO frontier VALUES (?)', [(n,) for n in starts])
        db.execute('INSERT INTO seen SELECT id FROM frontier')
        for level in range(1, depth + 1):
            frontier = [r[0] for r in db.execute('SELECT id FROM frontier ORDER BY id')]
            trace.append({'depth': level, 'frontier': frontier})
            rows = db.execute('''SELECT e.id, e.target FROM frontier f
                JOIN edges e ON e.subject=f.id ORDER BY f.id, e.id''').fetchall()
            for eid, target in rows:
                add(edge_chunks[eid])
                add(node_chunks[target])
                if not db.execute('SELECT 1 FROM seen WHERE id=?', (target,)).fetchone():
                    db.execute('INSERT INTO seen VALUES (?)', (target,))
                    db.execute('INSERT INTO following VALUES (?)', (target,))
            db.execute('DELETE FROM frontier')
            db.execute('INSERT INTO frontier SELECT id FROM following')
            db.execute('DELETE FROM following')
            if not db.execute('SELECT 1 FROM frontier LIMIT 1').fetchone():
                break
    finally:
        db.close()


def expand(corpus, seed_chunk_ids, backend='adjacency', max_depth=1,
           max_candidates=32, max_evidence_bytes=64000):
    """Return success or an explicit failure envelope, never partial success."""
    result = dict(schema_version='graphrag-retrieval-envelope-1', backend=backend,
                  seed_chunk_ids=[], candidate_chunk_ids=[], selected_chunk_ids=[],
                  selected_chunks=[], evidence_sha256=hashlib.sha256(canonical([])).hexdigest(),
                  evidence_bytes=2, evidence_tokens=None, budget_unit='utf8_bytes',
                  configuration=dict(max_depth=max_depth, max_candidates=max_candidates,
                                     max_evidence_bytes=max_evidence_bytes),
                  status='retrieval_error', error=None, trace=[])
    try:
        if backend not in ('adjacency', 'sqlite'):
            raise ValueError('unknown backend')
        if type(max_depth) is not int or not 0 <= max_depth <= 3:
            raise ValueError('max_depth must be an integer in 0..3')
        if type(max_candidates) is not int or not 1 <= max_candidates <= 128:
            raise ValueError('max_candidates must be an integer in 1..128')
        if type(max_evidence_bytes) is not int or max_evidence_bytes < 0:
            raise ValueError('max_evidence_bytes must be a nonnegative integer')
        if not isinstance(seed_chunk_ids, (list, tuple)):
            raise ValueError('seed_chunk_ids must be a list or tuple')
        for cid in seed_chunk_ids:
            _identifier(cid)
            if cid not in result['seed_chunk_ids']:
                result['seed_chunk_ids'].append(cid)
        _, edges, chunks, node_chunks, edge_chunks = _index(corpus)
        candidates = result['candidate_chunk_ids']
        seen_chunks = set()

        def add(cid):
            if cid not in seen_chunks:
                seen_chunks.add(cid)
                candidates.append(cid)

        starts = set()
        for cid in result['seed_chunk_ids']:
            if cid not in chunks:
                raise ValueError(f'unknown seed: {cid}')
            add(cid)
            chunk = chunks[cid]
            if chunk['chunk_type'] == 'node':
                starts.add(chunk['node_id'])
            else:
                edge = edges[chunk['edge_id']]
                for endpoint in ('subject', 'target'):
                    starts.add(edge[endpoint])
                    add(node_chunks[edge[endpoint]])
        traverse = _adjacency if backend == 'adjacency' else _sqlite
        traverse(edges, starts, max_depth, add, node_chunks, edge_chunks, result['trace'])
        if len(candidates) > max_candidates:
            result.update(status='budget_error', error='candidate count exceeds max_candidates')
            return result
        selected = [copy.deepcopy(chunks[cid]) for cid in candidates]
        packed = canonical(selected)
        if len(packed) > max_evidence_bytes:
            result.update(status='budget_error', error='evidence bytes exceed max_evidence_bytes')
            return result
        result.update(status='ok', selected_chunk_ids=list(candidates), selected_chunks=selected,
                      evidence_bytes=len(packed), evidence_sha256=hashlib.sha256(packed).hexdigest())
    except (KeyError, TypeError, ValueError, UnicodeError, sqlite3.Error, RecursionError) as exc:
        result.update(status='retrieval_error', error=f'{type(exc).__name__}: {exc}')
    return result
