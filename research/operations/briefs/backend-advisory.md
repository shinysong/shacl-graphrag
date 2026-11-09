# Final advisory metadata replay
Use160saved actualupdates-live-001 queryoutputs (allcompleted), notnewLLManswers, no paidcalls. Retain each originalanswer andstatus; checkerreceivesONLYscalar publishedused/currentcontenthashmetadata. No queryanswer/gold/sourcefetch passedtochecker, nofixedanswerrepair/veto. Compare samepolicyPython and actualpySHACL: requiredmetadata,64hexformat,equalityofsets. Reports areadvisoryversion-scope reviewpointers, nottruth/completenesscertificate. Eachsavedrowhas currentinputhashadvertisedbyexperimentcontroller andusedsnapshotinputhash; this is suppliedreliablemetadataforcontrolledrun,notautomaticdiscoveryofrealworldfreshness. Restoredidenticalcontenthasidenticalhash. Metadata mismatchcanflagunchangedanswer. Posthocscorer (notruntime) comparesknownconsumed authoredquerysetreference toreviewflags; matchingflaggedoutputs representpotentialreviewburden,NOT measuredwrongabstentionbecause no veto. Twofixedsavedrows initial/current anddeletefact/stale get4authoredmetadatacontrols each: currentmissing,matchingpublishedusedhash,malformedcurrent,bothmissing. Controls8separatefrom160actualrows; matchingmetadata canpasswrongoutput,showsdeclaredmetadata dependence.168inputrows x2checkers=336plannedcheckslots,168pairedreports,notindependenttrials. Scalar/nullstringdomainonly; noarbitrarymetadata typeclaim. pySHACLduplicate equalityviolationsdedupmessagecodes forpolicycomparison;rawTTLreportsretained.2unitmethods planned,fullplan andfailures retained, scorerfullcoverage/status. Noengine/LLManswerimprovement orSHACL superiorityclaim;samepolicyPython essential. Alloffline, Neptune stopalreadyaccepted butfinalstateunverified. Userrequested2hdeadline10:31:23UTC, noinfra/restart/push.

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

FILE tests/test_backend_advisory.py
import unittest
from pathlib import Path
from rdflib import Graph
from scripts.backend_advisory import python_report,shacl_report
SHAPES=Path('research/backend-reasoning-review-1/advisory-contracts-001/shapes.ttl')
class AdvisoryTests(unittest.TestCase):
    def test_published_metadata_limits_and_policy_parity(self):
        g=Graph().parse(SHAPES,format='turtle')
        cases=[({'used_input_hash':'a'*64,'current_input_hash':'a'*64},[]),({'used_input_hash':'a'*64,'current_input_hash':'b'*64},['fingerprint_disagreement_review_scope']),({},['missing_current_fingerprint','missing_used_fingerprint']),({'used_input_hash':'a'*64},['fingerprint_disagreement_review_scope','missing_current_fingerprint']),({'used_input_hash':'bad','current_input_hash':'bad'},['malformed_current_fingerprint','malformed_used_fingerprint'])]
        for metadata,expected in cases:
            self.assertEqual(python_report(metadata),expected)
            result=shacl_report(metadata,g);self.assertEqual(result['codes'],expected);self.assertEqual(result['conforms'],not expected)
    def test_answer_truth_is_not_checker_input(self):
        metadata={'used_input_hash':'a'*64,'current_input_hash':'a'*64}
        self.assertEqual(python_report(metadata),[])
        self.assertEqual(shacl_report(metadata,Graph().parse(SHAPES,format='turtle'))['codes'],[])
if __name__=='__main__':unittest.main()

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

FILE _workspace/backend-execution-20261106/score_advisory.py
import json,sys
from pathlib import Path
out=Path(sys.argv[1]);inputs=json.loads((out/'inputs.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()];plan=json.loads((out/'plan.json').read_text())
key=lambda r:(r['id'],r['policy']);assert len({key(r) for r in rows})==len(rows);assert {key(r) for r in rows}<={key(r) for r in plan}
lookup={key(r):r for r in rows};evaluation=json.loads(Path('research/backend-reasoning-review-1/updates-live-001/evaluation.json').read_text());reference={(x['event'],x['arm'],x['query_id']):x['matches_current_reference'] for x in evaluation['checks']}
summary={};checks=[]
for x in inputs:
    truth=reference[tuple(x['origin'][k] for k in ('event','arm','query_id'))]
    pair=[lookup.get((x['id'],p)) for p in ('python','shacl')]
    same=all(r and r['status']=='completed' for r in pair) and pair[0]['codes']==pair[1]['codes']
    checks.append({'id':x['id'],'cohort':x['cohort'],'policy_agreement':same,'source_query_set_matches_reference':truth})
    for policy,row in zip(('python','shacl'),pair):
        s=summary.setdefault(x['cohort']+'/'+policy,{'planned':0,'completed':0,'reports_requesting_review':0,'query_set_mismatch_with_review':0,'matching_query_set_with_review':0,'query_set_mismatch_without_review':0})
        s['planned']+=1
        if row and row['status']=='completed':
            s['completed']+=1;s['reports_requesting_review']+=row['review_requested']
            s['query_set_mismatch_with_review']+=not truth and row['review_requested']
            s['matching_query_set_with_review']+=truth and row['review_requested']
            s['query_set_mismatch_without_review']+=not truth and not row['review_requested']
            assert row['original_answer']==x['original_answer'] and row['answer_changed'] is False
result={'planned_checker_slots':len(plan),'observed_checker_slots':len(rows),'unobserved':len(plan)-len(rows),'policy_pairs':len(inputs),'agreeing_pairs':sum(x['policy_agreement'] for x in checks),'summary':summary,'checks':checks,'interpretation':'Offline replay, same metadata policy, no new answers or model calls. Version warning is not factual-error finding. Query-set matches use consumed authored reference; not external truth. Matching outputs flagged are review burden, not actual abstention because no veto. Authored metadata controls separate.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
assert len(rows)==len(plan) and all(x['policy_agreement'] for x in checks)
