# Actual SBOM release freshness scope
Bounded offline experiment using2pinned CC0 ProtonBridge SBOM examples,202unambiguous common identity keys(type,group-or-empty,name), eachfullydeclaresdependencyentries.4graphoperations×202=808planned querycontracts; all inspecteddevelopment, not freshheldout. Exactidentity correspondence deliberately excludesversion; no claimpackageidentitynormalization acrossarbitraryecosystems or external deploymenttruth. Originalbytes preserved and hashbound. Six normalizededge deltas;8versionfieldsincludingroot. Goal separate answer freshness detection from SHACL checking suppliedhashes.
Strong comparator complete edge delta + old query adjacency-read footprint; weak answer-nodeversionwatch clearly labeled, plusglobalsourcehash. Fullsnapshot reads are paid byofflinepreprocessing, not free discoveredchangefeed. Recordsourcebytes,edgeinspectioncounts andoldbucketreads; no latency/humaneffort threshold. Hiddenemptydelta is a separate authoredadversarialcontrol, notactualreleasebehavior. NoSHACL-specific advantageclaimed; noDBneeded,no paidcalls. Sourcesame allpolicies. FullSQLite recursiveCTE crosscheck everybefore/afterresult, outputmismatch preservedbyfailure (not repaired). Main observed2regressiontests pass; reviewers independently assess includedcode. Actualsourcefiles notprovided: unverifiedbyreview.
Retainedoutput evaluatedonsecondgraph; flaggedunchanged isn't necessarily policyerror becauseversions/provenance differ. Thisprimaryoutcome onlyidentityset. Rejectunequalidentitysets, missingentries,duplicateidentity. Delta-readscope valid onlyfixedpositivegraphoperations andfullchangefeed. Rule/operationchanges not covered. No inferredmaintenancebenefit orminimality. Runonlyafterindependentreviews, savefull808denominator. Keep reviewconcise~1500bytes; no otherreviews/gold/secrets.

## scripts/sbom_change_scope.py SHA256 2f6ff63ebba0584335ada420eac86780b3bf3407c20b07451cbffa5d6903374e
```python
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
    before, after = load(before_path), load(after_path)
    if before['nodes'] != after['nodes'] or before['entries'] != before['nodes'] or after['entries'] != after['nodes']:
        raise ValueError('requires_equal_unique_identities_and_full_declared_entries')
    rows = []
    for target in sorted(before['nodes']):
        for operation in OPS:
            old, footprint = query(before, target, operation)
            new, _ = query(after, target, operation)
            if old != sql_answer(before, target, operation) or new != sql_answer(after, target, operation):
                raise ValueError('independent_query_disagreement')
            rows.append({'target': target, 'operation': operation, 'before': sorted(old), 'after': sorted(new),
                         'answer_changed': old != new, 'old_adjacency_buckets_read': len(footprint),
                         'flags': flags(before, after, target, operation, old, footprint)})
    policies = {}
    for name in rows[0]['flags']:
        policies[name] = {'flagged': sum(r['flags'][name] for r in rows),
                          'missed_changed': sum(r['answer_changed'] and not r['flags'][name] for r in rows),
                          'flagged_unchanged': sum(not r['answer_changed'] and r['flags'][name] for r in rows)}
    result = {'planned': len(before['nodes'])*4, 'completed': len(rows),
              'changed_answers': sum(r['answer_changed'] for r in rows), 'policies': policies,
              'delta_edges': len(before['edges'] ^ after['edges']), 'nodes': len(before['nodes']),
              'preprocessing': {'full_source_bytes_read': before['source_bytes']+after['source_bytes'],
                                'edge_rows_inspected_for_delta': len(before['edges'])+len(after['edges']),
                                'complete_changefeed_assumed': True, 'identity_rule': 'Exact(type,group-or-empty,name), unique in both'},
              'source_sha256': [before['source_sha256'],after['source_sha256']], 'rows': rows,
              'limits': 'Inspected archived release pair; normalized identity answers exclude versions. Full snapshots used to derive delta. Hidden delta is authored control. No timing, human effort, external truth, SHACL or database advantage measurement.'}
    out.mkdir(parents=True, exist_ok=False)
    (out/'evaluation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('before', type=Path); p.add_argument('after', type=Path); p.add_argument('out', type=Path)
    a = p.parse_args(); evaluate(a.before, a.after, a.out)

```

## tests/test_sbom_change_scope.py SHA256 1bdbbd387700fc2e4872a44d8e99084bd8331fdf52bed7d202fc197887a80586
```python
import unittest
from scripts.sbom_change_scope import query, sql_answer, flags


class ChangeScope(unittest.TestCase):
    def graph(self, edges, sha):
        return {'nodes': set('ABCD'), 'edges': set(edges), 'versions': {n: '1' for n in 'ABCD'}, 'source_sha256': sha}

    def test_new_predecessor_not_in_old_answer(self):
        before = self.graph([('A','B')], 'old')
        after = self.graph([('A','B'),('C','A')], 'new')
        old, footprint = query(before, 'B', 'transitive_dependents')
        new, _ = query(after, 'B', 'transitive_dependents')
        self.assertEqual(old, {'A'}); self.assertEqual(new, {'A','C'})
        f = flags(before, after, 'B', 'transitive_dependents', old, footprint)
        self.assertTrue(f['complete_delta_read_footprint'])
        self.assertFalse(f['answer_node_versions_only'])

    def test_cycle_and_direct_self_edge(self):
        g = self.graph([('A','A'),('A','B'),('B','A'),('B','C')], 'old')
        for operation in ('direct_dependencies','transitive_dependencies','direct_dependents','transitive_dependents'):
            self.assertEqual(query(g,'A',operation)[0],sql_answer(g,'A',operation))
        self.assertIn('A',query(g,'A','direct_dependencies')[0])
        self.assertNotIn('A',query(g,'A','transitive_dependencies')[0])

```
