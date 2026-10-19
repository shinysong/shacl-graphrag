"""Actual local SHACL checks against the separately authored mutation catalog."""
import copy
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from rule_workbench.connectors import read_file
from rule_workbench.core import run_checks
from rule_workbench.exports import export_bundle, export_json, import_json
from scripts.build_workbench_domain_demos import build_projects, write_demos


def labels(results):
    return {(r['rule_id'], r['row']): r['status'] for r in results}


class DomainDemoTests(unittest.TestCase):
    def test_structure_and_mutation_catalog(self):
        bundles = build_projects()
        self.assertEqual(set(bundles), {'manufacturing', 'healthcare', 'finance', 'ecommerce'})
        self.assertEqual(bundles, build_projects())
        for domain, bundle in bundles.items():
            with self.subTest(domain=domain):
                project = bundle['project']
                self.assertEqual(len(project['tables'][0]['rows']), 200)
                self.assertGreaterEqual(len(project['tables']), 3)
                self.assertEqual(Counter(r['status'] for r in project['rules']), {'confirmed': 7, 'draft': 1})
                self.assertTrue(all(r['status'] == 'draft' for r in bundle['draft_project']['rules']))
                self.assertEqual(len(bundle['expected']), 1401)
                self.assertEqual(Counter(r['status'] for r in bundle['expected']), {'pass': 1350, 'violation': 30, 'unknown': 21})
                self.assertEqual(len({m['row'] for m in bundle['mutations']}), 50)
                self.assertEqual(set(Counter(m['label'] for m in bundle['mutations']).values()), {5})
                for rule in project['rules']:
                    self.assertEqual(bundle['policy'].splitlines()[rule['source']['line'] - 1], rule['source']['quote'])
                restored = copy.deepcopy(project)
                for mutation in bundle['mutations']:
                    row = restored['tables'][0]['rows'][mutation['row'] - 1]
                    self.assertEqual(row[mutation['column']], mutation['after'])
                    row[mutation['column']] = mutation['before']
                self.assertEqual(restored, bundle['baseline_project'])

    def test_real_shacl_matches_every_authored_label_and_clean_baseline(self):
        for domain, bundle in build_projects().items():
            with self.subTest(domain=domain):
                result = run_checks(bundle['project'])
                self.assertEqual(len(result['results']), len(bundle['expected']))
                self.assertEqual(labels(result['results']), labels(bundle['expected']))
                baseline = run_checks(bundle['baseline_project'])
                self.assertEqual(baseline['counts'], {'pass': 1400, 'violation': 0, 'unknown': 1, 'not_applicable': 0})
                draft = run_checks(bundle['draft_project'])
                self.assertEqual(draft['counts']['unknown'], 8)
                self.assertTrue(all(r['row'] is None for r in draft['results']))
                portable = import_json(export_json(bundle['project'], include_data=True))
                self.assertEqual(labels(run_checks(portable)['results']), labels(bundle['expected']))
                self.assertTrue(export_bundle(portable, run_checks(portable), include_data=True))

    def test_all_artifacts_roundtrip_and_reproducible_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / 'one', Path(temporary) / 'two'
            bundles = write_demos(first)
            write_demos(second)
            with self.assertRaises(FileExistsError):
                write_demos(first)
            for path in first.rglob('*'):
                if path.is_file():
                    self.assertEqual(path.read_bytes(), (second / path.relative_to(first)).read_bytes(), path.name)
            for domain, bundle in bundles.items():
                directory = first / domain
                original = bundle['project']
                by_name = {table['name']: table for table in original['tables']}
                imports = [read_file(filename, (directory / filename).read_bytes()) for filename in ['data.xlsx', 'data.sqlite']]
                csv_tables = []
                for name in by_name:
                    table = read_file(f'{name}.csv', (directory / f'{name}.csv').read_bytes())[0]
                    table['name'] = name  # CSV connector displays the filename including extension.
                    csv_tables.append(table)
                imports.append(csv_tables)
                for imported in imports:
                    remapped = copy.deepcopy(original)
                    for table in imported:
                        table['name'] = table['source'].get('sheet') or table['source'].get('table') or Path(table['source']['file']).stem
                    self.assertEqual({table['name'] for table in imported}, set(by_name))
                    for table in imported:
                        expected_table = by_name[table['name']]
                        self.assertEqual(table['rows'], expected_table['rows'])
                        self.assertEqual(table['columns'], expected_table['columns'])
                        self.assertFalse(table['source']['truncated'])
                        table['id'] = expected_table['id']
                    remapped['tables'] = imported
                    self.assertEqual(labels(run_checks(remapped)['results']), labels(bundle['expected']))


if __name__ == '__main__':
    unittest.main()
