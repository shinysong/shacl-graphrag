"""Software checks for a bounded positive entailment experiment, not measurements."""
import copy
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_ontology_reasoning_study as study


class OntologyReasoningTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.gold = study.fixture_suite()

    def test_fixture_denominator_and_evaluator_separation(self):
        self.assertEqual(study.fixture_suite(), (self.cases, self.gold))
        self.assertEqual(len(self.cases), 64)
        self.assertEqual(sum(len(c['queries']) for c in self.cases) * 3, 1920)
        for case in self.cases:
            self.assertEqual(set(case), {'id', 'schema', 'facts', 'queries'})
            for query in case['queries']:
                self.assertEqual(set(query), {'id', 'triple'})
        self.assertEqual(list(inspect.signature(study.infer).parameters), ['schema', 'facts', 'arm'])
        self.assertEqual(list(inspect.signature(study.json_closure).parameters), ['schema', 'facts'])
        case = self.cases[0]
        before = study.infer(case['schema'], case['facts'], 'json_rules')['triples']
        altered = copy.deepcopy(self.gold)
        altered[case['queries'][0]['id']]['membership'] = 'entailed'
        after = study.infer(case['schema'], case['facts'], 'json_rules')['triples']
        self.assertEqual(before, after)

    def test_query_parity_and_independent_expected_labels(self):
        # Full finite fixture check, not a claim of complete OWL-RL equivalence.
        for case in self.cases:
            outputs = [study.infer(case['schema'], case['facts'], arm)
                       for arm in ('json_rules', 'owlrl')]
            for query in case['queries']:
                predictions = [study.answer(query['triple'], result) for result in outputs]
                for prediction in predictions:
                    self.assertEqual(study.evaluate(prediction, self.gold[query['id']]),
                                     {'membership_agreement': True, 'conflict_agreement': True},
                                     query['id'])
                self.assertEqual(predictions[0]['membership'], predictions[1]['membership'])

    def test_missing_mappings_and_direction(self):
        for case in self.cases:
            result = study.infer(case['schema'], case['facts'], 'json_rules')
            for query in case['queries']:
                gold = self.gold[query['id']]
                if gold['query_kind'] in ('reverse', 'inverse_direction', 'chain_reverse'):
                    self.assertEqual(study.answer(query['triple'], result)['membership'], 'unknown')
                if not gold['mapped'] and gold['query_kind'] in ('subclass', 'transitive', 'inverse', 'property_chain'):
                    self.assertEqual(study.answer(query['triple'], result)['membership'], 'unknown')
                if gold['depth'] > 1 and gold['query_kind'] == 'direct':
                    self.assertEqual(study.answer(query['triple'], result)['membership'], 'unknown')

    def test_cycles_terminate_without_inventing_inverse(self):
        p, q, a, b = map(study.term, ('p', 'q', 'a', 'b'))
        schema = [(p, study.TYPE, study.TRANSITIVE), (p, study.SUBPROPERTY, q),
                  (q, study.SUBPROPERTY, p)]
        facts = [(a, p, b), (b, p, a)]
        closure, proof = study.json_closure(schema, facts)
        self.assertIn((a, p, a), closure)
        self.assertLess(len(closure), 20)
        self.assertTrue(study.proof_support((a, p, a), proof))
        closure, _ = study.json_closure(schema, [(a, p, b)])
        self.assertNotIn((b, p, a), closure)

    def test_proofs_use_actual_input_leaves(self):
        for case in self.cases:
            result = study.infer(case['schema'], case['facts'], 'json_rules')
            asserted = set(map(tuple, case['schema'] + case['facts']))
            for query in case['queries']:
                proof = study.answer(query['triple'], result)['proof']
                for node in proof:
                    if node['rule'] == 'asserted':
                        self.assertIn(tuple(node['triple']), asserted)
                    else:
                        self.assertTrue(node['premises'])
                        for premise in node['premises']:
                            self.assertIn(tuple(premise), result['triples'])

    def test_conflict_is_separate_and_does_not_explode(self):
        case = next(c for c in self.cases if self.gold[c['queries'][0]['id']]['conflict'])
        for arm in ('json_rules', 'owlrl'):
            result = study.infer(case['schema'], case['facts'], arm)
            self.assertTrue(result['conflicts'])
            unrelated = case['queries'][7]
            self.assertEqual(study.answer(unrelated['triple'], result)['membership'], 'unknown')
            if arm == 'owlrl':
                self.assertTrue(result['diagnostics'])
        asserted = study.infer(case['schema'], case['facts'], 'asserted')
        self.assertFalse(asserted['conflicts'])  # The conflicting superclass type is derived.

    def test_property_chain_validation(self):
        p, head, a = map(study.term, ('p', 'head', 'a'))
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            study.property_chains([(p, study.CHAIN, head), (head, study.FIRST, a),
                                   (head, study.REST, head)])
        with self.assertRaisesRegex(ValueError, 'Malformed'):
            study.property_chains([(p, study.CHAIN, head)])

    def test_failed_run_preserves_denominator_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'run'
            with patch.object(study, 'infer', side_effect=RuntimeError('injected failure')):
                with self.assertRaisesRegex(RuntimeError, 'injected failure'):
                    study.run(output)
            status = json.loads((output / 'status.json').read_text())
            self.assertEqual(status['status'], 'failed')
            self.assertEqual(status['completed_rows'], 0)
            self.assertEqual(status['planned_rows'], 1920)
            self.assertTrue(all(r['status'] == 'not_executed'
                                for r in json.loads((output / 'planned.json').read_text())))
            before = (output / 'status.json').read_bytes()
            with self.assertRaises(FileExistsError):
                study.run(output)
            self.assertEqual(before, (output / 'status.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
