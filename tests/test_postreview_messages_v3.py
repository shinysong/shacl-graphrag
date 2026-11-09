import copy,json
import unittest
from unittest.mock import patch
from scripts.postreview_messages_v3 import build_messages,validate_draft
from scripts.postreview_source_pack import unpack_sources
from tests import test_postreview_declarations as fixtures

class MessageTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):fixtures.DeclarationTests.setUpClass();cls.context={**fixtures.DeclarationTests.context,'history':None,'policies':['same workbook']}
 def draft(self):return {'answer':'Authored answer','claims':[{'claim_id':'c','text':'position','kind':'recorded','declaration':{'source_id':'PP6:2','field':'x_init_mm','value':107,'unit':'mm'}}],'limitations':[]}
 def test_same_draft_evidence_system(self):
  d=self.draft();ctx=copy.deepcopy(self.context);before=copy.deepcopy((d,ctx));a=build_messages('question',ctx,'self_review',d);b=build_messages('question',ctx,'report',d)
  x,y=[json.loads(r['messages'][1]['content']) for r in [a,b]]
  self.assertEqual(a['messages'][0],b['messages'][0]);self.assertEqual(x['draft'],y['draft']);self.assertEqual(x['selected_context'],y['selected_context']);self.assertIsNone(x['review_report']);self.assertIsNotNone(y['review_report']);self.assertEqual((d,ctx),before)
  self.assertIn('flag',[v['status'] for c in y['review_report']['claims'] for v in c['results']]);self.assertNotIn('data_turtle',str(y))
 def test_self_review_independent_of_checker_failure(self):
  with patch('scripts.postreview_messages_v3.review_declarations',side_effect=RuntimeError('checker unavailable')):
   self.assertIsNone(build_messages('q',self.context,'self_review',self.draft())['review_artifact'])
   with self.assertRaises(RuntimeError):build_messages('q',self.context,'report',self.draft())
 def test_packed_context_roundtrip(self):
  r=build_messages('q',self.context,representation='packed');p=json.loads(r['messages'][1]['content']);self.assertEqual(unpack_sources(p['selected_context']['sources']),self.context['sources']);self.assertIsNone(p['draft']);self.assertIsNone(p['review_report'])
 def test_reject_control_leak_and_invalid_draft(self):
  ctx=copy.deepcopy(self.context);ctx['expected']='gold'
  with self.assertRaises(ValueError):build_messages('q',ctx)
  with self.assertRaises(ValueError):build_messages('q',self.context,draft=self.draft())
  d=self.draft();d['claims'].append(copy.deepcopy(d['claims'][0]))
  with self.assertRaises(ValueError):validate_draft(d)
 def test_report_engine_parity(self):
  a=build_messages('q',self.context,'report',self.draft(),engine='python');b=build_messages('q',self.context,'report',self.draft(),engine='pyshacl');self.assertEqual(a['messages'],b['messages']);self.assertEqual(a['message_sha256'],b['message_sha256'])
if __name__=='__main__':unittest.main()
