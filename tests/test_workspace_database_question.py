"""Scripted interface checks, not measured model interpretation accuracy."""
from copy import deepcopy
import json
import unittest

from apps.factory_lab.workspace_database_question import ask

CATALOG = [{'approval_operation_id': 'approved-17', 'parameters': {'when': 'date', 'n': 'integer'},
            'question_scope': 'Observed units at the supplied date', 'version': 'reviewed-query-3'}]
PLAN = {'calls': [{'approval_operation_id': 'approved-17', 'parameters': {'when': '2026-11-19', 'n': 2}}],
        'unresolved': ['External truth is not established.']}
FINAL = {'answer': 'Observed units.', 'citations': ['e1'], 'unresolved': []}
RESULT = {'rows': [{'units': '9007199254740993'}], 'truncated': True, 'total_output_rows': 300,
          'returned_count': 1, 'status': 'incomplete', 'output_kind': 'potential_impact_candidates',
          'provenance': {'contract_fingerprint': 'abc', 'source': {'snapshot_sha256': '123'}}}


class Harness:
    def __init__(self, responses, result=RESULT):
        self.responses = iter(responses)
        self.messages = []; self.executions = []; self.snapshots = []
        self.result = result

    def call(self, messages):
        self.messages.append(deepcopy(messages))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return {'content': json.dumps(response), 'receipt': {'call_id': str(len(self.messages))}}

    def execute(self, ident, parameters, evidence_id):
        self.executions.append((ident, parameters, evidence_id))
        if isinstance(self.result, Exception):
            raise self.result
        return deepcopy(self.result)

    def run(self, **kwargs):
        return ask('Show the observed units', catalog=kwargs.pop('catalog', CATALOG), call=self.call,
                   execute=self.execute, checkpoint=self.snapshots.append, **kwargs)


