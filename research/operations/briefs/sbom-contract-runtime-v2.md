# Offline contract runtime corrected review
Supersedes job20261106T140515Z-sbom-contract-runtime-7ff5fe: both reviewers ready with dangling-source precedence warning; synthesis request exceeded context limit, no registered checks or completed analysis. Preserved counterexample. Reference now checks source validity before dependency_status as production does; regression added.
Source schemas1.2/1.4 both distinguish missing entry vs explicit empty. Five inspected CC0SBOM example sources,202/202/44/63/168 nodes, not freshheldout/deployedtruth. No raw source or evaluator answers inpacket. Complete Python AST-unparsed source below (same semantics, comments removed). Original file hashes bound. Planned: 7unit tests, 4query operations over all679nodes using independentSQLite original-source reference; preserve failures. Contract checks do not receive question/gold and cannot verify intent. Clarify/realworld return before sourcevalidity; others reject dangling. Directselfedge preserved; transitiveexcludesroot. No paid calls/DB.

## scripts/sbom_contracts.py SHA256 70e1edb5b36f73ad77227a3f18538cf3faa5a87b72b5114676339a9dde0af56a
```python
"""Bounded declared-SBOM contract interpreter. No model, oracle, or DB client.

Knowledge is about an archived document, never installed software or safety.
Missing dependency entry and explicit empty entry are retained separately.
"""
import argparse
import hashlib
import json
from collections import deque
from pathlib import Path
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import SH, XSD
EX = Namespace('https://example.org/shacl-study/sbom/')
OPERATIONS = ('direct_dependencies', 'transitive_dependencies', 'direct_dependents', 'transitive_dependents', 'dependency_status', 'clarify')
SCOPES = ('declared_document', 'real_world')

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def read_document(path):
    raw = Path(path).read_bytes()
    if len(raw) > 2000000:
        raise ValueError('document_byte_limit')
    document = json.loads(raw)
    if document.get('bomFormat') != 'CycloneDX' or document.get('specVersion') not in ('1.2', '1.4'):
        raise ValueError('unsupported_source_format')
    nodes = {}

    def add(component, pointer):
        ref = component.get('bom-ref')
        if not isinstance(ref, str) or not ref:
            raise ValueError('missing_component_identity')
        if ref in nodes:
            raise ValueError('duplicate_component_identity')
        nodes[ref] = {k: component[k] for k in ('name', 'group', 'version', 'type', 'purl') if k in component}
        nodes[ref]['pointer'] = pointer
        for index, child in enumerate(component.get('components', [])):
            add(child, f'{pointer}/components/{index}')
    root = document.get('metadata', {}).get('component')
    if root:
        add(root, '/metadata/component')
    for index, component in enumerate(document.get('components', [])):
        add(component, f'/components/{index}')
    if len(nodes) > 1000:
        raise ValueError('node_limit')
    entries = {}
    for index, entry in enumerate(document.get('dependencies', [])):
        ref = entry.get('ref')
        if not isinstance(ref, str) or not ref or ref in entries:
            raise ValueError('invalid_or_duplicate_dependency_ref')
        children = entry.get('dependsOn', [])
        if not isinstance(children, list) or any((not isinstance(c, str) or not c for c in children)):
            raise ValueError('invalid_dependency_children')
        if len(set(children)) != len(children):
            raise ValueError('duplicate_dependency_child')
        entries[ref] = {'children': sorted(children), 'pointer': f'/dependencies/{index}', 'dependsOn_present': 'dependsOn' in entry}
    if sum((len(x['children']) for x in entries.values())) > 5000:
        raise ValueError('edge_limit')
    dangling = sorted(({r for r in entries} | {c for e in entries.values() for c in e['children']}) - set(nodes))
    return {'source_sha256': hashlib.sha256(raw).hexdigest(), 'spec_version': document['specVersion'], 'root': root.get('bom-ref') if root else None, 'nodes': nodes, 'entries': entries, 'dangling': dangling, 'compositions': document.get('compositions'), 'world_completeness': 'unverified'}

def contract_errors(contract, snapshot):
    if not isinstance(contract, dict) or set(contract) != {'operation', 'target', 'scope'}:
        return ['input_shape']
    if not all((isinstance(contract[k], str) for k in contract)):
        return ['input_types']
    errors = []
    if contract['operation'] not in OPERATIONS:
        errors.append('unsupported_operation')
    if contract['scope'] not in SCOPES:
        errors.append('unsupported_scope')
    if contract['operation'] == 'clarify':
        if contract['target'] != '':
            errors.append('clarify_target_not_empty')
    elif contract['target'] not in snapshot['nodes']:
        errors.append('unknown_target')
    return sorted(errors)

def shacl_contract_errors(contract, snapshot):
    boundary = contract_errors(contract, snapshot)
    if boundary and boundary[0] in ('input_shape', 'input_types'):
        return {'status': 'input_rejected', 'codes': boundary, 'conforms': None}
    from pyshacl import validate
    graph, shapes = (Graph(), Graph())
    node = EX.contract
    graph.add((node, RDF.type, EX.Contract))
    for k, v in contract.items():
        graph.add((node, EX[k], Literal(v, datatype=XSD.string)))
    shape = EX.ContractShape
    shapes.add((shape, RDF.type, SH.NodeShape))
    shapes.add((shape, SH.targetClass, EX.Contract))
    for name, choices, code in [('operation', OPERATIONS, 'unsupported_operation'), ('scope', SCOPES, 'unsupported_scope')]:
        from rdflib import BNode
        from rdflib.collection import Collection
        prop, values = (BNode(), BNode())
        shapes.add((shape, SH.property, prop))
        shapes.add((prop, SH.path, EX[name]))
        Collection(shapes, values, [Literal(v, datatype=XSD.string) for v in choices])
        shapes.add((prop, SH['in'], values))
        shapes.add((prop, SH.message, Literal(code)))
    for ref in snapshot['nodes']:
        graph.add((EX.source, EX.allowedTarget, Literal(ref, datatype=XSD.string)))
    queries = [('unknown_target', 'SELECT $this WHERE {\n          $this ex:operation ?op; ex:target ?target.\n          FILTER(?op != "clarify")\n          FILTER NOT EXISTS { ex:source ex:allowedTarget ?target }\n        }'), ('clarify_target_not_empty', 'SELECT $this WHERE {\n          $this ex:operation ?op; ex:target ?target.\n          FILTER(STR(?op) = "clarify" && STR(?target) != "")\n        }')]
    for code, query in queries:
        from rdflib import BNode
        constraint = BNode()
        shapes.add((shape, SH.sparql, constraint))
        shapes.add((constraint, SH.select, Literal('PREFIX ex: <' + str(EX) + '>\n' + query)))
        shapes.add((constraint, SH.message, Literal(code)))
    conforms, report, _ = validate(graph, shacl_graph=shapes, inference='none', advanced=False)
    codes = sorted({str(m) for m in report.objects(None, SH.resultMessage)})
    return {'status': 'completed', 'codes': codes, 'conforms': bool(conforms)}

def execute(contract, snapshot):
    errors = contract_errors(contract, snapshot)
    if errors:
        return {'status': 'invalid_contract', 'codes': errors, 'refs': []}
    op, target, scope = (contract[k] for k in ('operation', 'target', 'scope'))
    if op == 'clarify':
        return {'status': 'needs_clarification', 'refs': [], 'world_completeness': 'unverified'}
    if scope == 'real_world':
        return {'status': 'unknown_world_scope', 'refs': [], 'world_completeness': 'unverified'}
    if snapshot['dangling']:
        return {'status': 'invalid_source_references', 'refs': [], 'dangling': snapshot['dangling']}
    nodes, entries = (snapshot['nodes'], snapshot['entries'])
    if op == 'dependency_status':
        knowledge = 'unknown_missing_entry' if target not in entries else 'reported_nonempty' if entries[target]['children'] else 'explicit_empty'
        return {'status': 'answered', 'refs': [], 'knowledge': knowledge, 'world_completeness': 'unverified'}
    reverse = op.endswith('dependents')
    adjacency = {n: set() for n in nodes}
    for src, entry in entries.items():
        for dest in entry['children']:
            adjacency[dest if reverse else src].add(src if reverse else dest)
    if op.startswith('direct_'):
        visited = {target}
        refs = adjacency[target]
    else:
        visited, queue = ({target}, deque([target]))
        while queue:
            at = queue.popleft()
            for dest in sorted(adjacency[at]):
                if dest not in visited:
                    visited.add(dest)
                    queue.append(dest)
        refs = visited - {target}
    opaque = sorted((set(nodes) if reverse else visited) - set(entries))
    return {'status': 'answered', 'refs': sorted(refs), 'opaque_dependency_entries': opaque, 'answer_scope': 'declared_edges_only', 'world_completeness': 'unverified'}

def inventory(snapshot):
    nodes, entries = (snapshot['nodes'], snapshot['entries'])
    depths = {}
    for source in nodes:
        distance, queue = ({source: 0}, deque([source]))
        while queue:
            at = queue.popleft()
            for dest in entries.get(at, {}).get('children', []):
                if dest in nodes and dest not in distance:
                    distance[dest] = distance[at] + 1
                    queue.append(dest)
        depths[source] = max(distance.values())
    return {'nodes': len(nodes), 'dependency_entries': len(entries), 'edges': sum((len(v['children']) for v in entries.values())), 'explicit_empty_entries': sum((not v['children'] for v in entries.values())), 'missing_entries': sorted(set(nodes) - set(entries)), 'dangling': snapshot['dangling'], 'max_shortest_path_depth': max(depths.values(), default=0), 'root': snapshot['root'], 'spec_version': snapshot['spec_version'], 'world_completeness': snapshot['world_completeness'], 'composition_present': snapshot['compositions'] is not None}
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.manifest.read_text())
    result = []
    for i, item in enumerate(manifest['documents']):
        try:
            snapshot = read_document(item['path'])
            if snapshot['source_sha256'] != item['sha256']:
                raise ValueError('source_hash_mismatch')
            (args.output / f'snapshot-{i}.json').write_text(canonical(snapshot) + '\n')
            result.append({'source': item['path'], 'source_sha256': item['sha256'], 'status': 'completed', **inventory(snapshot)})
        except Exception as e:
            result.append({'source': item['path'], 'status': 'failure', 'error': f'{type(e).__name__}: {e}'})
    (args.output / 'inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))
```

