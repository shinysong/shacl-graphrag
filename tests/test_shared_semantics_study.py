"""Offline software checks, not a benchmark or measured fault frequency."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rdflib.plugins.sparql import prepareQuery

from scripts import run_shared_semantics_study as m


class SharedSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.source, self.config = m.baseline(24, 17)
        self.query = prepareQuery(m.QUERY_TEXT)

    def outputs(self, name, subject):
        source, config = m.snapshot(self.source, self.config, name)
        evidence = m.reference_evidence(source, config, subject)
        return {w: m.decide(evidence, config, w) for w in m.WORKFLOWS}

    def test_predeclared_denominator_and_independent_snapshots(self):
        ids = m.planned_rows((24, 96), (17, 29))
        self.assertEqual(len(ids), 12288)
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(self.outputs('allow_backup', 'p0')['countries']['value'], ['C0', 'C1'])
        self.assertEqual(self.outputs('add_substitute_role', 'p2')['recommend']['value'], 's1')
        self.assertEqual(self.outputs('restrict_country', 'p4')['recommend']['value'], 's0')
        self.assertEqual(self.outputs('supplier_move', 'p3')['audit']['decision'], 'blocked')
        self.assertEqual(self.outputs('remove_country', 'p3')['audit']['decision'], 'unknown')
        self.assertEqual(self.outputs('cost_change', 'p4')['recommend']['value'], 's0')
        self.assertEqual(self.outputs('initial', 'p4')['recommend']['value'], 's4')
        self.assertEqual(self.outputs('rename_country_field', 'p4'), self.outputs('initial', 'p4'))
        self.assertEqual(self.config['allowed_roles'], ['primary'])

    def test_clean_all_snapshots_and_arms_match(self):
        for snap in m.SNAPSHOTS:
            source, config = m.snapshot(self.source, self.config, snap)
            for arm in m.ARMS:
                state = m.deploy(arm, source, config, self.source, self.config, 'clean', 'audit')
                for subject in m.SUBJECTS:
                    evidence = m.reference_evidence(source, config, subject)
                    for workflow in m.WORKFLOWS:
                        actual = m.execute(arm, state, subject, workflow, self.query)
                        self.assertEqual(actual['evidence'], evidence, (snap, arm, subject))
                        self.assertEqual(actual['output'], m.decide(evidence, config, workflow))

    def test_missing_empty_blocked_and_cost_contract(self):
        for subject in ('p6', 'p_missing'):
            self.assertEqual(self.outputs('initial', subject)['recommend']['decision'], 'unknown')
        self.assertEqual(self.outputs('initial', 'p5')['recommend']['decision'], 'unavailable')
        evidence = m.reference_evidence(self.source, self.config, 'p1')
        evidence['candidates'][0]['country'] = None
        self.assertEqual(m.decide(evidence, self.config, 'audit')['decision'], 'blocked')
        evidence = m.reference_evidence(self.source, self.config, 'p4')
        evidence['candidates'][0]['cost'] = None
        self.assertEqual(m.decide(evidence, self.config, 'recommend')['decision'], 'unknown')
        for row in evidence['candidates']:
            row['cost'] = 10
        self.assertEqual(m.decide(evidence, self.config, 'recommend')['value'], 's0')

    def test_stale_configuration_topology_and_wrong_mapping_not_repaired(self):
        source, config = m.snapshot(self.source, self.config, 'restrict_country')
        local = m.deploy('local_json', source, config, self.source, self.config,
                         'stale_config_copy', 'audit')
        self.assertEqual(m.execute('local_json', local, 'p4', 'audit', self.query)['output']['decision'], 'clear')
        self.assertEqual(m.execute('local_json', local, 'p4', 'recommend', self.query)['output']['value'], 's0')
        self.assertIsNot(local['configs']['audit'], local['configs']['countries'])
        for arm in m.ARMS:
            state = m.deploy(arm, source, config, self.source, self.config,
                             'common_wrong_mapping', 'audit')
            self.assertEqual(m.execute(arm, state, 'p5', 'audit', self.query)['output']['decision'], 'clear')
            if state['projection'] is not None:
                self.assertFalse(state['provenance']['config_stale'])
        shared = m.deploy('shared_json_live', source, config, self.source, self.config,
                          'stale_config_copy', 'audit')
        self.assertEqual(m.execute('shared_json_live', shared, 'p4', 'recommend', self.query)['output']['value'], 's4')

    def test_projection_staleness_and_metadata_exclusion(self):
        source, config = m.snapshot(self.source, self.config, 'supplier_move')
        for arm in m.ARMS:
            state = m.deploy(arm, source, config, self.source, self.config,
                             'stale_projection', 'audit')
            actual = m.execute(arm, state, 'p3', 'audit', self.query)['output']['decision']
            self.assertEqual(actual, 'clear' if state['projection'] is not None else 'blocked')
        changed = copy.deepcopy(self.source)
        changed['products'][0]['description'] = 'Restricted supplier, do not use!'
        self.assertEqual(m.project(changed, self.config), m.project(self.source, self.config))
        source, config = m.snapshot(self.source, self.config, 'rename_country_field')
        state = m.deploy('rdf_hybrid', source, config, self.source, self.config, 'stale_projection', 'audit')
        self.assertTrue(state['provenance']['config_stale'])
        self.assertTrue(state['provenance']['source_stale'])

    def test_rdf_retrieval_has_no_json_fallback(self):
        state = m.deploy('rdf_hybrid', self.source, self.config, self.source, self.config, 'clean', 'audit')
        with patch.object(m, 'retrieve_json', side_effect=AssertionError('JSON fallback')):
            self.assertEqual(m.execute('rdf_hybrid', state, 'p1', 'audit', self.query)['output']['decision'], 'blocked')
        with patch.object(state['graph'], 'query', side_effect=RuntimeError('query failure')):
            with self.assertRaisesRegex(RuntimeError, 'query failure'):
                m.execute('rdf_hybrid', state, 'p1', 'audit', self.query)

    def test_run_preserves_failures_denominator_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'run'
            with patch.object(m, 'execute', side_effect=RuntimeError('injected execution failure')):
                manifest = m.run(output, (24,), (17,))
            self.assertEqual(manifest['status'], 'complete_with_errors')
            self.assertEqual(manifest['completed_rows'], 3072)
            rows = [json.loads(line) for line in (output / 'rows.jsonl').read_text().splitlines()]
            self.assertTrue(all(r['status'] == 'error' and 'actual' not in r for r in rows))
            self.assertEqual(len(rows), len(json.loads((output / 'planned-row-ids.json').read_text())))
            with self.assertRaises(FileExistsError):
                m.run(output, (24,), (17,))

    def test_interruption_keeps_partial_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'run'
            with patch.object(m, 'execute', side_effect=KeyboardInterrupt('test interruption')):
                with self.assertRaises(KeyboardInterrupt):
                    m.run(output, (24,), (17,))
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'interrupted')
            self.assertEqual(manifest['completed_rows'], 0)
            self.assertEqual(manifest['planned_rows'], 3072)


if __name__ == '__main__':
    unittest.main()
