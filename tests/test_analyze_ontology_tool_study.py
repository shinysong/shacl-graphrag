"""Offline scorer boundary checks with scripted traces, not LLM outcomes."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('analysis', Path(__file__).parents[1] / 'scripts/analyze_ontology_tool_study.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class AnalysisTests(unittest.TestCase):
    def test_json_types_and_unordered_lists(self):
        self.assertFalse(m.typed_equal(True, 1))
        self.assertFalse(m.typed_equal(1, 1.0))
        self.assertTrue(m.typed_equal(['b', 'a'], ['a', 'b']))
        self.assertFalse(m.typed_equal(['a', 'a'], ['a']))

    def test_denominators_citations_caveats_and_failed_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            refs = root / 'references.json'
            refs.write_text(json.dumps([{'case_id': 'case01', 'family': 'F1', 'scenario': 'lapsed', 'expected': {'status': 'known', 'value': 'LEI-P', 'evidence_ids': ['r1'], 'required_caveat_terms': ['LAPSED']}}]))
            run = root / 'run'
            run.mkdir()
            answer = {'status': 'known', 'value': 'LEI-P', 'evidence_ids': ['invented'], 'caveats': []}
            (run / 'record.json').write_text(json.dumps({'rows': [{'case_id': 'case01', 'arm': 'A', 'status': 'finished', 'answer': answer, 'counts': {'model_calls': 2}}, {'case_id': 'case01', 'arm': 'B', 'status': 'not_executed'}, {'case_id': 'case01', 'arm': 'C', 'status': 'failed'}]}))
            (run / 'runtime.json').write_text(json.dumps([{'case_id': 'case01', 'runtime': {'question': 'Question', 'source_turtle': '<urn:r1> <urn:business-questions:id> "r1" .'}}]))
            episode = run / 'case01-A'
            episode.mkdir()
            events = [{'event_type': 'tool_result', 'payload': {'name': 'query', 'response': {'status': 'error', 'error_type': 'QueryRejected'}}}, {'event_type': 'tool_result', 'payload': {'name': 'check_query_contract', 'response': {'status': 'unknown'}}}, {'event_type': 'model_interpretation', 'payload': {'role': 'direct_accounting_parent'}}]
            (episode / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
            for n in (1, 2):
                call = episode / f'call{n}'
                call.mkdir()
                (call / 'request.json').write_text('{}')
            (episode / 'call1/metadata.json').write_text(json.dumps({'usage': {'cost': 0.01}}))
            (episode / 'call2/failure.json').write_text('{}')
            result = m.analyze([run], refs)
            counts = result['overall']['counts']
            self.assertEqual((counts['assigned'], counts['finished'], counts['unfinished'], counts['failed']), (3, 1, 1, 1))
            self.assertEqual(counts['decision_match'], 1)
            self.assertEqual(counts['qualified_decision_match'], 0)
            self.assertEqual(counts['evidence_exact'], 0)
            self.assertEqual(counts['invalid_citation_episodes'], 1)
            self.assertEqual(counts['calls_without_metadata'], 1)
            self.assertEqual(result['overall']['reported_cost_usd'], 0.01)
            self.assertEqual(result['overall']['check_results'], {'unknown': 1})
            self.assertEqual(len(result['rows'][0]['tool_errors']), 1)
            self.assertIn('unverified', result['rows'][0]['semantic_stage_attribution'])
            repeated = m.analyze([run, run], refs)
            self.assertEqual(repeated['overall']['counts']['assigned'], 6)
            self.assertEqual(len(repeated['repeated_assignments']), 3)


if __name__ == '__main__':
    unittest.main()
