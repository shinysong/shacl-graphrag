import copy
import unittest
from scripts.postreview_extended import review_extended


def difference():
 return {'kind':'difference','claim':{'value':50,'unit':'A'},'evidence':{'left':{'source_id':'left','value':450,'unit':'A'},'right':{'source_id':'right','value':500,'unit':'A'}}}
def selection():
 return {'kind':'selection','claim':{'selected_ids':['b'],'count':1},'evidence':{'universe_ids':['a','b'],'rows':[{'id':'a','position':106,'label':'Metallic inclusion'},{'id':'b','position':239,'label':'Porosity'}],'lower':100,'upper':250,'target_label':'Porosity'}}
def temporal():
 return {'kind':'temporal','claim':{'state':'selected','selected_id':'v1','latest_ids':['v2']},'evidence':{'event_date':'2025-06-30','scope':'PP6','history_complete':True,'documents':[{'id':'v1','scope':'PP6','valid_from':'2025-01-01','valid_to':'2025-07-01','release_date':'2024-12-20'},{'id':'v2','scope':'PP6','valid_from':'2025-07-01','valid_to':'2026-01-01','release_date':'2025-06-20'}]}}

class ExtendedTests(unittest.TestCase):
 def both(self,p):
  before=copy.deepcopy(p);a=review_extended(p,'python');b=review_extended(p,'pyshacl');self.assertEqual(a['results'],b['results']);self.assertEqual(p,before);return {r['check_id']:r['status'] for r in a['results']}
 def test_signed_difference_and_unit(self):
  p=difference();self.assertEqual(set(self.both(p).values()),{'pass'});p['claim']['value']=-50;p['claim']['unit']='mA';self.assertEqual(set(self.both(p).values()),{'flag'})
 def test_difference_missing_and_mixed_units_unknown(self):
  p=difference();p['evidence']['right']=None;self.assertEqual(set(self.both(p).values()),{'unknown'});p=difference();p['evidence']['right']['unit']='mA';self.assertEqual(set(self.both(p).values()),{'unknown'})
 def test_exact_set_and_count_axes(self):
  p=selection();self.assertEqual(set(self.both(p).values()),{'pass'});p['claim']={'selected_ids':['a'],'count':1};r=self.both(p);self.assertEqual(r['extra_member'],'flag');self.assertEqual(r['missing_member'],'flag');self.assertEqual(r['matching_count'],'pass');self.assertEqual(r['list_count_consistency'],'pass')
 def test_empty_selection_and_missing_universe(self):
  p=selection();p['evidence']['target_label']='absent';p['claim']={'selected_ids':[],'count':0};self.assertEqual(set(self.both(p).values()),{'pass'});p['evidence']['rows'].pop();r=self.both(p);self.assertEqual(r['matching_count'],'unknown');self.assertEqual(r['list_count_consistency'],'pass')
 def test_count_inconsistency(self):
  p=selection();p['claim']['count']=2;r=self.both(p);self.assertEqual(r['matching_count'],'flag');self.assertEqual(r['list_count_consistency'],'flag')
 def test_role_declared_not_nlp(self):
  p={'kind':'role','claim':{'role':'measured'},'evidence':{'declared_role':'nominal'}};self.assertEqual(self.both(p)['declared_role'],'flag');p['evidence']['declared_role']=None;self.assertEqual(self.both(p)['declared_role'],'unknown')
 def test_temporal_interior_and_latest_not_applicable(self):
  p=temporal();self.assertEqual(set(self.both(p).values()),{'pass'});p['claim']['selected_id']='v2';self.assertEqual(self.both(p)['selected_binding'],'flag')
 def test_temporal_boundary_and_wrong_scope(self):
  p=temporal();p['evidence']['event_date']='2025-07-01';p['claim']['selected_id']='v2';p['evidence']['documents'].append({'id':'x','scope':'PP7','valid_from':'2025-01-01','valid_to':'2026-01-01','release_date':'2025-06-29'});self.assertEqual(set(self.both(p).values()),{'pass'})
 def test_overlap_gap_and_incomplete_history(self):
  p=temporal();p['evidence']['documents'][1]['valid_from']='2025-06-01';p['claim'].update(state='ambiguous',selected_id=None);self.assertEqual(set(self.both(p).values()),{'pass'});p['claim'].update(state='selected',selected_id='v1');self.assertEqual(self.both(p)['temporal_state'],'flag');p=temporal();p['evidence']['event_date']='2026-01-01';p['claim'].update(state='unknown',selected_id=None);self.assertEqual(set(self.both(p).values()),{'pass'});p['evidence']['history_complete']=False;self.assertEqual(set(self.both(p).values()),{'unknown'})
 def test_latest_ties_are_sets(self):
  p=temporal();p['evidence']['documents'][0]['release_date']='2025-06-20';p['claim']['latest_ids']=['v1','v2'];self.assertEqual(set(self.both(p).values()),{'pass'});p['claim']['latest_ids']=['v2'];self.assertEqual(self.both(p)['missing_latest'],'flag')
 def test_bad_numeric_dates_duplicates_and_bounds(self):
  cases=[];p=difference();p['claim']['value']=float('nan');cases.append(p);p=selection();p['claim']['selected_ids']=['b','b'];cases.append(p);p=selection();p['evidence']['lower']=300;cases.append(p);p=temporal();p['evidence']['event_date']='2025-02-30';cases.append(p);p=temporal();p['evidence']['documents'][0]['valid_to']='2024-01-01';cases.append(p)
  for p in cases:
   for engine in ('python','pyshacl'):
    with self.assertRaises(ValueError):review_extended(p,engine)
if __name__=='__main__':unittest.main()
