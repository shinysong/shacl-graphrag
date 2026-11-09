import copy
import unittest
from scripts.postreview_evaluation import AXES,digest,PHASES
from scripts.postreview_compound import summarize_compound

class CompoundTests(unittest.TestCase):
 def fixture(self):
  p=[dict(case_id='a',model='fixture',context_id='q',subtargets=[dict(subtarget_id=t,selected_target_supported=True) for t in ['left','right','difference']])]
  o=[dict(case_id='a',phase=f,state='succeeded',payload={'answer':f}) for f in PHASES]
  a=[]
  for row in o:
   for t in ['left','right','difference']:
    ls={k:v[0] for k,v in AXES.items()}
    if t=='difference':ls['target_value']='withheld' if row['phase']=='report' else 'differs_or_offtarget'
    a.append(dict(case_id='a',phase=row['phase'],subtarget_id=t,annotator_id='authored',payload_sha256=digest(row['payload']),labels=ls,rationale='Synthetic accounting fixture'))
  return p,o,a
 def test_partial_not_whole_match_and_no_call_inflation(self):
  p,o,a=self.fixture();g=summarize_compound(p,o,a)['groups']['fixture']
  self.assertEqual(g['planned_workflows'],1);self.assertEqual(g['planned_subtargets'],3)
  self.assertEqual(g['workflow_execution']['draft']['succeeded'],1)
  self.assertEqual(g['subtarget_execution_slots']['draft']['succeeded'],3)
  self.assertEqual(g['workflow_label_coverage']['authored']['draft'],{'contains_wrong_or_withheld_target':1})
  self.assertEqual(g['subtarget_annotations']['authored']['transitions']['report']['target']['wrong_to_withheld'],1)
  self.assertEqual(g['subtarget_annotations']['authored']['phases']['report']['unnecessary_withholding'],1)
 def test_missing_annotation_stays_unscored(self):
  p,o,a=self.fixture();a.pop();g=summarize_compound(p,o,a)['groups']['fixture']
  self.assertEqual(g['workflow_label_coverage']['authored']['report'],{'incompletely_annotated':1})
 def test_failure_denominator_and_dependencies(self):
  p,o,a=self.fixture()
  for row in o: row.pop('payload');row.update(state='failed' if row['phase']=='draft' else 'not_attempted',reason='authored failure')
  g=summarize_compound(p,o,[])['groups']['fixture'];self.assertEqual(g['workflow_execution']['draft']['failed'],1);self.assertEqual(g['subtarget_execution_slots']['report']['not_attempted'],3)
 def test_bad_annotations_and_plan(self):
  for mode in ['duplicate','unknown','hash','eligibility','empty','missingphase']:
   p,o,a=self.fixture()
   if mode=='duplicate':p[0]['subtargets'].append(copy.deepcopy(p[0]['subtargets'][0]))
   if mode=='unknown':a[0]['subtarget_id']='unknown'
   if mode=='hash':a[0]['payload_sha256']='stale'
   if mode=='eligibility':p[0]['subtargets'][0]['selected_target_supported']='true'
   if mode=='empty':p[0]['subtargets']=[]
   if mode=='missingphase':o.pop()
   with self.assertRaises(ValueError):summarize_compound(p,o,a)
 def test_no_annotations_no_accuracy_and_immutable(self):
  p,o,a=self.fixture();before=copy.deepcopy((p,o,a));r=summarize_compound(p,o,[])
  self.assertEqual(r['groups']['fixture']['subtarget_annotations'],{});self.assertNotIn('accuracy',r);self.assertEqual((p,o,a),before)
 def test_disagreement_and_orthogonal_support_preserved(self):
  p,o,a=self.fixture()
  for row in a:row['labels']['target_value']='matches_reference';row['labels']['selected_evidence_support']='unsupported'
  b=copy.deepcopy(a[0]);b['annotator_id']='other';b['labels']['target_value']='unadjudicable';a.append(b)
  r=summarize_compound(p,o,a);self.assertFalse(r['consensus_performed']);self.assertEqual(len(r['subtarget_disagreements']),1)
  g=r['groups']['fixture'];self.assertEqual(g['workflow_label_coverage']['authored']['draft'],{'all_target_labels_match':1});self.assertEqual(g['subtarget_annotations']['authored']['phases']['draft']['axes']['selected_evidence_support'],{'unsupported':3})
if __name__=='__main__':unittest.main()
