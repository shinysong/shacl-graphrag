"""Strict bounded candidate generation and independent fresh-shadow validation.

No source fetching, evaluation references, physical prescriptions or source writes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from importlib.metadata import version
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD
from rdflib.namespace import SH

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'research/actionable-evidence-1'
EX = Namespace('urn:actionable-evidence:')
ARMS = ('direct_local_candidate', 'matched_Python_relation_candidate', 'SHACL_AF_relation_candidate')
POSTCHECKS = ('no_postcheck', 'shadow_revalidation')
ID = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}\Z', re.ASCII)


class SchemaError(ValueError):
    """Malformed bounded input; never a repaired or abstaining result."""


def require(condition, message):
    if not condition:
        raise SchemaError(message)


def keys(obj, expected, location):
    require(type(obj) is dict and set(obj) == set(expected.split()), f'{location}: exact required keys {expected}')


def identifier(value, location):
    require(type(value) is str and ID.fullmatch(value) is not None, f'{location}: bounded ASCII identifier required')


def string(value, location):
    require(type(value) is str and 1 <= len(value) <= 512 and not any(ord(c) < 32 for c in value), f'{location}: nonempty bounded string required')


def bounds(obj, location):
    require(type(obj['minimum']) is int and type(obj['maximum']) is int, f'{location}: integer bounds required')
    require(obj['minimum'] <= obj['maximum'], f'{location}: reversed bounds')


def check_schema(data):
    keys(data, 'target nodes edges dependencies', 'input')
    target = data['target']
    keys(target, 'id field unit version value minimum maximum', 'target')
    identifier(target['id'], 'target.id')
    require(target['field'] in ('setting', 'end_mm'), 'target.field: unsupported field')
    for name in ('unit', 'version'):
        string(target[name], f'target.{name}')
    require(target['value'] is None or type(target['value']) is int, 'target.value: integer or null required')
    bounds(target, 'target')
    for name, limit in (('nodes', 16), ('edges', 24), ('dependencies', 8)):
        require(type(data[name]) is list and len(data[name]) <= limit, f'{name}: bounded list required')
    ids = {target['id']}
    types = {target['id']: 'Target'}
    references = 0
    for node in data['nodes']:
        require(type(node) is dict, 'node: object required')
        require(node.get('type') in ('Reference', 'Bridge'), 'node.type: unsupported')
        keys(node, 'id type' if node['type'] == 'Bridge' else 'id type entity field unit version value citation', 'node')
        identifier(node['id'], 'node.id')
        require(node['id'] not in ids, 'duplicate ID')
        ids.add(node['id'])
        types[node['id']] = node['type']
        if node['type'] == 'Reference':
            references += 1
            identifier(node['entity'], 'reference.entity')
            require(node['field'] in ('setting', 'end_mm'), 'reference.field: unsupported field')
            for name in ('unit', 'version', 'citation'):
                string(node[name], f'reference.{name}')
            require(type(node['value']) is int, 'reference.value: integer required')
    require(references <= 4, 'at most four references')
    seen = set()
    for edge in data['edges']:
        keys(edge, 'from to', 'edge')
        identifier(edge['from'], 'edge.from')
        identifier(edge['to'], 'edge.to')
        pair = (edge['from'], edge['to'])
        require(pair not in seen, 'duplicate edge')
        seen.add(pair)
        require(edge['from'] in types and edge['to'] in types, 'dangling edge')
        require((types[edge['from']], types[edge['to']]) in {('Target', 'Reference'), ('Target', 'Bridge'), ('Bridge', 'Reference')}, 'edge outside fixed acyclic depth grammar')
    for dep in data['dependencies']:
        keys(dep, 'id target minimum maximum', 'dependency')
        identifier(dep['id'], 'dependency.id')
        require(dep['id'] not in ids, 'duplicate ID')
        ids.add(dep['id'])
        require(dep['target'] == target['id'], 'dependency must refer to target')
        bounds(dep, 'dependency')


def iri(identifier):
    return URIRef('urn:actionable-evidence:record:' + identifier)


def build_graph(data):
    graph = Graph()
    graph.bind('ex', EX)
    for obj, kind in [(data['target'], 'Target')] + [(n, n['type']) for n in data['nodes']] + [(d, 'Dependency') for d in data['dependencies']]:
        subject = iri(obj['id'])
        graph.add((subject, RDF.type, EX[kind]))
        for key, value in obj.items():
            if key in ('id', 'type') or value is None:
                continue
            term = iri(value) if key in ('entity', 'target') else Literal(value, datatype=XSD.integer if type(value) is int else None)
            graph.add((subject, EX[key], term))
    for edge in data['edges']:
        graph.add((iri(edge['from']), EX.edge, iri(edge['to'])))
    return graph


def derive(graph):
    validate(graph, shacl_graph=str(ASSETS / 'rules.ttl'), advanced=True,
             inference='none', iterate_rules=False, inplace=True)


def python_candidates(data, arm):
    target = data['target']
    reachable = {e['to'] for e in data['edges'] if e['from'] == target['id']}
    if arm != 'direct_local_candidate':
        bridges = {n['id'] for n in data['nodes'] if n['type'] == 'Bridge'} & reachable
        reachable |= {e['to'] for e in data['edges'] if e['from'] in bridges}
    return sorted(n['id'] for n in data['nodes'] if n['type'] == 'Reference' and n['id'] in reachable and n['entity'] == target['id'] and all(n[k] == target[k] for k in ('field', 'unit', 'version')))


def python_report(data):
    target = data['target']
    value = target['value']
    issues = []
    if value is None or type(value) is not int:
        issues.append({'focus': str(iri(target['id'])), 'message': 'target_value_required_integer'})
    elif not target['minimum'] <= value <= target['maximum']:
        issues.append({'focus': str(iri(target['id'])), 'message': 'target_bounds'})
    for dep in data['dependencies']:
        if value is None:
            issues.append({'focus': str(iri(dep['id'])), 'message': 'dependency_value_required'})
        elif not dep['minimum'] <= value <= dep['maximum']:
            issues.append({'focus': str(iri(dep['id'])), 'message': 'dependency_bounds'})
    return {'conforms': not issues, 'results': sorted(issues, key=lambda x: (x['focus'], x['message']))}


def report(data, graph):
    conforms, result_graph, _ = validate(graph, shacl_graph=str(ASSETS / 'shapes.ttl'), advanced=False, inference='none', inplace=False)
    issues = sorted([{'focus': str(result_graph.value(result, SH.focusNode)), 'message': str(result_graph.value(result, SH.resultMessage))} for result in result_graph.subjects(RDF.type, SH.ValidationResult)], key=lambda x: (x['focus'], x['message']))
    shacl = {'conforms': bool(conforms), 'results': issues}
    independent = python_report(data)
    return {'shacl': shacl, 'python': independent, 'validators_agree': shacl == independent}


def provenance():
    paths = [Path(__file__), ASSETS / 'rules.ttl', ASSETS / 'shapes.ttl', ASSETS / 'implementation-contract.md', ROOT / 'uv.lock']
    return {'versions': {name: version(name) for name in ('pyshacl', 'rdflib')}, 'sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}


def run(data, arm, postcheck):
    """Return a JSON-compatible result; raise SchemaError on invalid input/options.

    input_sha256 hashes canonical JSON. CLI additionally records exact file bytes.
    """
    require(arm in ARMS, 'unsupported arm')
    require(postcheck in POSTCHECKS, 'unsupported postcheck')
    check_schema(data)
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    original_graph = build_graph(data)
    before = report(data, original_graph)
    derived = []
    if arm == 'SHACL_AF_relation_candidate':
        private_graph = build_graph(data)
        derive(private_graph)
        uri_to_id = {iri(n['id']): n['id'] for n in data['nodes']}
        candidates = sorted(uri_to_id[ref] for ref in private_graph.objects(iri(data['target']['id']), EX.applicableReference))
        derived = candidates[:]
    else:
        candidates = python_candidates(data, arm)
    by_id = {n['id']: n for n in data['nodes']}
    citations = [by_id[ref]['citation'] for ref in candidates]
    patch = None
    after = None
    diff = []
    disposition = 'request_evidence' if not candidates else 'request_reconciliation'
    shadow_references = None
    if len(candidates) == 1:
        target = data['target']
        value = by_id[candidates[0]]['value']
        patch = {'target': target['id'], 'field': target['field'], 'old': target['value'], 'new': value}
        shadow = copy.deepcopy(data)
        shadow['target']['value'] = value
        if value != target['value']:
            diff = [{'path': '/target/value', 'old': target['value'], 'new': value}]
        shadow_graph = build_graph(shadow)
        if arm == 'SHACL_AF_relation_candidate':
            derive(shadow_graph)
            shadow_references = sorted(uri_to_id[ref] for ref in shadow_graph.objects(iri(target['id']), EX.applicableReference))
        after = report(shadow, shadow_graph)
        if postcheck == 'no_postcheck' or after['shacl']['conforms']:
            disposition = 'propose_patch'
    return {'status': 'ok', 'arm': arm, 'postcheck': postcheck,
            'input_sha256': hashlib.sha256(canonical).hexdigest(), 'input_hash_encoding': 'canonical-json-utf8',
            'candidate_reference_ids': candidates, 'candidate_citations': citations,
            'candidate_patch': patch, 'candidate': {'reference_ids': candidates, 'citations': citations, 'patch': patch} if patch is not None else None,
            'diff': diff, 'before_report': before, 'after_report': after, 'before': before, 'after': after,
            'original_unchanged': canonical == json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode(),
            'disposition': disposition, 'diagnostics': {'applicable_reference_count': len(candidates), 'rule_derived_reference_ids': derived, 'shadow_rule_derived_reference_ids': shadow_references, 'original_graph_triples': len(original_graph)},
            'provenance': provenance()}


def reject_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, 'duplicate JSON key')
        obj[key] = value
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--arm', choices=ARMS, required=True)
    parser.add_argument('--postcheck', choices=POSTCHECKS, required=True)
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        data = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
        result = run(data, args.arm, args.postcheck)
        result['input_file_sha256'] = hashlib.sha256(raw).hexdigest()
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except (SchemaError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(json.dumps({'status': 'schema_error', 'error_type': type(exc).__name__, 'message': str(exc)}))
        return 2
    except Exception as exc:
        print(json.dumps({'status': 'error', 'error_type': type(exc).__name__, 'message': str(exc)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
