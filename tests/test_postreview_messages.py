import copy,json,unittest
from jsonschema import ValidationError
from scripts.postreview_messages import messages

class PostreviewMessagesTests(unittest.TestCase):
 def fixture(self):
  d={'answer':'Recorded value is 4.','status':'answered','claims':[{'claim_id':'c','text':'Recorded value is 4.','kind':'recorded','source_id':'s','field':'value','value':4,'unit':None}],'limitations':[]}
  s=[{'source_id':'s','fields':{'value':{'value':4,'unit':None,'locator':'sheet/A2'}}}]
  return d,s
 def test_equal_engine_messages_and_no_mutation(self):
  d,s=self.fixture();before=copy.deepcopy((d,s));a=messages('value?',d,s);b=messages('value?',d,s,engine='pyshacl')
  self.assertEqual(a['messages'],b['messages']);self.assertEqual(a['response_schema'],b['response_schema']);self.assertEqual(a['normalized_report_sha256'],b['normalized_report_sha256']);self.assertEqual((d,s),before)
 def test_self_review_same_context(self):
  d,s=self.fixture();a=messages('value?',d,s);b=messages('value?',d,s,'self_review')
  self.assertEqual(a['messages'][0],b['messages'][0]);x=json.loads(a['messages'][1]['content']);y=json.loads(b['messages'][1]['content']);self.assertIsNone(y.pop('review_report'));self.assertIsNotNone(x.pop('review_report'));self.assertEqual(x,y)
 def test_empty_claims_not_whole_answer_pass(self):
  d,s=self.fixture();d['claims']=[];r=json.loads(messages('value?',d,s)['messages'][1]['content'])['review_report'];self.assertEqual(r['results'],[]);self.assertIn('unverified',r['coverage']);self.assertNotIn('conforms',r)
 def test_wrong_binding_and_derived_preserved(self):
  d,s=self.fixture();d['claims'][0]['source_id']='missing';a=messages('value?',d,s);r=json.loads(a['messages'][1]['content'])['review_report'];self.assertEqual({x['status'] for x in r['results']},{'unknown'})
  d['claims'][0]['kind']='derived';r=json.loads(messages('value?',d,s)['messages'][1]['content'])['review_report'];self.assertEqual({x['status'] for x in r['results']},{'not_applicable'})
 def test_malformed_or_duplicate_claims_rejected(self):
  d,s=self.fixture();d['claims'].append(copy.deepcopy(d['claims'][0]))
  with self.assertRaises(ValueError):messages('value?',d,s)
  d['claims'][0]['value']={'compound':4}
  with self.assertRaises(ValidationError):messages('value?',d,s)
if __name__=='__main__':unittest.main()
