import unittest
from pathlib import Path
from rdflib import Graph
from scripts.backend_advisory import python_report,shacl_report
SHAPES=Path('research/backend-reasoning-review-1/advisory-contracts-001/shapes.ttl')
class AdvisoryTests(unittest.TestCase):
    def test_published_metadata_limits_and_policy_parity(self):
        g=Graph().parse(SHAPES,format='turtle')
        cases=[({'used_input_hash':'a'*64,'current_input_hash':'a'*64},[]),({'used_input_hash':'a'*64,'current_input_hash':'b'*64},['fingerprint_disagreement_review_scope']),({},['missing_current_fingerprint','missing_used_fingerprint']),({'used_input_hash':'a'*64},['fingerprint_disagreement_review_scope','missing_current_fingerprint']),({'used_input_hash':'bad','current_input_hash':'bad'},['malformed_current_fingerprint','malformed_used_fingerprint'])]
        for metadata,expected in cases:
            self.assertEqual(python_report(metadata),expected)
            result=shacl_report(metadata,g);self.assertEqual(result['codes'],expected);self.assertEqual(result['conforms'],not expected)
    def test_answer_truth_is_not_checker_input(self):
        metadata={'used_input_hash':'a'*64,'current_input_hash':'a'*64}
        self.assertEqual(python_report(metadata),[])
        self.assertEqual(shacl_report(metadata,Graph().parse(SHAPES,format='turtle'))['codes'],[])
if __name__=='__main__':unittest.main()
