Bounded follow-up after actual7node68triple transport parity passed. Source7legacy records4links, facts only7record types+4relations; source-derived IDs but annotation/dictionary types and hierarchy are authored schema modeling, NOT actual domain ontology.8controlled schema/projection variants,4querysets each, arms assertedablation,same-policyPython,externalRDFS(owlrl.RDFS_Semantics),staleinitialRDFS,Neo4j+sharedexternalclosure,Neptune+sameclosure,n10s nativeon-demand=224live plannedslots;128offline. Tests5methods; manual evaluator-only expected rootmember/sourceReference sets storedseparate neverreadruntime. NoLLM oraccuracy/engineperformance claims. Queryset equalityonly, notfullRDFSclosure. First-proof provenance explicitlyfirstonly; deletion testsrecompute fullclosure instead ofclaimingallprooftracking. Native classlookupnodesInCategory and subpropertygetRels relDir>; identicalschema mapping configured manually, not RDFimportbenchmark. No denseRAGnewresults.
Operational plan: fixedexistingNeptuneendpoint/account from reviewedbackend_parity.py, cutofforiginal10:10:52UTC; newqueriesblocked120searlier,cleanuptillcutoff. NoAWScreation, no newpaidcalls. TemporarylocalDockerneo4j:5.26-community cachedimage, name shacl-n10s-study-20261106, labelresearch-owner=backend-inference-20261106,127.0.0.1:7475/7688only,2CPUs2GB,heap512pagecache256,authnonebehindloopback,jar5.26.0 mountreadonly,allow/unrestrictedn10s.* only. ExistingGUIcontaineruntouched. Officialjar12877219bytesSHA256509bec192befce6224a7e3bf78a0e6b74aeb8bf61eb7a1e009b7b62e0737900b;Apache2license saved after initial404failure. Coordinator must refuseexistingnamedcontainer, inspectlabelbeforestop/removeownedcontainerandvolumes, installownedemergencydockerstop at10:10:52UTC, then removeownedtimer whenfinished. Beforelive freeze inputs/code/refs; run5tests/offline128slots first. Localquerytimeout30s; log startupstatus/pluginversions; SHOWPROCEDURES andsmallnativequery errorsretained, no silentfallback. Namespaceforeachvariant clearedafterarm, finalcount/ASKverified; iffailurestop andreportunresolved. Runtime receives schemas/facts/querycontracts only, noexpectedanswers. Readonlyreview noactualtests yet. Source code review below plus prior adapter excerpt by reference is not supplied, mark unverified rather than assume.

Revision2: failclosed oncleanup exception or nonzero/missing remaining; persist failedreceipt beforeabort, unexecutedslots remainplan. Native requests/variant launch haveexplicit cutoff120s earlier, cleanuporiginalcutoff.5unitmethods includefailureinjection andverifiedemptycleanup. Wider importedsource/lock/jar manifest will freeze beforecalls; containerresource/timer verification required beforelaunch.

FILE scripts/backend_inference.py
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

FILE tests/test_backend_inference.py
import unittest
from scripts.backend_inference import build_variants,external_closure,answer,QUERIES,term,ANN,TAB,ALT,ROOT,SC,TYPE
from scripts.run_ontology_reasoning_study import json_closure

class BackendInferenceTests(unittest.TestCase):
    def test_alternative_support_survives_one_deletion(self):
        facts=[(term('a'),TYPE,ANN)]
        schema=[(ANN,SC,TAB),(TAB,SC,ROOT),(ANN,SC,ALT),(ALT,SC,ROOT)]
        for removed,expected in [(set(),[term('a')]),({(ANN,SC,TAB)},[term('a')]),({(ANN,SC,TAB),(ANN,SC,ALT)},[])]:
            current=[x for x in schema if x not in removed]
            py,_=json_closure(current,facts)
            self.assertEqual(answer(py,QUERIES[0]),expected)
            self.assertEqual(answer(external_closure(facts,current),QUERIES[0]),expected)
    def test_cycle_and_unrelated_class(self):
        facts=[(term('a'),TYPE,ANN)];schema=[(ANN,SC,TAB),(TAB,SC,ANN),(TAB,SC,ROOT)]
        py,_=json_closure(schema,facts);rdf=external_closure(facts,schema)
        for result in [py,rdf]:
            self.assertEqual(answer(result,QUERIES[0]),[term('a')]);self.assertEqual(answer(result,QUERIES[1]),[])
    def test_fixture_metadata_separates_controlled_omission(self):
        source={'nodes':[{'node_id':'PP6:2','node_type':'annotation'}],'edges':[{'subject':'PP6:2','field':'defect','target':'PP6:defect_code:4'}]}
        variants=build_variants(source)
        self.assertEqual(len(variants),8);self.assertEqual(len({v['id'] for v in variants}),8)
        self.assertIn('not natural source absence',variants[-1]['change_basis'])
        self.assertEqual(len(variants[0]['facts'])-len(variants[-1]['facts']),1)

class CleanupBoundaryTests(unittest.TestCase):
    def test_cleanup_failure_aborts_remaining_plan(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import patch
        from scripts.backend_inference import run
        for receipt in [{'remaining':1},RuntimeError('cleanup failure')]:
            class Fake:
                def load(self,*a):pass
                def query(self,*a):return []
                def cleanup(self):
                    if isinstance(receipt,Exception):raise receipt
                    return receipt
            with tempfile.TemporaryDirectory() as td:
                p=Path(td);(p/'source.json').write_text('{"nodes":[],"edges":[]}')
                with patch('scripts.backend_inference.NeoStore',return_value=Fake()),patch('scripts.backend_inference.NeptuneStore') as neptune:
                    with self.assertRaisesRegex(RuntimeError,'unresolved cleanup'):run(p/'source.json',p/'out',True)
                    neptune.assert_not_called()
                rows=(p/'out/results.jsonl').read_text().splitlines()
                self.assertEqual(len(rows),20)
                self.assertEqual(len(json.loads((p/'out/plan.json').read_text())),224)
                self.assertEqual(json.loads((p/'out/cleanup.json').read_text())[0]['status'],'failed')
    def test_verified_empty_cleanup(self):
        from unittest.mock import Mock
        from scripts.backend_inference import verified_cleanup
        for value in [0,False]:
            store=Mock();store.cleanup.return_value={'remaining':value}
            self.assertEqual(verified_cleanup(store),{'remaining':value})

if __name__=='__main__':unittest.main()
