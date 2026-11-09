"""Offline evaluator only: SQLite recursive reference over original source bytes.

Never import into model runtime or feedback tools. Does not use sbom_contracts.
"""
import json
import sqlite3
from pathlib import Path


def reference(path, contract):
    source = json.loads(Path(path).read_text())
    node_ids = []
    def walk(component):
        node_ids.append(component['bom-ref'])
        for child in component.get('components', []):
            walk(child)
    if source.get('metadata', {}).get('component'):
        walk(source['metadata']['component'])
    for component in source.get('components', []):
        walk(component)
    entries = source.get('dependencies', [])
    known = {x['ref'] for x in entries}
    op, target, scope = (contract[k] for k in ('operation', 'target', 'scope'))
    if op == 'clarify':
        return {'status': 'needs_clarification', 'refs': []}
    if scope == 'real_world':
        return {'status': 'unknown_world_scope', 'refs': []}
    if target not in node_ids:
        return {'status': 'invalid_contract', 'refs': []}
    edges = [(x['ref'], y) for x in entries for y in x.get('dependsOn', [])]
    if (known | {y for _, y in edges}) - set(node_ids):
        return {'status': 'invalid_source_references', 'refs': []}
    if op == 'dependency_status':
        selected = [x for x in entries if x['ref'] == target]
        state = ('unknown_missing_entry' if not selected else
                 'reported_nonempty' if selected[0].get('dependsOn', []) else 'explicit_empty')
        return {'status': 'answered', 'refs': [], 'knowledge': state}
    if op.endswith('dependents'):
        edges = [(b, a) for a, b in edges]
    with sqlite3.connect(':memory:') as connection:
        connection.execute('CREATE TABLE edge (a TEXT NOT NULL,b TEXT NOT NULL)')
        connection.executemany('INSERT INTO edge VALUES (?,?)', edges)
        if op.startswith('direct_'):
            rows = connection.execute('SELECT DISTINCT b FROM edge WHERE a=? ORDER BY b', (target,))
        elif op.startswith('transitive_'):
            rows = connection.execute('''WITH RECURSIVE reach(x) AS (
                SELECT ? UNION SELECT edge.b FROM edge JOIN reach ON edge.a=reach.x
                ) SELECT x FROM reach WHERE x<>? ORDER BY x''', (target, target))
        else:
            raise ValueError('unsupported_reference_operation')
        return {'status': 'answered', 'refs': [r[0] for r in rows]}


def compare(actual, expected):
    return {key: {'expected': value, 'actual': actual.get(key)}
            for key, value in expected.items() if actual.get(key) != value}
