"""Source display regression, not policy interpretation or agreement scoring."""
import unittest
from copy import deepcopy
from apps.factory_lab import preparation as p, policy_inputs
from tests.test_preparation import approved

class PolicyInputTests(unittest.TestCase):
 def test_only_unique_approved_fields_include_exact_source_values(self):
  draft=approved();before=deepcopy(draft)
  results=policy_inputs.describe(draft,p.POLICIES)
  minimum=results['shipping']['fields'][0]
  self.assertEqual(minimum['field'],'shipping_policies.minimum')
  self.assertEqual(minimum['records'],[{'value':'50000','record':1,'line_start':2,'line_end':2}])
  source=next(s for s in draft['sources'] if s['name']=='shipping_policies.csv')
  self.assertEqual(minimum['source']['sha256'],source['sha256'])
  self.assertEqual(draft,before)
  mapping=next(e for e in draft['entries'] if e['target']=='shipping_policies.minimum' and e['kind']=='mapping')
  mapping['status']='pending'
  self.assertEqual(policy_inputs.describe(draft,p.POLICIES)['shipping']['fields'][0]['records'],[])
  mapping['status']='approved';draft['entries'].append(deepcopy(mapping))
  ambiguous=policy_inputs.describe(draft,p.POLICIES)['shipping']['fields'][0]
  self.assertEqual(ambiguous['state'],'ambiguous');self.assertEqual(ambiguous['records'],[])
 def test_document_amount_does_not_rewrite_structured_values(self):
  draft=approved()
  entry=next(e for e in draft['entries'] if e['kind']=='policy' and e['target']=='shipping')
  entry['source']['text']='무료배송 기준은 7만 원입니다.'
  # Deliberate in-memory display input, not an importable or approved fixture.
  minimum=policy_inputs.describe(draft,p.POLICIES)['shipping']['fields'][0]
  self.assertEqual(minimum['records'][0]['value'],'50000')
  self.assertNotIn('agreement',minimum)
