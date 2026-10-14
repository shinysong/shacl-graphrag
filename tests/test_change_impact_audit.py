import copy
import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location('impact_audit', Path(__file__).resolve().parents[1] / 'scripts/analyze_change_impact_study.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ImpactAuditTests(unittest.TestCase):
    def fixture(self):
        packet = {'changed': 'c', 'nodes': [{'id': 'c', 'kind': 'component'}, {'id': 'p', 'kind': 'product'}], 'edges': [{'id': 'e', 'source': 'c', 'target': 'p', 'relation': 'partOf', 'status': 'active'}], 'catalog': {'partOf': 'forward'}, 'coverage': {'relations_complete': True, 'source_version': 'v1', 'advertised_version': 'v1'}}
        row = {'arm': 'typed_json', 'output': {'candidates': ['p'], 'eligible_edges': [['c', 'p', 'e']], 'unmapped_edge_ids': [], 'uncertainty': [], 'status': 'complete', 'witnesses': {'p': ['e']}}}
        return packet, row

    def test_fabricated_witness_rejected_even_when_answer_correct(self):
        p, r = self.fixture()
        audit.audit_runtime(p, r)
        r['output']['witnesses']['p'] = ['nonexistent']
        with self.assertRaises(AssertionError):
            audit.audit_runtime(p, r)

    def test_complete_claim_rejected_on_declared_missing_source(self):
        p, r = self.fixture()
        p['coverage']['relations_complete'] = False
        with self.assertRaises(AssertionError):
            audit.audit_runtime(p, r)

    def test_direction_and_cycle_closure(self):
        self.assertEqual(audit.closure('c', [('p', 'c')]), {'c'})
        self.assertEqual(audit.closure('c', [('c', 'a'), ('a', 'c'), ('a', 'p')]), {'c', 'a', 'p'})
        self.assertEqual(audit.closure('c', [('c', 'a'), ('a', 'p')], True), {'c', 'a'})


if __name__ == '__main__':
    unittest.main()
