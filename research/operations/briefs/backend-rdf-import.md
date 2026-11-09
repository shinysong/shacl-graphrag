# Bounded RDF import and native query bridge
Six cases: same real-source68triples with two profiles; authored6triples language/multivalue/customdatatype withtwo profiles; authored hierarchybase16triples andmissing-schema11triples withpreserveprofile. AllprofilesKEEP vocabulary/NODES types; defaultlike OVERWRITE+langfalse+customfalse vs ARRAY+langtrue+customtrue. Not literaldefaultconfig, not optimizedbaseline. Sourcevalues encodedJSONstrings, notnativeRDFnumerictypes. n10simport.inline andexport.spo; actualNeptune roundtrip sameinputs. 12roundtrip slots +8n10shierarchy queryslots =20planned. Exacttermsets normalizedRDF1.1 xsdstring/plainstring; noarbitraryRDFinvertibility/blanknodes/RDFstar/performance/QAclaim. Authoredfixture separate,notrealexternaltruth. Legacy hierarchyref consumespreviousmanualreference, neverreadruntime. Sourceandcapability pinned n10s5.26.0 onNeo4j5.26.32; same dedicated ownedtemporarycontainer7475, ownerlabel backend-inference-20261106. ExclusivelyemptyDB andnoconstraintsrequired beforeglobalgraphconfigcreation. Resource cleanup global ONLY inside verifiedownedemptydedicated DB, noGUI7474changes. DROP exactownedconstraint. Eachcasefinallycleanupverifiednodes0; onfailureabortkeepplan/rawreceipt/errors. Allnewrequestsstop10:08:52UTC cleanup10:10:52UTC viaimportedNativeN10s/NeptuneStore. NoAWSnewresources,restart,paidLLM,push. Read-onlyreview packet imports alreadyreviewed adapters omitted, markunverified. Freeze widerimports/scorer/refs beforelive. Twoofflinecodecunittests planned; noofflinefaken10ssuccess. Officialdocs https://neo4j.com/labs/neosemantics/5.14/reference/ support config names; actual5.26procedure signatures savedprivately, versiondifference acknowledged. Exportorimportfailures measured, noadaptive silentfix/retry. Properties/classes arefullIRIs and explicitinferenceconfig perquery. No gold runtime. Sourcecase payloads are within samepreviouslyauthorized publicdatascope.

FILE scripts/backend_rdf_import.py
"""n10s RDF import/export and native hierarchy probes on an exclusively owned DB."""
import json,subprocess
from pathlib import Path
from rdflib import URIRef,Literal,RDF,XSD
from scripts.backend_parity import canonical,triples_from_source,NeptuneStore
from scripts.backend_inference import NativeN10s,build_variants,QUERIES,TYPE,SC,SP,verified_cleanup

CONTAINER='shacl-n10s-study-20261106'
OWNER='backend-inference-20261106'
CONFIG_BASE={'handleVocabUris':'KEEP','handleRDFTypes':'NODES','handleMultival':'OVERWRITE','keepLangTag':False,'keepCustomDataTypes':False}
CONFIG_KEEP={**CONFIG_BASE,'handleMultival':'ARRAY','keepLangTag':True,'keepCustomDataTypes':True}

def cases(source):
    s='<urn:shacl-study:import:record>'
    authored=[(s,RDF.type.n3(),'<urn:shacl-study:import:Record>'),(s,'<urn:shacl-study:import:label>',Literal('Name',lang='en').n3()),(s,'<urn:shacl-study:import:label>',Literal('이름',lang='ko').n3()),(s,'<urn:shacl-study:import:alias>',Literal('Alpha').n3()),(s,'<urn:shacl-study:import:alias>',Literal('Beta').n3()),(s,'<urn:shacl-study:import:grade>',Literal('M42',datatype=URIRef('urn:shacl-study:import:Grade')).n3())]
    result=[]
    for name,triples,scope in [('source',triples_from_source(source),'same retained real source projection; literals are JSON strings, not native numeric types'),('authored',authored,'authored language/multivalue/customdatatype diagnostic, not real-domain evidence')]:
        for profile,config in [('defaultlike',CONFIG_BASE),('preserve',CONFIG_KEEP)]:
            result.append({'id':name+'-'+profile,'triples':sorted(triples),'config':config,'scope':scope,'queries':[]})
    variants={v['id']:v for v in build_variants(source)}
    for name in ['base','missing_schema']:
        v=variants[name];result.append({'id':'hierarchy-'+name.replace('_','-'),'triples':sorted(tuple(URIRef(x).n3() for x in t) for t in v['facts']+v['schema']),'config':CONFIG_KEEP,'scope':'authored same hierarchy imported as RDF, not manual LPG mapping','queries':QUERIES})
    return result


