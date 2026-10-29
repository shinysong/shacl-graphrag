"""Development software checks, not the future study's independent scorer."""
import copy
import json
import unittest

from scripts.build_evidence_report_demo import compute, fixtures, prompt


class EvidenceReportDevelopmentTests(unittest.TestCase):
    def test_same_observations_do_not_reveal_source_origin(self):
        omitted, absent = fixtures()[2:]
        self.assertNotEqual(omitted['source_rows'], absent['source_rows'])
        self.assertEqual(omitted['visible'], absent['visible'])
        self.assertEqual(compute(omitted['visible']), compute(absent['visible']))
        for arm in 'ABC':
            self.assertEqual(prompt(omitted['visible'], compute(omitted['visible']), arm),
                             prompt(absent['visible'], compute(absent['visible']), arm))

    def test_main_decisions_and_actual_owl_parity(self):
        results = [compute(c['visible']) for c in fixtures()]
        self.assertEqual([r['decision'] for r in results], ['required', 'not_required', 'unknown', 'unknown'])
        for r in results:
            self.assertEqual(r['derivation']['python_reachable'], r['derivation']['owlrl_reachable'])
        self.assertTrue(all(r['validation']['conforms'] for r in results))
        self.assertEqual(results[0]['path_row_ids'], ['r-bom-1', 'r-bom-2'])

    def test_expiry_boundary_and_missing_field(self):
        visible = fixtures()[0]['visible']
        visible['rows'][0]['expires_on'] = visible['as_of']
        self.assertEqual(compute(visible)['decision'], 'not_required')
        del visible['rows'][0]['expires_on']
        result = compute(visible)
        self.assertEqual(result['decision'], 'unknown')
        self.assertFalse(result['validation']['conforms'])

    def test_wrong_role_does_not_make_path(self):
        visible = fixtures()[0]['visible']
        visible['rows'][2]['predicate'] = 'storedAt'
        result = compute(visible)
        self.assertEqual(result['decision'], 'unknown')
        self.assertFalse(result['derivation']['python_reachable'])

    def test_duplicate_certificate_is_unknown(self):
        visible = fixtures()[0]['visible']
        visible['rows'].append(copy.deepcopy(visible['rows'][0]))
        self.assertEqual(compute(visible)['decision'], 'unknown')

    def test_arms_only_add_declared_payload_fields(self):
        visible = fixtures()[0]['visible']; report = compute(visible)
        def payload(arm):
            text = prompt(visible, report, arm)
            return json.loads(text[text.index('{'):])
        a, b, c = [payload(arm) for arm in 'ABC']
        self.assertEqual(a, visible)
        self.assertEqual(b.pop('computed_decision'), report['decision'])
        self.assertEqual(c.pop('computed_decision'), report['decision'])
        evidence = c.pop('computed_evidence')
        self.assertEqual(a, b); self.assertEqual(a, c)
        self.assertTrue(set(evidence['support_row_ids']) <= {r['row_id'] for r in visible['rows']})
        self.assertNotIn('source_rows', a)


if __name__ == '__main__':
    unittest.main()
