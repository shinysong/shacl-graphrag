"""Synthetic software checks only; these are not GraphRAG benchmarks."""
import csv
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_gleif_comparison as p


def relation(child, parent, kind=p.DIRECT, status='ACTIVE'):
    return {'Relationship.StartNode.NodeID': child,
            'Relationship.EndNode.NodeID': parent,
            'Relationship.RelationshipType': kind,
            'Relationship.RelationshipStatus': status,
            'Registration.RegistrationStatus': 'PUBLISHED'}


def exception(lei, reason='NON_CONSOLIDATING', category=p.CATEGORY):
    return {'LEI': lei, 'Exception.Category': category,
            **{f'Exception.Reason.{i}': reason if i == 1 else '' for i in range(1, 6)}}


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        # The discovery pool ends at LateDirect. Its extra RR appears later.
        self.rr = [relation(f'C{i}', f'P{i}') for i in range(12)]
        self.rr += [relation('LateDirect', 'LP', status='INACTIVE')]
        self.rr += [relation('LateDirect', 'LP')]
        # Connect two otherwise different families through ultimate RR.
        self.rr += [relation('P0', 'U', 'IS_ULTIMATELY_CONSOLIDATED_BY'),
                    relation('P1', 'U', 'IS_ULTIMATELY_CONSOLIDATED_BY')]
        # A prior ENTITY (not a prior center) taints a component via an ancestor.
        self.rr += [relation('P2', 'OldParent', 'IS_ULTIMATELY_CONSOLIDATED_BY')]
        self.es = [exception('LateDirect')] + [exception(f'E{i}') for i in range(12)]
        self.rr += [relation('E0', 'EU', 'IS_ULTIMATELY_CONSOLIDATED_BY'),
                    relation('E1', 'EU', 'IS_ULTIMATELY_CONSOLIDATED_BY')]
        ids = {r[k] for r in self.rr for k in
               ('Relationship.StartNode.NodeID', 'Relationship.EndNode.NodeID')}
        ids |= {r['LEI'] for r in self.es}
        self.entities = [{'LEI': lei, 'Entity.LegalName': 'Synthetic ' + lei,
                          'Entity.EntityStatus': 'ACTIVE',
                          'Registration.RegistrationStatus': 'ISSUED'} for lei in sorted(ids)]
        self.write_sources()

    def write_sources(self):
        files = {}
        for kind, records in [('rr', self.rr), ('repex', self.es), ('lei2', self.entities)]:
            text = io.StringIO()
            writer = csv.DictWriter(text, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
            path = self.base / f'{kind}.csv.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('source.csv', text.getvalue())
            files[kind] = {'sha256': p.sha256(path), 'record_count': len(records)}
        self.manifest = {'publish_date': 'synthetic fixture', 'files': files}
        self.manifest_path = self.base / 'manifest.json'
        self.manifest_path.write_text(json.dumps(self.manifest))
        self.prior = {'source_manifest': self.manifest,
                      'entities': {'OldParent': {}}, 'cohort': []}

    def prepare(self, name='out', **kwargs):
        return p.prepare(self.manifest_path, self.base / name, self.prior,
                         pool_size=13, development_each=2, reserved_each=2, **kwargs)

    def load(self, name, artifact):
        return json.loads((self.base / name / artifact).read_text())

    def test_determinism_disjoint_components_prior_exclusion_and_closure(self):
        a, b = self.prepare('a'), self.prepare('b')
        self.assertEqual(a, b)
        development = self.load('a', 'development-dataset.json')
        reserved = self.load('a', 'reserved-dataset.json')
        combined = development['cohort'] + reserved['cohort']
        self.assertEqual(len(combined), 8)
        self.assertEqual(len({c['lei'] for c in combined}), 8)
        # Build independent graph reachability, not the builder's union-find.
        adjacency = {}
        for r in self.rr:
            if r['Relationship.RelationshipStatus'] != 'ACTIVE':
                continue
            x, y = r['Relationship.StartNode.NodeID'], r['Relationship.EndNode.NodeID']
            adjacency.setdefault(x, set()).add(y)
            adjacency.setdefault(y, set()).add(x)
        touched = set()
        for c in combined:
            seen, pending = set(), [c['lei']]
            while pending:
                node = pending.pop()
                if node not in seen:
                    seen.add(node)
                    pending.extend(adjacency.get(node, set()) - seen)
            self.assertFalse(seen & touched)
            self.assertNotIn('OldParent', seen)
            touched |= seen
            self.assertNotEqual(c['lei'], 'LateDirect')
        self.assertNotIn('raw_entities', development)
        self.assertTrue(all('raw_relationships' not in c for c in development['cohort']))
        for split in (development, reserved):
            self.assertEqual(sum(c['kind'] == 'parent' for c in split['cohort']), 2)
            self.assertEqual(sum(c['kind'] == 'exception' for c in split['cohort']), 2)
        self.assertEqual(a['row_counts'], {k: v['record_count'] for k, v in self.manifest['files'].items()})
        self.assertEqual((self.base / 'a/source-manifest.json').read_bytes(), self.manifest_path.read_bytes())

    def test_exclusion_cases_forced_ahead_of_valid_candidates(self):
        # Force invalid candidates to the front: test does not depend on lucky sampling.
        self.es += [exception('E2', 'NO_LEI')]
        for row in self.entities:
            if row['LEI'] == 'P3':
                row['Registration.RegistrationStatus'] = 'LAPSED'
            if row['LEI'] == 'E3':
                row['Entity.EntityStatus'] = 'INACTIVE'
        self.rr += [relation('C4', 'P5')]
        self.es += [exception('C5')]
        self.write_sources()
        invalid = {'C2', 'C3', 'C4', 'C5', 'LateDirect', 'E2', 'E3'}
        with patch.object(p, 'rank', side_effect=lambda lei, purpose: (0 if lei in invalid else 1, lei)):
            self.prepare()
        cases = self.load('out', 'development-dataset.json')['cohort'] + self.load('out', 'reserved-dataset.json')['cohort']
        self.assertFalse({c['lei'] for c in cases} & invalid)

    def test_connected_candidates_and_old_parent_are_forced_to_front(self):
        front = {'C0', 'C1', 'C2', 'E0', 'E1'}
        with patch.object(p, 'rank', side_effect=lambda lei, purpose: (0 if lei in front else 1, lei)):
            self.prepare()
        cases = self.load('out', 'development-dataset.json')['cohort'] + self.load('out', 'reserved-dataset.json')['cohort']
        centers = {c['lei'] for c in cases}
        self.assertEqual(len(centers & {'C0', 'C1'}), 1)
        self.assertEqual(len(centers & {'E0', 'E1'}), 1)
        self.assertNotIn('C2', centers)

    def test_preserves_reporting_reasons_and_other_raw_categories(self):
        self.es.insert(0, exception('E4', 'NATURAL_PERSONS', 'ULTIMATE_ACCOUNTING_CONSOLIDATION_PARENT'))
        self.es += [exception('C0', 'NATURAL_PERSONS', 'ULTIMATE_ACCOUNTING_CONSOLIDATION_PARENT')]
        self.write_sources()
        with patch.object(p, 'rank', side_effect=lambda lei, purpose: (0 if lei in {'E4', 'C0'} else 1, lei)):
            self.prepare()
        raw = self.load('out', 'development-raw.json')
        self.assertEqual(len(next(c for c in raw['cohort'] if c['lei'] == 'E4')['raw_exceptions']), 2)
        self.assertEqual(next(c for c in raw['cohort'] if c['lei'] == 'E4')['reason'], 'NON_CONSOLIDATING')
        self.assertEqual(len(next(c for c in raw['cohort'] if c['lei'] == 'C0')['raw_exceptions']), 1)

    def test_no_overwrite_and_summary_has_no_identity_or_gold(self):
        result = self.prepare()
        before = {f.name: f.read_bytes() for f in (self.base / 'out').iterdir()}
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(before, {f.name: f.read_bytes() for f in (self.base / 'out').iterdir()})
        summary = json.dumps(result)
        self.assertNotIn('Synthetic', summary)
        self.assertNotIn('NON_CONSOLIDATING', summary)
        self.assertNotIn('"lei"', summary)

    def test_hash_release_and_count_fail_closed(self):
        with (self.base / 'rr.csv.zip').open('ab') as output:
            output.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.prepare('hash')
        self.assertFalse((self.base / 'hash').exists())
        self.write_sources()
        self.manifest['files']['rr']['record_count'] += 1
        self.manifest_path.write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(ValueError, 'Row count mismatch'):
            self.prepare('count')
        self.assertFalse((self.base / 'count').exists())
        self.write_sources()
        changed = dict(self.manifest, publish_date='other release')
        self.manifest_path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'Release differs'):
            self.prepare('release')


if __name__ == '__main__':
    unittest.main()
