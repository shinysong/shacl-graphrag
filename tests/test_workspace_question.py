import json
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab.workspace_service import WorkspaceService
from tests.workspace_fixtures import approved, compared

class Gateway:
    config={'model':'scripted-not-live'}
    def __init__(self,answers):self.answers=iter(answers);self.calls=[]
    def call(self,key,messages):
        self.calls.append((key,messages))
        answer=next(self.answers)
        if isinstance(answer,Exception):raise answer
        return {'content':json.dumps(answer)}

PLAN={'calls':[{'tool':'source_lookup','arguments':{'table':'orders','identifier':'O1'}}],
      'unresolved':['Refund eligibility not supported by this lookup']}
FINAL={'answer':'Scripted source observation','citations':['e1'],'unresolved':[]}

class QuestionTests(unittest.TestCase):
    def test_real_lookup_scripted_answer_durable_and_no_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';gateway=Gateway([PLAN,FINAL]);service=WorkspaceService(path,question_gateway=gateway)
            row=service.store.create('approved',approved())
            request={'action':'ask','id':row['id'],'revision':1,'request_key':'q','question':'Check O1 and refund eligibility'}
            op=service.handle(request)['operation']
            self.assertEqual(op['state'],'completed')
            result=op['result'];self.assertEqual(result['evidence'][0]['result']['mode'],'source_lookup')
            self.assertEqual(result['unresolved'],PLAN['unresolved'])
            self.assertEqual(result['workspace']['revision'],1)
            self.assertEqual(len(gateway.calls),2)
            self.assertEqual(WorkspaceService(path).handle(request)['operation']['result'],result)
            self.assertEqual(len(gateway.calls),2)

    def test_failed_answer_retains_actual_lookup_and_raw_plan_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            gateway=Gateway([PLAN,RuntimeError('provider unavailable')]);service=WorkspaceService(Path(tmp)/'db',question_gateway=gateway)
            row=service.store.create('approved',approved());request={'action':'ask','id':row['id'],'revision':1,'request_key':'q','question':'Check O1'}
            op=service.handle(request)['operation']
            self.assertEqual(op['state'],'failed')
            self.assertEqual(op['result']['evidence'][0]['state'],'completed')
            self.assertEqual(len(op['result']['model_responses']),1)
            self.assertTrue(service.handle(request)['reused'])
            self.assertEqual(len(gateway.calls),2)

    def test_unadvertised_tool_and_fabricated_citation_fail(self):
        for responses in ([{'calls':[{'tool':'run_sql','arguments':{}}],'unresolved':[]}],
                          [PLAN,{**FINAL,'citations':['invented']} ]):
            with self.subTest(responses=responses),tempfile.TemporaryDirectory() as tmp:
                gateway=Gateway(responses);service=WorkspaceService(Path(tmp)/'db',question_gateway=gateway)
                row=service.store.create('approved',approved())
                op=service.handle({'action':'ask','id':row['id'],'revision':1,'request_key':'q','question':'Check order'})['operation']
                self.assertEqual(op['state'],'failed')
                self.assertTrue(op['result']['model_responses'])

    def test_server_question_gateway_requires_separate_opt_in(self):
        from apps.factory_lab.public_runtime import Demo
        from apps.factory_lab.public_server import make_server
        with tempfile.TemporaryDirectory() as tmp:
            demo=Demo(Path(tmp))
            with self.assertRaises(ValueError):make_server(demo,0,workspace_questions=True)
            demo.gateway=Gateway([])
            server=make_server(demo,0,workspace_model_proposals=True)
            try:self.assertIsNone(server.workspace.question_gateway)
            finally:server.server_close()
            server=make_server(demo,0,workspace_questions=True)
            try:
                self.assertIs(server.workspace.question_gateway,demo.gateway)
                self.assertIsNone(server.workspace.proposal_gateway)
            finally:server.server_close()

    def test_compound_lookup_and_real_commerce_checks_reach_answer_model(self):
        plan={'calls':[PLAN['calls'][0],{'tool':'replacement_proposal','arguments':{
            'item':'I1','replacement':'S2','retain_discount':True,'free_shipping':True,
            'split':False,'promise_arrival':True}}],'unresolved':['Actual refund execution unavailable']}
        with tempfile.TemporaryDirectory() as tmp:
            gateway=Gateway([plan,{**FINAL,'citations':['e1','e2']}])
            service=WorkspaceService(Path(tmp)/'db',question_gateway=gateway)
            row=service.store.create('shop',approved())
            result=service.handle({'action':'ask','id':row['id'],'revision':1,'request_key':'compound',
                                   'question':'Check order O1, assess S2 replacement for I1, and refund it.'})['operation']
            self.assertEqual(result['state'],'completed',result.get('error'))
            trace=result['result'];full=trace['evidence'][1]['result']
            projected=trace['answer_input']['evidence'][1]['result']
            self.assertEqual(full['preparation']['parameter_origin'],'model_interpretation')
            self.assertEqual(projected['preparation']['parameter_origin'],'model_interpretation')
            self.assertTrue(all(e['parameter_origin']=='model_interpretation' for e in trace['evidence']))
            self.assertNotIn('Explicit user proposal',full['preparation']['notice'])
            self.assertIn('source_rdf',full)
            self.assertNotIn('source_rdf',projected)
            for field in ('facts','calculations','delivery_assessment','limitations','unresolved'):
                self.assertEqual(full[field],projected[field])
            for field in ('conforms','results','same_policy_python_flags','features','checks'):
                self.assertEqual(full['shacl'][field],projected['shacl'][field])
            self.assertEqual(full['owl']['witnesses'],projected['owl']['witnesses'])
            actual=json.loads(gateway.calls[1][1][1]['content'])
            self.assertEqual(actual,trace['answer_input'])
            self.assertIn('source_rdf',actual['evidence'][1]['answer_projection']['excluded_paths'])
            self.assertEqual(len(gateway.calls),2)

    def test_rejected_trace_retains_checkpoint_terminates_and_never_recalls(self):
        from unittest.mock import patch
        from apps.factory_lab import workspace_store as ws
        for cap in ('MAX_STORED_BYTES','MAX_DOCUMENT_BYTES'):
            with self.subTest(cap=cap),tempfile.TemporaryDirectory() as tmp:
                gateway=Gateway([PLAN,FINAL]);service=WorkspaceService(Path(tmp)/'db',question_gateway=gateway)
                row=service.store.create('approved',approved())
                request={'action':'ask','id':row['id'],'revision':1,'request_key':'quota','question':'Check O1'}
                original=service.store.checkpoint; committed=[]
                def checkpoint(oid,trace):
                    if committed:
                        with patch.object(ws,cap,1):original(oid,trace)
                    else:
                        original(oid,trace)
                        committed.append(json.loads(json.dumps(trace)))
                finish=service.store.finish
                def reject_finish(*args,**kwargs):
                    with patch.object(ws,cap,1):finish(*args,**kwargs)
                with patch.object(service.store,'checkpoint',side_effect=checkpoint),patch.object(service.store,'finish',side_effect=reject_finish):
                    op=service.handle(request)['operation']
                self.assertEqual(op['state'],'failed')
                self.assertIn('Latest trace could not be persisted',op['error'])
                self.assertEqual(op['result'],committed[0])
                calls=len(gateway.calls)
                self.assertTrue(WorkspaceService(Path(tmp)/'db',question_gateway=gateway).handle(request)['reused'])
                self.assertEqual(len(gateway.calls),calls)


