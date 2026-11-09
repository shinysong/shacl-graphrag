Only Neptune adapter shown. Existing fixed CUTOFF=2026-11-06T10:10:52Z; sourcebuild/jsoncanonical/digest and querynormalization bodies omitted, markunverified.
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

