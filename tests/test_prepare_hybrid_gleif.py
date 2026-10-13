"""Synthetic software tests for frozen real-source preparation, not benchmarks."""
import csv
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_hybrid_gleif as p


def rr(a, b, kind=p.DIRECT, status='ACTIVE'):
    return {'Relationship.StartNode.NodeID': a, 'Relationship.EndNode.NodeID': b,
            'Relationship.RelationshipType': kind, 'Relationship.RelationshipStatus': status,
            'Registration.RegistrationStatus': 'PUBLISHED',
            'Relationship.Period.1.PeriodType': 'ACCOUNTING_PERIOD',
            'Relationship.Period.1.StartDate': '2000-01-01'}


class HybridPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.records = [rr(f'C{i}-{j}', f'C{i}-{j+1}') for i in range(30) for j in range(4)]
        self.records += [rr('C0-4', 'OLD', 'IS_ULTIMATELY_CONSOLIDATED_BY'),
                         rr('C1-0', 'C1-extra'), rr('C1-0', 'inactive', status='INACTIVE')]
        self.write_sources()

    def write_sources(self):
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=self.records[0].keys())
        writer.writeheader()
        writer.writerows(self.records)
        with zipfile.ZipFile(self.base / 'rr.csv.zip', 'w') as archive:
            archive.writestr('rr.csv', stream.getvalue())
        self.manifest = {'publish_date': 'synthetic', 'files': {'rr': {
            'sha256': p.sha256(self.base / 'rr.csv.zip'), 'record_count': len(self.records)}}}
        (self.base / 'manifest.json').write_text(json.dumps(self.manifest))
        (self.base / 'prior.json').write_text(json.dumps({
            'source_manifest': self.manifest, 'entities': {'OLD': {}}, 'cohort': []}))

    def prepare(self, name='out', **kwargs):
        return p.prepare(self.base / 'manifest.json', self.base / name,
                         [self.base / 'prior.json'], per_depth=2, **kwargs)

    def test_reachability_complete_neighborhood_no_gold_and_disjointness(self):
        summary = self.prepare()
        cases = json.loads((self.base / 'out/runtime-cases.json').read_text())
        gold = json.loads((self.base / 'out/evaluator.json').read_text())
        self.assertEqual(summary['case_count'], 12)
        used = set()
        for positive, negative in zip(cases[::2], cases[1::2]):
            self.assertEqual(positive['records'], negative['records'])
            components = {gold[positive['id']]['selected_component'], gold[positive['id']]['distractor_component']}
            self.assertEqual(len(components), 2)
            self.assertFalse(used & components)
            used |= components
            for case in (positive, negative):
                self.assertNotIn('expected', json.dumps(case))
                self.assertNotIn('C0-', json.dumps(case))
                contract = case['contract']
                frontier, reached = {contract['subject']}, set()
                for _ in range(contract['max_hops']):
                    next_nodes = set()
                    for node in frontier:
                        # All eligible outgoing source rows must be present.
                        outgoing = [i for i, r in enumerate(self.records, 1)
                                    if r['Relationship.StartNode.NodeID'] == node
                                    and r['Relationship.RelationshipType'] == p.DIRECT
                                    and r['Relationship.RelationshipStatus'] == 'ACTIVE']
                        self.assertTrue({f'rr-{i}' for i in outgoing} <= {r['id'] for r in case['records']})
                        next_nodes.update(r['object'] for r in case['records'] if r['subject'] == node)
                    reached |= next_nodes
                    frontier = next_nodes
                expected = 'reachable' if contract['target'] in reached else 'not_reachable'
                self.assertEqual(expected, gold[case['id']]['expected_decision'])
                self.assertIn(contract['target'], {r['object'] for r in case['records']})
                self.assertTrue(all(r['period_fields']['Relationship.Period.1.PeriodType'] == 'ACCOUNTING_PERIOD'
                                    for r in case['records']))
        self.assertEqual(self.prepare('again'), summary)

    def test_shortfall_no_synthetic_substitution(self):
        self.records = [rr('A', 'B'), rr('X', 'Y')]
        self.write_sources()
        result = self.prepare()
        self.assertEqual(result['selected_centers_per_depth'], {'4': 0, '2': 0, '1': 1})
        self.assertEqual(result['case_count'], 2)

    def test_hash_count_release_and_overwrite_fail_closed(self):
        with (self.base / 'rr.csv.zip').open('ab') as out:
            out.write(b'tamper')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.prepare()
        self.write_sources()
        self.manifest['files']['rr']['record_count'] += 1
        for name in ('manifest.json', 'prior.json'):
            data = json.loads((self.base / name).read_text())
            if name == 'prior.json':
                data['source_manifest'] = self.manifest
            else:
                data = self.manifest
            (self.base / name).write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'row count mismatch'):
            self.prepare()
        self.write_sources()
        self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.manifest['publish_date'] = 'wrong'
        (self.base / 'manifest.json').write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, 'release mismatch'):
            self.prepare('bad-release')

    def test_cycles_and_branch_closure(self):
        adjacency = {'A': [('B', 1), ('C', 2)], 'B': [('A', 3), ('D', 4)],
                     'C': [('E', 5)], 'D': [('F', 6)]}
        distances, evidence = p.neighborhood(adjacency, 'A', 2)
        self.assertEqual(distances, {'A': 0, 'B': 1, 'C': 1, 'D': 2, 'E': 2})
        self.assertEqual(evidence, {1, 2, 3, 4, 5})


if __name__ == '__main__':
    unittest.main()
