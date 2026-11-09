Only adapter/cleanup shown. Other imported routines were independently reviewed in completed priorjob; their full bodies omitted here and must be marked unverified in this review.
class NativeN10s:
    def __init__(self,namespace):self.namespace=namespace;self.owned=False
    def request(self,query,params=None,cleanup=False):
        if dt.datetime.now(dt.timezone.utc) >= CUTOFF-dt.timedelta(seconds=0 if cleanup else 120):
            raise RuntimeError("live experiment cutoff")
        data={'statements':[{'statement':query,'parameters':{'run':self.namespace,**(params or {})}}]}
        req=urllib.request.Request('http://127.0.0.1:7475/db/neo4j/tx/commit',canonical(data).encode(),{'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as r:body=json.load(r)
        if body.get('errors'):raise RuntimeError(canonical(body['errors']))
        r=body['results'][0];return [dict(zip(r['columns'],x['row'],strict=True)) for x in r['data']]
    def load(self,variant):
        if self.request('MATCH (n:InferenceOwned {run:$run}) RETURN count(n) AS count')[0]['count']:raise ValueError('nonempty namespace')
        self.owned=True
        self.request('UNWIND $classes AS c CREATE (:InferenceOwned:InferenceClass {run:$run,id:c})',{'classes':CLASSES})
        entities=sorted({s for s,p,o in variant['facts'] if p==TYPE})
        self.request('UNWIND $ids AS id CREATE (:InferenceOwned:InferenceRecord {run:$run,id:id})',{'ids':entities})
        self.request('UNWIND $names AS name CREATE (:InferenceOwned:InferenceProperty {run:$run,name:name})',{'names':list(RELATION_NAMES.values())})
        for s,p,o in variant['facts']:
            if p==TYPE:
                self.request('MATCH (s:InferenceRecord {run:$run,id:$s}),(o:InferenceClass {run:$run,id:$o}) CREATE (s)-[:INSTANCE_OF]->(o)',{'s':s,'o':o})
            else:
                rel=RELATION_NAMES[p]
                self.request(f'MATCH (s:InferenceRecord {{run:$run,id:$s}}),(o:InferenceRecord {{run:$run,id:$o}}) CREATE (s)-[:{rel}]->(o)',{'s':s,'o':o})
        for s,p,o in variant['schema']:
            if p==SC:
                self.request('MATCH (s:InferenceClass {run:$run,id:$s}),(o:InferenceClass {run:$run,id:$o}) CREATE (s)-[:SUBCLASS]->(o)',{'s':s,'o':o})
            elif p==SP:
                self.request('MATCH (s:InferenceProperty {run:$run,name:$s}),(o:InferenceProperty {run:$run,name:$o}) CREATE (s)-[:SUBPROPERTY]->(o)',{'s':RELATION_NAMES[s],'o':RELATION_NAMES[o]})
    def query(self,q):
        if q['kind']=='type':
            rows=self.request('MATCH (c:InferenceClass {run:$run,id:$target}) CALL n10s.inference.nodesInCategory(c,{inCatRel:"INSTANCE_OF",subCatRel:"SUBCLASS"}) YIELD node WHERE node.run=$run RETURN DISTINCT node.id AS id',{'target':q['target']})
        else:
            rows=self.request('MATCH (s:InferenceRecord {run:$run,id:$start}) CALL n10s.inference.getRels(s,$target,{relDir:">",relLabel:"InferenceProperty",relNameProp:"name",subRelRel:"SUBPROPERTY"}) YIELD rel,node WHERE node.run=$run RETURN DISTINCT node.id AS id',{'start':q['start'],'target':RELATION_NAMES[q['target']]})
        return sorted({r['id'] for r in rows})
    def cleanup(self):
        if not self.owned:return {'namespace_not_owned':True}
        self.request('MATCH (n:InferenceOwned {run:$run}) DETACH DELETE n',cleanup=True)
        return self.request('MATCH (n:InferenceOwned {run:$run}) RETURN count(n) AS remaining',cleanup=True)[0]

def verified_cleanup(store):
    receipt=store.cleanup()
    if not isinstance(receipt,dict) or 'remaining' not in receipt or receipt['remaining'] not in (0,False):
        raise RuntimeError('Cleanup not verified empty: '+repr(receipt))
    return receipt

