"""Versioned RDF projection and fixed SPARQL tools; no LLM query generation."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx
from rdflib import Dataset, Graph as RDFGraph, Literal, Namespace, RDF, URIRef, XSD
from .graph import NAMESPACE, RELATIONS, snapshot, validate_args

VOCAB = Namespace('urn:factory-demo:vocab:')
BASE = 'urn:factory-demo:'
FIELDS = ('id', 'name', 'status', 'product', 'capability', 'valid_from', 'valid_until')
KINDS = {'Machine', 'Order', 'Capability', 'Qualification'}
ENDPOINT = 'https://shacl-graphrag-research.cluster-cj60oo44gibs.ap-northeast-2.neptune.amazonaws.com:8182/sparql'
ACCOUNT, REGION, CLUSTER = '985658740608', 'ap-northeast-2', 'shacl-graphrag-research'


def graph_uri(version):
    # URI construction is pure. Source integrity is checked by project/run/load.
    if version not in ('factory-v1', 'factory-v2', 'factory-v3'):
        raise ValueError('Unknown snapshot')
    return URIRef(BASE + 'graph:' + version)


def subject(version, entity_id):
    return URIRef(BASE + version + ':entity:' + quote(entity_id, safe=''))


def project(version):
    source, sha = snapshot(version)
    g = RDFGraph(identifier=graph_uri(version))
    meta = URIRef(BASE + version + ':snapshot')
    g.add((meta, VOCAB.source_sha256, Literal(sha)))
    g.add((meta, VOCAB.as_of, Literal(source['as_of'], datatype=XSD.date)))
    for node in source['nodes']:
        if node['kind'] not in KINDS or set(node) - set(FIELDS) - {'kind'}:
            raise ValueError('Unsupported source node contract')
        s = subject(version, node['id'])
        g.add((s, RDF.type, VOCAB[node['kind']]))
        for k in FIELDS:
            if k in node:
                if not isinstance(node[k], str):
                    raise ValueError('Source fields must be strings')
                g.add((s, VOCAB[k], Literal(node[k], datatype=XSD.date if k.startswith('valid_') else None)))
    ids = {n['id'] for n in source['nodes']}
    for a, relation, b in source['edges']:
        if relation not in RELATIONS or a not in ids or b not in ids:
            raise ValueError('Invalid source relationship')
        g.add((subject(version, a), VOCAB[relation], subject(version, b)))
    return g


def canonical_triples(g):
    # RDF 1.1 xsd:string and a simple string denote the same term.
    def canonical(term):
        if isinstance(term, Literal) and term.datatype == XSD.string:
            return Literal(str(term)).n3()
        return term.n3()
    return sorted(tuple(canonical(t) for t in triple) for triple in g)


def export(version):
    return ''.join(' '.join(t) + ' .\n' for t in canonical_triples(project(version)))


def templates(version, tool, args):
    """Tuple LIMIT precedes property joins, matching each Cypher tool's limit."""
    args = validate_args(tool, args)
    iri = graph_uri(version).n3()
    def lit(s): return Literal(s).n3()
    entity = subject(version, next(iter(args.values()))).n3()
    if tool == 'find_entities':
        roles, columns, order, limit = ('entity',), ('entity',), '?entity_id', 30
        match = f'?entity f:id ?entity_id; f:name ?search_name . FILTER(CONTAINS(LCASE(?entity_id), LCASE({lit(args["text"])})) || CONTAINS(LCASE(?search_name), LCASE({lit(args["text"])})))'
    elif tool == 'inspect_entity':
        roles, columns, order, limit = ('entity', 'neighbor'), ('entity', 'neighbor', 'relation', 'from_id'), '?relation ?neighbor_id', 60
        match = f'BIND({entity} AS ?entity) ?entity f:id ?entity_id . OPTIONAL {{ VALUES ?relation {{ ' + ' '.join(VOCAB[r].n3() for r in sorted(RELATIONS)) + ' } { ?entity ?relation ?neighbor . ?entity f:id ?from_id } UNION { ?neighbor ?relation ?entity . ?neighbor f:id ?from_id } ?neighbor f:id ?neighbor_id . }'
    elif tool == 'impacted_orders':
        roles, columns, order, limit = ('order', 'machine'), ('order', 'machine', 'required_capability'), '?order_id ?required_capability', 30
        match = f'BIND({entity} AS ?machine) ?order f:ASSIGNED_TO ?machine; f:id ?order_id . OPTIONAL {{ ?order f:REQUIRES ?cap . ?cap f:id ?required_capability }}'
    elif tool == 'replacement_candidates':
        roles, columns, order, limit = ('order', 'machine'), ('order', 'machine', 'required_capability'), '?machine_id ?required_capability', 30
        match = f'BIND({entity} AS ?order) ?order f:REQUIRES ?cap . ?machine f:CAPABLE_OF ?cap; f:id ?machine_id . ?cap f:id ?required_capability .'
    else:
        roles, columns, order, limit = ('machine', 'qualification'), ('machine', 'qualification'), '?qualification_id', 30
        match = f'BIND({entity} AS ?machine) ?machine f:id ?machine_id . OPTIONAL {{ ?machine f:HAS_QUALIFICATION ?qualification . ?qualification f:id ?qualification_id }}'
    # Bind a sentinel key before property joins: an unbound optional node must not scan all nodes.
    props = []
    for role in roles:
        fields = ' '.join(f'OPTIONAL {{ ?{role}_key f:{k} ?{role}_{k} }}' for k in FIELDS if k != 'id')
        props.append(f'BIND(COALESCE(?{role}, <urn:factory-demo:unbound>) AS ?{role}_key) OPTIONAL {{ ?{role}_key f:id ?{role}_id; a ?{role}_kind . {fields} }}')
    query = f'PREFIX f: <{VOCAB}> SELECT * WHERE {{ GRAPH {iri} {{ {{ SELECT * WHERE {{ GRAPH {iri} {{ {match} }} }} ORDER BY {order} LIMIT {limit} }} ' + ' '.join(props) + f' }} }} ORDER BY {order}'
    return query, roles, columns, limit