def export_terms(rows):
    triples=set()
    for row in rows:
        if row.get('subjectSPO'):raise ValueError('RDF-star not in scope')
        if row['isLiteral']:
            dtype=row.get('literalType');lang=row.get('literalLang') or None
            if dtype==str(XSD.string) or lang:dtype=None
            obj=Literal(row['object'],lang=lang,datatype=URIRef(dtype) if dtype else None).n3()
        else:obj=URIRef(row['object']).n3()
        triples.add((URIRef(row['subject']).n3(),URIRef(row['predicate']).n3(),obj))
    return sorted(triples)


def imported_query(client,q):
    if q['kind']=='type':
        result=client.request('MATCH (c:Resource {uri:$target}) CALL n10s.inference.nodesInCategory(c,{inCatRel:$inCat,subCatRel:$subCat}) YIELD node RETURN DISTINCT node.uri AS id',{'target':q['target'],'inCat':TYPE,'subCat':SC})
    else:
        result=client.request('MATCH (s:Resource {uri:$start}) CALL n10s.inference.getRels(s,$target,{relDir:">",relLabel:"Resource",relNameProp:"uri",subRelRel:$subRel}) YIELD rel,node RETURN DISTINCT node.uri AS id',{'start':q['start'],'target':q['target'],'subRel':SP})
    return sorted({r['id'] for r in result})


def run(source_path,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False);source=json.loads(Path(source_path).read_text());inputs=cases(source)
    plan=[{'case':c['id'],'operation':op} for c in inputs for op in ['n10s_roundtrip','neptune_roundtrip']+[q['id'] for q in c['queries']]]
    for f,obj in [('source.json',source),('cases.json',inputs),('plan.json',plan)]: (out/f).write_text(canonical(obj)+'\n')
    (out/'runtime.py').write_bytes(Path(__file__).read_bytes())
    raw=json.loads(subprocess.check_output(['docker','inspect',CONTAINER]))[0]
    assert raw['Config']['Labels'].get('research-owner')==OWNER and raw['State']['Running']
    assert raw['HostConfig']['PortBindings']['7474/tcp']==[{'HostIp':'127.0.0.1','HostPort':'7475'}]
    client=NativeN10s('import-capability');owned=False;cleanup=[]
    def emit(row):
        with (out/'results.jsonl').open('a') as h:h.write(canonical(row)+'\n');h.flush()
    try:
        count=client.request('MATCH (n) RETURN count(n) AS count')[0]['count']
        constraints=client.request('SHOW CONSTRAINTS YIELD name RETURN name')
        (out/'preflight.json').write_text(canonical({'empty_count':count,'constraints':constraints,'owner':OWNER,'container':CONTAINER})+'\n')
        if count or constraints:raise RuntimeError('exclusive empty DB required')
        owned=True
        client.request('CREATE CONSTRAINT backend_n10s_import_unique FOR (r:Resource) REQUIRE r.uri IS UNIQUE')
        for case in inputs:
            neptune=None;case_owned=False
            try:
                case_owned=True
                config=client.request('CALL n10s.graphconfig.init($config)',{'config':case['config']})
                (out/(case['id']+'-config.json')).write_text(canonical(config)+'\n')
                rdf=' .\n'.join(' '.join(t) for t in case['triples'])+' .\n'
                (out/(case['id']+'.nt')).write_text(rdf)
                loaded=client.request('CALL n10s.rdf.import.inline($rdf,"N-Triples",{})',{'rdf':rdf})
                (out/(case['id']+'-load.json')).write_text(canonical(loaded)+'\n')
                if len(loaded)!=1 or loaded[0]['terminationStatus']!='OK':raise RuntimeError('import did not report OK')
                try:
                    rawexport=client.request('CALL n10s.rdf.export.spo(null,null,null)')
                    (out/(case['id']+'-export.json')).write_text(canonical(rawexport)+'\n')
                    emit({'case':case['id'],'operation':'n10s_roundtrip','status':'completed','triples':export_terms(rawexport)})
                except Exception as exc:emit({'case':case['id'],'operation':'n10s_roundtrip','status':'failed','error':str(exc)})
                for q in case['queries']:
                    try:emit({'case':case['id'],'operation':q['id'],'status':'completed','answer':imported_query(client,q)})
                    except Exception as exc:emit({'case':case['id'],'operation':q['id'],'status':'failed','error':str(exc)})
                neptune=NeptuneStore('backend-'+out.name+'-'+case['id']);neptune.load(case['triples'])
                try:
                    rows=neptune.query([['?s','?p','?o']],['?s','?p','?o'])
                    emit({'case':case['id'],'operation':'neptune_roundtrip','status':'completed','triples':sorted({tuple(r[k] for k in ('?s','?p','?o')) for r in rows})})
                except Exception as exc:emit({'case':case['id'],'operation':'neptune_roundtrip','status':'failed','error':str(exc)})
            finally:
                errors=[]
                if neptune:
                    try:cleanup.append({'case':case['id'],'store':'neptune','receipt':verified_cleanup(neptune)})
                    except Exception as exc:errors.append(str(exc));cleanup.append({'case':case['id'],'store':'neptune','error':str(exc)})
                if case_owned:
                    try:
                        client.request('MATCH (n:Resource) DETACH DELETE n',cleanup=True)
                        client.request('CALL n10s.graphconfig.drop()',cleanup=True)
                        remaining=client.request('MATCH (n) RETURN count(n) AS count',cleanup=True)[0]['count']
                        cleanup.append({'case':case['id'],'store':'n10s','remaining':remaining})
                        if remaining:errors.append('nonempty after cleanup')
                    except Exception as exc:errors.append(str(exc));cleanup.append({'case':case['id'],'store':'n10s','error':str(exc)})
                (out/'cleanup.json').write_text(canonical(cleanup)+'\n')
                if errors:raise RuntimeError('cleanup failed; no continuation: '+repr(errors))
    except Exception as exc:
        (out/'failure.json').write_text(canonical({'error':type(exc).__name__+': '+str(exc)})+'\n');raise
    finally:
        if owned:
            client.request('DROP CONSTRAINT backend_n10s_import_unique IF EXISTS',cleanup=True)
            final={'nodes':client.request('MATCH (n) RETURN count(n) AS count',cleanup=True),'constraints':client.request('SHOW CONSTRAINTS YIELD name RETURN name',cleanup=True)}
            (out/'final-cleanup.json').write_text(canonical(final)+'\n')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.source,a.output)

