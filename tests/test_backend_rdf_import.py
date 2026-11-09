import unittest
from scripts.backend_rdf_import import export_terms
from rdflib import XSD
class ExportTermTests(unittest.TestCase):
    def test_tags_and_custom_types_remain_distinct(self):
        base={'subject':'urn:s','predicate':'urn:p','object':'same','isLiteral':True,'literalType':str(XSD.string),'literalLang':None,'subjectSPO':None}
        rows=[base,{**base,'literalLang':'en'},{**base,'literalType':'urn:Grade'}]
        triples=export_terms(rows)
        self.assertEqual(len(triples),3)
        self.assertEqual({t[2] for t in triples},{'"same"','"same"@en','"same"^^<urn:Grade>'})
    def test_rdfstar_not_silently_flattened(self):
        with self.assertRaisesRegex(ValueError,'RDF-star'):export_terms([{'subjectSPO':['a','b','c']}])
if __name__=='__main__':unittest.main()
