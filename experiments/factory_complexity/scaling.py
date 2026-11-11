"""Separate unrelated-size and related-fanout diagnostics; no LLM or DB server."""
import copy
import json
import math
import resource
import time
from pathlib import Path
from .fixtures import make_case,digest
from .tools import Views,RDFStudyTools,SQLStudyTools
from apps.factory_lab.evidence import canonical,model_evidence
from apps.factory_lab.review import review

REQUESTS=[('impacted_orders',{'machine_id':'M02'}),
          ('replacement_candidates',{'order_id':'O17'}),('replacement_candidates',{'order_id':'O18'}),
          ('qualification_records',{'machine_id':'M01'}),('qualification_records',{'machine_id':'M02'}),
          ('qualification_records',{'machine_id':'M03'})]


def triple_count(source):
    # Every node attribute, including kind->rdf:type, contributes one triple.
    return sum(len(n) for n in source['nodes'])+len(source['edges'])


def expand(source,target_triples=None,candidate_count=None):
    if (target_triples is None)==(candidate_count is None):raise ValueError('Choose one scaling axis')
    data=copy.deepcopy(source)
    if target_triples is not None:
        if target_triples not in (1000,10000,100000):raise ValueError('Unregistered size')
        count=max(0,math.ceil((target_triples-triple_count(data))/22))
    else:
        if candidate_count not in (29,30,31):raise ValueError('Unregistered fanout')
        count=candidate_count-3
    for i in range(count):
        mid,oid,cid,qid=(f'D{x}{i:06d}' for x in ('M','O','C','Q'))
        cap=cid if target_triples is not None else 'CAP-CUT'
        data['nodes'].extend([
            {'id':mid,'kind':'Machine','name':mid,'status':'available'},
            {'id':qid,'kind':'Qualification','name':qid,'product':'P-A','capability':cap,
             'valid_from':'2026-01-01','valid_until':'2026-12-31'}])
        data['edges'].extend([[mid,'CAPABLE_OF',cap],[mid,'HAS_QUALIFICATION',qid]])
        if target_triples is not None:
            data['nodes'].extend([{'id':oid,'kind':'Order','name':oid,'product':'P-A'},
                                  {'id':cid,'kind':'Capability','name':cid}])
            data['edges'].extend([[oid,'ASSIGNED_TO',mid],[oid,'REQUIRES',cid]])
    return data


def write_runtime(path,current):
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    before=make_case('Q2','C')['views']['factory-v2']
    versions={'factory-v2':before,'factory-v3':current}
    manifest={'current':'factory-v3','question':'Offline fixed-query size diagnostic; no model called.','versions':{}}
    for version,data in versions.items():
        (path/(version+'.json')).write_text(canonical(data)+'\n')
        manifest['versions'][version]={'source_sha256':digest(data),'view_sha256':digest(data)}
    (path/'manifest.json').write_text(canonical(manifest)+'\n')


def logical(evidence):
    """Across sizes source identities differ; preserve all row/limit semantics."""
    return [{k:v for k,v in model_evidence(e).items() if k!='source_sha256'} for e in evidence]


def checkpoint(output,result):
    temp=output/'result.tmp'
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    temp.replace(output/'result.json')


def measure(directory,axis,value,repeats=3):
    if repeats!=3:raise ValueError('Frozen three repeats')
    output=Path(directory);output.mkdir(parents=True,exist_ok=False)
    (output/'query-results').mkdir()
    result={'axis':axis,'value':value,'repeats':repeats,'status':'started','rows':[],
        'scope':'Local immutable in-memory SQLite/RDFLib diagnostic; build and hash verification separate from query. Not production full-content-per-query path, DB-server benchmark, LLM efficacy or memory attribution.',
        'model_calls':0,'aws_calls':0}
    checkpoint(output,result)
    try:
        base=make_case('Q2','C')['views']['factory-v3']
        if axis=='unrelated':source=expand(base,target_triples=value)
        elif axis=='fanout':source=expand(base,candidate_count=value)
        else:raise ValueError('Unknown axis')
        write_runtime(output/'runtime',source)
        t=time.perf_counter();views=Views(output/'runtime');result['source_load_hash_validation_seconds']=time.perf_counter()-t
        result.update(source_sha256=digest(source),nodes=len(source['nodes']),edges=len(source['edges']),projected_current_triples=triple_count(source))
        checkpoint(output,result)
        result['adapter_build_seconds']={};results={}
        # Alternate execution order between declared cells, avoiding a fixed SQL-first order.
        adapters=[SQLStudyTools,RDFStudyTools] if value%2 else [RDFStudyTools,SQLStudyTools]
        for cls in adapters:
            t=time.perf_counter();adapter=cls(views);result['adapter_build_seconds'][adapter.name]=time.perf_counter()-t
            checkpoint(output,result)
            if isinstance(adapter,RDFStudyTools):
                from apps.factory_lab.rdf_graph import graph_uri
                actual=len(adapter.dataset.graph(graph_uri('factory-v3')))
                result['actual_rdf_current_triples']=actual
                if actual!=result['projected_current_triples']:raise AssertionError('Projection triple count mismatch')
            outputs=[]
            try:
                for repetition in range(-1,repeats):
                    evidence=[]
                    for index,(tool,args) in enumerate(REQUESTS):
                        t=time.perf_counter();out=adapter.run('factory-v3',tool,args);elapsed=time.perf_counter()-t
                        evidence.append(out)
                        evidence_file=f'query-results/{adapter.name}-r{repetition}-q{index}.json'
                        (output/evidence_file).write_text(canonical(out)+'\n')
                        result['rows'].append({'backend':adapter.name,'repeat':repetition,'warmup':repetition==-1,
                            'request_index':index,'tool':tool,'arguments':args,'seconds':elapsed,
                            'row_count':len(out['rows']),'limit_reached':out['limit_reached'],
                            'evidence_file':evidence_file})
                        # Save each completed timing before the next potentially killed query.
                        checkpoint(output,result)
                    outputs.append(evidence)
                if any(logical(e)!=logical(outputs[0]) for e in outputs):raise AssertionError('Repeated result differs')
                results[adapter.name]=outputs[0]
                (output/(adapter.name+'-evidence.json')).write_text(canonical(outputs[0])+'\n')
            finally:
                if isinstance(adapter,SQLStudyTools):adapter.close()
        result['backend_order']=list(results)
        result['sql_rdf_logical_equal']=logical(results['study_sqlite'])==logical(results['study_rdflib'])
        if not result['sql_rdf_logical_equal']:raise AssertionError('SQL RDF result mismatch')
        evidence=results['study_rdflib'];result['checker_seconds']={};reports={}
        for mode in ('python','shacl'):
            t=time.perf_counter();reports[mode]=review(evidence,mode);result['checker_seconds'][mode]=time.perf_counter()-t
        result['checker_flags_equal']=reports['python']['flags']==reports['shacl']['flags']
        (output/'reports.json').write_text(canonical(reports)+'\n')
        if not result['checker_flags_equal']:raise AssertionError('Checker mismatch')
        result['status']='completed'
    except Exception as error:
        result.update(status='failed',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        result['process_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        checkpoint(output,result)
    return result
