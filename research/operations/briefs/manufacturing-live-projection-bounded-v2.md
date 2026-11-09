# Bounded live manufacturing projection
User authorized8hcontinuation, manufacturing main and existing DBs on/off ifneeded. Existing Neptune only account985658740608 regionap-northeast-2 cluster shacl-graphrag-research, no create, same existing localNeo4j ownedcontainer. New resource stop immutable2026-11-07T16:30:00Z, researchwindowends23:12:55Z. No new paidLLM calls. Source7nodes4edges unchanged, queries9 (Q7unsupported);4backends36planned slots, retainall failures. New output namespace backend-manufacturing-v2-20261107-001. Readiness errors preserved DescribeDBClustersAccessDenied, localhostNeo4jrefused. Startonlyafter installverifyactive ownedtimer and independently review. STS accountcheck, containerownercheck. Fixedstop service retries60s, EC2failurecanpreventstop; no guaranteedbillingclaim. Stopafterexecutioninfinally and timer remains until explicitAPIstoppedconfirmation. Do not overwrite old runtime, guards, data. Copied runtime differs onlydeadline. Payloadonlyqueries previouslyoffline16/18completed2unsupported withpairparity. Independent reviewers must flag omittedsource fidelity unverified. New livechecks backend equality only, not QA orDBspeed. Five mockedcontrolchecks andsystemdunitverification passed; noactualresourcecalls yet.

Packet shortened after ContextLimit; previous attempts preserved. Omitted SQL/RDF/Neo compilers/source/queries are previously reviewed but independently unverified here. Runtime change only CUTOFF to2026-11-07T16:30:00+00:00. Headers/endpoints same fixed ownedcluster; runtime namespace prefixvalidated. Main verifies frozenfiles and old/newdiff beforelaunch.
```python
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


```

Revision: independent AWS/local stop branches; failures recorded together and timer retries. Tests clock fixed; six mocked cases including AWSfailure/localfailure. Original blocked job retained.
