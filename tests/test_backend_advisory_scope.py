import unittest
from scripts.backend_advisory_scope import fingerprint
from scripts.backend_inference import TYPE,SC,SP,term
class FingerprintScopeTests(unittest.TestCase):
    def test_relation_change_does_not_change_type_family(self):
        a={'facts':[(term('a'),TYPE,term('Class')),(term('a'),term('p'),term('b'))],'schema':[(term('Class'),SC,term('Root')),(term('p'),SP,term('ref'))]}
        b={**a,'facts':a['facts'][:1]}
        self.assertEqual(fingerprint(a,'type_schema'),fingerprint(b,'type_schema'))
        self.assertNotEqual(fingerprint(a,'relation_schema'),fingerprint(b,'relation_schema'))
        self.assertNotEqual(fingerprint(a,'all'),fingerprint(b,'all'))
    def test_schema_change_and_record_order(self):
        a={'facts':[(term('a'),TYPE,term('C')),(term('b'),TYPE,term('C'))],'schema':[(term('C'),SC,term('R'))]}
        b={**a,'schema':[]};reordered={**a,'facts':a['facts'][::-1]}
        self.assertNotEqual(fingerprint(a,'type_schema'),fingerprint(b,'type_schema'))
        self.assertEqual(fingerprint(a,'relation_schema'),fingerprint(b,'relation_schema'))
        self.assertEqual(fingerprint(a,'all'),fingerprint(reordered,'all'))
if __name__=='__main__':unittest.main()
