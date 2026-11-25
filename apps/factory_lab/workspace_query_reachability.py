"""Separate bounded directed reachability family; no supplied SQL or oracle data."""
from collections import deque
from copy import deepcopy
import time

from .workspace_database import DatabaseSourceError, _quote
from .workspace_store import check_cancel
from .workspace_query_contracts import _keys, _name, _text, _typed, _require, _json, fingerprint

VERSION = 'reviewed-query-reachability-1'
CAPS = {'max_depth': 128, 'max_nodes': 10000, 'max_edges': 100000}


def compile_spec(engine, draft, spec, relations):
    _keys(spec, 'id title question_scope query_kind edge_id_entry_id source_entry_id destination_entry_id node_entry_id source_relation_id destination_relation_id direction node_key_type comparison parameters seed_parameter seed_policy include_seed node_semantics endpoint_policy edge_filters projection budgets output_kind limitations policy_references')
    _name(spec['id']); _text(spec['title']); _text(spec['question_scope'])
    _require(spec['query_kind'] == 'directed_reachability' and spec['direction'] in ('forward', 'reverse'), 'Unsupported traversal direction')
    _require(spec['node_key_type'] in ('integer', 'text') and spec['comparison'] == 'binary_exact', 'Unsupported node identity')
    _require(spec['seed_policy'] == 'require_existing_node' and spec['include_seed'] is False and spec['node_semantics'] == 'distinct_reachable' and spec['endpoint_policy'] == 'require_existing_node', 'Unsupported traversal policy')
    _require(spec['output_kind'] == 'potential_impact_candidates', 'Unsupported traversal output claim')
    _require(isinstance(spec['limitations'], list) and all(isinstance(v, str) for v in spec['limitations']) and isinstance(spec['policy_references'], list), 'Invalid scope annotations')
    _keys(spec['budgets'], 'max_depth max_nodes max_edges')
    for key, cap in CAPS.items():
        _require(type(spec['budgets'][key]) is int and 1 <= spec['budgets'][key] <= cap, 'Traversal budget exceeds server bound')
    params = spec['parameters']
    _require(isinstance(params, dict) and len(params) <= 20, 'Invalid parameter schema')
    for name, kind in params.items():
        _name(name); _require(kind in ('integer', 'text', 'number', 'date'), 'Unsupported parameter type')
    _require(isinstance(spec['seed_parameter'], str) and params.get(spec['seed_parameter']) == spec['node_key_type'], 'Seed parameter type mismatch')
    fields = engine._fields(draft); used = set()
    def field(entry_id):
        _require(isinstance(entry_id, str) and entry_id in fields, 'Traversal requires approved fields')
        used.add(entry_id)
        return fields[entry_id]['source']
    edge, src, dst, node = [field(spec[k]) for k in ('edge_id_entry_id', 'source_entry_id', 'destination_entry_id', 'node_entry_id')]
    _require(edge['file'] == src['file'] == dst['file'], 'Edge fields must share one table')
    _require(spec['source_entry_id'] != spec['destination_entry_id'], 'Distinct endpoint fields required')
    _require(isinstance(relations, dict) and spec['source_relation_id'] != spec['destination_relation_id'], 'Two distinct endpoint relations required')
    rel_deps = {}
    for rkey, endpoint in [('source_relation_id', 'source_entry_id'), ('destination_relation_id', 'destination_entry_id')]:
        rid = spec[rkey]
        _require(isinstance(rid, str) and rid in relations, 'Endpoint relation approval missing')
        rel = relations[rid]; engine._verify(rel, approved=True)
        rs = rel['spec']
        _keys(rs, 'id child_entry_id parent_entry_id interpretation join_policy')
        _require(rel['kind'] == 'relation' and rs['id'] == rid and rs['child_entry_id'] == spec[endpoint] and rs['parent_entry_id'] == spec['node_entry_id'] and rs['join_policy'] == 'left_many_to_one_preserve_root', 'Endpoint relation interpretation mismatch')
        deps = engine._dependencies(draft, [rs['child_entry_id'], rs['parent_entry_id']])
        fresh = engine._envelope(draft, 'relation', rs, deps, rel['origin'])
        _require(fresh['fingerprint'] == rel['fingerprint'], 'Endpoint relation approval is stale')
        # Same declaration requirement as v1, with actual keys verified under the
        # traversal's stricter typed binary equality and execution resource guard.
        table = next(s for s in draft['sources'] if s['name'] == edge['file'])
        ptable = next(s for s in draft['sources'] if s['name'] == node['file'])
        child = field(rs['child_entry_id'])
        fks = table['foreign_keys']
        _require(any(f['from'] == child['column'] and f['table'] == node['file'] and
            (f['to'] == node['column'] or f['to'] is None and ptable['primary_key'] == [node['column']]) and
            sum(x['id'] == f['id'] for x in fks) == 1 for f in fks), 'Declared endpoint foreign key required')
        rel_deps[rid] = deepcopy(rel)
    _require(isinstance(spec['edge_filters'], list) and len(spec['edge_filters']) <= 20, 'Edge filter bound exceeded')
    filters = []
    for pred in spec['edge_filters']:
        _require(isinstance(pred, dict) and pred.get('op') in ('eq','lt','lte','gt','gte','is_null'), 'Unsupported edge filter')
        _keys(pred, 'entry_id op' if pred['op'] == 'is_null' else 'entry_id op parameter value_type')
        f = field(pred['entry_id']); _require(f['file'] == edge['file'], 'Filter must use edge field')
        if pred['op'] != 'is_null':
            _require(isinstance(pred['parameter'], str) and pred['value_type'] in ('integer','text','number','date') and params.get(pred['parameter']) == pred['value_type'], 'Edge filter parameter type mismatch')
        filters.append((pred, f['column']))
    _require(isinstance(spec['projection'], list) and len(spec['projection']) <= 20, 'Node projection bound exceeded')
    projections = []; names = {'node_id','minimum_depth','predecessor_id','witness_edge_id','witness_path'}
    for item in spec['projection']:
        _keys(item, 'entry_id name'); name = _name(item['name'])
        _require(name not in names, 'Duplicate or reserved projection name'); names.add(name)
        f = field(item['entry_id']); _require(f['file'] == node['file'], 'Projection must use node field')
        projections.append((name, f['column']))
    return {'edge':edge, 'src':src, 'dst':dst, 'node':node, 'filters':filters, 'projections':projections,
            'dependencies': {'fields':engine._dependencies(draft, used), 'relations':rel_deps}}


