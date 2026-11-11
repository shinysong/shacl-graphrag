import copy
import json
import tempfile
import time
import unittest
import threading
from unittest.mock import patch,MagicMock
import httpx
from datetime import datetime,timezone,timedelta
from pathlib import Path
from apps.factory_lab.review import python_flags,shacl_flags,review
from apps.factory_lab.graph import validate_args,snapshot
from apps.factory_lab.store import Store
from apps.factory_lab.agent import Runner
from apps.factory_lab.llm import billing_details
from apps.factory_lab.llm import Gateway
from apps.factory_lab.server import Handler,ThreadingHTTPServer
from decimal import Decimal

class FactoryTests(unittest.TestCase):
    def row(self):
        return {'key':'O17|M01|CAP-CUT','status':'available','capability':'CAP-CUT','required':'CAP-CUT','product':'P-A','at':'2026-11-09','records':[{'product':'P-A','capability':'CAP-CUT','valid_from':'2026-01-01','valid_until':'2026-12-31'}]}
    def test_independent_policies_expected_flags(self):
        base=self.row();cases=[(base,[])]
        for field,value,code in [('status','unavailable','status-not-available'),('capability','OTHER','capability-missing'),('records',[],'qualification-not-retrieved')]:
            r=copy.deepcopy(base);r[field]=value;cases.append((r,[code]))
        for field,value in [('product','P-B'),('capability','OTHER'),('valid_from','2026-11-10'),('valid_until','2026-11-08')]:
            r=copy.deepcopy(base);r['records'][0][field]=value;cases.append((r,['qualification-not-applicable']))
        # Different records must not satisfy different halves of the conjunction.
        r=copy.deepcopy(base);r['records'][0]['product']='P-B';second=copy.deepcopy(base['records'][0]);second['valid_until']='2026-10-31';r['records'].append(second);cases.append((r,['qualification-not-applicable']))
        for row,codes in cases:
            expected=[{'candidate':row['key'],'code':code} for code in codes]
            with self.subTest(row=row):
                self.assertEqual(python_flags([row]),expected);self.assertEqual(shacl_flags([row]),expected)
    def test_empty_not_pass(self):
        for mode in ['python','shacl','self']:self.assertEqual(review([],mode)['assessment'],'not_assessed')
    def test_alternate_evidence_paths(self):
        candidate={'tool':'replacement_candidates','as_of':'2026-11-09','rows':[{'machine':{'id':'M01','status':'available'},'order':{'id':'O17','product':'P-A'},'required_capability':'CAP-CUT'}]}
        m={'id':'M01','kind':'Machine'};q=self.row()['records'][0]|{'id':'Q01','kind':'Qualification'}
        for entity,neighbor in [(m,q),(q,m)]:
            item={'tool':'inspect_entity','rows':[{'entity':entity,'neighbor':neighbor,'relation':'HAS_QUALIFICATION','from_id':'M01'}]}
            for engine in ['python','shacl']:
                report=review([candidate,item],engine);self.assertEqual(report['flags'],[])
    def test_cost_parsing_preserves_known_costs(self):
        d,a=billing_details({'usage':{'cost':0.03},'choices':[{}]},200,Decimal('0.1'))
        self.assertEqual(d['cost'],'0.03');self.assertIsNone(a)
        for cost in ['NaN',-1,{},'bad',0.2]:
            d,a=billing_details({'usage':{'cost':cost}},200,Decimal('0.1'));self.assertIsNotNone(a)
    def test_gateway_retains_cost_on_malformed_choice_and_stops_anomaly(self):
        with tempfile.TemporaryDirectory() as d:
            work=Path(d);(work/'execution-gate.json').write_text('{"approved":true,"files":{}}')
            s=Store(work/'s.db');g=Gateway.__new__(Gateway);g.store=s;g.work=work;g.key='test-not-a-secret'
            g.session={'deadline':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'max_usd':'5','max_attempts':100}
            g.config={'model':'test','provider':'test','prompt_price':'0.000001','completion_price':'0.000001','max_tokens':100}
            client=MagicMock();client.__enter__.return_value=client
            body={'usage':{'cost':0.001},'choices':[{}]}
            response=MagicMock();response.status_code=200;response.text=json.dumps(body);response.json.return_value=body;client.post.return_value=response
            with patch('apps.factory_lab.llm.WORK',work),patch('apps.factory_lab.llm.httpx.Client',return_value=client):
                with self.assertRaises(RuntimeError):g.call('r',[{'role':'user','content':'test'}])
                self.assertEqual(s.budget()['reported_usd'],'0.001')
                body['usage']['cost']='NaN'
                with self.assertRaises(RuntimeError):g.call('r',[{'role':'user','content':'test'}])
                self.assertTrue((work/'paid-stop.json').exists())
                count=client.post.call_count
                with self.assertRaises(RuntimeError):g.call('r',[{'role':'user','content':'test'}])
                self.assertEqual(client.post.call_count,count)
    def test_http_origin_and_sse_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'s.db');rid=s.create({'question':'test'});s.status(rid,'completed','done');s.event(rid,'final',{'text':'done'})
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.store=s;server.token='test-token'
            t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
            try:
                url=f'http://127.0.0.1:{server.server_port}'
                with httpx.Client(trust_env=False) as c:
                    self.assertEqual(c.get(url+'/').status_code,200)
                    self.assertEqual(c.get(url+'/',headers={'Host':'attacker.invalid'}).status_code,403)
                    self.assertEqual(c.post(url+'/api/runs',json={}).status_code,403)
                    self.assertEqual(c.post(url+'/api/runs',json={},headers={'X-CSRF-Token':'test-token','Origin':'https://attacker.invalid'}).status_code,403)
                    r=c.get(url+'/api/runs/'+rid+'/events');self.assertIn('text/event-stream',r.headers['content-type']);self.assertIn('"text":"done"',r.text)
            finally:server.shutdown();server.server_close();t.join()
    def test_tool_schema_rejects_arbitrary_queries(self):
        for name,args in [('cypher',{'query':'MATCH (n) DELETE n'}),('find_entities',{'text':''}),('inspect_entity',{'entity_id':'M02','query':'delete'})]:
            with self.assertRaises(ValueError):validate_args(name,args)
    def test_source_versions(self):
        a,ha=snapshot('factory-v1');b,hb=snapshot('factory-v2');self.assertNotEqual(ha,hb)
        self.assertEqual([n['status'] for n in a['nodes'] if n['id']=='M02'],['available'])
        self.assertEqual([n['status'] for n in b['nodes'] if n['id']=='M02'],['unavailable'])
    def test_reservation_nonrefund_and_deadline(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'s.db');session={'deadline':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'max_attempts':2,'max_usd':'1'}
            c=s.reserve('r','0.7',session);s.settle(c,'failed',{'cost':None})
            with self.assertRaises(RuntimeError):s.reserve('r','0.4',session)
            self.assertEqual(s.budget()['reserved_nonrefunded_usd'],'0.7')
            session['deadline']='2000-01-01T00:00:00+00:00'
            with self.assertRaises(RuntimeError):s.reserve('r','0.1',session)
    def test_recovery_keeps_original_events(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'s.db');rid=s.create({'question':'test'});s.status(rid,'running');s.recover()
            self.assertEqual(s.get(rid)['status'],'interrupted');self.assertEqual([e['kind'] for e in s.events(rid)],['queued','interrupted'])
    def test_real_runner_with_scripted_gateway_is_software_test_only(self):
        class FakeGraph:
            def run(self,version,name,args):return {'tool':name,'arguments':args,'rows':[],'snapshot':version}
        class FakeGateway:
            def __init__(self,store):self.n=0
            def call(self,rid,messages,tools=None):
                self.n+=1
                if self.n==1:return {'role':'assistant','content':None,'tool_calls':[{'id':'c1','type':'function','function':{'name':'impacted_orders','arguments':'{"machine_id":"M02"}'}}]}
                return {'role':'assistant','content':'Scripted software-test output; not a measured LLM answer.'}
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'s.db');r=Runner(s,FakeGraph(),FakeGateway);rid=r.start({'question':'M02?','snapshot':'factory-v2','review':'shacl'})
            for _ in range(100):
                if s.get(rid)['status'] not in ('queued','running'):break
                time.sleep(.02)
            self.assertEqual(s.get(rid)['status'],'completed')
            kinds=[e['kind'] for e in s.events(rid)]
            for k in ['tool_started','tool_completed','draft','review_completed','final']:self.assertIn(k,kinds)
            self.assertEqual(s.budget()['attempts'],0)
            child=r.start({'question':'그럼 다음은?','snapshot':'factory-v2','review':'self','parent_id':rid})
            for _ in range(100):
                if s.get(child)['status'] not in ('queued','running'):break
                time.sleep(.02)
            self.assertEqual(s.get(child)['status'],'completed')
            self.assertEqual(s.get(child)['config']['parent_id'],rid)
            self.assertEqual(len([e for e in s.events(child) if e['kind']=='context']),1)

if __name__=='__main__':unittest.main()
