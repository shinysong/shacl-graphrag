"""Authored question tool controls with scripted model responses, not quality evaluation."""
import json
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab import preparation as p, workspace_question
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_workspace_question import Gateway, FINAL
from tests.test_workspace_relations import fixture


class RelationQuestionTests(unittest.TestCase):
    def test_real_comparison_in_answer_input_replay_and_withdrawal(self):
        draft, rid = fixture()
        plan = {'calls': [{'tool': 'relation_rows', 'arguments': {'relation_id': rid, 'value': value}}
                          for value in ('A', 'C')], 'unresolved': ['Refund policy not checked']}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'db'
            gateway = Gateway([plan, {**FINAL, 'citations': ['e1', 'e2']}])
            service = WorkspaceService(path, question_gateway=gateway)
            row = service.store.create('Relations', draft)
            request = dict(action='ask', id=row['id'], revision=1, request_key='q',
                           question='Compare A and C across orders and lines; can they be refunded?')
            op = service.handle(request)['operation']
            self.assertEqual(op['state'], 'completed', op.get('error'))
            trace = op['result']
            self.assertEqual(len(trace['catalog']['relation_rows']), 1)
            for e, counts in zip(trace['evidence'], ({'source':2,'target':1}, {'source':1,'target':0})):
                self.assertEqual(e['parameter_origin'], 'model_interpretation')
                self.assertEqual(e['result']['record_counts'], counts)
                self.assertIn('relationship_truth', e['result']['unchecked'])
            self.assertEqual(trace['answer_input']['evidence'], trace['evidence'])
            self.assertNotIn('secret', json.dumps(trace['answer_input']))
            self.assertEqual(trace['unresolved'], plan['unresolved'])
            self.assertEqual(WorkspaceService(path).handle(request)['operation']['result'], trace)
            self.assertEqual(len(gateway.calls), 2)
            relation = next(e for e in draft['entries'] if e['id'] == rid)
            service.handle(dict(action='change', id=row['id'], revision=1, decisions=[
                dict(entry_id=rid, status='excluded', target=relation['target'],
                     note='Withdraw', interpretation=relation['interpretation'])]))
            service.question_gateway = Gateway([plan])
            failed = service.handle({**request, 'revision':2, 'request_key':'new'})['operation']
            self.assertEqual(failed['state'], 'failed')
            self.assertNotIn('relation_rows', failed['result']['catalog'])
            self.assertEqual(failed['result']['evidence'], [])
            self.assertEqual(len(service.question_gateway.calls), 1)
            self.assertEqual(service.handle(request)['operation']['result'], trace)

    def test_invalid_parameters_preserve_failed_evidence(self):
        draft, rid = fixture()
        for args in ({'relation_id':'invented','value':'A'},
                     {'relation_id':rid,'value':' '},
                     {'relation_id':rid,'value':'A','query':'anything'}):
            with self.subTest(args=args):
                responses = iter([dict(calls=[dict(tool='relation_rows', arguments=args)], unresolved=[]),
                                  dict(answer='No result',citations=[],unresolved=['No valid comparison'])])
                saved=[]
                result=workspace_question.ask(draft,'Compare records',
                    lambda messages: {'content':json.dumps(next(responses))}, lambda t:saved.append(json.loads(json.dumps(t))))
                self.assertEqual(result['evidence'][0]['state'],'failed')
                self.assertNotIn('result',result['evidence'][0])
                self.assertEqual(result['answer_input']['evidence'],result['evidence'])
