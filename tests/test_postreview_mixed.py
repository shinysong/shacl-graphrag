import copy,json,unittest
from unittest.mock import patch
from scripts.postreview_mixed import mixed_review,prepare_messages

class MixedReviewTests(unittest.TestCase):
 def fixture(self):
  sources=[{'source_id':'a','source':{'archive_path':'book','sheet':'data','sha256':'h','values':{'welding_setting':1,'x_init_mm':106},'cells':[{'cell':'B2','value':1},{'cell':'D2','value':106}],'header_rows':[{'cells':[{'cell':'D1','value':'x_init [mm]'}]}],'field_cells':{'welding_setting':'B2','x_init_mm':'D2'},'dictionary_refs':{'welding_setting':'d'}}},{'source_id':'d','source':{'archive_path':'book','sheet':'settings','sha256':'h','excel_row':3,'values':[1,27,450],'cells':[{'cell':'A3','value':1},{'cell':'B3','value':27},{'cell':'C3','value':450}],'header_rows':[{'cells':[{'cell':'C2','value':'Idc (A)'}]}]}}]
  base={'claim_id':'c','text':'authored fixture','kind':'recorded','source_id':'a','field':'x_init_mm','value':106,'unit':'mm','anchor_id':None,'dictionary_id':None,'lookup_kind':None}
  lookup={**base,'claim_id':'l','kind':'lookup','source_id':None,'field':None,'value':450,'unit':'A','anchor_id':'a','dictionary_id':'d','lookup_kind':'nominal_idc'}
  derived={**base,'claim_id':'i','kind':'derived','source_id':None,'field':None,'value':None,'unit':None}
  return {'answer':'Authored example only.','status':'partial','claims':[base,lookup,derived],'limitations':['No truth check']},sources
 def both(self,d,s):
  old=copy.deepcopy((d,s));a=mixed_review(d,s);b=mixed_review(d,s,'pyshacl');self.assertEqual(a['normalized_report'],b['normalized_report']);self.assertEqual((d,s),old);return a['normalized_report']['results']
 def test_mixed_declared_scopes(self):
  d,s=self.fixture();r=self.both(d,s);self.assertEqual(len(r),12);self.assertEqual([x['status'] for x in r].count('pass'),11);self.assertEqual(r[-1]['status'],'not_applicable')
 def test_value_unit_and_missing_header(self):
  d,s=self.fixture();d['claims'][0].update(value=107,unit='cm');r=self.both(d,s);self.assertEqual(sum(x['status']=='flag' for x in r),2)
  s[0]['source']['header_rows']=[];r=self.both(d,s);self.assertEqual(next(x['status'] for x in r if x['claim_id']=='c' and x['check_id']=='unit_agreement'),'unknown')
 def test_missing_lookup_declaration_and_evidence(self):
  d,s=self.fixture();d['claims'][1]['dictionary_id']=None;r=self.both(d,s);self.assertEqual(next(x['status'] for x in r if x['claim_id']=='l'),'unknown')
  d,s=self.fixture();r=self.both(d,s[:1]);self.assertEqual(next(x['status'] for x in r if x['claim_id']=='l' and x['check_id']=='lookup_value'),'unknown')
 def test_misclassified_claim_remains_unverified(self):
  d,s=self.fixture();c=d['claims'][1];c.update(kind='derived',lookup_kind=None,anchor_id=None,dictionary_id=None,value=999);r=self.both(d,s);self.assertEqual(next(x['status'] for x in r if x['claim_id']=='l'),'not_applicable')
 def test_invalid_binding_and_duplicate_claims(self):
  for mode in ['unused','blank','duplicate','bad_source']:
   d,s=self.fixture()
   if mode=='unused':d['claims'][0]['anchor_id']='a'
   if mode=='blank':d['claims'][0]['field']=' '
   if mode=='duplicate':d['claims'].append(copy.deepcopy(d['claims'][0]))
   if mode=='bad_source':s[0]['source']['values']='unsupported'
   with self.assertRaises(ValueError):mixed_review(d,s)
 def test_messages_engine_equal_and_context_matched(self):
  d,s=self.fixture();a=prepare_messages('Question',d,s);b=prepare_messages('Question',d,s,engine='pyshacl');c=prepare_messages('Question',d,s,'self_review');self.assertEqual(a['messages'],b['messages']);self.assertEqual(a['messages'][0],c['messages'][0]);x=json.loads(a['messages'][1]['content']);y=json.loads(c['messages'][1]['content']);self.assertIsNotNone(x.pop('review_report'));self.assertIsNone(y.pop('review_report'));self.assertEqual(x,y)
 def test_empty_claims_no_verdict(self):
  d,s=self.fixture();d['claims']=[];r=mixed_review(d,s)['normalized_report'];self.assertEqual(r['results'],[]);self.assertIn('unverified',r['coverage']);self.assertNotIn('conforms',r)
 def test_self_review_survives_checker_failure(self):
  d,s=self.fixture()
  with patch('scripts.postreview_mixed.mixed_review',side_effect=RuntimeError('checker unavailable')) as checker:
   result=prepare_messages('Question',d,s,'self_review');checker.assert_not_called();self.assertIsNone(result['review_artifact'])
   with self.assertRaises(RuntimeError):prepare_messages('Question',d,s,'report')
 def test_schema_valid_bad_binding_remains_self_review_input(self):
  d,s=self.fixture();d['claims'][0]['anchor_id']='invalid unused binding'
  result=prepare_messages('Question',d,s,'self_review');self.assertEqual(json.loads(result['messages'][1]['content'])['draft'],d)
  with self.assertRaises(ValueError):prepare_messages('Question',d,s,'report')
if __name__=='__main__':unittest.main()
