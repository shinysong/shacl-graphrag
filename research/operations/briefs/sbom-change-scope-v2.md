# Actual SBOM release freshness scope
Bounded offline experiment using2pinned CC0 ProtonBridge SBOM examples,202unambiguous common identity keys(type,group-or-empty,name), eachfullydeclaresdependencyentries.4graphoperations×202=808planned querycontracts; all inspecteddevelopment, not freshheldout. Exactidentity correspondence deliberately excludesversion; no claimpackageidentitynormalization acrossarbitraryecosystems or external deploymenttruth. Originalbytes preserved and hashbound. Six normalizededge deltas;8versionfieldsincludingroot. Goal separate answer freshness detection from SHACL checking suppliedhashes.
Strong comparator complete edge delta + old query adjacency-read footprint; weak answer-nodeversionwatch clearly labeled, plusglobalsourcehash. Fullsnapshot reads are paid byofflinepreprocessing, not free discoveredchangefeed. Recordsourcebytes,edgeinspectioncounts andoldbucketreads; no latency/humaneffort threshold. Hiddenemptydelta is a separate authoredadversarialcontrol, notactualreleasebehavior. NoSHACL-specific advantageclaimed; noDBneeded,no paidcalls. Sourcesame allpolicies. FullSQLite recursiveCTE crosscheck everybefore/afterresult, outputmismatch preservedbyfailure (not repaired). Main observed2regressiontests pass; reviewers independently assess includedcode. Actualsourcefiles notprovided: unverifiedbyreview.
Retainedoutput evaluatedonsecondgraph; flaggedunchanged isn't necessarily policyerror becauseversions/provenance differ. Thisprimaryoutcome onlyidentityset. Rejectunequalidentitysets, missingentries,duplicateidentity. Delta-readscope valid onlyfixedpositivegraphoperations andfullchangefeed. Rule/operationchanges not covered. No inferredmaintenancebenefit orminimality. Runonlyafterindependentreviews, savefull808denominator. Keep reviewconcise~1500bytes; no otherreviews/gold/secrets.

Revision: previousimplementationreview blocked loss of partial outputs on exception. Originaljob/revieweroutputs preserved; submission rejected because coordinator edited before submittingreviews. Newcode createsoutputdir first, retains sourcefailures, writes everyqueryrow immediately, catchesreferencefailures and keeps complete planneddenominator.3unitregressionspassed including injected allreferencefailures. Logical preprocessingcounter renamed; not total executedwork.

## scripts/sbom_change_scope.py SHA256 fce401e39645353e6cbfaed271470d26f52789b53bd5817f650a09fcbd505e67
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

```

## tests/test_sbom_change_scope.py SHA256 1fff4a1ab8fefe1aaeb6dc64eb2e2e30f909aa0485b2cafcb0dfd1171289694e
```python
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from scripts.sbom_change_scope import query, sql_answer, flags, evaluate


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

    def test_reference_failure_keeps_all_planned_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = {'metadata': {'component': {'bom-ref': 'A', 'type': 'application', 'name': 'a'}},
                   'components': [], 'dependencies': [{'ref': 'A', 'dependsOn': []}]}
            source = root/'source.json'; source.write_text(json.dumps(doc))
            with patch('scripts.sbom_change_scope.sql_answer', side_effect=RuntimeError('injected_reference_failure')):
                evaluate(source, source, root/'result')
            result = json.loads((root/'result/evaluation.json').read_text())
            self.assertEqual((result['planned'],result['completed'],result['failures']), (4,0,4))
            self.assertEqual(len((root/'result/rows.jsonl').read_text().splitlines()),4)
            self.assertTrue(all(r['error_type']=='RuntimeError' and r['before']==[] for r in result['rows']))

```
