"""Bounded Factory Lab transport parity. No model calls, deletion, or AWS power actions.

Run as: uv run --locked python -m scripts.factory_backend_parity --output PATH --neo4j --import-neo4j
Neptune is opt-in through a separately approved, time-bounded authorization file.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from apps.factory_lab.graph import Graph, snapshot
from apps.factory_lab.rdf_graph import RDFLibGraph, NeptuneGraph, export, graph_uri
from apps.factory_lab.review import review

VERSIONS = ('factory-v1', 'factory-v2', 'factory-v3')
# Input requests only; no expected answers or evaluation labels reach a backend.
REQUESTS = [
 ('find_entities',{'text':'M0'}),('find_entities',{'text':'자격'}),('find_entities',{'text':'not present'}),
 ('find_entities',{'text':'" } UNION { ?s ?p ?o } #'}),
 ('inspect_entity',{'entity_id':'M01'}),('inspect_entity',{'entity_id':'Q03'}),('inspect_entity',{'entity_id':'O17'}),('inspect_entity',{'entity_id':'missing'}),
 ('impacted_orders',{'machine_id':'M02'}),('impacted_orders',{'machine_id':'M01'}),
 ('replacement_candidates',{'order_id':'O17'}),('replacement_candidates',{'order_id':'O18'}),('replacement_candidates',{'order_id':'O19'}),
 ('qualification_records',{'machine_id':'M01'}),('qualification_records',{'machine_id':'M02'}),('qualification_records',{'machine_id':'M03'})]


def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def save(path,x): Path(path).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def common_evidence(result):
    # Explicit future generator contract: transport queries/integrity/backend are audit only.
    return {k:result[k] for k in ('tool','arguments','snapshot','source_sha256','as_of','rows','scope','limit_reached')}


def execute(output, neo4j=False, import_neo4j=False, neptune_authorization=None, import_neptune=False):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    plan=[{'backend':b,'version':v,'request':i,'tool':t,'arguments':a,'status':'unattempted'}
          for b in ('rdflib_sparql','neo4j_cypher','neptune_sparql') for v in VERSIONS for i,(t,a) in enumerate(REQUESTS)]
    save(out/'plan.json',plan);sources={}
    for v in VERSIONS:
        d,sha=snapshot(v);save(out/(v+'.json'),d);(out/(v+'.nt')).write_text(export(v))
        sources[v]={'source_sha256':sha,'graph':str(graph_uri(v)), 'rdf_sha256':hashlib.sha256((out/(v+'.nt')).read_bytes()).hexdigest()}
    save(out/'sources.json',sources)
    backends={'rdflib_sparql':RDFLibGraph()};initialization={}
    for name,enabled,factory,do_import in [('neo4j_cypher',neo4j,Graph,import_neo4j),('neptune_sparql',bool(neptune_authorization),lambda:NeptuneGraph(neptune_authorization),import_neptune)]:
        if not enabled:
            initialization[name]={'status':'unattempted','reason':'not enabled / no current bounded authorization'};continue
        try:
            backend=factory(); receipts=[]
            for v in VERSIONS:
                receipts.append({'version':v,'result':backend.load(v) if do_import else backend.verify_content(v)})
                save(out/(name+'-preflight.json'),receipts)
            backends[name]=backend;initialization[name]={'status':'ready'}
        except Exception as e:
            initialization[name]={'status':'failed','error_type':type(e).__name__,'message':str(e)}
    save(out/'initialization.json',initialization)
    results={}
    for slot in plan:
        backend=backends.get(slot['backend'])
        if backend is None:slot['reason']=initialization.get(slot['backend'],{});continue
        path=f'{slot["backend"]}-{slot["version"]}-{slot["request"]:02}.json'
        try:
            result=backend.run(slot['version'],slot['tool'],slot['arguments'])
            save(out/path,result);slot.update(status='completed',artifact=path,rows=len(result['rows']),evidence_sha256=digest(common_evidence(result)))
            results[(slot['backend'],slot['version'],slot['request'])]=result
        except Exception as e:
            slot.update(status='failed',error_type=type(e).__name__,message=str(e));save(out/path,slot)
        save(out/'plan.json',plan)
    comparisons=[]
    for name in ('neo4j_cypher','neptune_sparql'):
        for v in VERSIONS:
            for i,_ in enumerate(REQUESTS):
                left=results.get(('rdflib_sparql',v,i));right=results.get((name,v,i));both=left is not None and right is not None
                comparisons.append({'backend':name,'version':v,'request':i,'status':'compared' if both else 'unmeasured','same_ordered_rows':left['rows']==right['rows'] if both else None,'same_common_evidence':common_evidence(left)==common_evidence(right) if both else None})
    reports={}
    for b in backends:
        reports[b]={}
        for v in VERSIONS:
            keys=[(b,v,i) for i in (10,11,13,14,15)]
            if not all(k in results for k in keys):continue
            evidence=[results[k] for k in keys]
            py,sh=review(evidence,'python'),review(evidence,'shacl')
            reports[b][v]={'python':py,'shacl':sh,'same_flags':py['flags']==sh['flags']}
    save(out/'comparisons.json',comparisons);save(out/'reports.json',reports);save(out/'plan.json',plan)
    summary={'planned_slots':len(plan),'completed':sum(s['status']=='completed' for s in plan),'failed_query_slots':sum(s['status']=='failed' for s in plan),'unattempted':sum(s['status']=='unattempted' for s in plan),'initialization':initialization,'compared':sum(c['status']=='compared' for c in comparisons),'mismatches':sum(c['status']=='compared' and not c['same_common_evidence'] for c in comparisons),'paid_llm_calls':0,'aws_power_actions':0,'scope':'Authored development transport/checker comparison; not LLM answer efficacy, DB performance, maintenance labor or OWL reasoning.'}
    save(out/'summary.json',summary);return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--neo4j',action='store_true');p.add_argument('--import-neo4j',action='store_true');p.add_argument('--neptune-authorization');p.add_argument('--import-neptune',action='store_true');a=p.parse_args()
    if a.import_neo4j and not a.neo4j:p.error('--import-neo4j requires --neo4j')
    if a.import_neptune and not a.neptune_authorization:p.error('--import-neptune requires --neptune-authorization')
    print(canonical(execute(a.output,a.neo4j,a.import_neo4j,a.neptune_authorization,a.import_neptune)))
