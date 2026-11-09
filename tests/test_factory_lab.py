import copy
import json
import tempfile
import time
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from apps.factory_lab.review import python_flags,shacl_flags,review
from apps.factory_lab.graph import validate_args,snapshot
from apps.factory_lab.store import Store
from apps.factory_lab.agent import Runner

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

if __name__=='__main__':unittest.main()
