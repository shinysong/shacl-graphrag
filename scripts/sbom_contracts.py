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
OPERATIONS = ('direct_dependencies', 'transitive_dependencies',
              'direct_dependents', 'transitive_dependents', 'dependency_status', 'clarify')
SCOPES = ('declared_document', 'real_world')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_document(path):
    raw = Path(path).read_bytes()
    if len(raw) > 2_000_000:
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
        if not isinstance(children, list) or any(not isinstance(c, str) or not c for c in children):
            raise ValueError('invalid_dependency_children')
        if len(set(children)) != len(children):
            raise ValueError('duplicate_dependency_child')
        entries[ref] = {'children': sorted(children), 'pointer': f'/dependencies/{index}',
                        'dependsOn_present': 'dependsOn' in entry}
    if sum(len(x['children']) for x in entries.values()) > 5000:
        raise ValueError('edge_limit')
    dangling = sorted(({r for r in entries} | {c for e in entries.values() for c in e['children']}) - set(nodes))
    return {'source_sha256': hashlib.sha256(raw).hexdigest(), 'spec_version': document['specVersion'],
            'root': root.get('bom-ref') if root else None, 'nodes': nodes, 'entries': entries,
            'dangling': dangling, 'compositions': document.get('compositions'),
            'world_completeness': 'unverified'}


def contract_errors(contract, snapshot):
    if not isinstance(contract, dict) or set(contract) != {'operation', 'target', 'scope'}:
        return ['input_shape']
    if not all(isinstance(contract[k], str) for k in contract):
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
    # Shared transport boundary is not a SHACL conformance result.
    boundary = contract_errors(contract, snapshot)
    if boundary and boundary[0] in ('input_shape', 'input_types'):
        return {'status': 'input_rejected', 'codes': boundary, 'conforms': None}
    from pyshacl import validate
    graph, shapes = Graph(), Graph()
    node = EX.contract
    graph.add((node, RDF.type, EX.Contract))
    for k, v in contract.items():
        graph.add((node, EX[k], Literal(v, datatype=XSD.string)))
    shape = EX.ContractShape
    shapes.add((shape, RDF.type, SH.NodeShape))
    shapes.add((shape, SH.targetClass, EX.Contract))
    for name, choices, code in [('operation', OPERATIONS, 'unsupported_operation'),
                                 ('scope', SCOPES, 'unsupported_scope')]:
        from rdflib import BNode
        from rdflib.collection import Collection
        prop, values = BNode(), BNode()
        shapes.add((shape, SH.property, prop)); shapes.add((prop, SH.path, EX[name]))
        Collection(shapes, values, [Literal(v, datatype=XSD.string) for v in choices])
        shapes.add((prop, SH['in'], values)); shapes.add((prop, SH.message, Literal(code)))
    # Target membership and clarify are represented as SHACL-SPARQL checks.
    for ref in snapshot['nodes']:
        graph.add((EX.source, EX.allowedTarget, Literal(ref, datatype=XSD.string)))
    queries = [
        ('unknown_target', '''SELECT $this WHERE {
          $this ex:operation ?op; ex:target ?target.
          FILTER(?op != "clarify")
          FILTER NOT EXISTS { ex:source ex:allowedTarget ?target }
        }'''),
        ('clarify_target_not_empty', '''SELECT $this WHERE {
          $this ex:operation ?op; ex:target ?target.
          FILTER(STR(?op) = "clarify" && STR(?target) != "")
        }''')]
    for code, query in queries:
        from rdflib import BNode
        constraint = BNode()
        shapes.add((shape, SH.sparql, constraint))
        shapes.add((constraint, SH.select, Literal('PREFIX ex: <'+str(EX)+'>\n'+query)))
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
    nodes, entries = snapshot['nodes'], snapshot['entries']
    if op == 'dependency_status':
        knowledge = ('unknown_missing_entry' if target not in entries else
                     'reported_nonempty' if entries[target]['children'] else 'explicit_empty')
        return {'status': 'answered', 'refs': [], 'knowledge': knowledge,
                'world_completeness': 'unverified'}
    reverse = op.endswith('dependents')
    adjacency = {n: set() for n in nodes}
    for src, entry in entries.items():
        for dest in entry['children']:
            adjacency[dest if reverse else src].add(src if reverse else dest)
    if op.startswith('direct_'):
        visited = {target}; refs = adjacency[target]
    else:
        visited, queue = {target}, deque([target])
        while queue:
            at = queue.popleft()
            for dest in sorted(adjacency[at]):
                if dest not in visited:
                    visited.add(dest); queue.append(dest)
        refs = visited - {target}  # A cycle never counts its starting component as its own answer.
    opaque = sorted((set(nodes) if reverse else visited) - set(entries))
    return {'status': 'answered', 'refs': sorted(refs), 'opaque_dependency_entries': opaque,
            'answer_scope': 'declared_edges_only', 'world_completeness': 'unverified'}


def inventory(snapshot):
    nodes, entries = snapshot['nodes'], snapshot['entries']
    depths = {}
    for source in nodes:
        distance, queue = {source: 0}, deque([source])
        while queue:
            at = queue.popleft()
            for dest in entries.get(at, {}).get('children', []):
                if dest in nodes and dest not in distance:
                    distance[dest] = distance[at] + 1; queue.append(dest)
        depths[source] = max(distance.values())
    return {'nodes': len(nodes), 'dependency_entries': len(entries),
            'edges': sum(len(v['children']) for v in entries.values()),
            'explicit_empty_entries': sum(not v['children'] for v in entries.values()),
            'missing_entries': sorted(set(nodes) - set(entries)), 'dangling': snapshot['dangling'],
            'max_shortest_path_depth': max(depths.values(), default=0),
            'root': snapshot['root'], 'spec_version': snapshot['spec_version'],
            'world_completeness': snapshot['world_completeness'],
            'composition_present': snapshot['compositions'] is not None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('manifest', type=Path); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(args.manifest.read_text()); result = []
    for i, item in enumerate(manifest['documents']):
        try:
            snapshot = read_document(item['path'])
            if snapshot['source_sha256'] != item['sha256']:
                raise ValueError('source_hash_mismatch')
            (args.output/f'snapshot-{i}.json').write_text(canonical(snapshot)+'\n')
            result.append({'source': item['path'], 'source_sha256': item['sha256'], 'status': 'completed', **inventory(snapshot)})
        except Exception as e:
            result.append({'source': item['path'], 'status': 'failure', 'error': f'{type(e).__name__}: {e}'})
    (args.output/'inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