def decode(bindings, version, roles, columns):
    rows = []
    for binding in bindings:
        row = {}
        for column in columns:
            value = binding.get(column)
            if column in roles:
                ident = binding.get(column + '_id')
                if value is None or ident is None:
                    row[column] = None
                    continue
                kind = binding.get(column + '_kind')
                if not isinstance(kind, URIRef) or not str(kind).startswith(str(VOCAB)) or str(kind)[len(str(VOCAB)):] not in KINDS:
                    raise ValueError('Unsupported RDF node type')
                props = {k: str(binding[column+'_'+k]) for k in FIELDS if binding.get(column+'_'+k) is not None}
                if value != subject(version, props['id']):
                    raise ValueError('RDF identity mismatch')
                props.update(kind=str(kind)[len(str(VOCAB)):], namespace=NAMESPACE, version=version, entity_id=props['id'])
                row[column] = props
            elif column == 'relation':
                if value is None:
                    row[column] = None
                else:
                    relation = str(value)[len(str(VOCAB)):]
                    if value != VOCAB[relation] or relation not in RELATIONS:
                        raise ValueError('Unexpected relation')
                    row[column] = relation
            else:
                row[column] = None if value is None else str(value)
        rows.append(row)
    return rows


class RDFTools:
    def verify_content(self, version):
        expected = project(version)
        query = f'SELECT ?s ?p ?o WHERE {{ GRAPH {graph_uri(version).n3()} {{ ?s ?p ?o }} }} LIMIT {len(expected)+1}'
        actual = RDFGraph()
        for row in self.select(query):
            actual.add((row['s'], row['p'], row['o']))
        if canonical_triples(actual) != canonical_triples(expected):
            raise RuntimeError('RDF graph differs from immutable source projection')
        return {'verified_before_query': True, 'triples': len(actual), 'source_sha256': snapshot(version)[1]}

    def run(self, version, tool, args):
        source, sha = snapshot(version)
        query, roles, columns, limit = templates(version, tool, args)
        integrity = self.verify_content(version)
        rows = decode(self.select(query), version, roles, columns)
        return {'tool': tool, 'arguments': args, 'snapshot': version, 'source_sha256': sha,
                'as_of': source['as_of'], 'query': query, 'rows': rows,
                'scope': 'selected query result in authored snapshot; not completeness proof',
                'integrity': integrity, 'limit_reached': len(rows) >= limit, 'backend': self.name}