## scripts/sbom_reference.py SHA256 1f125b83380f4241b576592407b59151978a29308c6978219821a4f9a3e30a4b
```python
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
        state = 'unknown_missing_entry' if not selected else 'reported_nonempty' if selected[0].get('dependsOn', []) else 'explicit_empty'
        return {'status': 'answered', 'refs': [], 'knowledge': state}
    if op.endswith('dependents'):
        edges = [(b, a) for a, b in edges]
    with sqlite3.connect(':memory:') as connection:
        connection.execute('CREATE TABLE edge (a TEXT NOT NULL,b TEXT NOT NULL)')
        connection.executemany('INSERT INTO edge VALUES (?,?)', edges)
        if op.startswith('direct_'):
            rows = connection.execute('SELECT DISTINCT b FROM edge WHERE a=? ORDER BY b', (target,))
        elif op.startswith('transitive_'):
            rows = connection.execute('WITH RECURSIVE reach(x) AS (\n                SELECT ? UNION SELECT edge.b FROM edge JOIN reach ON edge.a=reach.x\n                ) SELECT x FROM reach WHERE x<>? ORDER BY x', (target, target))
        else:
            raise ValueError('unsupported_reference_operation')
        return {'status': 'answered', 'refs': [r[0] for r in rows]}

def compare(actual, expected):
    return {key: {'expected': value, 'actual': actual.get(key)} for key, value in expected.items() if actual.get(key) != value}
```

