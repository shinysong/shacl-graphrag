"""Bounded basic-graph-pattern transport comparison. No gold or LLM client."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote
import urllib.request
from rdflib import Graph, Literal, URIRef, RDF
from rdflib.util import from_n3

BASE = 'urn:shacl-study:backend:'
CUTOFF = dt.datetime.fromisoformat('2026-11-07T16:30:00+00:00')
ENDPOINT = 'https://shacl-graphrag-research.cluster-cj60oo44gibs.ap-northeast-2.neptune.amazonaws.com:8182/sparql'

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()

def uri(x):
    return URIRef(BASE + quote(x, safe='')).n3()

def val(x):
    return Literal(canonical(x)).n3()

def field(x):
    return uri('field:' + x)

def variable(x):
    return isinstance(x, str) and re.fullmatch(r'\?[a-z][a-z0-9_]*', x) is not None

def check_pattern(patterns, project):
    if not 1 <= len(patterns) <= 12 or not project:
        raise ValueError('bounded nonempty patterns/project required')
    bound = set()
    for triple in patterns:
        if len(triple) != 3:
            raise ValueError('triple arity')
        for i, x in enumerate(triple):
            if variable(x):
                bound.add(x)
            else:
                term = from_n3(x)
                if not isinstance(term, (URIRef, Literal)) or (i < 2 and not isinstance(term, URIRef)) or term.n3() != x:
                    raise ValueError('only canonical URI/literal constants')
    if len(project) != len(set(project)) or not set(project) <= bound:
        raise ValueError('unbound/duplicate projection')

def triples_from_source(source):
    triples = set()
    for n in source['nodes']:
        s, raw = uri(n['node_id']), n['source']
        triples.add((s, RDF.type.n3(), uri(n['node_type'] + 'Record')))
        triples.add((s, field('payload'), val(raw)))
        triples.add((s, field('coupon'), val(raw['coupon'])))
        triples.add((s, field('source_sha256'), val(raw['sha256'])))
        if isinstance(raw['values'], dict):
            fields = raw['values']
        else:
            headers = {}
            for row in raw['header_rows']:
                for c in row['cells']:
                    if c['value'] is not None:
                        headers[re.sub(r'\d+$', '', c['cell'])] = c['value']
            fields = {str(headers[re.sub(r'\d+$', '', c['cell'])]): c['value'] for c in raw['cells']}
        for key, value in fields.items():
            triples.add((s, field(key), val(value)))
    for e in source['edges']:
        triples.add((uri(e['subject']), uri('relation:' + e['field']), uri(e['target'])))
    return sorted(triples)

def normalized(rows, project):
    result = []
    for row in rows:
        if set(row) != set(project):
            raise ValueError('result variables differ')
        result.append({v: row[v] for v in project})
    return sorted({canonical(r): r for r in result}.values(), key=canonical)

class SQLStore:
    name = 'sqlite_python'
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE triples(s TEXT,p TEXT,o TEXT,PRIMARY KEY(s,p,o))')
    def load(self, triples):
        self.db.executemany('INSERT INTO triples VALUES(?,?,?)', triples)
    def query(self, patterns, project):
        check_pattern(patterns, project)
        refs, where, args = {}, [], []
        for i, triple in enumerate(patterns):
            for col, term in zip(('s','p','o'), triple, strict=True):
                ref = f't{i}.{col}'
                if variable(term):
                    if term in refs:
                        where.append(f'{ref}={refs[term]}')
                    else:
                        refs[term] = ref
                else:
                    where.append(f'{ref}=?'); args.append(term)
        query = 'SELECT DISTINCT '+','.join(refs[v] for v in project)+' FROM '+','.join(f'triples t{i}' for i in range(len(patterns)))
        if where:
            query += ' WHERE '+' AND '.join(where)
        return normalized([dict(zip(project,r,strict=True)) for r in self.db.execute(query,args)],project)
    def cleanup(self):
        self.db.close()

class RDFStore:
    name = 'rdflib_offline'
    def __init__(self):
        self.graph = Graph()
    def load(self, triples):
        for s,p,o in triples:
            self.graph.add((from_n3(s),from_n3(p),from_n3(o)))
    def query(self, patterns, project):
        check_pattern(patterns,project)
        query = 'SELECT DISTINCT '+' '.join(project)+' WHERE {'+' . '.join(' '.join(t) for t in patterns)+'}'
        return normalized([{v:r[i].n3() for i,v in enumerate(project)} for r in self.graph.query(query)],project)
    def cleanup(self):
        self.graph.close()

class NeoStore:
    name = 'neo4j_cypher'
    def __init__(self, namespace):
        if not re.fullmatch(r'backend-[a-z0-9-]{1,60}',namespace):
            raise ValueError('owned namespace required')
        self.namespace=namespace
        self.owned=False
    def request(self, query, params=None):
        data={'statements':[{'statement':query,'parameters':{'run':self.namespace,**(params or {})}}]}
        req=urllib.request.Request('http://127.0.0.1:7474/db/neo4j/tx/commit',canonical(data).encode(),{'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response:
            body=json.load(response)
        if body.get('errors'):
            raise RuntimeError(canonical(body['errors']))
        r=body['results'][0]
        return [dict(zip(r['columns'],x['row'],strict=True)) for x in r['data']]
    def load(self, triples):
        if self.request('MATCH (n:BackendTerm {run:$run}) RETURN count(n) AS count')[0]['count']:
            raise ValueError('nonempty namespace')
        self.owned=True
        self.request('UNWIND $terms AS term CREATE (:BackendTerm {run:$run,key:term})',{'terms':sorted({x for s,p,o in triples for x in (s,o)})})
        self.request('UNWIND $triples AS t MATCH (s:BackendTerm {run:$run,key:t[0]}),(o:BackendTerm {run:$run,key:t[2]}) CREATE (s)-[:BACKEND_TRIPLE {run:$run,p:t[1]}]->(o)',{'triples':triples})
    def query(self, patterns, project):
        check_pattern(patterns,project)
        refs,where,params,matches={},[],{},[]
        for i,triple in enumerate(patterns):
            matches.append(f'(s{i}:BackendTerm {{run:$run}})-[r{i}:BACKEND_TRIPLE {{run:$run}}]->(o{i}:BackendTerm {{run:$run}})')
            for j,(ref,term) in enumerate(zip((f's{i}.key',f'r{i}.p',f'o{i}.key'),triple,strict=True)):
                if variable(term):
                    if term in refs:
                        where.append(ref+'='+refs[term])
                    else:
                        refs[term]=ref
                else:
                    key=f'k{i}_{j}';params[key]=term;where.append(ref+'=$'+key)
        query=' '.join('MATCH '+match for match in matches)
        if where: query+=' WHERE '+' AND '.join(where)
        query+=' RETURN DISTINCT '+','.join(refs[v]+' AS '+v[1:] for v in project)
        return normalized([{'?'+k:v for k,v in r.items()} for r in self.request(query,params)],project)
    def cleanup(self):
        if not self.owned: return {'namespace_not_owned':True}
        self.request('MATCH (n:BackendTerm {run:$run}) DETACH DELETE n')
        return self.request('MATCH (n:BackendTerm {run:$run}) RETURN count(n) AS remaining')[0]

class NeptuneStore:
    name = 'neptune_sparql'
    def __init__(self, namespace):
        if not re.fullmatch(r'backend-[a-z0-9-]{1,60}',namespace):
            raise ValueError('owned namespace required')
        import boto3
        self.session=boto3.Session(region_name='ap-northeast-2')
        account=self.session.client('sts').get_caller_identity()['Account']
        if account != '985658740608': raise ValueError('wrong account')
        self.graph=uri('graph:'+namespace)
        self.owned=False
    def request(self, query, update=False, cleanup=False):
        if dt.datetime.now(dt.timezone.utc) >= CUTOFF-dt.timedelta(seconds=0 if cleanup else 120):
            raise RuntimeError('Neptune operational cutoff; no extension')
        from botocore.awsrequest import AWSRequest
        from botocore.auth import SigV4Auth
        from urllib.parse import urlencode
        body=urlencode({'update' if update else 'query':query}).encode()
        request=AWSRequest(method='POST',url=ENDPOINT,data=body,headers={'Content-Type':'application/x-www-form-urlencoded','Accept':'application/sparql-results+json'})
        SigV4Auth(self.session.get_credentials().get_frozen_credentials(),'neptune-db','ap-northeast-2').add_auth(request)
        req=urllib.request.Request(ENDPOINT,body,dict(request.headers))
        with urllib.request.urlopen(req,timeout=30) as response:
            raw=response.read()
        return json.loads(raw) if raw else {}
    def load(self, triples):
        if self.request(f'ASK {{GRAPH {self.graph} {{?s ?p ?o}}}}')['boolean']:
            raise ValueError('nonempty graph')
        self.owned=True
        data=' .\n'.join(' '.join(t) for t in triples)+' .'
        self.request(f'INSERT DATA {{GRAPH {self.graph} {{{data}}}}}',update=True)
    def query(self, patterns, project):
        check_pattern(patterns,project)
        query='SELECT DISTINCT '+' '.join(project)+f' WHERE {{GRAPH {self.graph} {{'+' . '.join(' '.join(t) for t in patterns)+'}}'
        result=self.request(query)
        rows=[]
        for binding in result['results']['bindings']:
            row={}
            for v in project:
                b=binding[v[1:]]
                if b['type']=='uri': term=URIRef(b['value'])
                elif b['type'] in ('literal','typed-literal'):
                    dtype=b.get('datatype')
                    # RDF 1.1 plain strings and xsd:string are equivalent here.
                    if dtype=='http://www.w3.org/2001/XMLSchema#string':dtype=None
                    term=Literal(b['value'],lang=b.get('xml:lang'),datatype=dtype)
                else:raise ValueError('unexpected result term kind')
                row[v]=term.n3()
            rows.append(row)
        return normalized(rows,project)
    def cleanup(self):
        if not self.owned: return {'namespace_not_owned':True}
        self.request(f'CLEAR GRAPH {self.graph}',update=True,cleanup=True)
        return {'remaining':self.request(f'ASK {{GRAPH {self.graph} {{?s ?p ?o}}}}',cleanup=True)['boolean']}

def execute(source_path, contracts_path, output, live=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    source=json.loads(Path(source_path).read_text());contracts=json.loads(Path(contracts_path).read_text())
    (output/'source.json').write_text(canonical(source)+'\n')
    (output/'contracts.json').write_text(canonical(contracts)+'\n')
    (output/'runtime.py').write_bytes(Path(__file__).read_bytes())
    triples=triples_from_source(source)
    (output/'triples.json').write_text(canonical(triples)+'\n')
    # Runtime never reads evaluator reference files.
    names=['sqlite_python','rdflib_offline']+(['neo4j_cypher','neptune_sparql'] if live else [])
    plan=[{'backend':name,'case_id':q['id'],'status':'planned'} for name in names for q in contracts]
    (output/'plan.json').write_text(canonical(plan)+'\n')
    namespace='backend-'+output.name
    constructors=[SQLStore,RDFStore]+([lambda:NeoStore(namespace),lambda:NeptuneStore(namespace)] if live else [])
    cleanup=[]
    with (output/'results.jsonl').open('a') as results:
        for name,constructor in zip(names,constructors,strict=True):
            try:
                store=None;load_error=None;t=time.perf_counter()
                try:
                    store=constructor();store.load(triples)
                except Exception as exc:
                    load_error=type(exc).__name__+': '+str(exc)
                load_ms=(time.perf_counter()-t)*1000
                for q in contracts:
                    row={'backend':name,'case_id':q['id'],'question_type':q['question_type'],'scope':q['scope'],'source_hash':digest(source),'contract_hash':digest(q),'load_ms_shared':load_ms}
                    t=time.perf_counter()
                    try:
                        if load_error: raise RuntimeError(load_error)
                        if q.get('unsupported'):
                            row.update(status='unsupported',reason=q['unsupported'])
                        else:
                            bindings=store.query(q['patterns'],q['project'])
                            row.update(status='completed',bindings=bindings,binding_sha256=digest(bindings))
                    except Exception as exc:
                        row.update(status='dependency_not_run' if load_error else 'query_failure',error=type(exc).__name__+': '+str(exc))
                    row['elapsed_ms']=(time.perf_counter()-t)*1000
                    results.write(canonical(row)+'\n');results.flush()
            finally:
                if store:
                    try:cleanup.append({'backend':name,'status':'completed','receipt':store.cleanup()})
                    except Exception as exc:cleanup.append({'backend':name,'status':'failed','error':str(exc)})
                else:cleanup.append({'backend':name,'status':'not_constructed','error':load_error})
                (output/'cleanup.json').write_text(canonical(cleanup)+'\n')
    (output/'cleanup.json').write_text(canonical(cleanup)+'\n')
    return plan

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--contracts',required=True);p.add_argument('--output',required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
    execute(a.source,a.contracts,a.output,a.live)
