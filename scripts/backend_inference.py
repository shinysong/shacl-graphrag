"""Small authored RDFS hierarchy diagnostic on retained source record identifiers."""
from __future__ import annotations
import json
import datetime as dt
import time
import urllib.request
from pathlib import Path
from rdflib import Graph, RDF, RDFS, URIRef
from owlrl import DeductiveClosure, RDFS_Semantics
from scripts.backend_parity import canonical, digest, uri, NeoStore, NeptuneStore, RDFStore, CUTOFF
from scripts.run_ontology_reasoning_study import json_closure

TYPE=str(RDF.type); SC=str(RDFS.subClassOf); SP=str(RDFS.subPropertyOf)
def term(x):return str(URIRef(uri(x)[1:-1]))
ANN=term('annotationRecord');DICT=term('dictionaryRecord');TAB=term('TabularRecord');ALT=term('AlternateRecord');ROOT=term('EvidenceRecord');UNRELATED=term('UnrelatedRecord')
DEF=term('relation:defect');WELD=term('relation:welding_setting');REF=term('sourceReference')
CLASSES=[ANN,DICT,TAB,ALT,ROOT,UNRELATED]
RELATION_NAMES={DEF:'DEFECT',WELD:'WELDING',REF:'SOURCE_REFERENCE'}

def build_variants(source):
    facts={(term(n['node_id']),TYPE,term(n['node_type']+'Record')) for n in source['nodes']}
    facts|={(term(e['subject']),term('relation:'+e['field']),term(e['target'])) for e in source['edges']}
    base={(ANN,SC,TAB),(DICT,SC,TAB),(TAB,SC,ROOT),(DEF,SP,REF),(WELD,SP,REF)}
    dual=base|{(ANN,SC,ALT),(ALT,SC,ROOT)}
    schema_variants=[('base',base),('two_supports',dual),('remove_primary',dual-{(ANN,SC,TAB)}),('remove_both_annotation_supports',dual-{(ANN,SC,TAB),(ANN,SC,ALT)}),('missing_schema',set()),('cycle',base|{(TAB,SC,ANN)}),('reverse_schema',{(b,p,a) for a,p,b in base})]
    variants=[{'id':name,'facts':sorted(facts),'schema':sorted(schema),'change_basis':'authored schema intervention, not observed source defect'} for name,schema in schema_variants]
    variants.append({'id':'remove_source_edge','facts':sorted(facts-{(term('PP6:2'),DEF,term('PP6:defect_code:4'))}),'schema':sorted(base),'change_basis':'controlled removal from selected projection, not natural source absence'})
    return variants

QUERIES=[{'id':'I1_superclass','kind':'type','target':ROOT},{'id':'I1_unrelated','kind':'type','target':UNRELATED},{'id':'I2_forward','kind':'relation','start':term('PP6:2'),'target':REF},{'id':'I2_reverse','kind':'relation','start':term('PP6:defect_code:4'),'target':REF}]

def answer(triples,q):
    return sorted({s for s,p,o in triples if p==TYPE and o==q['target']}) if q['kind']=='type' else sorted({o for s,p,o in triples if s==q['start'] and p==q['target']})

def external_closure(facts,schema):
    g=Graph()
    for triple in facts+schema:g.add(tuple(URIRef(x) for x in triple))
    DeductiveClosure(RDFS_Semantics,axiomatic_triples=False,datatype_axioms=False).expand(g)
    return sorted(tuple(str(x) for x in t) for t in g if all(isinstance(x,URIRef) for x in t))

def query_store(store,q):
    patterns=[['?x',URIRef(TYPE).n3(),URIRef(q['target']).n3()]] if q['kind']=='type' else [[URIRef(q['start']).n3(),URIRef(q['target']).n3(),'?x']]
    rows=store.query(patterns,['?x'])
    return sorted({r['?x'][1:-1] for r in rows})

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