def execute(engine, draft, approved, parameters, relations, *, cancel_requested=None, partial=None):
    started = time.monotonic(); steps = 0
    def progress():
        nonlocal steps
        steps += 1
        return int((cancel_requested is not None and cancel_requested()) or steps > engine.max_steps or time.monotonic() - started > engine.timeout)
    def deadline():
        check_cancel(cancel_requested)
        _require(time.monotonic() - started <= engine.timeout, 'Traversal exceeded time limit')
    check_cancel(cancel_requested)
    engine._verify(approved, approved=True)
    draft = engine.adapter.restore(draft)
    check_cancel(cancel_requested)
    spec = approved['spec']
    _require(len(_json(spec).encode()) <= 65536, 'Contract exceeds byte bound')
    compiled = compile_spec(engine, draft, spec, relations)
    current = engine._envelope(draft, 'query', spec, compiled['dependencies'], approved['origin'])
    _require(approved['kind'] == 'query' and approved['fingerprint'] == current['fingerprint'], 'Query approval is stale')
    _require(isinstance(parameters, dict) and set(parameters) == set(spec['parameters']), 'Supply exactly the approved parameters')
    for name, kind in spec['parameters'].items():
        _typed(parameters[name], kind)
    registry = engine.adapter.registry; record = registry._record(draft['database']['source_id'])
    _require(record['snapshot_sha256'] == approved['source']['snapshot_sha256'], 'Snapshot binding changed')
    node, edge, src, dst = [compiled[k] for k in ('node','edge','src','dst')]
    nt, nk, et, ek = [_quote(v) for v in (node['file'],node['column'],edge['file'],edge['column'])]
    outgoing, incoming = (src, dst) if spec['direction'] == 'forward' else (dst, src)
    oc, ic = _quote(outgoing['column']), _quote(incoming['column'])
    key_type = spec['node_key_type']; seed = parameters[spec['seed_parameter']]
    budgets = spec['budgets']; reasons = set(); examined = 0; nulls = 0; dangling = 0
    visited = {seed}; queue = deque([(seed, 0)]); found = partial['rows'] if partial is not None else []; parents = {}
    encode = lambda v: str(v) if type(v) is int else v
    check_cancel(cancel_requested)
    with registry._connection(registry._data(record)) as con:
        con.set_progress_handler(progress, 1); con.execute('BEGIN')
        # Streaming typed scans and uniqueness checks share the execution VM and
        # wall-clock budget. Never materialize the edge table or adjacency map.
        typed = {(node['file'], node['column'], key_type), (src['file'], src['column'], key_type), (dst['file'],dst['column'],key_type)}
        typed.update((edge['file'], column, p['value_type']) for p,column in compiled['filters'] if p['op'] != 'is_null')
        for table,column,kind in sorted(typed):
            for row in con.execute(f'SELECT {_quote(column)} FROM {_quote(table)} WHERE {_quote(column)} IS NOT NULL'):
                _typed(row[0], kind); deadline()
        edge_key_type = None
        for row in con.execute(f'SELECT {ek} FROM {et}'):
            kind = 'integer' if type(row[0]) is int else 'text'
            _typed(row[0], kind); deadline()
            _require(edge_key_type is None or edge_key_type == kind, 'Edge identity types must be homogeneous')
            edge_key_type = kind
        for table,column in ((nt,nk),(et,ek)):
            _require(con.execute(f'SELECT 1 FROM {table} WHERE {column} IS NULL LIMIT 1').fetchone() is None, 'Identity field contains null')
            _require(con.execute(f'SELECT 1 FROM {table} GROUP BY +{column} COLLATE BINARY HAVING count(*) > 1 LIMIT 1').fetchone() is None, 'Identity field is not unique')
        # Reject a declared FK that finds a different parent through affinity or
        # collation than exact typed identity; do not inherit NOCASE semantics.
        for endpoint in (src,dst):
            cc = 'c.' + _quote(endpoint['column']); pp = 'p.' + nk
            mismatch = con.execute(f'SELECT 1 FROM {et} c JOIN {nt} p ON {pp} = +{cc} WHERE NOT ((+{pp} COLLATE BINARY) = (+{cc} COLLATE BINARY)) LIMIT 1').fetchone()
            _require(mismatch is None, 'Foreign-key comparison differs from binary exact identity')
        projected = ', '.join(_quote(c) for _,c in compiled['projections'])
        node_sql = f'SELECT {nk}' + (', '+projected if projected else '') + f' FROM {nt} WHERE (+{nk} COLLATE BINARY) = (+? COLLATE BINARY) LIMIT 2'
        def lookup(key):
            matches = con.execute(node_sql, (key,)).fetchall()
            _require(len(matches) <= 1, 'Node identity is not unique')
            return matches[0] if matches else None
        _require(lookup(seed) is not None, 'unresolved_seed:absent')
        clauses = [f'(+{oc} COLLATE BINARY) = (+? COLLATE BINARY)']; filter_values=[]
        for pred,column in compiled['filters']:
            c = _quote(column)
            if pred['op'] == 'is_null': clauses.append(c+' IS NULL')
            else:
                op = {'eq':'=','lt':'<','lte':'<=','gt':'>','gte':'>='}[pred['op']]
                clauses.append(f'(+{c} COLLATE BINARY) {op} (+? COLLATE BINARY)'); filter_values.append(parameters[pred['parameter']])
        edge_sql = f'SELECT {ek}, {ic} FROM {et} WHERE ' + ' AND '.join(clauses) + f' ORDER BY +{ek} COLLATE BINARY'
        stop = False
        while queue and not stop:
            current_key, depth = queue.popleft(); deadline()
            for edge_row in con.execute(edge_sql, (current_key,*filter_values)):
                deadline()
                if examined >= budgets['max_edges']:
                    reasons.add('max_edges'); stop = True; break
                examined += 1; edge_id, successor = edge_row
                _require(type(edge_id) in (int,str), 'Edge identity must be integer or text')
                _typed(edge_id, 'integer' if type(edge_id) is int else 'text')
                if successor is None:
                    nulls += 1; reasons.add('null_endpoint'); continue
                if successor in visited: continue
                details = lookup(successor)
                if details is None:
                    dangling += 1; reasons.add('missing_endpoint'); continue
                if depth >= budgets['max_depth']:
                    reasons.add('max_depth'); continue
                if len(visited) >= budgets['max_nodes']:
                    reasons.add('max_nodes'); stop = True; break
                visited.add(successor); parents[successor] = current_key
                queue.append((successor,depth+1))
                # Retain only bounded displayed rows; predecessor map is bounded
                # by max_nodes and supplies paths even when predecessors omitted.
                if len(found) < engine.max_rows:
                    path = [successor]; prev = successor
                    while prev != seed:
                        deadline()
                        prev = parents[prev]; path.append(prev)
                    row = {'node_id': encode(successor), 'minimum_depth':depth+1,
                           'predecessor_id':encode(current_key), 'witness_edge_id':encode(edge_id),
                           'witness_path':[encode(v) for v in reversed(path)]}
                    row.update({name:encode(details[i+1]) for i,(name,_) in enumerate(compiled['projections'])})
                    _require(len(_json(found + [row]).encode()) <= engine.max_bytes, 'Query result exceeds byte limit')
                    found.append(row)
        deadline()
    complete = not reasons; count = len(visited)-1
    result = {'version':VERSION,'query_kind':'directed_reachability', 'status':'complete' if complete else 'incomplete',
        'closure_complete':complete,'incomplete_reasons':sorted(reasons),'rows':found,
        'returned_count':len(found),'discovered_count':count,'total_output_rows':count if complete else None,
        'truncated':count > len(found),'output_kind':spec['output_kind'],
        'scope':'registered_snapshot_potential_impact_not_external_truth',
        'limitations':deepcopy(spec['limitations']),'policy_references':deepcopy(spec['policy_references']),
        'policy_reference_status':'annotations_only_not_document_verification','budgets':deepcopy(budgets),
        'traversal_observations':{'visited_nodes_including_seed':len(visited),'examined_edges':examined,
            'null_reachable_endpoints':nulls,'missing_reachable_endpoints':dangling,
            'endpoint_observation_scope':'eligible_edges_examined_from_reached_nodes',
            'sqlite_vm_steps':steps,'max_steps':engine.max_steps,'timeout_seconds':engine.timeout,
            'direction':spec['direction'],'node_key_type':key_type,'comparison':'binary_exact',
            'edge_key_type':edge_key_type,
            'timeout_scope':'invocation_elapsed_checked_after_restore_and_during_snapshot_work',
            'restore_interruption':'registry_owned_limits_not_traversal_progress_handler',
            'integer_encoding':'decimal_integer_string','witness_semantics':'one_deterministic_shortest_path_not_all_paths'},
        'provenance':{'contract_fingerprint':approved['fingerprint'],'review':deepcopy(approved['review']),
            'origin':deepcopy(approved['origin']),'source':deepcopy(approved['source']),
            'dependency_fingerprint':fingerprint(approved['dependencies']),'dependencies':deepcopy(approved['dependencies']),
            'parameters':{k:encode(v) for k,v in parameters.items()}}}
    _require(len(_json(result).encode()) <= engine.max_bytes, 'Query result and provenance exceed byte limit')
    return result
