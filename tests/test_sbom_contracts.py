import json
import tempfile
import unittest
from pathlib import Path

from scripts.sbom_contracts import read_document, execute, contract_errors, shacl_contract_errors
from scripts.sbom_reference import reference, compare


class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'source.json'
        self.document = {'bomFormat': 'CycloneDX', 'specVersion': '1.4',
                         'components': [{'bom-ref': x, 'name': x} for x in 'ABCD'],
                         'dependencies': [{'ref': 'A', 'dependsOn': ['B']},
                                          {'ref': 'B', 'dependsOn': ['A', 'C']}, {'ref': 'C'}]}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        self.path.write_text(json.dumps(self.document)); self.snapshot = read_document(self.path)

    def contract(self, op, target='A', scope='declared_document'):
        return {'operation': op, 'target': target, 'scope': scope}

    def test_cycle_direction_and_reference(self):
        for op, target, refs in [('transitive_dependencies', 'A', ['B', 'C']),
                                 ('transitive_dependents', 'C', ['A', 'B']),
                                 ('direct_dependencies', 'A', ['B']),
                                 ('direct_dependents', 'A', ['B'])]:
            c = self.contract(op, target); result = execute(c, self.snapshot)
            self.assertEqual(result['refs'], refs)
            self.assertEqual(compare(result, reference(self.path, c)), {})

    def test_absent_is_not_explicit_empty(self):
        self.assertEqual(execute(self.contract('dependency_status', 'C'), self.snapshot)['knowledge'], 'explicit_empty')
        self.assertEqual(execute(self.contract('dependency_status', 'D'), self.snapshot)['knowledge'], 'unknown_missing_entry')

    def test_world_scope_and_clarification(self):
        self.assertEqual(execute(self.contract('direct_dependencies', scope='real_world'), self.snapshot)['status'], 'unknown_world_scope')
        self.assertEqual(execute(self.contract('clarify', ''), self.snapshot)['status'], 'needs_clarification')

    def test_checker_cannot_certify_question_interpretation(self):
        correct = self.contract('direct_dependencies', 'C')
        wrong = self.contract('direct_dependents', 'C')
        self.assertNotEqual(execute(correct, self.snapshot)['refs'], execute(wrong, self.snapshot)['refs'])
        for c in [correct, wrong]:
            self.assertEqual(contract_errors(c, self.snapshot), [])
            self.assertEqual(shacl_contract_errors(c, self.snapshot)['codes'], [])

    def test_shared_boundary_and_policy_parity(self):
        for c in [self.contract('unsupported'), self.contract('direct_dependencies', 'absent'),
                  self.contract('clarify', 'A'), self.contract('direct_dependencies', scope='unsupported'),
                  {'operation': 1, 'target': 'A', 'scope': 'declared_document'}]:
            self.assertEqual(contract_errors(c, self.snapshot), shacl_contract_errors(c, self.snapshot)['codes'])

    def test_new_edge_to_previously_excluded_node(self):
        c = self.contract('transitive_dependencies')
        old = execute(c, self.snapshot)
        self.document['dependencies'].append({'ref': 'C', 'dependsOn': ['D']})
        # Replace instead of duplicate: a new relevant edge requires reading current source.
        self.document['dependencies'].pop(2)
        self.save(); new = execute(c, self.snapshot)
        self.assertNotIn('D', old['refs']); self.assertIn('D', new['refs'])

    def test_dangling_and_duplicate_references(self):
        self.document['dependencies'][0]['dependsOn'].append('Z'); self.save()
        self.assertEqual(execute(self.contract('direct_dependencies'), self.snapshot)['status'], 'invalid_source_references')
        c = self.contract('dependency_status')
        self.assertEqual(compare(execute(c, self.snapshot), reference(self.path, c)), {})
        self.document['components'].append({'bom-ref': 'A', 'name': 'duplicate'})
        with self.assertRaisesRegex(ValueError, 'duplicate_component_identity'):
            self.save()


if __name__ == '__main__':
    unittest.main()
