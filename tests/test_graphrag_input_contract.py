import hashlib
import unittest
from scripts.graphrag_check import canonical_bytes
from scripts.graphrag_input_contract import ARMS, COVERAGE, prepare_bundle, account_bundle


def fixture():
    e={'question_id':'q','status':'ok','selected_chunks':[],'selected_chunk_ids':[],
       'evidence_sha256':hashlib.sha256(canonical_bytes([])).hexdigest()}
    r={'raw_conforms':True,'results':[],'applicable_bindings':0,'coverage':COVERAGE,'no_bindings_status':'unknown'}
    return {'question_id':'q','question':'Find the record.'},{a:dict(e) for a in ARMS},r


class ContractTests(unittest.TestCase):
    def test_messages_and_vacuous_status(self):
        q,e,r=fixture();m=prepare_bundle(q,e,r)
        self.assertEqual(m['A1'],m['C']);self.assertEqual(m['C'],m['E'])
        self.assertIn('unknown',m['D'][1]['content'])
        self.assertEqual(m['C'][0],m['D'][0])

    def test_failed_retrieval_and_question_rejected(self):
        for field,value in [('status','error'),('question_id','other')]:
            q,e,r=fixture();e['A1'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):prepare_bundle(q,e,r)

    def test_missing_report_or_arm_rejected(self):
        q,e,r=fixture();r.pop('coverage')
        with self.assertRaises(ValueError):prepare_bundle(q,e,r)
        q,e,r=fixture();e.pop('B')
        with self.assertRaises(ValueError):prepare_bundle(q,e,r)

    def test_inclusive_budget_no_mutation(self):
        q,e,r=fixture();m=prepare_bundle(q,e,r);before=canonical_bytes(m)
        result=account_bundle(m,lambda _:4096)
        self.assertTrue(result['all_arms_within_accounting_cap']);self.assertFalse(result['generator_ready'])
        result=account_bundle(m,lambda _:4097)
        self.assertFalse(result['all_arms_within_accounting_cap']);self.assertEqual(before,canonical_bytes(m))
        result=account_bundle(m,lambda _:0,byte_cap=1)
        self.assertFalse(result['all_arms_within_accounting_cap'])

    def test_invalid_counter_rejected(self):
        q,e,r=fixture();m=prepare_bundle(q,e,r)
        for count in [True,-1,1.2]:
            with self.subTest(count=count),self.assertRaises(ValueError):account_bundle(m,lambda _:count)

    def test_malformed_report(self):
        for field,value in [('raw_conforms',None),('results',None),('applicable_bindings',True),
                            ('coverage',''),('no_bindings_status','pass')]:
            q,e,r=fixture();r[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):prepare_bundle(q,e,r)

    def test_different_valid_evidence(self):
        q,e,r=fixture()
        chunks=[{'chunk_id':'node:n','chunk_type':'node','node_id':'n','text':'{"id":"n"}'}]
        e['D'].update(selected_chunks=chunks,selected_chunk_ids=['node:n'],evidence_sha256=hashlib.sha256(canonical_bytes(chunks)).hexdigest())
        with self.assertRaisesRegex(ValueError,'C/D/E evidence mismatch'):prepare_bundle(q,e,r)
