import unittest
from scripts.score_contract_mapping import score


class MappingScore(unittest.TestCase):
    def test_unknown_does_not_mask_wrong_target_or_operation(self):
        expected = {'operation': 'transitive_dependencies', 'target': 'A', 'scope': 'real_world'}
        output = {'status': 'unknown_world_scope', 'refs': []}
        for key, value in [('operation', 'direct_dependents'), ('target', 'B')]:
            result = score({**expected, key: value}, expected, output, output, True)
            self.assertFalse(result['mapping_correct'])
            self.assertTrue(result['result_agreement'])
            self.assertTrue(result['valid_but_wrong_mapping'])

    def test_exact_and_invalid_are_separate(self):
        expected = {'operation': 'clarify', 'target': '', 'scope': 'declared_document'}
        output = {'status': 'needs_clarification', 'refs': []}
        self.assertTrue(score(expected, expected, output, output, True)['mapping_correct'])
        self.assertFalse(score({**expected, 'extra': 'x'}, expected, output, output, False)['mapping_correct'])