FILE tests/test_backend_rdf_import.py
import unittest
from scripts.backend_rdf_import import export_terms
from rdflib import XSD
class ExportTermTests(unittest.TestCase):
    def test_tags_and_custom_types_remain_distinct(self):
        base={'subject':'urn:s','predicate':'urn:p','object':'same','isLiteral':True,'literalType':str(XSD.string),'literalLang':None,'subjectSPO':None}
        rows=[base,{**base,'literalLang':'en'},{**base,'literalType':'urn:Grade'}]
        triples=export_terms(rows)
        self.assertEqual(len(triples),3)
        self.assertEqual({t[2] for t in triples},{'"same"','"same"@en','"same"^^<urn:Grade>'})
    def test_rdfstar_not_silently_flattened(self):
        with self.assertRaisesRegex(ValueError,'RDF-star'):export_terms([{'subjectSPO':['a','b','c']}])
if __name__=='__main__':unittest.main()

FILE _workspace/backend-execution-20261106/score_import.py
import json,sys
from pathlib import Path
out=Path(sys.argv[1]);plan=json.loads((out/'plan.json').read_text());cases={c['id']:c for c in json.loads((out/'cases.json').read_text())}
rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()] if (out/'results.jsonl').exists() else []
key=lambda x:(x['case'],x['operation'])
assert len({key(x) for x in rows})==len(rows)
assert {key(x) for x in rows}<={key(x) for x in plan}
ref=json.loads(Path('research/backend-reasoning-review-1/inference-contracts-001/evaluator-only.json').read_text())['expected']
checks=[]
for p in plan:
    row=next((r for r in rows if key(r)==key(p)),{**p,'status':'not_observed'})
    check={**p,'status':row['status']}
    if row['status']=='completed':
        if p['operation'].endswith('roundtrip'):
            expected={tuple(t) for t in cases[p['case']]['triples']};observed={tuple(t) for t in row['triples']}
            check.update(input_triples=len(expected),output_triples=len(observed),missing=sorted(expected-observed),extra=sorted(observed-expected),exact_terms=expected==observed)
        else:
            variant='missing_schema' if p['case']=='hierarchy-missing-schema' else 'base'
            check['matches_current_reference']=row['answer']==ref[variant][p['operation']]
    checks.append(check)
result={'planned':len(plan),'observed':len(rows),'completed':sum(r['status']=='completed' for r in rows),'unobserved':len(plan)-len(rows),'checks':checks,'interpretation':'Small configured RDF-to-LPG import/export diagnostic. Exact URI/literal-term comparison for this bundle only, no general invertibility/performance/QA claim. Authored fixtures separate from source projection.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({**{k:v for k,v in result.items() if k!='checks'},'checks':[{k:v for k,v in c.items() if k not in ('missing','extra')} for c in checks]},indent=2))
