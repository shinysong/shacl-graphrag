import unittest
from scripts import run_hybrid_intent as s

class IntentTests(unittest.TestCase):
    def test_fixture_scope_and_runtime_isolation(self):
        cases,gold=s.fixtures();self.assertEqual(len(cases),24)
        for c in cases:
            self.assertEqual(set(c),{'id','question','entities','records'})
            self.assertNotIn('depth',c['entities']);self.assertNotIn('load',c['entities'])
            expected=gold[c['id']]['expected'];compiled=s.compile_case(c,expected)
            if compiled:
                self.assertEqual(s.runner.core.check_python(compiled)['decision'],gold[c['id']]['expected_execution'])
                self.assertEqual(s.runner.core.check_shacl(compiled)['decision'],gold[c['id']]['expected_execution'])
            else:self.assertEqual(expected['decision'],'abstain')
    def test_schema_only_does_not_repair_valid_wrong_intent(self):
        c=s.fixtures()[0][0]
        wrong={'decision':'compile','depth':4,'load':'full'}
        self.assertEqual(s.compile_case(c,wrong)['contract']['depth'],4)
        for bad in ({'decision':'compile','depth':3,'load':'full'},{'decision':'abstain','depth':1,'load':None},{'decision':'compile','depth':True,'load':'basic'}):
            with self.assertRaises(ValueError):s.validate_prediction(bad)
