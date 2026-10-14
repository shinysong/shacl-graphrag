"""Offline controller checks; none are additional research trials."""
import copy
import inspect
import json
import unittest
from scripts import run_bounded_refresh_study as r
from scripts import run_semantic_guard_study as g
from scripts import run_shared_semantics_study as base
from scripts.analyze_shared_semantics_study import reference


class BoundedRefreshTests(unittest.TestCase):
    def setUp(self):
        self.original, self.config = base.baseline(24, 17)

    def fixture(self, snapshot='initial', fault='clean', subject='p0', arm='shared_json_projection'):
        source, config = base.snapshot(self.original, self.config, snapshot)
        state = base.deploy(arm, source, config, self.original, self.config, fault, 'audit')
        actuals = {}
        for task in g.TASKS:
            installed = state['configs'].get(task, state['configs'].get('shared'))
            evidence = base.retrieve_json(state['data'], installed, subject, state['projection'] is not None)
            actuals[task] = dict(output=base.decide(evidence, installed, task), evidence=evidence)
        publisher = copy.deepcopy(config)
        if fault == 'common_wrong_mapping':
            publisher['location_field'] = 'tax_country'
        consumed = self.original if fault == 'stale_projection' and state['projection'] is not None else source
        packet = g.make_packet(actuals, state['configs'], publisher, source, consumed, subject,
                               state['projection'], state['provenance'].get('projected_location_field'))
        packet['subject'] = subject
        return packet, source, config

    def invoke(self, packet, source, policy='selective_refresh', catalog='documented', unavailable=False):
        self.calls = 0
        payload = json.dumps(source).encode()
        def fetch():
            self.calls += 1
            self.assertEqual(self.calls, 1)
            if unavailable:
                raise r.SourceUnavailable('test outage')
            return payload
        result = r.runtime_policy(packet, g.CATALOGS[catalog], policy, fetch)
        self.assertEqual(self.calls, result['fetch_attempts'])
        self.assertEqual(result['payload_bytes'], len(payload) if self.calls and not unavailable else 0)
        return result

    def test_correct_case_eager_and_selective(self):
        packet, source, _ = self.fixture()
        frozen = copy.deepcopy(packet)
        for policy, count in [('veto_only', 0), ('selective_refresh', 0), ('eager_refresh', 1)]:
            result = self.invoke(packet, source, policy)
            self.assertEqual(result['fetch_attempts'], count)
            self.assertTrue(all(result['allowed'].values()))
            self.assertFalse(any(result['changed_outputs'].values()))
        self.assertEqual(packet, frozen)

    def test_cost_change_triggers_whole_bundle_once(self):
        packet, source, config = self.fixture('cost_change', 'stale_projection', 'p4')
        result = self.invoke(packet, source)
        self.assertEqual(result['before_checks']['countries']['selective']['status'], 'valid')
        self.assertEqual(result['before_checks']['recommend']['selective']['status'], 'conflict')
        self.assertEqual(result['fetch_attempts'], 1)
        self.assertTrue(all(result['allowed'].values()))
        self.assertFalse(result['changed_outputs']['countries'])
        self.assertTrue(result['changed_outputs']['recommend'])
        for task in g.TASKS:
            self.assertEqual(result['actuals'][task], reference(source, config, 'p4', task))

    def test_semantic_catalog_blocks_or_preserves_wrong_mapping(self):
        packet, source, config = self.fixture(fault='common_wrong_mapping', subject='p5')
        for catalog in ('documented', 'absent'):
            for policy in r.POLICIES:
                result = self.invoke(packet, source, policy, catalog)
                self.assertEqual(result['fetch_attempts'], 0)
                self.assertFalse(any(result['allowed'].values()))
        result = self.invoke(packet, source, 'eager_refresh', 'mislabeled')
        self.assertTrue(all(result['allowed'].values()))
        self.assertEqual(result['fetch_attempts'], 1)
        self.assertFalse(any(result['changed_outputs'].values()))
        self.assertNotEqual(result['actuals']['audit']['output'], reference(source, config, 'p5', 'audit')['output'])

    def test_unavailable_withholds_entire_requested_bundle(self):
        packet, source, _ = self.fixture('cost_change', 'stale_projection', 'p4')
        result = self.invoke(packet, source, unavailable=True)
        self.assertEqual(result['error']['type'], 'SourceUnavailable')
        self.assertFalse(any(result['allowed'].values()))
        self.assertEqual(result['actuals'], packet['actuals'])
        packet, source, _ = self.fixture()
        result = self.invoke(packet, source, unavailable=True)
        self.assertEqual(result['fetch_attempts'], 0)
        self.assertTrue(all(result['allowed'].values()))

    def test_stale_response_and_config_only_change(self):
        packet, _, _ = self.fixture('supplier_move', 'stale_projection', 'p3')
        result = self.invoke(packet, self.original)
        self.assertFalse(any(result['allowed'].values()))
        for task in g.TASKS:
            self.assertEqual(result['after_checks'][task]['selective']['status'], 'conflict')
            self.assertEqual(result['refreshed_packet']['workflows'][task]['hashes']['current_dependency'],
                             packet['workflows'][task]['hashes']['current_dependency'])
        packet, _, _ = self.fixture('allow_backup', 'stale_config_copy')
        result = self.invoke(packet, self.original)
        self.assertTrue(all(result['allowed'].values()))

    def test_refresh_cannot_fill_source_absence(self):
        packet, source, _ = self.fixture('remove_country', 'stale_projection', 'p3')
        result = self.invoke(packet, source)
        self.assertTrue(all(result['allowed'].values()))
        self.assertTrue(all(a['output']['decision'] == 'unknown' for a in result['actuals'].values()))

    def test_cross_conflict_triggers_refresh_and_semantic_block_is_group_wide(self):
        packet, source, _ = self.fixture('restrict_country', 'stale_config_copy', 'p4', 'local_json')
        result = self.invoke(packet, source)
        self.assertEqual(result['before_checks']['audit']['cross']['status'], 'conflict')
        self.assertEqual(result['fetch_attempts'], 1)
        packet, source, _ = self.fixture()
        packet['workflows']['countries']['installed']['location_field'] = 'tax_country'
        result = self.invoke(packet, source, 'eager_refresh')
        self.assertEqual(result['fetch_attempts'], 0)
        self.assertFalse(result['allowed']['countries'])
        self.assertTrue(result['allowed']['audit'])

    def test_signature_scoring_and_declared_denominators(self):
        self.assertEqual(tuple(inspect.signature(r.runtime_policy).parameters), ('packet', 'catalog', 'policy', 'fetch'))
        known = dict(output=dict(decision='clear', value=None))
        unknown = dict(output=dict(decision='unknown', value=None))
        corrected = r.evaluate(unknown, known, known, True)
        self.assertTrue(corrected['corrected_wrong_to_correct'])
        self.assertEqual(corrected['outcome'], 'correct_retained')
        self.assertTrue(r.evaluate(known, unknown, known, True)['regression_correct_to_wrong'])
        self.assertFalse(r.evaluate(unknown, known, known, False)['corrected_wrong_to_correct'])
        self.assertTrue(r.evaluate(known, known, known, False)['unnecessary_abstention'])
        self.assertTrue(r.evaluate(unknown, unknown, unknown, False)['correct_unknown_withheld'])
        self.assertEqual(r.EXPECTED, 331776)
        self.assertEqual(r.EXPECTED // 3, 110592)


if __name__ == '__main__':
    unittest.main()
