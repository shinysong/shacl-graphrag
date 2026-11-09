import unittest
import json
from decimal import Decimal
from scripts.source_semantics import classify, valid_response
from scripts.run_source_semantics import assess, used


class SourceSemantics(unittest.TestCase):
    def test_missing_fields_have_distinct_meanings(self):
        doc={'components':[{'bom-ref':'x'}]}
        schema={'definitions':{'component':{'properties':{'scope':{'default':'required'}}}}}
        self.assertEqual(classify(doc,'x','consumer_scope',schema),'required')
        self.assertEqual(classify(doc,'x','dependency_knowledge',schema),'unknown')
        doc['dependencies']=[{'ref':'x'}]
        self.assertEqual(classify(doc,'x','dependency_knowledge',schema),'explicit_empty')
        doc['components'][0]['scope']='optional'
        self.assertEqual(classify(doc,'x','consumer_scope',schema),'optional')
        self.assertEqual(classify(doc,'x','external_claim',schema),'not_established')

    def test_response_boundary_does_not_assess_explanation_truth(self):
        self.assertTrue(valid_response({'classification':'required','basis':'Unsupported explanation can pass this structure check.'}))
        self.assertFalse(valid_response({'classification':[], 'basis':'x'}))
        self.assertFalse(valid_response({'classification':'required','basis':' '}))

    def test_invalid_structure_keeps_full_reservation(self):
        provider={'model':'m','provider':'p'}
        def data(answer):
            return {'model':'m','provider':'p','usage':{'cost':0.01,'prompt_tokens':10,'completion_tokens':20},
                    'choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer)}}]}
        for answer in [{}, {'classification':'required','basis':''}, {'classification':'bad','basis':'x'}]:
            r=assess(data(answer),provider,100,Decimal('1'))
            self.assertEqual(r['status'],'output_failure')
            self.assertEqual(used({'reservations':[{'state':'resolved','reserved_usd':'1',**r}]}),Decimal('1'))
        wrong={'classification':'excluded','basis':'A valid label can still be wrong for the question.'}
        r=assess(data(wrong),provider,100,Decimal('1'))
        self.assertEqual(r['status'],'completed');self.assertEqual(r['contract'],wrong)
