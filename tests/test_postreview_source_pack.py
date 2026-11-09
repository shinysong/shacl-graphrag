import copy
import unittest
from scripts.postreview_source_pack import pack_sources,unpack_sources

class SourcePackTests(unittest.TestCase):
 def fixture(self):return [{'id':'a','archive_path':'file','sha256':'hash','sheet':'sheet','header_rows':[{'cells':[{'cell':'A1','value':'unit'}]}],'cells':[{'cell':'A2','value':None,'formula':'=1','cached_value':1},{'cell':'B2','value':2}],'values':{'x':None}}, {'id':'b','archive_path':'file','sha256':'hash','sheet':'sheet','header_rows':[{'cells':[{'cell':'A1','value':'unit'}]}],'cells':[]}, {'id':'synthetic','documents':[{'value':None}]}]
 def test_roundtrip_and_template_reuse(self):
  source=self.fixture();before=copy.deepcopy(source);packed=pack_sources(source);self.assertEqual(unpack_sources(packed),source);self.assertEqual(len(packed['worksheet_templates']),2);self.assertEqual(source,before)
 def test_missing_null_and_empty_distinct(self):
  source=[{}, {'cells':[]},{'cells':[{}, {'value':None}]}];self.assertEqual(unpack_sources(pack_sources(source)),source)
 def test_detached_copy(self):
  s=self.fixture();p=pack_sources(s);p['worksheet_templates'][0]['header_rows'][0]['cells'][0]['value']='changed';self.assertEqual(s[0]['header_rows'][0]['cells'][0]['value'],'unit')
 def test_invalid_table_and_ref(self):
  for mode in ['index','boolindex','row','mask','duplicate','collision']:
   p=pack_sources(self.fixture())
   if mode=='index':p['records'][0]['worksheet_template']=-1
   if mode=='boolindex':p['records'][0]['worksheet_template']=True
   if mode=='row':p['records'][0]['cell_table']['rows'][0].pop()
   if mode=='mask':p['records'][0]['cell_table']['present'][0][0]=1
   if mode=='duplicate':p['records'][0]['cell_table']['columns'][0]=p['records'][0]['cell_table']['columns'][1]
   if mode=='collision':p['records'][0]['record']['sheet']='other'
   with self.assertRaises(ValueError):unpack_sources(p)
if __name__=='__main__':unittest.main()