class DatabaseQuestionTests(unittest.TestCase):
    def test_fixed_execution_preserves_full_evidence_scope_and_receipt(self):
        h = Harness([PLAN, FINAL]); result = h.run()
        self.assertEqual(h.executions, [('approved-17', PLAN['calls'][0]['parameters'], 'e1')])
        packet = json.loads(h.messages[1][1]['content'])
        self.assertEqual(packet['evidence'][0]['result'], RESULT)
        self.assertEqual(result['evidence'][0]['result'], RESULT)
        self.assertEqual(result['unresolved'], PLAN['unresolved'])
        self.assertEqual(result['model_responses'][0]['receipt']['call_id'], '1')
        self.assertEqual(h.snapshots[0]['evidence'], [])
        self.assertEqual(result['catalog'], CATALOG)
        self.assertEqual(len(h.messages), 2)

    def test_all_selections_validated_before_first_execution(self):
        for bad in ({'approval_operation_id': 'unapproved', 'parameters': {}},
                    {'approval_operation_id': 'approved-17', 'parameters': {'when': '2026-11-19', 'n': 2}, 'sql': 'SELECT 1'}):
            with self.subTest(bad=bad):
                plan = deepcopy(PLAN); plan['calls'].append(bad)
                h = Harness([plan])
                with self.assertRaises(ValueError): h.run()
                self.assertEqual(h.executions, [])
                self.assertEqual(h.snapshots[-1]['plan'], plan)

    def test_exact_parameter_types_and_names(self):
        for values in ({'when': '2026-11-19', 'n': True}, {'when': '2026-11-19', 'n': '2'},
                       {'when': '2026-02-30', 'n': 2}, {'when': '20261119', 'n': 2},
                       {'when': '2026-11-19', 'n': 2**63}, {'when': '2026-11-19'},
                       {'when': '2026-11-19', 'n': {'from_evidence': 'e1'}},
                       {'when': '2026-11-19', 'n': 2, 'extra': 3}):
            with self.subTest(values=values):
                plan = deepcopy(PLAN); plan['calls'][0]['parameters'] = values
                h = Harness([plan])
                with self.assertRaises(ValueError): h.run()
                self.assertEqual(h.executions, [])

    def test_catalog_and_call_limits(self):
        for catalog in (CATALOG * 2, CATALOG * 21):
            h = Harness([])
            with self.assertRaises(ValueError): h.run(catalog=catalog)
            self.assertEqual(h.messages, [])
        plan = deepcopy(PLAN); plan['calls'] *= 5
        h = Harness([plan])
        with self.assertRaises(ValueError): h.run()
        self.assertEqual(h.executions, [])

    def test_unresolved_and_empty_catalog_skip_unneeded_answer_call(self):
        h = Harness([{'calls': [], 'unresolved': ['Date missing']}]); out = h.run()
        self.assertEqual(out['unresolved'], ['Date missing'])
        self.assertEqual(len(h.messages), 1)
        h = Harness([]); out = h.run(catalog=[])
        self.assertEqual(h.messages, [])
        self.assertTrue(out['unresolved'])
        self.assertEqual(out['citations'], [])

    def test_failed_execution_is_not_citable_or_retried(self):
        h = Harness([PLAN], result=ValueError('Snapshot changed')); out = h.run()
        self.assertEqual(out['evidence'][0]['state'], 'failed')
        self.assertEqual(len(h.executions), 1)
        self.assertEqual(len(h.messages), 1)
        self.assertEqual(out['citations'], [])

    def test_invalid_citation_retains_full_trace(self):
        h = Harness([PLAN, {**FINAL, 'citations': ['invented']}])
        with self.assertRaises(ValueError): h.run()
        self.assertEqual(h.snapshots[-1]['evidence'][0]['result'], RESULT)
        self.assertEqual(len(h.snapshots[-1]['model_responses']), 2)

    def test_wrong_valid_interpretation_is_preserved(self):
        plan = deepcopy(PLAN); plan['calls'][0]['parameters']['n'] = 99
        h = Harness([plan, {**FINAL, 'answer': 'A semantically wrong but schema-valid answer.'}])
        out = h.run()
        self.assertEqual(out['answer'], 'A semantically wrong but schema-valid answer.')
        self.assertEqual(h.executions[0][1]['n'], 99)

    def test_answer_context_overflow_retains_all_evidence_without_second_call(self):
        result = {'rows': [{'value': 'x' * 40000}], 'truncated': False}
        h = Harness([PLAN], result=result)
        with self.assertRaises(ValueError): h.run()
        self.assertEqual(len(h.messages), 1)
        self.assertEqual(h.snapshots[-1]['evidence'][0]['result'], result)
        self.assertFalse(h.snapshots[-1]['failure']['evidence_truncated'])
        self.assertEqual(h.snapshots[-1]['failure']['phase'], 'answering')

    def test_catalog_context_overflow_prevents_paid_call(self):
        catalog = deepcopy(CATALOG); catalog[0]['question_scope'] = 'x' * 40000
        h = Harness([])
        with self.assertRaises(ValueError): h.run(catalog=catalog)
        self.assertEqual(h.messages, [])
        self.assertFalse(h.snapshots[-1]['failure']['call_sent'])

    def test_provider_failure_leaves_evidence_and_does_not_retry(self):
        h = Harness([PLAN, RuntimeError('Provider unavailable')])
        with self.assertRaises(RuntimeError): h.run()
        self.assertEqual(len(h.messages), 2)
        self.assertEqual(h.snapshots[-1]['evidence'][0]['result'], RESULT)

    def test_cancel_after_response_retains_raw_response(self):
        class Cancelled(RuntimeError): pass
        h = Harness([PLAN])
        def cancel():
            if h.messages: raise Cancelled()
        with self.assertRaises(Cancelled): h.run(check_cancel=cancel)
        self.assertEqual(len(h.snapshots[-1]['model_responses']), 1)
        self.assertEqual(h.executions, [])

    def test_differently_named_contract_uses_identical_interface(self):
        catalog = [{'approval_operation_id': 'membership-traversal-9', 'parameters': {'seed': 'text'}}]
        plan = {'calls': [{'approval_operation_id': 'membership-traversal-9', 'parameters': {'seed': 'P7'}}], 'unresolved': []}
        h = Harness([plan, FINAL]); h.run(catalog=catalog)
        self.assertEqual(h.executions, [('membership-traversal-9', {'seed': 'P7'}, 'e1')])


if __name__ == '__main__':
    unittest.main()
