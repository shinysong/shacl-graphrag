import copy,unittest
from scripts.postreview_lookup import review_lookup

class LookupReviewTests(unittest.TestCase):
 def fixture(self):
  sources=[{'source_id':'a','source':{'archive_path':'book','sheet':'data','sha256':'hash1','cells':[{'cell':'B2','value':1}],'header_rows':[],'dictionary_refs':{'welding_setting':'d'},'field_cells':{'welding_setting':'B2'}}}, {'source_id':'d','source':{'archive_path':'book','sheet':'settings','sha256':'hash1','excel_row':3,'cells':[{'cell':'A3','value':1},{'cell':'C3','value':450}],'header_rows':[{'cells':[{'cell':'C2','value':'Idc (A)'}]}]}}]
  claim={'claim_id':'c','lookup_kind':'nominal_idc','anchor_id':'a','dictionary_id':'d','value':450,'unit':'A'}
  return claim,sources
 def check(self,c,s):
  before=copy.deepcopy((c,s));a=review_lookup(c,s);b=review_lookup(c,s,'pyshacl');self.assertEqual(a['results'],b['results']);self.assertEqual((c,s),before);return {r['check_id']:r['status'] for r in a['results']}
 def test_matching(self):
  c,s=self.fixture();self.assertEqual(set(self.check(c,s).values()),{'pass'})
 def test_value_and_unit_mismatches(self):
  c,s=self.fixture();c.update(value=451,unit='mA');r=self.check(c,s);self.assertEqual(r['lookup_value'],'flag');self.assertEqual(r['declared_unit'],'flag')
 def test_reference_and_key_mismatches(self):
  c,s=self.fixture();s[0]['source']['dictionary_refs']['welding_setting']='other';s[1]['source']['cells'][0]['value']=2;r=self.check(c,s);self.assertEqual(r['declared_reference'],'flag');self.assertEqual(r['dictionary_key'],'flag')
 def test_missing_target(self):
  c,s=self.fixture();r=self.check(c,s[:1]);self.assertEqual(r['declared_reference'],'pass');self.assertEqual(r['lookup_value'],'unknown')
 def test_missing_anchor(self):
  c,s=self.fixture();r=self.check(c,s[1:]);self.assertEqual(r['declared_reference'],'unknown');self.assertEqual(r['lookup_value'],'pass')
 def test_namespace_and_header(self):
  c,s=self.fixture();s[1]['source']['sha256']='hash2';s[1]['source']['header_rows'][0]['cells'][0]['value']='Other';r=self.check(c,s);self.assertEqual(r['workbook_hash'],'flag');self.assertEqual(r['declared_header'],'flag');self.assertEqual(r['declared_unit'],'unknown')
 def test_formula_is_unknown(self):
  c,s=self.fixture();s[1]['source']['cells'][1]['formula']='=other';self.assertEqual(self.check(c,s)['lookup_value'],'unknown')
 def test_false_but_consistent_not_detected(self):
  c,s=self.fixture();c['value']=999;s[1]['source']['cells'][1]['value']=999;self.assertEqual(self.check(c,s)['lookup_value'],'pass')
 def test_path_and_header_formula(self):
  c,s=self.fixture();s[1]['source']['archive_path']='other';s[1]['source']['header_rows'][0]['cells'][0]['formula']='=header';r=self.check(c,s);self.assertEqual(r['workbook_path'],'flag');self.assertEqual(r['declared_header'],'unknown');self.assertEqual(r['declared_unit'],'unknown')
 def test_duplicates_and_unknown_kind(self):
  c,s=self.fixture()
  with self.assertRaises(ValueError):review_lookup(c,s+s)
  c['lookup_kind']='anything'
  with self.assertRaises(ValueError):review_lookup(c,s)
 def test_defect_label(self):
  c,s=self.fixture();c.update(lookup_kind='defect_label',value='Porosity',unit=None)
  s[0]['source']['dictionary_refs']={'defect':'d'};s[0]['source']['field_cells']={'defect':'B2'}
  s[1]['source']['cells'][1]={'cell':'B3','value':'Porosity'};s[1]['source']['header_rows']=[{'cells':[{'cell':'B1','value':'Defect'}]}]
  self.assertEqual(set(self.check(c,s).values()),{'pass'})
  c['value']='Other';self.assertEqual(self.check(c,s)['lookup_value'],'flag')
 def test_anchor_and_key_formulas(self):
  for source,cell in [(0,0),(1,0)]:
   c,s=self.fixture();s[source]['source']['cells'][cell]['formula']='=unknown';self.assertEqual(self.check(c,s)['dictionary_key'],'unknown')
 def test_malformed_supported_source_fields(self):
  mutations=[('header_rows',{}),('header_rows',''),('header_rows',[{}]),('header_rows',[{'cells':{}}]),('dictionary_refs',[]),('field_cells',{'x':5}),('excel_row',False),('cells',[{'cell':1,'value':1}]),('cells',[{'cell':'Z9','value':[]}]),('cells',[{'cell':'Z9','value':1,'formula':3}])]
  for key,value in mutations:
   for engine in ('python','pyshacl'):
    c,s=self.fixture();s[1]['source'][key]=value
    with self.subTest(key=key,value=value,engine=engine):
     with self.assertRaises((ValueError,TypeError)):review_lookup(c,s,engine)
if __name__=='__main__':unittest.main()
