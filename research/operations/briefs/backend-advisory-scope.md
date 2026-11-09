# Declared question-family fingerprint replay
Prioradvisory:160savedDBoutputs,globalmetadata32flags including8querysetmismatches and24matchingoutputs; noLLM/veto. Thisfollowup uses SAME160savedoutputs and8frozeninputstates plus4typedquerycontracts. Runtime doesnotreadgold/evaluation; operationalpreprocessor computes advertisedfingerprintsfor global/typefacts+subClassOfschema/relationfacts+subPropertyOfschema. Currentandusedsnapshot matchedbyoriginalpublishedglobalhash, restoreidenticalcontentsamehash. Allruntimefacts are savedcontrolledinputs, notnewsourcefetch. Samepublishedmetadata wouldneedavailabilitytoallfuturegeneratorarms; thisdoesnotestablishnewLLMinterventionparity. Threepolicies:global,declaredcorrecttype/relationfamily,swappedfamilynegativecontrol.160rows x3policies x2checkers=960slots,480pairedreports,notindependenttrials. ActualSHACL+Python sameexistinghashshapes/policies, onlyhashmetadata passed; originalanswers unchanged/no veto. Querykind is predeclaredtypedcontract,notnatural-languageextraction orlearnedontology. FamilySC/SPscopevalidONLYdeclaredselectedtwohierarchyrules (notdomain/range/mixedfullRDFS). Fullschemafields beyondthosewouldrequireexpandeddependencies. Wrongfamily controlretained; do notselectpolicybygold. Correctflagsproxyreviewburden,notmeasuredhumanhours oractualabstention. Offlineonly,NeptunealreadyStopaccepted09:14:59finalstateunverified. Importedbodiesomitted,markunverified; priorcompletedreviews/runscoverboundedexistingpolicy,2newunitmethods planned. Scoreronlyposthocreadsconsumedreference. Fullplanbeforeprocessing/failuresretained; no paidcalls/push. Freezeinputs/code/scorer/shapes beforeexecute.

FILE scripts/backend_advisory_scope.py
"""Declared question-family metadata replay; no current source service or answer repair."""
import json
from pathlib import Path
from rdflib import Graph
from scripts.backend_parity import canonical,digest
from scripts.backend_inference import TYPE,SC,SP
from scripts.backend_updates import input_digest
from scripts.backend_advisory import python_report,shacl_report
POLICIES={'global':{'type':'all','relation':'all'},'declared_family':{'type':'type_schema','relation':'relation_schema'},'swapped_family_control':{'type':'relation_schema','relation':'type_schema'}}


def fingerprint(state,family):
    if family=='all':return input_digest(state)
    if family=='type_schema':value={'facts':[t for t in state['facts'] if t[1]==TYPE],'schema':[t for t in state['schema'] if t[1]==SC]}
    elif family=='relation_schema':value={'facts':[t for t in state['facts'] if t[1]!=TYPE],'schema':[t for t in state['schema'] if t[1]==SP]}
    else:raise ValueError('unknown declared family')
    return digest({k:sorted(v) for k,v in value.items()})


def run(parent,shapes_path,output):
    parent=Path(parent);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    saved=[json.loads(x) for x in (parent/'results.jsonl').read_text().splitlines()]
    states=json.loads((parent/'states.json').read_text());queries=json.loads((parent/'queries.json').read_text())
    kinds={q['id']:q['kind'] for q in queries};state_by_hash={input_digest(s):s for s in states}
    plan=[{'row_index':i,'policy':p,'checker':c} for i in range(len(saved)) for p in POLICIES for c in ('python','shacl')]
    for file,value in [('plan.json',plan),('policies.json',POLICIES),('states.json',states),('queries.json',queries)]: (out/file).write_text(canonical(value)+'\n')
    (out/'runtime.py').write_bytes(Path(__file__).read_bytes());(out/'shapes.ttl').write_bytes(Path(shapes_path).read_bytes())
    # Fingerprints are published by this controlled preprocessor, not discovered by SHACL.
    inputs=[]
    try:
        for i,row in enumerate(saved):
            current=state_by_hash[row['current_input_hash']];used=state_by_hash[row['used_input_hash']]
            for policy,mapping in POLICIES.items():
                family=mapping[kinds[row['query_id']]]
                inputs.append({'row_index':i,'policy':policy,'family':family,'origin':{k:row[k] for k in ('event','arm','query_id')},'original_answer':row.get('answer'),'original_status':row['status'],'metadata':{'used_input_hash':fingerprint(used,family),'current_input_hash':fingerprint(current,family)}})
        (out/'inputs.json').write_text(canonical(inputs)+'\n')
        shapes=Graph().parse(shapes_path,format='turtle')
        with (out/'results.jsonl').open('a') as h:
            for x in inputs:
                for checker in ('python','shacl'):
                    row={**x,'checker':checker,'answer_changed':False,'decision':'advisory_only_no_veto'}
                    try:
                        if checker=='python':codes=python_report(x['metadata'])
                        else:
                            report=shacl_report(x['metadata'],shapes);codes=report['codes'];row['conforms']=report['conforms'];(out/(str(x['row_index'])+'-'+x['policy']+'-report.ttl')).write_text(report['validation_graph'])
                        row.update(status='completed',codes=codes,review_requested=bool(codes))
                    except Exception as exc:row.update(status='checker_failure',error=type(exc).__name__+': '+str(exc))
                    h.write(canonical(row)+'\n');h.flush()
    except Exception as exc:
        (out/'failure.json').write_text(canonical({'error':type(exc).__name__+': '+str(exc)})+'\n');raise

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--parent',required=True);p.add_argument('--shapes',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.parent,a.shapes,a.output)

