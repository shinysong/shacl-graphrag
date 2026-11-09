"""Advisory metadata checks on saved DB results; no veto, source lookup, or repair."""
import json,re
from pathlib import Path
from rdflib import Graph,Namespace,Literal,RDF
from pyshacl import validate
from scripts.backend_parity import canonical,digest
EX=Namespace('urn:shacl-study:advisory:');SH=Namespace('http://www.w3.org/ns/shacl#')


def python_report(metadata):
    codes=set()
    for field,label in [('used_input_hash','used'),('current_input_hash','current')]:
        value=metadata.get(field)
        if value is None:codes.add('missing_'+label+'_fingerprint')
        elif not re.fullmatch('[0-9a-f]{64}',value):codes.add('malformed_'+label+'_fingerprint')
    # sh:equals compares value sets, including a missing value on either side.
    used=set() if metadata.get('used_input_hash') is None else {metadata['used_input_hash']}
    current=set() if metadata.get('current_input_hash') is None else {metadata['current_input_hash']}
    if used!=current:codes.add('fingerprint_disagreement_review_scope')
    return sorted(codes)


def shacl_report(metadata,shapes):
    g=Graph();node=EX['result'];g.add((node,RDF.type,EX.Result))
    for field,p in [('used_input_hash',EX.usedHash),('current_input_hash',EX.currentHash)]:
        if metadata.get(field) is not None:g.add((node,p,Literal(metadata[field])))
    conforms,report,_=validate(g,shacl_graph=shapes,inference='none',advanced=False)
    codes=sorted({str(m) for m in report.objects(None,SH.resultMessage)})
    return {'conforms':bool(conforms),'codes':codes,'validation_graph':report.serialize(format='turtle')}


def build_inputs(saved):
    actual=[]
    for i,row in enumerate(saved):
        actual.append({'id':'actual-'+str(i),'cohort':'saved_backend_output','origin':{k:row[k] for k in ('event','arm','query_id')},'original_status':row['status'],'original_answer':row.get('answer'),'metadata':{k:row.get(k) for k in ('used_input_hash','current_input_hash')}})
    controls=[]
    for event,arm,query in [('initial','python_current','I2_forward'),('delete_fact','neptune_stale','I2_forward')]:
        row=next(r for r in actual if r['origin']=={'event':event,'arm':arm,'query_id':query})
        for variant in ['missing_current','matching_published_metadata','malformed_current','missing_both']:
            c=json.loads(canonical(row));c['id']='control-'+event+'-'+variant;c['cohort']='authored_metadata_control';c['control']=variant
            if variant=='missing_current':c['metadata']['current_input_hash']=None
            elif variant=='matching_published_metadata':c['metadata']['used_input_hash']=c['metadata']['current_input_hash']
            elif variant=='malformed_current':c['metadata']['current_input_hash']='not-a-fingerprint'
            else:c['metadata']={'used_input_hash':None,'current_input_hash':None}
            controls.append(c)
    return actual+controls


def run(saved_path,shapes_path,output):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    saved=[json.loads(x) for x in Path(saved_path).read_text().splitlines()];inputs=build_inputs(saved)
    (out/'inputs.json').write_text(canonical(inputs)+'\n');(out/'shapes.ttl').write_bytes(Path(shapes_path).read_bytes());(out/'runtime.py').write_bytes(Path(__file__).read_bytes())
    (out/'plan.json').write_text(canonical([{'id':x['id'],'policy':p} for x in inputs for p in ('python','shacl')])+'\n')
    shapes=Graph().parse(shapes_path,format='turtle')
    with (out/'results.jsonl').open('a') as h:
        for x in inputs:
            for policy in ('python','shacl'):
                row={'id':x['id'],'policy':policy,'cohort':x['cohort'],'origin':x['origin'],'original_status':x['original_status'],'original_answer':x['original_answer'],'input_hash':digest(x),'answer_changed':False,'decision':'advisory_only_no_veto'}
                try:
                    if policy=='python':codes=python_report(x['metadata'])
                    else:
                        report=shacl_report(x['metadata'],shapes);codes=report['codes'];row['conforms']=report['conforms'];(out/(x['id']+'-report.ttl')).write_text(report['validation_graph'])
                    row.update(status='completed',codes=codes,review_requested=bool(codes))
                except Exception as exc:row.update(status='checker_failure',error=type(exc).__name__+': '+str(exc))
                h.write(canonical(row)+'\n');h.flush()
    return inputs

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--saved',required=True);p.add_argument('--shapes',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.saved,a.shapes,a.output)
