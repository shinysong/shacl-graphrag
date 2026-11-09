import copy,unittest
from rdflib.compare import isomorphic
from rdflib import Graph
from scripts.postreview_native_paths import review_native_paths
from scripts.postreview_lookup import review_lookup

class NativePathsTests(unittest.TestCase):
 def fixture(self):
  a={'source_id':'a','source':{'archive_path':'book','sheet':'data','sha256':'h','excel_row':2,'cells':[{'cell':'B2','value':1}],'header_rows':[],'field_cells':{'welding_setting':'B2'},'dictionary_refs':{'welding_setting':'d'}}}
  d={'source_id':'d','source':{'archive_path':'book','sheet':'settings','sha256':'h','excel_row':3,'cells':[{'cell':'A3','value':1},{'cell':'C3','value':450}],'header_rows':[{'cells':[{'cell':'C2','value':'Idc (A)'}]}]}}
  c={'claim_id':'c','lookup_kind':'nominal_idc','anchor_id':'a','dictionary_id':'d','value':450,'unit':'A'}
  return c,[a,d]
 def both(self,c,s):
  before=copy.deepcopy((c,s));a=review_native_paths(c,s);b=review_native_paths(c,s,'pyshacl');self.assertEqual(a['results'],b['results']);self.assertEqual((c,s),before)
  old=review_lookup(c,s);self.assertEqual({r['check_id']:r['status'] for r in a['results']},{r['check_id']:r['status'] for r in old['results'] if r['check_id']!='declared_unit'});return b
 def test_matching_paths(self):
  c,s=self.fixture();r=self.both(c,s);self.assertTrue(all(x['status']=='pass' for x in r['results']));self.assertTrue(r['raw_shacl_conforms'])
 def test_each_comparison_flags(self):
  mutations=[('declared_reference',lambda c,s:s[0]['source']['dictionary_refs'].update(welding_setting='other')),('dictionary_key',lambda c,s:s[1]['source']['cells'][0].update(value=2)),('lookup_value',lambda c,s:c.update(value=451)),('workbook_hash',lambda c,s:s[1]['source'].update(sha256='other')),('workbook_path',lambda c,s:s[1]['source'].update(archive_path='other')),('declared_header',lambda c,s:s[1]['source']['header_rows'][0]['cells'][0].update(value='other'))]
  for name,mutate in mutations:
   c,s=self.fixture();mutate(c,s);r=self.both(c,s);self.assertEqual({x['check_id'] for x in r['results'] if x['status']=='flag'},{name});self.assertFalse(r['raw_shacl_conforms'])
 def test_missing_evidence_raw_conformance_not_completion(self):
  c,s=self.fixture();r=self.both(c,[]);self.assertTrue(r['raw_shacl_conforms']);self.assertTrue(all(x['status']=='unknown' for x in r['results']))
  r=self.both(c,s[:1]);self.assertEqual(next(x['status'] for x in r['results'] if x['check_id']=='lookup_value'),'unknown')
 def test_formula_and_null_are_unknown(self):
  for change in [{'formula':'=1+1'},{'value':None}]:
   c,s=self.fixture();s[1]['source']['cells'][1].update(change);r=self.both(c,s);self.assertEqual(next(x['status'] for x in r['results'] if x['check_id']=='lookup_value'),'unknown')
 def test_consistent_corruption_passes(self):
  c,s=self.fixture();c['value']=999;s[1]['source']['cells'][1]['value']=999;r=self.both(c,s);self.assertTrue(all(x['status']=='pass' for x in r['results']))
 def test_shapes_stable_and_graph_has_sources(self):
  c,s=self.fixture();a=self.both(c,s);c['value']=999;b=self.both(c,s);self.assertTrue(isomorphic(Graph().parse(data=a['shapes_turtle'],format='turtle'),Graph().parse(data=b['shapes_turtle'],format='turtle')));self.assertIn('sameTerm',a['shapes_turtle']);self.assertNotIn('450',a['shapes_turtle']);self.assertIn('workbookHash',a['data_turtle'])
 def test_strict_types_and_units_outside_scope(self):
  c,s=self.fixture();c['value']=450.0;c['unit']='kA';r=self.both(c,s);self.assertEqual(next(x['status'] for x in r['results'] if x['check_id']=='lookup_value'),'flag');self.assertNotIn('declared_unit',[x['check_id'] for x in r['results']])
 def test_malformed_input_rejected(self):
  c,s=self.fixture();s[1]['source']['header_rows']={}
  for engine in ['python','pyshacl']:
   with self.assertRaises(ValueError):review_native_paths(c,s,engine)
 def test_input_shapes_do_not_include_engine_enrichment(self):
  c,s=self.fixture();a=review_native_paths(c,s);b=review_native_paths(c,s,'pyshacl')
  original=Graph().parse(data=a['shapes_turtle'],format='turtle');frozen=Graph().parse(data=b['shapes_turtle'],format='turtle');effective=Graph().parse(data=b['effective_shapes_turtle'],format='turtle')
  self.assertTrue(isomorphic(original,frozen));self.assertTrue(set(frozen)<=set(effective));self.assertIsNone(a['effective_shapes_turtle'])
if __name__=='__main__':unittest.main()