def run(source_path,output,live=False):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    source=json.loads(Path(source_path).read_text());variants=build_variants(source)
    (out/'source.json').write_text(canonical(source)+'\n');(out/'variants.json').write_text(canonical(variants)+'\n');(out/'queries.json').write_text(canonical(QUERIES)+'\n');(out/'runtime.py').write_bytes(Path(__file__).read_bytes())
    arms=['asserted','python_rules','external_rdfs','stale_base_rdfs']+(['neo4j_shared_closure','neptune_shared_closure','n10s_native'] if live else [])
    plan=[{'variant':v['id'],'arm':arm,'query_id':q['id'],'status':'planned'} for v in variants for arm in arms for q in QUERIES]
    (out/'plan.json').write_text(canonical(plan)+'\n');cleanup=[]
    stale=external_closure(variants[0]['facts'],variants[0]['schema'])
    with (out/'results.jsonl').open('a') as handle:
        for v in variants:
            if live and dt.datetime.now(dt.timezone.utc) >= CUTOFF-dt.timedelta(seconds=120):
                raise RuntimeError('live launch cutoff; remaining plan retained')
            # Same declared semantics; query results only, not full closure equality.
            start=time.perf_counter();python,proofs=json_closure(v['schema'],v['facts']);python_ms=(time.perf_counter()-start)*1000
            start=time.perf_counter();rdf=external_closure(v['facts'],v['schema']);rdf_ms=(time.perf_counter()-start)*1000
            (out/(v['id']+'-closure.json')).write_text(canonical({'python':sorted(python),'rdfs':rdf,'python_first_derivation_only':{canonical(k):x for k,x in proofs.items()},'python_ms':python_ms,'external_rdfs_ms':rdf_ms})+'\n')
            for arm in arms:
                store=None;load_error=None;load_ms=None
                try:
                    start=time.perf_counter()
                    try:
                        namespace='backend-'+out.name+'-'+v['id'].replace('_','-')
                        if arm=='neo4j_shared_closure':store=NeoStore(namespace)
                        elif arm=='neptune_shared_closure':store=NeptuneStore(namespace)
                        elif arm=='n10s_native':store=NativeN10s(namespace)
                        if store:
                            store.load(v if arm=='n10s_native' else [tuple(URIRef(x).n3() for x in t) for t in rdf])
                        load_ms=(time.perf_counter()-start)*1000
                    except Exception as exc:load_error=type(exc).__name__+': '+str(exc)
                    for q in QUERIES:
                        row={'variant':v['id'],'arm':arm,'query_id':q['id'],'input_hash':digest(v),'load_ms_shared':load_ms}
                        start=time.perf_counter()
                        try:
                            if load_error:raise RuntimeError(load_error)
                            if arm=='n10s_native':result=store.query(q)
                            elif store:result=query_store(store,q)
                            else:result=answer({'asserted':v['facts'],'python_rules':python,'external_rdfs':rdf,'stale_base_rdfs':stale}[arm],q)
                            row.update(status='completed',answer=result)
                        except Exception as exc:row.update(status='dependency_not_run' if load_error else 'query_failure',error=type(exc).__name__+': '+str(exc))
                        row['query_ms']=(time.perf_counter()-start)*1000;handle.write(canonical(row)+'\n');handle.flush()
                finally:
                    cleanup_error=None
                    if store:
                        try:cleanup.append({'variant':v['id'],'arm':arm,'status':'completed','receipt':verified_cleanup(store)})
                        except Exception as exc:
                            cleanup_error=exc
                            cleanup.append({'variant':v['id'],'arm':arm,'status':'failed','error':str(exc)})
                    (out/'cleanup.json').write_text(canonical(cleanup)+'\n')
                    if cleanup_error: raise RuntimeError('Stop after unresolved cleanup') from cleanup_error
    return plan

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--live',action='store_true');a=p.parse_args();run(a.source,a.output,a.live)
