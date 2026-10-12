"""Regression checks using original YAGO constraints and actual sampled facts."""
import json
import sys
import unittest
from pathlib import Path

from rdflib import Graph, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_yago_pilot as p


class YagoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.shapes, cls.taxonomy = (Graph().parse(p.FIX / n) for n in
                                             ('data.ttl', 'schema.ttl', 'taxonomy.ttl'))
        cls.manifest = json.loads((p.FIX / 'manifest.json').read_text())
        cls.cohort = cls.manifest['cohort']
        cls.item = cls.cohort[0]
        cls.subject = URIRef(cls.item['subject'])

    def case(self, variant):
        return p.make_case(self.data, self.cohort, self.item, variant)

    def check(self, evidence):
        return p.inspect(evidence, self.shapes, self.taxonomy, self.subject)

    def test_original_schema_bytes(self):
        self.assertEqual(p.sha(p.FIX / 'schema.ttl'),
                         self.manifest['source']['files']['schema']['turtle_sha256'])

    def test_absent_relation_is_allowed_by_native_shape(self):
        _, evidence = self.case('missing_relation')
        self.assertTrue(self.check(evidence)[0])
        self.assertFalse(list(evidence.objects(self.subject, p.SC.birthPlace)))

    def test_nested_datatype_constraint_is_not_skipped(self):
        _, evidence = self.case('wrong_datatype')
        passed, _, issues, _ = self.check(evidence)
        self.assertFalse(passed)
        self.assertIn(str(p.SH.OrConstraintComponent), {i[2] for i in issues})

    def test_retrieval_type_context_is_repairable_without_gold(self):
        source, evidence = self.case('missing_target_type')
        before = p.graph_text(source)
        self.assertFalse(self.check(evidence)[0])
        repaired = p.repair(source, evidence, self.check(evidence)[2])
        self.assertTrue(self.check(repaired)[0])
        self.assertEqual(before, p.graph_text(source))

    def test_source_errors_cannot_be_repaired_by_rereading(self):
        for variant in ('wrong_class', 'duplicate_relation', 'wrong_datatype'):
            with self.subTest(variant=variant):
                source, evidence = self.case(variant)
                repaired = p.repair(source, evidence, self.check(evidence)[2])
                self.assertFalse(self.check(repaired)[0])

    def test_wrong_fact_passes_but_differs_from_gold(self):
        _, evidence = self.case('wrong_place')
        self.assertTrue(self.check(evidence)[0])
        self.assertNotIn((self.subject, p.SC.birthPlace, URIRef(self.item['place'])), evidence)


if __name__ == '__main__':
    unittest.main()
