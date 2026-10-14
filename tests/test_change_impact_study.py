import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_change_impact_study as study


class ChangeImpactTests(unittest.TestCase):
    def test_cycle_inverse_retired_and_unrelated(self):
        packet = {
            'changed': 'c', 'nodes': [{'id': n, 'kind': 'product' if n in 'pur' else 'component'} for n in ('c', 'a', 'p', 'u', 'r')],
            'edges': [
                {'id': 'inverse', 'source': 'a', 'target': 'c', 'relation': 'contains', 'status': 'active'},
                {'id': 'up', 'source': 'a', 'target': 'p', 'relation': 'usedIn', 'status': 'active'},
                {'id': 'cycle', 'source': 'p', 'target': 'c', 'relation': 'partOf', 'status': 'active'},
                {'id': 'noise', 'source': 'c', 'target': 'u', 'relation': 'associatedWith', 'status': 'active'},
                {'id': 'retired', 'source': 'c', 'target': 'r', 'relation': 'partOf', 'status': 'retired'}],
            'catalog': study.CATALOG, 'coverage': {'relations_complete': True, 'source_version': 'v2', 'advertised_version': 'v2'}}
        for arm in ('typed_json', 'typed_rdf'):
            output = study.select(packet, arm)
            self.assertEqual(output['candidates'], ['p'])
            self.assertEqual(output['witnesses']['p'], ['inverse', 'up'])
        self.assertEqual(study.select(packet, 'direct_only')['candidates'], [])
        self.assertEqual(study.select(packet, 'untyped_transitive')['candidates'], ['p', 'u'])

    def test_missing_edge_preserves_unknown_without_gold_repair(self):
        case, packet = study.make_case(4, 3, 11, 'missing_edge')
        output = study.select(packet, 'typed_json')
        self.assertEqual(len(output['candidates']), 2)
        self.assertEqual(len(case['truth']), 3)
        self.assertEqual(output['status'], 'partial/unknown')
        self.assertIn('declared_relation_incompleteness', output['uncertainty'])
        self.assertNotIn('truth', packet)
        self.assertNotIn('canonical_bom', packet)
        # Changing evaluator truth cannot influence the selector.
        case['truth'] = ['fabricated']
        self.assertEqual(study.select(packet, 'typed_json'), output)

    def test_wrong_catalog_is_used_and_scored_not_repaired(self):
        case, packet = study.make_case(2, 1, 23, 'bad_mapping')
        output = study.select(packet, 'typed_rdf')
        self.assertIn('unrelated', output['candidates'])
        self.assertEqual(output['status'], 'complete')
        result = study.score(output, case['truth'])
        self.assertEqual(result['false_positive'], ['unrelated'])
        self.assertTrue(result['unsafe_complete_claim'])

    def test_stale_source_and_mapping_uncertainty(self):
        for fault, reason in [('stale_edge', 'stale_source'), ('missing_mapping', 'unmapped_active_relation')]:
            case, packet = study.make_case(2, 3, 37, fault)
            output = study.select(packet, 'typed_json')
            self.assertEqual(output['status'], 'partial/unknown')
            self.assertIn(reason, output['uncertainty'])
            self.assertFalse(study.score(output, case['truth'])['unsafe_complete_claim'])
        _, stale = study.make_case(2, 3, 37, 'stale_edge')
        self.assertIn('old_product', study.select(stale, 'typed_json')['candidates'])

    def test_lossless_formats_and_duplicate_ids(self):
        _, packet = study.make_case(8, 3, 53, 'missing_mapping')
        for fmt in study.FORMATS:
            encoded = study.encode(packet, fmt)
            self.assertEqual(study.decode(encoded, fmt), packet)
        for key in ('nodes', 'edges'):
            invalid = copy.deepcopy(packet)
            invalid[key].append(copy.deepcopy(invalid[key][0]))
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                study.normalize(invalid)

    def test_foregrounds_vary_and_truth_is_fault_independent(self):
        truths = []
        for seed in study.SEEDS:
            clean, original = study.make_case(4, 3, seed, 'complete')
            truths.append(clean['truth'])
            self.assertEqual(len(clean['canonical_bom']), 13)
            self.assertEqual(len(clean['truth']), 3)
            self.assertEqual(study.select(original, 'typed_json')['candidates'], clean['truth'])
            for fault in study.FAULTS:
                case, _ = study.make_case(4, 3, seed, fault)
                self.assertEqual(case['truth'], clean['truth'])
                self.assertEqual(case['canonical_bom'], clean['canonical_bom'])
        self.assertEqual(len({tuple(t) for t in truths}), 4)
        self.assertEqual(study.EXPECTED_CASES, 192)
        self.assertEqual(study.EXPECTED_ROWS, 2304)

    def test_wrong_relation_stays_undetected(self):
        case, packet = study.make_case(1, 1, 11, 'wrong_relation')
        output = study.select(packet, 'typed_json')
        self.assertEqual(output['candidates'], [])
        self.assertEqual(output['status'], 'complete')
        self.assertTrue(study.score(output, case['truth'])['unsafe_complete_claim'])

    def test_existing_output_refused_and_interruption_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileExistsError):
                study.run(folder)
            output = Path(folder) / 'partial'
            # Exercise failure journaling without running any case or study matrix.
            with (patch.object(study, 'make_case', side_effect=RuntimeError('injected interruption')),
                  self.assertRaisesRegex(RuntimeError, 'injected interruption')):
                study.run(output)
            import json
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'partial')
            self.assertEqual(manifest['completed_rows'], 0)
            self.assertEqual(manifest['failure']['type'], 'RuntimeError')
            self.assertTrue((output / 'source' / 'run_change_impact_study.py').exists())


if __name__ == '__main__':
    unittest.main()
