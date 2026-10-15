"""Bounded artifact-isolation and authored-fixture checks, not model evaluation."""
import importlib.util
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from rdflib import Graph, Literal, RDF

SPEC = importlib.util.spec_from_file_location('tool_cases', Path(__file__).parents[1] / 'scripts/prepare_ontology_tool_cases.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class OntologyToolCasesTests(unittest.TestCase):
    def test_cohort_and_runtime_allowlist(self):
        cases = m.build_cases()
        self.assertEqual(Counter(c['family'] for c in cases), {f: 3 for f in ['M1', 'M2', 'M3', 'F1', 'F2', 'F3']})
        self.assertEqual([c['case_id'] for c in cases], [f'case{i:02d}' for i in range(1, 19)])
        for c in cases:
            self.assertEqual(set(c['runtime']), {'question', 'source_turtle', 'physical_schema', 'public_policies', 'ontology', 'shapes_turtle', 'scope_metadata', 'answer_contract'})
            self.assertIn(m.ASOF, c['runtime']['question'])
            self.assertNotIn(c['scenario'], json.dumps(c['runtime']))
            Graph().parse(data=c['runtime']['source_turtle'], format='turtle')
            Graph().parse(data=c['runtime']['shapes_turtle'], format='turtle')
        self.assertTrue(all(c['runtime']['public_policies'] == cases[0]['runtime']['public_policies'] for c in cases))

    def test_lapsed_fact_is_preserved_and_not_policy_eligible(self):
        c = next(c for c in m.build_cases() if c['scenario'] == 'lapsed_reported_parent')
        graph = Graph().parse(data=c['runtime']['source_turtle'], format='turtle')
        self.assertIn((m.NS['record/r1'], m.NS.registration_status, Literal('LAPSED')), graph)
        self.assertEqual(c['expected']['status'], 'known')
        self.assertEqual(c['expected']['required_caveat_terms'], ['LAPSED'])
        self.assertIn('PUBLISHED', c['runtime']['public_policies']['internal_review'])

    def test_scorer_is_physically_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'export'
            cases = m.export_cases(path)
            self.assertEqual(len(list((path / 'runtime').glob('*.json'))), 18)
            for c in cases:
                payload = json.loads((path / 'runtime' / f"{c['case_id']}.json").read_text())
                self.assertEqual(payload, c['runtime'])
                self.assertNotIn('expected', payload)
                self.assertNotIn('family', payload)
            refs = json.loads((path / 'scorer/references.json').read_text())
            self.assertEqual(len(refs), 18)
            self.assertNotIn('runtime', refs[0])

    def test_shapes_cover_all_types_and_missing_certificate(self):
        from pyshacl import validate
        cases = m.build_cases()
        shapes = Graph().parse(data=m.shapes_turtle(), format='turtle')
        from rdflib import Namespace
        sh = Namespace('http://www.w3.org/ns/shacl#')
        self.assertEqual(set(shapes.objects(None, sh.targetClass)), {m.NS[k] for k in m.KINDS})
        missing = next(c for c in cases if c['scenario'] == 'missing_certificate')
        graph = Graph().parse(data=missing['runtime']['source_turtle'], format='turtle')
        conforms, _, _ = validate(graph, shacl_graph=shapes)
        self.assertFalse(conforms)
        clean = next(c for c in cases if c['scenario'] == 'equivalent_unit_success')
        conforms, _, _ = validate(Graph().parse(data=clean['runtime']['source_turtle'], format='turtle'), shacl_graph=shapes)
        self.assertTrue(conforms)


if __name__ == '__main__':
    unittest.main()