class QuestionEnvelopeTests(unittest.TestCase):
    def test_saved_fenced_messages_preserve_evidence_and_unresolved_scope(self):
        class Fenced(Gateway):
            def call(self,key,messages):
                response=super().call(key,messages)
                response['content']='```json\n'+response['content']+'\n```'
                return response
        with tempfile.TemporaryDirectory() as tmp:
            gateway=Fenced([PLAN,FINAL]);service=WorkspaceService(Path(tmp)/'db',question_gateway=gateway)
            row=service.store.create('approved',approved())
            request={'action':'ask','id':row['id'],'revision':1,'request_key':'fenced','question':'Show O1 and refund eligibility'}
            result=service.handle(request)['operation']
            self.assertEqual(result['state'],'completed',result.get('error'))
            self.assertEqual(result['result']['unresolved'],PLAN['unresolved'])
            self.assertEqual(result['result']['evidence'][0]['result']['mode'],'source_lookup')
            self.assertTrue(all(r['content'].startswith('```json') and r['response_format']=='json_fence' for r in result['result']['model_responses']))
            self.assertEqual(len(gateway.calls),2)
            self.assertTrue(service.handle(request)['reused']);self.assertEqual(len(gateway.calls),2)
        for content in ('```json\n{"calls":','Explanation\n{"calls":[],"unresolved":[]}',
                        '```json\n{"calls":[{"tool":"run_sql","arguments":{}}],"unresolved":[]}\n```'):
            class Raw(Gateway):
                def call(self,key,messages):self.calls.append((key,messages));return {'content':content}
            with self.subTest(content=content),tempfile.TemporaryDirectory() as tmp:
                gateway=Raw([]);service=WorkspaceService(Path(tmp)/'db',question_gateway=gateway);row=service.store.create('approved',approved())
                op=service.handle({'action':'ask','id':row['id'],'revision':1,'request_key':'bad','question':'Show O1'})['operation']
                self.assertEqual(op['state'],'failed');self.assertEqual(len(gateway.calls),1)
                self.assertEqual(op['result']['model_responses'][0]['content'],content)
                self.assertEqual(op['result']['evidence'],[])
