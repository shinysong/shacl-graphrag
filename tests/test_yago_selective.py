"""Safety checks for selective gating on incomplete real-data evidence."""
import json
import sys
import unittest
from pathlib import Path

from rdflib import Graph, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_yago_selective as p


class SelectiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.shapes, cls.taxonomy = (Graph().parse(p.FIX / n) for n in
                                             ('data.ttl', 'schema.ttl', 'taxonomy.ttl'))
        cls.cohort = json.loads((p.FIX / 'manifest.json').read_text())['cohort']
        cls.item = cls.cohort[0]
        cls.subject = URIRef(cls.item['subject'])

    def case(self, variant):
        source, evidence = p.make_case(self.data, self.cohort, self.item, variant)
        issues = p.inspect(evidence, self.shapes, self.taxonomy, self.subject)[2]
        return source, evidence, issues

    def test_unrelated_violations_remain_recorded_but_do_not_block(self):
        for v in ('missing_label', 'wrong_datatype'):
            _, evidence, issues = self.case(v)
            self.assertTrue(issues)
            self.assertTrue(p.selective_gate(evidence, issues, self.subject, 'S1')[0])

    def test_missing_relation_recovers_only_from_source(self):
        source, evidence, issues = self.case('missing_relation')
        passed, blockers, complete = p.selective_gate(evidence, issues, self.subject, 'S2')
        self.assertFalse(passed)
        repaired = p.selective_repair(source, evidence, self.subject, blockers, complete)
        self.assertIn((self.subject, p.SC.birthPlace, URIRef(self.item['place'])), repaired)

    def test_unknown_source_stays_unknown(self):
        source, evidence, issues = self.case('source_missing_relation')
        _, blockers, complete = p.selective_gate(evidence, issues, self.subject, 'S2')
        repaired = p.selective_repair(source, evidence, self.subject, blockers, complete)
        self.assertFalse(p.selective_gate(repaired, [], self.subject, 'S2')[0])
        self.assertFalse(list(source.objects(self.subject, p.SC.birthPlace)))

    def test_completeness_alone_cannot_check_place_class(self):
        _, evidence, issues = self.case('wrong_class')
        self.assertFalse(p.selective_gate(evidence, issues, self.subject, 'S2')[0])
        self.assertTrue(p.selective_gate(evidence, issues, self.subject, 'C2')[0])

    def test_conflicting_relations_are_blocked(self):
        _, evidence, issues = self.case('duplicate_relation')
        for condition in ('S1', 'S2', 'C2'):
            self.assertFalse(p.selective_gate(evidence, issues, self.subject, condition)[0])

    def test_plausible_wrong_fact_remains_undetectable(self):
        _, evidence, issues = self.case('wrong_place')
        self.assertTrue(p.selective_gate(evidence, issues, self.subject, 'S2')[0])
        self.assertNotIn((self.subject, p.SC.birthPlace, URIRef(self.item['place'])), evidence)
