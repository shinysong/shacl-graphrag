import copy
import unittest
from scripts.post_answer_review import review, token

class PostAnswerReviewTests(unittest.TestCase):
    def packet(self):
        return {'claims':[{'claim_id':'c1','kind':'recorded','source_id':'s1','field':'current','value':450,'unit':'A'}],
                'sources':[{'source_id':'s1','fields':{'current':{'value':450,'unit':'A','locator':'B2'}}}]}
    def outcomes(self,p):
        before=copy.deepcopy(p); a=review(p); b=review(p,'pyshacl')
        self.assertEqual(a['results'],b['results']); self.assertEqual(p,before)
        return {r['check_id']:r['status'] for r in a['results']}
    def test_matching_and_mismatching_values(self):
        p=self.packet(); self.assertEqual(set(self.outcomes(p).values()),{'pass'})
        p['claims'][0]['value']=451; self.assertEqual(self.outcomes(p)['value_agreement'],'flag')
    def test_source_omission_is_unknown(self):
        p=self.packet();p['sources']=[];self.assertEqual(set(self.outcomes(p).values()),{'unknown'})
    def test_field_omission(self):
        p=self.packet();p['sources'][0]['fields']={};r=self.outcomes(p)
        self.assertEqual(r['source_binding'],'pass'); self.assertEqual(r['field_binding'],'unknown')
    def test_units_and_missing_units(self):
        p=self.packet();p['claims'][0]['unit']='mA';self.assertEqual(self.outcomes(p)['unit_agreement'],'flag')
        p['claims'][0]['unit']=None;self.assertEqual(self.outcomes(p)['unit_agreement'],'unknown')
        p['sources'][0]['fields']['current']['unit']=None;self.assertEqual(self.outcomes(p)['unit_agreement'],'unknown')
    def test_derived_is_not_checked(self):
        p=self.packet();p['claims'][0]['kind']='derived';p['claims'][0]['value']=999
        self.assertEqual(set(self.outcomes(p).values()),{'not_applicable'})
    def test_exact_types_no_coercion(self):
        for wrong in ['450',450.0,True]:
            p=self.packet();p['claims'][0]['value']=wrong;self.assertEqual(self.outcomes(p)['value_agreement'],'flag')
    def test_missing_value_unknown(self):
        for side in ('claim','source'):
            p=self.packet()
            if side=='claim':p['claims'][0]['value']=None
            else:p['sources'][0]['fields']['current']['value']=None
            self.assertEqual(self.outcomes(p)['value_agreement'],'unknown')
    def test_duplicate_ids_rejected(self):
        for collection in ('claims','sources'):
            p=self.packet();p[collection].append(copy.deepcopy(p[collection][0]))
            for engine in ('python','pyshacl'):
                with self.assertRaises(ValueError):review(p,engine)
    def test_injection_strings_are_literals(self):
        p=self.packet();s='"; DROP GRAPH <urn:x>; #\n';p['claims'][0]['value']=s;p['sources'][0]['fields']['current']['value']=s
        self.assertEqual(self.outcomes(p)['value_agreement'],'pass')
    def test_invalid_scalar_and_unknown_engine(self):
        for value in [[],{},float('nan'),float('inf')]:
            with self.assertRaises(ValueError):token(value)
        with self.assertRaises(ValueError):review(self.packet(),'other')
    def test_empty_packet_not_successful_answer(self):
        p={'claims':[],'sources':[]};b=review(p,'pyshacl')
        self.assertEqual(b['executed_checks'],0);self.assertEqual(b['results'],[])

if __name__=='__main__':unittest.main()
