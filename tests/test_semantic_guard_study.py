"""Guard contract checks: offline software tests, not additional study outcomes."""
import copy
import unittest
from scripts import run_semantic_guard_study as g
from scripts import run_shared_semantics_study as base


class SemanticGuardTests(unittest.TestCase):
    def setUp(self):
        self.source, self.config = base.baseline(24, 17)

    def packet(self, snapshot='initial', fault='clean', subject='p0', arm='shared_json_projection'):
        source, config = base.snapshot(self.source, self.config, snapshot)
        state = base.deploy(arm, source, config, self.source, self.config, fault, 'audit')
        actuals = {}
        for task in g.TASKS:
            installed = state['configs'].get(task, state['configs'].get('shared'))
            evidence = base.retrieve_json(state['data'], installed, subject, state['projection'] is not None)
            actuals[task] = dict(output=base.decide(evidence, installed, task), evidence=evidence)
        publisher = copy.deepcopy(config)
        if fault == 'common_wrong_mapping':
            publisher['location_field'] = 'tax_country'
        consumed = self.source if fault == 'stale_projection' and state['projection'] is not None else source
        return g.make_packet(actuals, state['configs'], publisher, source, consumed, subject,
                             state['projection'], state['provenance'].get('projected_location_field'))

    def test_cost_relevance_and_unrelated_records(self):
        packet = self.packet('cost_change', 'stale_projection', 'p4')
        for task in ('countries', 'audit'):
            self.assertEqual(g.freshness_guard(packet, task, True)['status'], 'valid')
        self.assertEqual(g.freshness_guard(packet, 'recommend', True)['status'], 'conflict')
        changed = copy.deepcopy(self.source)
        changed['suppliers'].append(dict(id='unrelated', old_country='C2', cost=999))
        changed['products'].append(dict(id='unrelated'))
        changed['products'][0]['description'] = 'new unrelated metadata'
        for task in g.TASKS:
            self.assertEqual(g.dependency(changed, 'old_country', 'p0', task),
                             g.dependency(self.source, 'old_country', 'p0', task))

    def test_stale_role_policy_and_inactive_edge_dependencies(self):
        packet = self.packet('allow_backup', 'stale_config_copy')
        self.assertEqual(g.freshness_guard(packet, 'countries', True)['status'], 'conflict')
        packet = self.packet('add_substitute_role', 'stale_config_copy', 'p2')
        self.assertEqual(g.freshness_guard(packet, 'countries', True)['status'], 'conflict')
        before = g.dependency(self.source, 'old_country', 'p0', 'countries')
        self.assertEqual(len(before['connected']), 2)  # backup remains visible before eligibility.
        changed = copy.deepcopy(self.source)
        changed['edges'][1]['role'] = 'replacement'
        self.assertNotEqual(before, g.dependency(changed, 'old_country', 'p0', 'countries'))

    def test_wrong_mapping_catalog_limits_and_coherent_cross_pass(self):
        packet = self.packet(fault='common_wrong_mapping', subject='p5')
        self.assertEqual(g.freshness_guard(packet, 'audit')['status'], 'valid')
        self.assertEqual(g.freshness_guard(packet, 'audit', True)['status'], 'valid')
        self.assertEqual(g.cross_guard(packet)['status'], 'valid')
        self.assertEqual(g.semantic_guard(packet, 'audit', g.CATALOGS['documented'])['status'], 'conflict')
        self.assertEqual(g.semantic_guard(packet, 'audit', g.CATALOGS['absent'])['status'], 'missing')
        self.assertEqual(g.semantic_guard(packet, 'audit', g.CATALOGS['mislabeled'])['status'], 'valid')
        self.assertEqual(packet['actuals']['audit']['output']['decision'], 'clear')

    def test_cross_workflow_contradiction_and_recommend_evidence(self):
        packet = self.packet('restrict_country', 'stale_config_copy', 'p4', 'local_json')
        self.assertIn('audit_countries_contradiction', g.cross_guard(packet)['reasons'])
        packet = self.packet()
        packet['actuals']['recommend']['output'] = dict(decision='recommended', value='missing_supplier')
        self.assertIn('recommend_countries_contradiction', g.cross_guard(packet)['reasons'])

    def test_rename_and_projection_mapping_semantics(self):
        packet = self.packet('rename_country_field', 'stale_projection')
        self.assertEqual(g.freshness_guard(packet, 'countries', True)['status'], 'conflict')
        self.assertEqual(g.semantic_guard(packet, 'countries', g.CATALOGS['documented'])['status'], 'valid')
        packet['workflows']['countries']['projection_mapping'] = 'tax_country'
        self.assertEqual(g.semantic_guard(packet, 'countries', g.CATALOGS['documented'])['status'], 'conflict')

    def test_scoring_known_and_unknown_withheld(self):
        known = dict(output=dict(decision='clear', value=None))
        unknown = dict(output=dict(decision='unknown', value=None))
        self.assertTrue(g.evaluate(known, known, False)['unnecessary_abstention'])
        self.assertFalse(g.evaluate(unknown, unknown, False)['unnecessary_abstention'])
        self.assertTrue(g.evaluate(unknown, unknown, False)['correct_unknown_withheld'])
        self.assertEqual(g.evaluate(known, unknown, True)['outcome'], 'wrong_allowed')
        self.assertEqual(g.evaluate(known, unknown, False)['outcome'], 'wrong_withheld')

    def test_bad_input_rows_and_packet_rejected(self):
        manifest = dict(sizes=[24, 96], seeds=[17, 29], protocol='shared-semantics-1',
                        status='complete', completed_rows=12288, planned_rows=12288)
        ids = base.planned_rows((24, 96), (17, 29))
        with self.assertRaises(ValueError):
            g.validate_rows(manifest, ids, [])
        with self.assertRaises(ValueError):
            g.validate_rows(manifest, ids + [ids[0]], [])
        with self.assertRaises(ValueError):
            g.make_packet({}, {'shared': self.config}, self.config, self.source, self.source, 'p0')


if __name__ == '__main__':
    unittest.main()
