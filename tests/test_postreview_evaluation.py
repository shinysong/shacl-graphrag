import copy
import unittest
from scripts.postreview_evaluation import summarize, digest, AXES

class EvaluationTests(unittest.TestCase):
 def fixture(self):
  plan=[dict(case_id='a',model='fixture',context_id='q1',selected_target_supported=True),dict(case_id='b',model='fixture',context_id='q2',selected_target_supported=False)]
  out=[dict(case_id=cid,phase=p,state='succeeded',payload={'answer':cid+p}) for cid in ['a','b'] for p in ['draft','self_review','report']]
  def annotation(cid,p,target,support):
   labels={a:v[0] for a,v in AXES.items()};labels.update(target_value=target,selected_evidence_support=support)
   return dict(annotator_id='authored-fixture',case_id=cid,phase=p,payload_sha256=digest(next(x['payload'] for x in out if x['case_id']==cid and x['phase']==p)),labels=labels,rationale='Authored software fixture, not human/model outcome.')
  anns=[annotation('a','draft','differs_or_offtarget','unsupported'),annotation('a','report','withheld','no_assertion'),annotation('b','draft','withheld','no_assertion'),annotation('b','report','matches_reference','unsupported')]
  return plan,out,anns
 def test_wrong_to_withheld_and_unsupported_match_separate(self):
  p,o,a=self.fixture();r=summarize(p,o,a)['groups']['fixture'];x=r['annotators']['authored-fixture'];self.assertEqual(x['transitions']['report']['target'],{'wrong_to_withheld':1,'withheld_to_matching':1});self.assertEqual(x['phases']['report']['unnecessary_withholding'],1);self.assertEqual(x['phases']['report']['axes']['selected_evidence_support']['unsupported'],1)
 def test_full_failure_denominator(self):
  p,o,a=self.fixture()
  for x in o:
   if x['case_id']=='b':
    x.pop('payload');x.update(state='failed' if x['phase']=='draft' else 'not_attempted',reason='authored draft failure')
  a=[x for x in a if x['case_id']=='a'];r=summarize(p,o,a)['groups']['fixture'];self.assertEqual(r['planned_workflows'],2);self.assertEqual(r['execution']['report']['not_attempted'],1);self.assertEqual(r['annotators']['authored-fixture']['transitions']['report']['not_scored_pairs'],1)
 def test_missing_annotation_is_unscored(self):
  p,o,a=self.fixture();r=summarize(p,o,a)['groups']['fixture']['annotators']['authored-fixture']['phases']['self_review'];self.assertEqual(r['scored'],0);self.assertEqual(r['successful_unscored'],2)
 def test_binding_duplicate_and_invalid_labels_rejected(self):
  for mode in ['hash','duplicate','axis','value','failed']:
   p,o,a=self.fixture()
   if mode=='hash':a[0]['payload_sha256']='stale'
   if mode=='duplicate':a.append(copy.deepcopy(a[0]))
   if mode=='axis':a[0]['labels'].pop('unit')
   if mode=='value':a[0]['labels']['unit']='excellent'
   if mode=='failed':o[0].pop('payload');o[0].update(state='failed',reason='test')
   with self.assertRaises(ValueError):summarize(p,o,a)
 def test_plan_and_dependency_rejected(self):
  for mode in ['missing','duplicate','eligibility','dependency']:
   p,o,a=self.fixture()
   if mode=='missing':o.pop()
   if mode=='duplicate':p.append(copy.deepcopy(p[0]))
   if mode=='eligibility':p[0]['selected_target_supported']='true'
   if mode=='dependency':o[0].pop('payload');o[0].update(state='failed',reason='test')
   with self.assertRaises(ValueError):summarize(p,o,[])
 def test_disagreement_retained_no_consensus(self):
  p,o,a=self.fixture();b=copy.deepcopy(a[0]);b['annotator_id']='second-fixture';b['labels']['target_value']='unadjudicable';a.append(b);before=copy.deepcopy((p,o,a));r=summarize(p,o,a);self.assertFalse(r['consensus_performed']);self.assertEqual(r['disagreements'][0]['axes'],['target_value']);self.assertEqual((p,o,a),before)
 def test_no_annotations_no_invented_accuracy(self):
  p,o,a=self.fixture();r=summarize(p,o,[]);self.assertEqual(r['groups']['fixture']['annotators'],{});self.assertNotIn('accuracy',r)
if __name__=='__main__':unittest.main()
