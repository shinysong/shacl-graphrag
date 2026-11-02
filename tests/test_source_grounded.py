import copy
import unittest
from scripts.source_grounded.generate import base, cases
from scripts.source_grounded.runtime import python_candidates, sql_candidates, rdf_candidates, python_conforms, shacl_conforms


class SourceGroundedTests(unittest.TestCase):
    def assert_parity(self, payload, expected):
        for fn in (python_candidates, sql_candidates, rdf_candidates):
            self.assertEqual(fn(payload), expected, fn.__name__)

    def test_generated_contracts_and_validation(self):
        for payload, reference in cases():
            with self.subTest(case=reference['id']):
                self.assert_parity(payload, reference['contract_candidates'])
                self.assertEqual(python_conforms(payload), reference['expected_conforms'])
                self.assertEqual(shacl_conforms(payload)[0], reference['expected_conforms'])

    def test_causes_are_not_visible(self):
        pending = {}
        for payload, reference in cases():
            key = (reference['source'], reference['family'])
            if reference['state'] == 'source_absence':
                pending[key] = payload
            if reference['state'] == 'retrieval_omission':
                self.assertEqual(payload, pending[key])

    def test_cycle_terminates_and_role_is_not_material(self):
        records, question, expected, _, ident = base('hinge', 2)
        records += [dict(id=ident('cycle'), type='Event', input=ident('n2'), output=ident('n0')),
                    dict(id=ident('decoy'), type='Product'),
                    dict(id=ident('work'), type='Event', input=ident('decoy'), output=ident('decoy'), with_role=ident('n0'))]
        payload = dict(source='hinge', records=records, question=question)
        self.assert_parity(payload, expected)

    def test_equal_time_not_strictly_earlier(self):
        records, question, _, _, _ = base('bpi', 0)
        records[1]['time'] = records[2]['time']
        self.assert_parity(dict(source='bpi', records=records, question=question), [])

    def test_wrong_datatype_and_wrong_reference_class(self):
        records, question, _, _, _ = base('penelope', 0)
        for mutation in ('datatype', 'class'):
            changed = copy.deepcopy(records)
            if mutation == 'datatype':
                changed[1]['current'] = '400'
            else:
                changed[2]['setting'] = changed[0]['id']
            payload = dict(source='penelope', records=changed, question=question)
            self.assertFalse(python_conforms(payload))
            self.assertFalse(shacl_conforms(payload)[0])

    def test_wrong_fact_is_structurally_valid(self):
        examples = [(p, e) for p, e in cases() if e['state'] == 'false_fact']
        self.assertEqual(len(examples), 24)
        for payload, reference in examples:
            self.assertTrue(shacl_conforms(payload)[0])
            self.assertNotEqual(python_candidates(payload), reference['external_candidates'])

    def test_product_start_includes_itself(self):
        payload = dict(source='hinge', question={'target': 'P'}, records=[dict(id='P', type='Product')])
        self.assert_parity(payload, ['P'])

    def test_candidate_wrong_class_references(self):
        records, question, _, _, _ = base('penelope', 0)
        for index in (0, 2):
            changed = copy.deepcopy(records)
            changed[index]['type'] = 'Material'
            self.assert_parity(dict(source='penelope', records=changed, question=question), [])
        records, question, _, _, _ = base('bpi', 0)
        records[0]['type'] = 'Material'
        self.assert_parity(dict(source='bpi', records=records, question=question), [])