FILE tests/test_backend_advisory_scope.py
import unittest
from scripts.backend_advisory_scope import fingerprint
from scripts.backend_inference import TYPE,SC,SP,term
class FingerprintScopeTests(unittest.TestCase):
    def test_relation_change_does_not_change_type_family(self):
        a={'facts':[(term('a'),TYPE,term('Class')),(term('a'),term('p'),term('b'))],'schema':[(term('Class'),SC,term('Root')),(term('p'),SP,term('ref'))]}
        b={**a,'facts':a['facts'][:1]}
        self.assertEqual(fingerprint(a,'type_schema'),fingerprint(b,'type_schema'))
        self.assertNotEqual(fingerprint(a,'relation_schema'),fingerprint(b,'relation_schema'))
        self.assertNotEqual(fingerprint(a,'all'),fingerprint(b,'all'))
    def test_schema_change_and_record_order(self):
        a={'facts':[(term('a'),TYPE,term('C')),(term('b'),TYPE,term('C'))],'schema':[(term('C'),SC,term('R'))]}
        b={**a,'schema':[]};reordered={**a,'facts':a['facts'][::-1]}
        self.assertNotEqual(fingerprint(a,'type_schema'),fingerprint(b,'type_schema'))
        self.assertEqual(fingerprint(a,'relation_schema'),fingerprint(b,'relation_schema'))
        self.assertEqual(fingerprint(a,'all'),fingerprint(reordered,'all'))
if __name__=='__main__':unittest.main()

FILE _workspace/backend-execution-20261106/score_scope.py
import json,sys
from pathlib import Path
out=Path(sys.argv[1]);plan=json.loads((out/'plan.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()];inputs=json.loads((out/'inputs.json').read_text());expected={(x['row_index'],x['policy']):x for x in inputs}
key=lambda r:(r['row_index'],r['policy'],r['checker']);assert len({key(r) for r in rows})==len(rows);assert {key(r) for r in rows}<={key(r) for r in plan}
parent=Path('research/backend-reasoning-review-1/updates-live-001');ev=json.loads((parent/'evaluation.json').read_text());ref={(x['event'],x['arm'],x['query_id']):x['matches_current_reference'] for x in ev['checks']}
lookup={key(r):r for r in rows};summary={};pairs=[]
for p in plan:
    row=lookup.get(key(p));s=summary.setdefault(p['policy']+'/'+p['checker'],{'planned':0,'completed':0,'review_flags':0,'mismatch_with_review':0,'matching_with_review':0,'mismatch_without_review':0});s['planned']+=1
    if row and row['status']=='completed':
        x=expected[(p['row_index'],p['policy'])];assert row['original_answer']==x['original_answer'] and not row['answer_changed']
        matches=ref[tuple(row['origin'][k] for k in ('event','arm','query_id'))];flag=row['review_requested']
        s['completed']+=1;s['review_flags']+=flag;s['mismatch_with_review']+=not matches and flag;s['matching_with_review']+=matches and flag;s['mismatch_without_review']+=not matches and not flag
for i,p in expected:
    a,b=[lookup.get((i,p,c)) for c in ('python','shacl')];pairs.append(bool(a and b and a['status']==b['status']=='completed' and a['codes']==b['codes']))
result={'planned_checker_slots':len(plan),'observed':len(rows),'pairs':len(pairs),'agreeing_pairs':sum(pairs),'summary':summary,'interpretation':'Derived replay on same160controlledbackendoutputs. Typedfamilymapping supplied, not learnedNLunderstanding. Metadataonly/noLLM/veto/repair. Correctflags quantify proxyreviewburden, not actual labor orabstention.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert len(rows)==len(plan) and all(pairs)
