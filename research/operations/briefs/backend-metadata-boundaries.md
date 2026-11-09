# Frozen metadata checker boundary diagnostic
Offline only. Prior actual160backendrows and8metadata controls had Python/SHACL agreement onlyfor canonical strings ormissing. Prior review explicitly left trailing-newline regex and other inputtypes unverified. This is a new authored 17case/34slot diagnostic, no source/DB/model calls and no QA efficacy. Keep originalchecker/shapes unchanged, retain failures and disagreements. Values are synthetic metadata, not facts or gold. Fullplan frozen beforeprocessing, no expectation inside runtime. Scoreafterward all planned slots, exception and completed disagreement separately. Prioractual336/960slots remain original. No generalarbitrarypolicy parityclaim. Existing liveexperiments completed, Neptune stopped/temporaryn10sremoved. Imported canonical is deterministicJSONserialization. Otherimports shown. Reviewpacket includescomplete runtime/checkers/shapes; noheldoutgold/secrets. Registeredchecks empty; diagnosticexplicitlymainexecutesafterbothreviewsready.

FILE scripts/backend_metadata_boundaries.py
"""Offline diagnostic of frozen advisory checkers at their input boundaries."""
import argparse
import json
from pathlib import Path

from rdflib import Graph
from scripts.backend_advisory import python_report, shacl_report
from scripts.backend_parity import canonical


def cases():
    same = lambda value: {'used_input_hash': value, 'current_input_hash': value}
    values = {
        'canonical_same': 'a' * 64, 'empty': '', 'short': 'a' * 63,
        'long': 'a' * 65, 'uppercase': 'A' * 64,
        'lf_suffix': 'a' * 64 + '\n', 'crlf_suffix': 'a' * 64 + '\r\n',
        'lf_prefix': '\n' + 'a' * 64, 'space_suffix': 'a' * 64 + ' ',
        'unicode': 'ａ' * 64, 'integer': 123, 'boolean': True,
        'list': ['a' * 64], 'dictionary': {'value': 'a' * 64},
    }
    rows = [{'id': name, 'metadata': same(value), 'cohort': 'authored_boundary'} for name, value in values.items()]
    rows += [
        {'id': 'canonical_different', 'metadata': {'used_input_hash': 'a' * 64, 'current_input_hash': 'b' * 64}, 'cohort': 'authored_boundary'},
        {'id': 'missing_both', 'metadata': {}, 'cohort': 'authored_boundary'},
        {'id': 'missing_current', 'metadata': {'used_input_hash': 'a' * 64}, 'cohort': 'authored_boundary'},
    ]
    return rows


def run(shapes_path, output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = cases()
    plan = [{'id': row['id'], 'checker': checker} for row in inputs for checker in ('python', 'shacl')]
    (output / 'inputs.json').write_text(canonical(inputs) + '\n')
    (output / 'plan.json').write_text(canonical(plan) + '\n')
    (output / 'runtime.py').write_bytes(Path(__file__).read_bytes())
    (output / 'advisory-runtime.py').write_bytes(Path('scripts/backend_advisory.py').read_bytes())
    (output / 'shapes.ttl').write_bytes(shapes_path.read_bytes())
    shapes = Graph().parse(shapes_path, format='turtle')
    with (output / 'results.jsonl').open('a') as handle:
        for item in inputs:
            for checker in ('python', 'shacl'):
                row = {'id': item['id'], 'checker': checker}
                try:
                    if checker == 'python':
                        codes = python_report(item['metadata'])
                    else:
                        result = shacl_report(item['metadata'], shapes)
                        codes = result['codes']
                        (output / (item['id'] + '-report.ttl')).write_text(result['validation_graph'])
                        row['conforms'] = result['conforms']
                    row.update(status='completed', codes=codes, review_requested=bool(codes))
                except Exception as error:
                    row.update(status='checker_failure', error=f'{type(error).__name__}: {error}')
                handle.write(canonical(row) + '\n')
                handle.flush()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shapes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.shapes, args.output)

FILE scripts/backend_advisory.py
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

FILE research/backend-reasoning-review-1/advisory-contracts-001/shapes.ttl
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <urn:shacl-study:advisory:> .
ex:ResultShape a sh:NodeShape ; sh:targetClass ex:Result ;
 sh:property ex:UsedRequired, ex:CurrentRequired, ex:UsedFormat, ex:CurrentFormat, ex:VersionAgreement .
ex:UsedRequired sh:path ex:usedHash ; sh:minCount 1 ; sh:message "missing_used_fingerprint" .
ex:CurrentRequired sh:path ex:currentHash ; sh:minCount 1 ; sh:message "missing_current_fingerprint" .
ex:UsedFormat sh:path ex:usedHash ; sh:pattern "^[0-9a-f]{64}$" ; sh:message "malformed_used_fingerprint" .
ex:CurrentFormat sh:path ex:currentHash ; sh:pattern "^[0-9a-f]{64}$" ; sh:message "malformed_current_fingerprint" .
ex:VersionAgreement sh:path ex:usedHash ; sh:equals ex:currentHash ; sh:message "fingerprint_disagreement_review_scope" .
