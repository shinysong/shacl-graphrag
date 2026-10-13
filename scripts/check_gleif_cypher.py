"""Development-only Neo4j retrieval parity; local fixtures are not a performance benchmark.

Requires an already-running disposable Neo4j 5 localhost HTTP server. This script
never starts a server. Namespace-scoped writes and cleanup use a random run ID.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from rdflib import RDF, Graph, Literal, URIRef

try:
    from scripts import run_gleif_comparison as c
except ModuleNotFoundError:
    import run_gleif_comparison as c

LABELS = {str(c.EX[name]): name for name in ('Entity', 'Person', 'QuerySubject')}
CREATE_NODES = '''UNWIND $nodes AS row
CREATE (n:GleifParity {run_id: $run_id, id: row.id}) SET n += row.properties
FOREACH (_ IN CASE WHEN 'Entity' IN row.labels THEN [1] ELSE [] END | SET n:Entity)
FOREACH (_ IN CASE WHEN 'Person' IN row.labels THEN [1] ELSE [] END | SET n:Person)
FOREACH (_ IN CASE WHEN 'QuerySubject' IN row.labels THEN [1] ELSE [] END | SET n:QuerySubject)'''
CREATE_EDGES = '''UNWIND $edges AS row
MATCH (s:GleifParity {run_id: $run_id, id: row.s}),
      (o:GleifParity {run_id: $run_id, id: row.o})
CREATE (s)-[:directParent]->(o)'''
QUERY = '''MATCH (s:GleifParity {run_id: $run_id, id: $subject})
OPTIONAL MATCH (s)-[:directParent]->(p:GleifParity {run_id: $run_id})
WITH collect(DISTINCT s) + collect(DISTINCT p) AS selected
UNWIND selected AS n
WITH DISTINCT n
OPTIONAL MATCH (n)-[:directParent]->(o:GleifParity {run_id: $run_id})
RETURN n.id AS id, labels(n) AS labels, properties(n) AS properties,
       collect(DISTINCT o.id) AS parents'''
CLEANUP = 'MATCH (n:GleifParity {run_id: $run_id}) DETACH DELETE n'
VERSION = 'CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition'


def local_endpoint(value):
    if not re.fullmatch(r'http://127\.0\.0\.1:[0-9]{1,5}', value):
        raise ValueError('Endpoint must be explicitly supplied as http://127.0.0.1:<port>')
    if not 1 <= int(value.rsplit(':', 1)[1]) <= 65535:
        raise ValueError('Invalid port')
    return value + '/db/neo4j/tx/commit'


def development_only(dataset):
    cohort = dataset.get('cohort', [])
    if not cohort or any(item.get('split') != 'development' for item in cohort):
        raise ValueError('DevelopmentOnly: reserved/evaluation data are not executable')
    return cohort


def to_lpg(graph):
    """Typed edges, native class labels and JSON arrays of RDF literal metadata."""
    nodes, edges = {}, []

    def node(term):
        if not isinstance(term, URIRef):
            raise TypeError('Only IRI nodes supported in bounded GLEIF mapping')
        return nodes.setdefault(str(term), {'id': str(term), 'labels': [], 'properties': {}})

    for s, p, o in graph:
        n = node(s)
        if p == RDF.type:
            if str(o) not in LABELS:
                raise ValueError('Unsupported RDF class: ' + str(o))
            n['labels'].append(LABELS[str(o)])
        elif isinstance(o, Literal):
            n['properties'].setdefault(str(p), []).append({
                'value': str(o), 'datatype': str(o.datatype) if o.datatype else None,
                'language': o.language})
        elif p == c.EX.directParent:
            node(o)
            edges.append({'s': str(s), 'o': str(o)})
        else:
            raise ValueError('Unsupported IRI predicate: ' + str(p))
    for n in nodes.values():
        n['labels'].sort()
        n['properties'] = {p: json.dumps(sorted(values, key=lambda v: json.dumps(v, sort_keys=True)),
                                         ensure_ascii=False, sort_keys=True)
                           for p, values in n['properties'].items()}
    return sorted(nodes.values(), key=lambda n: n['id']), sorted(edges, key=lambda e: (e['s'], e['o']))


def from_rows(rows):
    graph = Graph()
    reverse = {label: URIRef(iri) for iri, label in LABELS.items()}
    for row in rows:
        subject = URIRef(row['id'])
        for label in row['labels']:
            if label == 'GleifParity':
                continue
            graph.add((subject, RDF.type, reverse[label]))
        for predicate, encoded in row['properties'].items():
            if predicate in {'id', 'run_id'}:
                continue
            for value in json.loads(encoded):
                graph.add((subject, URIRef(predicate), Literal(
                    value['value'], datatype=URIRef(value['datatype']) if value['datatype'] else None,
                    lang=value['language'], normalize=False)))
        for parent in row['parents']:
            graph.add((subject, c.EX.directParent, URIRef(parent)))
    return graph


def execute(client, endpoint, query, parameters=None):
    response = client.post(endpoint, json={'statements': [{'statement': query,
                          'parameters': parameters or {}, 'resultDataContents': ['row']}]})
    response.raise_for_status()
    payload = response.json()
    if payload.get('errors'):
        raise RuntimeError(json.dumps(payload['errors']))
    result = payload['results'][0]
    return [dict(zip(result['columns'], row['row'], strict=True)) for row in result['data']]


def digest(facts):
    return hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('development', type=Path)
    parser.add_argument('--endpoint', required=True, help='http://127.0.0.1:<explicit HTTP port>')
    parser.add_argument('--username', default='neo4j')
    parser.add_argument('--password-env', default='NEO4J_PASSWORD')
    parser.add_argument('--no-auth', action='store_true', help='Disposable localhost server only')
    args = parser.parse_args()
    endpoint = local_endpoint(args.endpoint)
    dataset = json.loads(args.development.read_text())
    cohort = development_only(dataset)
    password = None if args.no_auth else os.environ.get(args.password_env)
    if not args.no_auth and not password:
        parser.error('Set the password environment variable or explicitly use --no-auth')
    config = json.loads((c.FIX / 'config.json').read_text())
    run_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-gleif-cypher-' + uuid.uuid4().hex
    output = c.ROOT / 'runs' / run_id
    output.mkdir(parents=True)
    hashes = {}
    for name in ('scripts/check_gleif_cypher.py', 'scripts/run_gleif_comparison.py',
                 'scripts/run_gleif_pilot.py', 'experiments/comparison/config.json', 'uv.lock'):
        src, dest = c.ROOT / name, output / 'inputs' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        hashes[name] = c.old.sha(src)
    shutil.copyfile(args.development, output / 'development.json')
    record = {'run_id': run_id, 'status': 'running', 'scope': 'development native Cypher/RDF parity only',
              'limitations': 'Small local fixtures; timings include HTTP/serialization; no performance or memory benchmark.',
              'protocol': config['protocol_version'], 'config': config, 'endpoint': args.endpoint,
              'dataset_sha256': c.old.sha(args.development), 'inputs_sha256': hashes,
              'source_manifest': dataset.get('source_manifest'), 'neo4j_version': None,
              'queries': {'retrieve': QUERY, 'create_nodes': CREATE_NODES, 'create_edges': CREATE_EDGES,
                          'cleanup': CLEANUP, 'version': VERSION, 'sparql': c.old.QUERY},
              'cases': []}
    def save():
        c.old.write(output / 'record.json', record)

    save()
    try:
        with httpx.Client(auth=None if args.no_auth else (args.username, password),
                          trust_env=False, follow_redirects=False, timeout=30) as client:
            record['neo4j_version'] = execute(client, endpoint, VERSION)
            save()
            for item in cohort:
                for variant in config[item['kind'] + '_variants']:
                    case_id = item['lei'] + '-' + variant
                    namespace = run_id + ':' + case_id
                    params = {'run_id': namespace, 'subject': str(c.LEI[item['lei']])}
                    row = {'case_id': case_id, 'variant': variant, 'namespace': namespace,
                           'status': 'running', 'parity': False}
                    record['cases'].append(row)
                    save()
                    try:
                        source = c.build_case(dataset, item, variant)
                        nodes, edges = to_lpg(source)
                        start = time.perf_counter()
                        execute(client, endpoint, CREATE_NODES, {**params, 'nodes': nodes})
                        execute(client, endpoint, CREATE_EDGES, {**params, 'edges': edges})
                        row['load_http_ms'] = (time.perf_counter() - start) * 1000
                        start = time.perf_counter()
                        native = execute(client, endpoint, QUERY, params)
                        row['cypher_http_ms'] = (time.perf_counter() - start) * 1000
                        start = time.perf_counter()
                        rdf_raw = c.old.retrieve(source, c.LEI[item['lei']])
                        row['sparql_ms'] = (time.perf_counter() - start) * 1000
                        lpg_raw = from_rows(native)
                        row['raw_parity'] = c.canonical(rdf_raw) == c.canonical(lpg_raw)
                        rdf = c.canonical(c.omit(rdf_raw, c.LEI[item['lei']], variant))
                        lpg = c.canonical(c.omit(lpg_raw, c.LEI[item['lei']], variant))
                        row.update(rdf_sha256=digest(rdf), lpg_sha256=digest(lpg),
                                   parity=row['raw_parity'] and rdf == lpg, status='ok')
                        case_path = output / case_id
                        case_path.mkdir()
                        source.serialize(case_path / 'source.ttl', format='turtle')
                        c.old.write(case_path / 'native-rows.json', native)
                        c.old.write(case_path / 'rdf-facts.json', rdf)
                        c.old.write(case_path / 'lpg-facts.json', lpg)
                        if not row['parity']:
                            row['status'] = 'mismatch'
                    except Exception as exc:  # noqa: BLE001 - Preserve failed experiments and cleanup failures.
                        row.update(status='error', error=f'{type(exc).__name__}: {exc}')
                    finally:
                        try:
                            execute(client, endpoint, CLEANUP, params)
                            row['cleanup'] = 'ok'
                        except Exception as exc:  # noqa: BLE001 - Preserve failed experiments and cleanup failures.
                            row.update(cleanup='error', cleanup_error=f'{type(exc).__name__}: {exc}')
                        save()
            record['status'] = 'completed' if all(
                r['status'] == 'ok' and r['parity'] and r['cleanup'] == 'ok'
                for r in record['cases']) else 'failed'
    except Exception as exc:  # noqa: BLE001 - Preserve failed experiments and cleanup failures.
        record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
    finally:
        record['finished_utc'] = datetime.now(UTC).isoformat()
        save()
        print(output / 'record.json')
    return 0 if record['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