## tests/test_sbom_contracts.py SHA256 db331aae44680b86fe1ca44d6e38490ecdc5f119e3ff38fc8703f87f941faf11
```python
import json
import tempfile
import unittest
from pathlib import Path
from scripts.sbom_contracts import read_document, execute, contract_errors, shacl_contract_errors
from scripts.sbom_reference import reference, compare

class Contracts(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'source.json'
        self.document = {'bomFormat': 'CycloneDX', 'specVersion': '1.4', 'components': [{'bom-ref': x, 'name': x} for x in 'ABCD'], 'dependencies': [{'ref': 'A', 'dependsOn': ['B']}, {'ref': 'B', 'dependsOn': ['A', 'C']}, {'ref': 'C'}]}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        self.path.write_text(json.dumps(self.document))
        self.snapshot = read_document(self.path)

    def contract(self, op, target='A', scope='declared_document'):
        return {'operation': op, 'target': target, 'scope': scope}

    def test_cycle_direction_and_reference(self):
        for op, target, refs in [('transitive_dependencies', 'A', ['B', 'C']), ('transitive_dependents', 'C', ['A', 'B']), ('direct_dependencies', 'A', ['B']), ('direct_dependents', 'A', ['B'])]:
            c = self.contract(op, target)
            result = execute(c, self.snapshot)
            self.assertEqual(result['refs'], refs)
            self.assertEqual(compare(result, reference(self.path, c)), {})

    def test_absent_is_not_explicit_empty(self):
        self.assertEqual(execute(self.contract('dependency_status', 'C'), self.snapshot)['knowledge'], 'explicit_empty')
        self.assertEqual(execute(self.contract('dependency_status', 'D'), self.snapshot)['knowledge'], 'unknown_missing_entry')

    def test_world_scope_and_clarification(self):
        self.assertEqual(execute(self.contract('direct_dependencies', scope='real_world'), self.snapshot)['status'], 'unknown_world_scope')
        self.assertEqual(execute(self.contract('clarify', ''), self.snapshot)['status'], 'needs_clarification')

    def test_checker_cannot_certify_question_interpretation(self):
        correct = self.contract('direct_dependencies', 'C')
        wrong = self.contract('direct_dependents', 'C')
        self.assertNotEqual(execute(correct, self.snapshot)['refs'], execute(wrong, self.snapshot)['refs'])
        for c in [correct, wrong]:
            self.assertEqual(contract_errors(c, self.snapshot), [])
            self.assertEqual(shacl_contract_errors(c, self.snapshot)['codes'], [])

    def test_shared_boundary_and_policy_parity(self):
        for c in [self.contract('unsupported'), self.contract('direct_dependencies', 'absent'), self.contract('clarify', 'A'), self.contract('direct_dependencies', scope='unsupported'), {'operation': 1, 'target': 'A', 'scope': 'declared_document'}]:
            self.assertEqual(contract_errors(c, self.snapshot), shacl_contract_errors(c, self.snapshot)['codes'])

    def test_new_edge_to_previously_excluded_node(self):
        c = self.contract('transitive_dependencies')
        old = execute(c, self.snapshot)
        self.document['dependencies'].append({'ref': 'C', 'dependsOn': ['D']})
        self.document['dependencies'].pop(2)
        self.save()
        new = execute(c, self.snapshot)
        self.assertNotIn('D', old['refs'])
        self.assertIn('D', new['refs'])

    def test_dangling_and_duplicate_references(self):
        self.document['dependencies'][0]['dependsOn'].append('Z')
        self.save()
        self.assertEqual(execute(self.contract('direct_dependencies'), self.snapshot)['status'], 'invalid_source_references')
        c = self.contract('dependency_status')
        self.assertEqual(compare(execute(c, self.snapshot), reference(self.path, c)), {})
        self.document['components'].append({'bom-ref': 'A', 'name': 'duplicate'})
        with self.assertRaisesRegex(ValueError, 'duplicate_component_identity'):
            self.save()
if __name__ == '__main__':
    unittest.main()
```