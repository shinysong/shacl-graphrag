"""Independent saved-snapshot SPARQL verification, not an RDF database benchmark."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, unquote

from rdflib import Graph, Literal, Namespace, RDF, URIRef

EX = Namespace('urn:lifecycle:')
QUERY = '''SELECT DISTINCT ?supplier ?region ?country ?role ?supply ?location ?within
WHERE {
  ?product a <urn:lifecycle:Product> .
  ?supply rdf:subject ?product .
  BIND (?supply AS ?supplyAnchor)
  ?supplyAnchor a rdf:Statement ;
    rdf:predicate <urn:lifecycle:SUPPLIED_BY> ; rdf:object ?supplier ;
    <urn:lifecycle:role> ?role .
  FILTER (?role = ?allowed0 || ?role = ?allowed1)
  BIND (?supplier AS ?supplierAnchor)
  ?supplierAnchor a <urn:lifecycle:Supplier> .
  ?location rdf:subject ?supplierAnchor .
  BIND (?location AS ?locationAnchor)
  ?locationAnchor a rdf:Statement ;
    rdf:predicate <urn:lifecycle:LOCATED_IN> ; rdf:object ?region .
  BIND (?region AS ?regionAnchor)
  ?regionAnchor a <urn:lifecycle:Region> .
  ?within rdf:subject ?regionAnchor .
  BIND (?within AS ?withinAnchor)
  ?withinAnchor a rdf:Statement ;
    rdf:predicate <urn:lifecycle:IN_COUNTRY> ; rdf:object ?country .
  ?country a <urn:lifecycle:Country> .
}'''


def iri(kind, identifier):
    return URIRef('urn:lifecycle:' + kind + ':' + quote(identifier, safe=''))


def identifier(value, kind):
    prefix = 'urn:lifecycle:' + kind + ':'
    value = str(value)
    if not value.startswith(prefix):
        raise ValueError('Unexpected result namespace')
    return unquote(value[len(prefix):])


def as_rdf(snapshot):
    graph = Graph()
    for node in snapshot['nodes']:
        graph.add((iri('entity', node['id']), RDF.type, EX[node['kind']]))
    for edge in snapshot['edges']:
        statement = iri('edge', edge['id'])
        graph.add((statement, RDF.type, RDF.Statement))
        graph.add((statement, RDF.subject, iri('entity', edge['s'])))
        graph.add((statement, RDF.predicate, EX[edge['kind']]))
        graph.add((statement, RDF.object, iri('entity', edge['t'])))
        if edge['role'] is not None:
            graph.add((statement, EX.role, Literal(edge['role'])))
    return graph


def query(graph, subject, allowed_roles):
    if not allowed_roles or set(allowed_roles) - {'primary', 'backup'}:
        raise ValueError('Unsupported roles')
    bindings = {'product': iri('entity', subject), 'allowed0': Literal(allowed_roles[0]),
                'allowed1': Literal(allowed_roles[-1])}
    paths = []
    for row in graph.query(QUERY, initBindings=bindings, initNs={'rdf': RDF}):
        paths.append(dict(product=subject, supplier=identifier(row.supplier, 'entity'),
                          region=identifier(row.region, 'entity'),
                          country=identifier(row.country, 'entity'), role=str(row.role),
                          supply_edge=identifier(row.supply, 'edge'),
                          location_edge=identifier(row.location, 'edge'),
                          country_edge=identifier(row.within, 'edge')))
    unique = {json.dumps(p, sort_keys=True): p for p in paths}
    return {'countries': sorted({p['country'] for p in paths}),
            'paths': [unique[k] for k in sorted(unique)]}


def coverage(record, rows):
    """Reconstruct the declared matrix independently; reject missing/duplicate work."""
    checkpoints = ('initial', 'add_products', 'change_region', 'delete_supply',
                   'restore_supply', 'add_backup', 'allow_backup', 'revert_rule')
    subjects = [*[f'p{i}' for i in range(18)], 'new0', 'missing']
    arms = ('json_scan', 'json_indexed', 'neo4j')
    expected_snapshots = {(n, r, c) for n in record['sizes']
                          for r in range(record['repeats']) for c in checkpoints}
    snapshot_keys = [(s['size'], s['repeat'], s['checkpoint']) for s in record['snapshots']]
    if len(snapshot_keys) != len(set(snapshot_keys)) or set(snapshot_keys) != expected_snapshots:
        raise ValueError('Incomplete or duplicate snapshot coverage')
    expected_rows = {(*key, subject, arm) for key in expected_snapshots
                     for subject in subjects for arm in arms}
    row_keys = [(r['size'], r['repeat'], r['checkpoint'], r['subject'], r['arm']) for r in rows]
    if len(row_keys) != len(set(row_keys)) or set(row_keys) != expected_rows:
        raise ValueError('Incomplete or duplicate row coverage')
    expected_ids = {f'n{n}-r{r}-{c}-{subject}-{arm}' for n, r, c, subject, arm in expected_rows}
    if len({r['id'] for r in rows}) != len(rows) or {r['id'] for r in rows} != expected_ids:
        raise ValueError('Invalid row identities')
    for row in rows:
        if row['id'] != f"n{row['size']}-r{row['repeat']}-{row['checkpoint']}-{row['subject']}-{row['arm']}":
            raise ValueError('Row identity binding mismatch')
    if record['planned_rows'] != len(expected_rows):
        raise ValueError('Declared denominator mismatch')
    return len(expected_snapshots), len(expected_snapshots) * len(subjects), expected_ids


def verify(run, output):
    if output.exists():
        raise FileExistsError(output)
    record = json.loads((run / 'record.json').read_text())
    rows = [json.loads(p.read_text()) for p in sorted((run / 'rows').glob('*.json'))]
    result = {'status': 'running', 'scope': 'RDFLib in-memory SPARQL, not RDF DB',
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'query': QUERY, 'snapshots_checked': 0, 'queries_checked': 0,
              'rows_compared': 0, 'mismatches': [], 'answers': []}
    def save():
        output.write_text(json.dumps(result, indent=2) + '\n')
    save()
    try:
        if record['status'] != 'completed' or len(rows) != record['planned_rows']:
            raise ValueError('Require completed source run with full denominator')
        expected_snapshots, expected_queries, expected_ids = coverage(record, rows)
        compared_ids = set()
        for item in record['snapshots']:
            path = run / item['path']
            if hashlib.sha256(path.read_bytes()).hexdigest() != item['file_sha256']:
                raise ValueError('Snapshot hash mismatch')
            snapshot = json.loads(path.read_text())
            graph = as_rdf(snapshot)
            selected = [r for r in rows if all(r[k] == item[k] for k in ('size', 'repeat', 'checkpoint'))]
            for subject in sorted({r['subject'] for r in selected}):
                answer = query(graph, subject, snapshot['config']['allowed_roles'])
                result['answers'].append({**{k: item[k] for k in ('size', 'repeat', 'checkpoint')},
                                          'subject': subject, 'answer': answer})
                for row in (r for r in selected if r['subject'] == subject):
                    if row['id'] in compared_ids:
                        raise ValueError('Row compared twice')
                    compared_ids.add(row['id'])
                    result['rows_compared'] += 1
                    if row['status'] != 'ok' or answer != row['answer'] or answer != row['expected']:
                        result['mismatches'].append(row['id'])
                result['queries_checked'] += 1
            result['snapshots_checked'] += 1
            save()
        if (compared_ids != expected_ids or result['snapshots_checked'] != expected_snapshots
                or result['queries_checked'] != expected_queries):
            raise ValueError('Final coverage mismatch')
        result['status'] = 'completed' if not result['mismatches'] else 'mismatch'
    except BaseException as exc:
        result.update(status='failed', error_type=type(exc).__name__)
        raise
    finally:
        save()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.run, args.output)
    print(json.dumps({k: result[k] for k in ('status', 'snapshots_checked', 'queries_checked', 'rows_compared', 'mismatches')}))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
