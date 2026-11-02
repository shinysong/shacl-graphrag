"""Meaningful policy boundaries on independent authored runtime examples."""
import copy
import json
import unittest
from scripts.actionable_evidence.runtime import run, SchemaError, check_schema


def sample():
    return dict(target=dict(id='obs',field='end_mm',unit='mm',version='v1',value=None,minimum=0,maximum=1000),
                nodes=[dict(id='bridge',type='Bridge'),dict(id='ref',type='Reference',entity='obs',field='end_mm',unit='mm',version='v1',value=240,citation='synthetic://independent/source/1')],
                edges=[{'from':'obs','to':'bridge'},{'from':'bridge','to':'ref'}],
                dependencies=[dict(id='dep',target='obs',minimum=100,maximum=300)])


class ActionablePolicyTests(unittest.TestCase):
    def test_depth_ablation_and_full_evidence_parity(self):
        data=sample(); original=json.dumps(data,sort_keys=True)
        direct=run(data,'direct_local_candidate','shadow_revalidation')
        python=run(data,'matched_Python_relation_candidate','shadow_revalidation')
        rules=run(data,'SHACL_AF_relation_candidate','shadow_revalidation')
        self.assertEqual(direct['disposition'],'request_evidence')
        self.assertEqual(python['disposition'],'propose_patch')
        for key in ('candidate','before_report','after_report','diff','disposition'):
            self.assertEqual(python[key],rules[key])
        self.assertEqual(original,json.dumps(data,sort_keys=True))
        self.assertTrue(rules['original_unchanged'])

    def test_dependency_veto_preserves_pre_veto_patch(self):
        data=sample();data['dependencies'][0]['maximum']=230
        unchecked=run(data,'SHACL_AF_relation_candidate','no_postcheck')
        checked=run(data,'SHACL_AF_relation_candidate','shadow_revalidation')
        self.assertEqual(unchecked['candidate'],checked['candidate'])
        self.assertEqual(unchecked['disposition'],'propose_patch')
        self.assertEqual(checked['disposition'],'request_reconciliation')
        self.assertTrue(checked['after_report']['validators_agree'])
        self.assertFalse(checked['after_report']['shacl']['conforms'])

    def test_entity_role_unit_version_filters_and_ambiguity(self):
        for key,value in [('entity','other'),('field','setting'),('unit','cm'),('version','v0')]:
            data=sample();data['nodes'][1][key]=value
            for arm in ('matched_Python_relation_candidate','SHACL_AF_relation_candidate'):
                self.assertEqual(run(data,arm,'shadow_revalidation')['disposition'],'request_evidence')
        data=sample();r=copy.deepcopy(data['nodes'][1]);r['id']='ref2';data['nodes'].append(r)
        data['edges'].append({'from':'bridge','to':'ref2'})
        result=run(data,'SHACL_AF_relation_candidate','shadow_revalidation')
        self.assertEqual(result['disposition'],'request_reconciliation')
        self.assertEqual(result['candidate_reference_ids'],['ref','ref2'])
        self.assertIsNone(result['candidate_patch'])

    def test_schema_rejects_hidden_gold_cycles_and_wrong_numbers(self):
        variants=[]
        a=sample();a['gold']=240;variants.append(a)
        a=sample();a['nodes'][1]['value']=True;variants.append(a)
        a=sample();a['edges'].append({'from':'bridge','to':'obs'});variants.append(a)
        a=sample();a['edges'][0]['to']='missing';variants.append(a)
        a=sample();a['nodes'].append(copy.deepcopy(a['nodes'][1]));variants.append(a)
        for data in variants:
            with self.assertRaises(SchemaError):check_schema(data)

    def test_validation_cannot_detect_external_false_reference(self):
        data=sample();external_truth=240;data['nodes'][1]['value']=250
        result=run(data,'SHACL_AF_relation_candidate','shadow_revalidation')
        self.assertEqual(result['disposition'],'propose_patch')
        self.assertTrue(result['after_report']['shacl']['conforms'])
        self.assertNotEqual(result['candidate_patch']['new'],external_truth)


if __name__=='__main__':unittest.main()
