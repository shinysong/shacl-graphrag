"""Portable release behavior; mocked model responses are software tests, not QA evidence."""
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from apps.factory_lab.public_runtime import Demo, EXAMPLES, PublicGateway, read, selected_review
from apps.factory_lab.public_server import make_server
from apps.factory_lab.store import Store

CFG = {'model': 'test/model', 'provider': 'test', 'prompt_per_million': '1',
       'completion_per_million': '2', 'max_tokens': 3072, 'max_calls': 12, 'max_usd': '1', 'hours': 2}


class FakeGateway:
    """Uses saved output as a scripted response, never a fresh model result."""
    def __init__(self, store, directory, config, key):
        self.config = CFG
        self.session = {'deadline': (datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()}
        self.example = next(x for x in read(EXAMPLES/'replays.json') if x['id']=='c01')
        self.count = 0
        self.messages = []
    def call(self, rid, messages):
        self.messages.append(messages)
        self.count += 1
        p = self.example['plan']
        data = [{'requirements': self.example['requirements']},
                {'steps': p['steps'], 'unplanned': p['model_unplanned']},
                {k:v for k,v in self.example['answer'].items() if k!='citation_reference_errors'}][self.count-1]
        return {'content': json.dumps(data)}


class PublicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_keyless_replay_requires_no_env_or_network(self):
        with patch.dict(os.environ, {}, clear=True), patch('httpx.Client', side_effect=AssertionError('No network')):
            d = Demo(self.path)
            self.assertEqual(len(d.replays), 4)
            self.assertFalse(d.config()['live_enabled'])
            with self.assertRaises(RuntimeError): d.start({'question':'test'})
            self.assertEqual(d.store.budget()['attempts'], 0)

    def test_scripted_model_full_cycle_real_rdf_shacl_and_lineage(self):
        d = Demo(self.path, CFG, FakeGateway)
        rid = d.start({'question': d.replays['c01']['question'], 'review':'shacl'})
        d.worker.join(30)
        self.assertFalse(d.worker.is_alive())
        run = d.store.get(rid)
        self.assertEqual(run['status'], 'completed')
        obj = json.loads(run['answer'])
        self.assertEqual(d.gateway.count, 3)
        self.assertEqual(len(obj['execution']['calls']), 9)
        self.assertTrue(any(c['input_lineage'] for c in obj['execution']['calls']))
        self.assertEqual(obj['review']['engine'], 'shacl')
        self.assertIn('raw_report_turtle', obj['review']['explanation'])
        final_context = json.dumps(d.gateway.messages[-1])
        self.assertIn('selected_qualification_review', final_context)
        self.assertNotIn('raw_report_turtle', final_context)
        self.assertNotIn('shapes_turtle', final_context)
        self.assertTrue(obj['answer']['coverage'])
        self.assertEqual(d.store.budget()['attempts'], 0)

    def test_failed_decomposition_is_retained_no_retry(self):
        class Bad(FakeGateway):
            def call(self, *a): self.count+=1; return {'content':'not JSON'}
        d = Demo(self.path, CFG, Bad);rid=d.start({'question':'test'})
        d.worker.join(10)
        self.assertEqual(d.store.get(rid)['status'],'failed')
        self.assertEqual(d.gateway.count,1)
        self.assertTrue(d.store.events(rid))

    def test_opt_in_owl_reaches_final_context_without_raw_closure(self):
        d = Demo(self.path, CFG, FakeGateway)
        rid = d.start({'question':d.replays['c01']['question'], 'review':'shacl', 'owl':True})
        d.worker.join(30)
        obj = json.loads(d.store.get(rid)['answer'])
        self.assertEqual(d.store.get(rid)['status'], 'completed')
        self.assertTrue(obj['owl']['witnesses'])
        self.assertTrue(obj['owl']['evidence_ids'])
        context = json.dumps(d.gateway.messages[-1])
        self.assertIn('authored_ontology_classification', context)
        self.assertIn('ManufacturingCapability', context)
        self.assertNotIn('inferred_ntriples', context)
        self.assertEqual(d.gateway.count, 3)

    def test_cancel_after_inflight_prevents_next_call(self):
        entered, release = threading.Event(), threading.Event()
        class Slow(FakeGateway):
            def call(self,*a): entered.set(); release.wait(5);return super().call(*a)
        d=Demo(self.path, CFG, Slow);rid=d.start({'question':'test'})
        self.assertTrue(entered.wait(5));d.cancel(rid);release.set();d.worker.join(10)
        self.assertEqual(d.store.get(rid)['status'],'cancelled');self.assertEqual(d.gateway.count,1)

    def test_rejected_connection_remains_unresolved_not_crash(self):
        class BadPlan(FakeGateway):
            def call(self,*a):
                value=super().call(*a)
                if self.count==2:
                    data=json.loads(value['content']);data['steps'][0]['binding']['kind']='Order'
                    value={'content':json.dumps(data)}
                return value
        d=Demo(self.path, CFG, BadPlan);rid=d.start({'question':'test'})
        d.worker.join(20)
        self.assertEqual(d.store.get(rid)['status'],'completed')
        events=d.store.events(rid)
        self.assertTrue(next(e for e in events if e['kind']=='plan_checked')['payload']['rejections'])
        self.assertTrue(next(e for e in events if e['kind']=='review_completed')['payload']['requirements'])

    def test_gateway_persists_cap_and_unknown_billing_stops(self):
        store=Store(self.path/'state.sqlite');g=PublicGateway(store,self.path,CFG,'test-secret');rid=store.create({})
        original=g.session.copy()
        self.assertEqual(PublicGateway(store,self.path,CFG,'test-secret').session,original)
        with self.assertRaises(ValueError): PublicGateway(store,self.path,CFG|{'hours':3},'test-secret')
        request=httpx.Request('POST','https://openrouter.ai/api/v1/chat/completions')
        response=httpx.Response(200,json={'choices':[{'message':{'content':'{}'},'finish_reason':'stop'}]},request=request)
        with patch('httpx.Client') as client:
            client.return_value.__enter__.return_value.post.return_value=response
            with self.assertRaises(RuntimeError):g.call(rid,[{'role':'user','content':'hello'}])
            self.assertEqual(store.budget()['attempts'],1);self.assertEqual(store.budget()['unresolved'],1)
            with self.assertRaises(RuntimeError):g.call(rid,[{'role':'user','content':'again'}])
            self.assertEqual(client.return_value.__enter__.return_value.post.call_count,1)
        self.assertNotIn('test-secret',(self.path/'session.json').read_text())

    def test_http_replay_host_csrf_and_no_paid_activation(self):
        server=make_server(Demo(self.path),0);thread=threading.Thread(target=server.serve_forever);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with httpx.Client(trust_env=False) as c:
                conf=c.get(base+'/api/config').json()
                self.assertEqual(c.get(base+'/api/examples/c01').status_code,200)
                self.assertEqual(c.get(base+'/api/config',headers={'Host':'evil.test'}).status_code,403)
                self.assertEqual(c.post(base+'/api/runs',json={'question':'test'}).status_code,403)
                self.assertEqual(c.post(base+'/api/runs',json={'question':'test'},headers={'X-CSRF-Token':conf['csrf']}).status_code,409)
                self.assertEqual(c.get(base+'/.env').status_code,404)
                self.assertEqual(c.get(base+'/api/examples/missing').status_code,404)
        finally:server.shutdown();server.server_close();thread.join()

    def test_filtered_qualification_evidence_reaches_both_reviewers(self):
        from experiments.factory_complexity.tools import Views, RDFStudyTools
        from experiments.query_contracts.competing import CompetingTools
        tools=CompetingTools(RDFStudyTools(Views(EXAMPLES/'snapshots')))
        base=tools.run('factory-v3','replacement_candidates',{'order_id':'O17'})
        for filtered in ('current_qualification_records','expired_qualification_records'):
            result=tools.run('factory-v3',filtered,{'machine_id':'M01'})
            # Equivalence checks empty and populated selected evidence alike.
            def execution(name):return {'calls':[
                {'tool':'replacement_candidates','arguments':{'order_id':'O17'},'result':base},
                {'tool':name,'arguments':{'machine_id':'M01'},'result':result}]}
            for engine in ('python','shacl'):
                actual=selected_review(execution(filtered),engine)
                expected=selected_review(execution('qualification_records'),engine)
                self.assertEqual(actual['flags'],expected['flags'])
                self.assertIn(filtered,actual['qualification_evidence_tools'])

    def test_gateway_preserves_malformed_response_without_secret(self):
        store=Store(self.path/'state.sqlite');g=PublicGateway(store,self.path,CFG,'secret-never-log');rid=store.create({})
        req=httpx.Request('POST','https://openrouter.ai/api/v1/chat/completions')
        response=httpx.Response(200,text='malformed secret-never-log',request=req)
        with patch('httpx.Client') as client:
            client.return_value.__enter__.return_value.post.return_value=response
            with self.assertRaises(RuntimeError):g.call(rid,[{'role':'user','content':'hello'}])
        bodies=list((self.path/'calls').glob('*-response.txt'))
        self.assertEqual(len(bodies),1)
        self.assertEqual(bodies[0].read_text(),'malformed [REDACTED]')
        self.assertEqual(len(list((self.path/'calls').glob('*-request.json'))),1)
        self.assertEqual(store.budget()['attempts'],1)
        self.assertEqual(store.budget()['unresolved'],1)

    def test_extension_has_executable_semantics(self):
        from examples.factory_lab.extensions.unavailable_candidates import run
        result=run('O17')
        self.assertTrue(result['rows'])
        self.assertTrue(all(x['machine']['status']=='unavailable' for x in result['rows']))
        self.assertTrue(all(x['order']['id']=='O17' for x in result['rows']))
        with self.assertRaises(ValueError):run('O17" } UNION { ?s ?p ?o')