class RDFLibGraph(RDFTools):
    name = 'rdflib_sparql'
    def __init__(self, versions=('factory-v1', 'factory-v2', 'factory-v3')):
        self.dataset = Dataset()
        for version in versions:
            target = self.dataset.graph(graph_uri(version))
            for triple in project(version): target.add(triple)
    def select(self, query):
        return [{str(k): v for k, v in row.asdict().items()} for row in self.dataset.query(query)]


class NeptuneGraph(RDFTools):
    """Explicit bounded authorization; never starts/stops/deletes AWS resources."""
    name = 'neptune_sparql'
    def __init__(self, authorization):
        self.authorization = Path(authorization)
        self._authorize()
        import boto3
        from botocore.config import Config
        self.session = boto3.Session(region_name=REGION)
        cfg = Config(connect_timeout=5, read_timeout=10, retries={'total_max_attempts': 1})
        if self.session.client('sts', config=cfg).get_caller_identity()['Account'] != ACCOUNT:
            raise RuntimeError('Wrong AWS account')

    def _authorize(self, write=False):
        a = json.loads(self.authorization.read_text())
        now = datetime.now(timezone.utc)
        if (a.get('account') != ACCOUNT or a.get('region') != REGION or a.get('cluster') != CLUSTER
            or a.get('endpoint') != ENDPOINT or a.get('approved') is not True
            or not 0 < a.get('cost_cap_usd', 0) <= 10
            or not datetime.fromisoformat(a['starts_at']) <= now < datetime.fromisoformat(a['deadline'])
            or (datetime.fromisoformat(a['deadline']) - datetime.fromisoformat(a['starts_at'])).total_seconds() > 4*3600
            or write and a.get('allow_persistent_import') is not True):
            raise RuntimeError('No valid bounded Neptune authorization')
        return a

    def request(self, query, update=False):
        self._authorize(write=update)
        from botocore.awsrequest import AWSRequest
        from botocore.auth import SigV4Auth
        body = urlencode({'update' if update else 'query': query}).encode()
        request = AWSRequest(method='POST', url=ENDPOINT, data=body,
                             headers={'Content-Type':'application/x-www-form-urlencoded', 'Accept':'application/sparql-results+json'})
        SigV4Auth(self.session.get_credentials().get_frozen_credentials(), 'neptune-db', REGION).add_auth(request)
        with httpx.Client(timeout=15, trust_env=False, follow_redirects=False) as client:
            response = client.post(ENDPOINT, content=body, headers=dict(request.headers))
        response.raise_for_status()
        return response.json() if not update else None

    def select(self, query):
        rows = []
        for result in self.request(query)['results']['bindings']:
            row = {}
            for k, v in result.items():
                if v['type'] == 'uri': row[k] = URIRef(v['value'])
                elif v['type'] in ('literal','typed-literal'):
                    row[k] = Literal(v['value'], lang=v.get('xml:lang'), datatype=v.get('datatype'))
                else: raise ValueError('Unexpected SPARQL binding type')
            rows.append(row)
        return rows

    def load(self, version):
        self._authorize(write=True)
        graph = graph_uri(version).n3()
        if self.select(f'SELECT ?s WHERE {{ GRAPH {graph} {{ ?s ?p ?o }} }} LIMIT 1'):
            return {'already_loaded': True, **self.verify_content(version)}
        # One INSERT, no destructive reset. Failure leaves state for explicit inspection.
        self.request(f'INSERT DATA {{ GRAPH {graph} {{\n{export(version)} }} }}', update=True)
        return {'already_loaded': False, **self.verify_content(version)}
