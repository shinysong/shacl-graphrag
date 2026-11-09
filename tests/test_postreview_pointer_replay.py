import unittest
from scripts.postreview_pointer_replay import resolve,packet_for
from scripts.post_answer_review import review

class PointerReplayTests(unittest.TestCase):
 def node(self):return {'values':{'defect':4},'field_cells':{'defect':'A2'},'dictionary_refs':{'defect':'d'},'cells':[{'cell':'A2','value':4,'formula':None}]}
 def test_exact_supported_paths(self):
  n=self.node()
  for p,v in [('values.defect',4),('dictionary_refs.defect','d'),('field_cells.defect','A2'),('cells[0].cell','A2'),('cells[0].value',4),('cells.A2',4),('A2',4)]:self.assertEqual(resolve(n,p),(v,True))
 def test_no_fuzzy_or_multi_pointer_repair(self):
  for p in ['defect','row 2','values.defect, values.other','values.x_init [mm]','A2:G2','values.__class__','cells[-1].value']:
   self.assertEqual(resolve(self.node(),p),(None,False))
 def test_array_path_and_formula(self):
  n={'values':[4,'Label'],'cells':[{'cell':'A2','value':4},{'cell':'B2','value':'Label'}]};self.assertEqual(resolve(n,'values[1]'),('Label',True));n['cells'][1]['formula']='=x';self.assertEqual(resolve(n,'values[1]'),(None,False))
 def test_inconsistent_source_rejected(self):
  n=self.node();n['values']['defect']=5
  with self.assertRaises(ValueError):resolve(n,'values.defect')
 def test_metadata_mismatch_is_not_truth_scoring(self):
  import json
  a={'claims':[{'text':'The cell is A2','kind':'recorded','value':'A2','unit':None,'citations':[{'chunk_id':'n','locator':'A2'}]}]}
  p,m=packet_for(a,[{'chunk_id':'n','text':json.dumps(self.node())}]);self.assertEqual(m[0]['selected_pointer_value'],4)
  x=review(p);y=review(p,'pyshacl');self.assertEqual(x['results'],y['results']);self.assertEqual(next(r['status'] for r in x['results'] if r['check_id']=='value_agreement'),'flag')
 def test_missing_citation_and_empty_claims(self):
  a={'claims':[{'text':'No binding','kind':'recorded','value':4,'unit':None,'citations':[]}]};p,m=packet_for(a,[]);self.assertEqual(len(m),1);self.assertEqual({r['status'] for r in review(p)['results']},{'unknown'})
  p,m=packet_for({'claims':[]},[]);self.assertEqual(review(p)['results'],[])
if __name__=='__main__':unittest.main()
