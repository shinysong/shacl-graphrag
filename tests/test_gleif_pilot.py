"""Independent safety properties for the pilot's interventions and scoring."""
import importlib.util
import unittest
from pathlib import Path

from rdflib import Graph, Literal

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pilot', ROOT / 'scripts/run_gleif_pilot.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.child, self.parent, self.other = 'A' * 18 + '12', 'B' * 18 + '34', 'C' * 18 + '56'
        self.dataset = {'entities': {lei: {'lei': lei, 'name': name} for lei, name in
                                    [(self.child, 'Child'), (self.parent, 'Parent'), (self.other, 'Other')]}}
        self.item = {'lei': self.child, 'kind': 'parent', 'parent': self.parent}
        self.shapes = Graph().parse(ROOT / 'experiments/gleif/shapes.ttl')

    def test_repair_cannot_recover_injected_source_error_from_gold(self):
        source, evidence = p.make_case(self.dataset, self.item, 'invalid_lei')
        passed, _, issues, _ = p.inspect(evidence, self.shapes)
        self.assertFalse(passed)
        repaired = p.repair(source, evidence, p.LEI[self.child], issues)
        self.assertFalse(p.inspect(repaired, self.shapes)[0])
        self.assertIn((p.LEI[self.parent], p.EX.lei, Literal('INVALID-LEI')), repaired)

    def test_retrieval_omission_repairs_without_mutating_source(self):
        source, evidence = p.make_case(self.dataset, self.item, 'missing_relation')
        before = p.graph_text(source)
        self.assertFalse(p.inspect(evidence, self.shapes)[0])
        repaired = p.repair(source, evidence, p.LEI[self.child], p.inspect(evidence, self.shapes)[2])
        self.assertTrue(p.inspect(repaired, self.shapes)[0])
        self.assertEqual(before, p.graph_text(source))
        self.assertEqual(p.graph_text(repaired), p.graph_text(p.retrieve(source, p.LEI[self.child])))

    def test_wrong_fact_passes_shape_but_differs_from_snapshot(self):
        _, evidence = p.make_case(self.dataset, self.item, 'wrong_parent')
        self.assertTrue(p.inspect(evidence, self.shapes)[0])
        self.assertNotIn((p.LEI[self.child], p.EX.directParent, p.LEI[self.parent]), evidence)

    def test_citation_existence_is_not_answer_support(self):
        _, evidence = p.make_case(self.dataset, self.item, 'clean')
        answer = {'status': 'answer', 'kind': 'parent', 'value': self.parent,
                  'evidence_ids': [next(iter(p.facts(evidence)))]}
        self.assertFalse(p.answer_support(answer, evidence, p.LEI[self.child]))
        answer['evidence_ids'] = list(p.facts(evidence))
        self.assertTrue(p.answer_support(answer, evidence, p.LEI[self.child]))
        answer['value'] = self.other
        self.assertFalse(p.answer_support(answer, evidence, p.LEI[self.child]))

    def test_reporting_exception_is_not_a_missing_parent_violation(self):
        item = {'lei': self.child, 'kind': 'exception', 'reason': 'NO_LEI'}
        _, evidence = p.make_case(self.dataset, item, 'clean')
        self.assertTrue(p.inspect(evidence, self.shapes)[0])
        self.assertTrue(p.python_conforms(evidence))


if __name__ == '__main__':
    unittest.main()
