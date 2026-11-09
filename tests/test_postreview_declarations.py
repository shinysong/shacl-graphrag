import copy,json
from pathlib import Path
import unittest
from scripts.postreview_declarations import review_declarations

class DeclarationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  c=json.loads(Path('research/refined-hybrid-1/neo4j-source-001/frozen/source-corpus-v1.json').read_text());nodes={json.loads(x['text'])['id']:json.loads(x['text']) for x in c['chunks'] if x['chunk_type']=='node'}
  cls.context={'sources':[nodes[k] for k in ['PP6:2','PP6:12','PP6:defect_code:4','PP6:defect_code:1','PP6:welding_settings_code:1','PP6:welding_settings_code:3']], 'role_catalog':{'PP6:welding_settings_code:1':'nominal'}}
 def claim(self,kind,d,text='Authored software claim'):return {'claim_id':'c','text':text,'kind':kind,'declaration':d}
 def both(self,c,context=None,expected_state='completed'):
  draft={'answer':'Authored answer','claims':[c],'limitations':[]};context=copy.deepcopy(context or self.context);before=copy.deepcopy((draft,context));reports=[review_declarations(draft,context,e) for e in ['python','pyshacl']]
  self.assertEqual(reports[0]['claims'][0]['state'],expected_state);self.assertEqual(reports[1]['claims'][0]['state'],expected_state);
  if expected_state=='completed':self.assertTrue(reports[0]['claims'][0]['results']);self.assertTrue(reports[1]['claims'][0]['results'])
  self.assertEqual(reports[0]['claims'][0]['results'],reports[1]['claims'][0]['results']);self.assertEqual((draft,context),before);return reports[0]['claims'][0]
 def test_recorded_and_lookup(self):
  r=self.both(self.claim('recorded',{'source_id':'PP6:2','field':'x_init_mm','value':107,'unit':'mm'}));self.assertIn('flag',[x['status'] for x in r['results']])
  r=self.both(self.claim('lookup',{'anchor_id':'PP6:2','dictionary_id':'PP6:defect_code:4','lookup_kind':'defect_label','value':'Metallic inclusion','unit':None}));self.assertTrue(all(x['status']=='pass' for x in r['results']))
 def test_difference(self):
  d={'left':{'anchor_id':'PP6:2','dictionary_id':'PP6:welding_settings_code:1','value':450,'unit':'A'},'right':{'anchor_id':'PP6:12','dictionary_id':'PP6:welding_settings_code:3','value':500,'unit':'A'},'value':50,'unit':'A'}
  r=self.both(self.claim('difference',d));self.assertTrue(all(x['status']=='pass' for x in r['results']));d['value']=-50;r=self.both(self.claim('difference',d));self.assertIn('signed_difference',[x['check_id'] for x in r['results'] if x['status']=='flag'])
 def test_selection_and_missing_dictionary(self):
  c=self.claim('selection',{'universe_ids':['PP6:2','PP6:12'],'lower':100,'upper':250,'target_label':'Porosity','selected_ids':['PP6:12'],'count':1});r=self.both(c);self.assertTrue(all(x['status']=='pass' for x in r['results']))
  context=copy.deepcopy(self.context);context['sources']=[s for s in context['sources'] if s['id']!='PP6:defect_code:1'];r=self.both(c,context);self.assertIn('unknown',[x['status'] for x in r['results']])
 def test_role_prose_blindspot_and_forged_evidence(self):
  r=self.both(self.claim('role',{'source_id':'PP6:welding_settings_code:1','role':'nominal'},'actually measured'));self.assertEqual(r['results'][0]['status'],'pass')
  r=self.both(self.claim('role',{'source_id':'PP6:welding_settings_code:1','role':'nominal','evidence':{'declared_role':'measured'}}),expected_state='input_failure');self.assertEqual(r['state'],'input_failure')
 def test_temporal_and_missing_history(self):
  d={'event_date':'2025-06-30','scope':'PP6','state':'selected','selected_id':'v1','latest_ids':['v1']};r=self.both(self.claim('temporal',d));self.assertTrue(all(x['status']=='unknown' for x in r['results']))
  context=copy.deepcopy(self.context);context['history']={'history_complete':True,'documents':[{'id':'v1','scope':'PP6','valid_from':'2025-01-01','valid_to':'2026-01-01','release_date':'2024-12-01'}]};r=self.both(self.claim('temporal',d),context);self.assertTrue(all(x['status']=='pass' for x in r['results']))
 def test_failure_kept_and_other_claim_continues(self):
  c=self.claim('role',{'source_id':'PP6:2'});good=self.claim('unverified',{});good['claim_id']='d';draft={'answer':'fixture','claims':[c,good],'limitations':[]};r=review_declarations(draft,self.context);self.assertEqual([x['state'] for x in r['claims']],['input_failure','completed']);self.assertFalse(r['answer_modified'])
 def test_empty_claims_and_duplicate_ids(self):
  d={'answer':'fixture','claims':[],'limitations':[]};self.assertEqual(review_declarations(d,self.context)['declared_claim_count'],0)
  c=self.claim('unverified',{});d['claims']=[c,c]
  with self.assertRaises(ValueError):review_declarations(d,self.context)
if __name__=='__main__':unittest.main()
