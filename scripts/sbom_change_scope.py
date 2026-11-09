"""Declared identity-set freshness over two archived SBOMs; no deployment claim."""
import argparse
import hashlib
import json
import sqlite3
from collections import deque
from pathlib import Path

OPS = ('direct_dependencies', 'transitive_dependencies', 'direct_dependents', 'transitive_dependents')


def load(path):
    raw = Path(path).read_bytes(); doc = json.loads(raw)
    components = [doc['metadata']['component']] + doc['components']
    identities, by_ref, versions = set(), {}, {}
    for node in components:
        if node.get('components'):
            raise ValueError('nested_components_not_supported_in_this_release_check')
        identity = json.dumps([node['type'], node.get('group', ''), node['name']], separators=(',', ':'))
        if identity in identities or node['bom-ref'] in by_ref:
            raise ValueError('ambiguous_identity')
        identities.add(identity); by_ref[node['bom-ref']] = identity; versions[identity] = node.get('version')
    entries, edges = set(), set()
    for entry in doc.get('dependencies', []):
        parent = by_ref[entry['ref']]
        if parent in entries:
            raise ValueError('duplicate_entry')
        entries.add(parent)
        edges.update((parent, by_ref[child]) for child in entry.get('dependsOn', []))
    return {'nodes': identities, 'entries': entries, 'edges': edges, 'versions': versions,
            'source_sha256': hashlib.sha256(raw).hexdigest(), 'source_bytes': len(raw)}


def query(graph, target, operation):
    reverse = operation.endswith('dependents')
    adjacency = {n: set() for n in graph['nodes']}
    for a, b in graph['edges']:
        adjacency[b if reverse else a].add(a if reverse else b)
    visited, queue, reads = {target}, deque([target]), set()
    while queue:
        at = queue.popleft(); reads.add(at)
        for child in adjacency[at]:
            if child not in visited:
                visited.add(child)
                if operation.startswith('transitive_'):
                    queue.append(child)
    answer = adjacency[target] if operation.startswith('direct_') else visited - {target}
    return answer, reads


def sql_answer(graph, target, operation):
    edges = [(b, a) for a, b in graph['edges']] if operation.endswith('dependents') else graph['edges']
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE edge(a TEXT,b TEXT)'); db.executemany('INSERT INTO edge VALUES (?,?)', edges)
        if operation.startswith('direct_'):
            return {r[0] for r in db.execute('SELECT b FROM edge WHERE a=?', (target,))}
        return {r[0] for r in db.execute('WITH RECURSIVE reach(x) AS (SELECT ? UNION SELECT b FROM edge JOIN reach ON a=x) SELECT x FROM reach WHERE x<>?', (target, target))}


def flags(before, after, target, operation, old_answer, read_footprint):
    delta = before['edges'] ^ after['edges']
    reverse = operation.endswith('dependents')
    changed_buckets = {b if reverse else a for a, b in delta}
    # Answer-only baseline intentionally weak; complete delta + read footprint is the strong comparator.
    answer_nodes = old_answer | {target}
    changed_versions = {n for n in before['nodes'] if before['versions'][n] != after['versions'][n]}
    return {
        'global_source_hash': before['source_sha256'] != after['source_sha256'],
        'answer_node_versions_only': bool(answer_nodes & changed_versions),
        'complete_delta_read_footprint': bool(read_footprint & changed_buckets),
        'hidden_delta_adversarial_control': False,
    }


def evaluate(before_path, after_path, out):
    out.mkdir(parents=True, exist_ok=False)
    try:
        before, after = load(before_path), load(after_path)
    except Exception as error:
        (out/'source-failure.json').write_text(json.dumps({'error_type': type(error).__name__, 'message': str(error)}))
        raise
    if before['nodes'] != after['nodes'] or before['entries'] != before['nodes'] or after['entries'] != after['nodes']:
        (out/'source-failure.json').write_text(json.dumps({'error': 'requires_equal_unique_identities_and_full_declared_entries'}))
        raise ValueError('requires_equal_unique_identities_and_full_declared_entries')
    rows = []
    for target in sorted(before['nodes']):
        for operation in OPS:
            row = {'target': target, 'operation': operation, 'state': 'execution_failure'}
            try:
                old, footprint = query(before, target, operation)
                new, _ = query(after, target, operation)
                row.update(before=sorted(old), after=sorted(new))
                old_sql = sql_answer(before, target, operation)
                new_sql = sql_answer(after, target, operation)
                row.update(reference_before=sorted(old_sql), reference_after=sorted(new_sql))
                if old != old_sql or new != new_sql:
                    row['state'] = 'reference_disagreement'
                else:
                    row.update(state='completed', answer_changed=old != new,
                               old_adjacency_buckets_read=len(footprint),
                               flags=flags(before, after, target, operation, old, footprint))
            except Exception as error:
                row.update(error_type=type(error).__name__, message=str(error))
            rows.append(row)
            with (out/'rows.jsonl').open('a') as handle:
                handle.write(json.dumps(row, ensure_ascii=False)+'\n'); handle.flush()
    completed = [r for r in rows if r['state'] == 'completed']
    policies = {}
    for name in (completed[0]['flags'] if completed else {}):
        policies[name] = {'flagged': sum(r['flags'][name] for r in completed),
                          'missed_changed': sum(r['answer_changed'] and not r['flags'][name] for r in completed),
                          'flagged_unchanged': sum(not r['answer_changed'] and r['flags'][name] for r in completed)}
    result = {'planned': len(before['nodes'])*4, 'completed': len(completed), 'failures': len(rows)-len(completed),
              'changed_answers': sum(r['answer_changed'] for r in completed), 'policies': policies,
              'delta_edges': len(before['edges'] ^ after['edges']), 'nodes': len(before['nodes']),
              'preprocessing': {'full_source_bytes_read': before['source_bytes']+after['source_bytes'],
                                'logical_edge_rows_for_one_delta': len(before['edges'])+len(after['edges']),
                                'complete_changefeed_assumed': True, 'identity_rule': 'Exact(type,group-or-empty,name), unique in both'},
              'source_sha256': [before['source_sha256'],after['source_sha256']], 'rows': rows,
              'limits': 'Inspected archived release pair; normalized identity answers exclude versions. Full snapshots used to derive delta. Logical counters exclude repeated query/index construction and are not total processing work. Hidden delta is authored control. No timing, human effort, external truth, SHACL or database advantage measurement.'}
    (out/'evaluation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('before', type=Path); p.add_argument('after', type=Path); p.add_argument('out', type=Path)
    a = p.parse_args(); evaluate(a.before, a.after, a.out)
