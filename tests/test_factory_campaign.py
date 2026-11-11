"""Paid-scope gates tested with scripted transport only; no external calls."""
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import tempfile
import unittest
import fcntl
from unittest.mock import MagicMock
from unittest.mock import patch
from experiments.factory_complexity import campaign as c
from apps.factory_lab.store import ROOT,Store
from apps.factory_lab.llm import Gateway

class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'_workspace');self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.work=self.base/'campaign'
        self.deadline=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
        self.clock=patch.object(c,'DEADLINE',self.deadline);self.clock.start();self.addCleanup(self.clock.stop)
        cfg={'model':'test/model','provider':'test-provider','prompt_price':'0.00000075','completion_price':'0.00000375','request_price':'0','seed_supported':True}
        ready={'model':'test/model','checked_at':datetime.now(timezone.utc).isoformat(),'data':{'data':{'endpoints':[{
            'tag':'test-provider','pricing':{'prompt':'0.00000075','completion':'0.00000375'},
            'supported_parameters':['tools','tool_choice','temperature','max_tokens','seed']}]}}}
        c.write(self.base/'model.json',cfg);c.write(self.base/'readiness.json',ready)
        self.prepared=c.prepare(self.work,ROOT/'research/factory-complexity-1/development-001/runtime',self.base/'model.json',self.base/'readiness.json')
    def authorize_fake(self):
        c.write(self.work/'approval.json',{'approved':True,'campaign_id':c.CAMPAIGN,'deadline':self.deadline,'max_attempts':108,'max_usd':'5','human_message':'SCRIPTED TEST ONLY; never real authority'})
        gate=c.read(self.work/'execution-gate.json');gate.update(approved=True,approval_sha256=c.hash_file(self.work/'approval.json'));c.write(self.work/'execution-gate.json',gate)
    def test_preparation_closed_and_no_evaluator_gate_reads(self):
        gate=c.read(self.work/'execution-gate.json')
        self.assertFalse(gate['approved']);self.assertFalse((self.work/'state.sqlite').exists())
        self.assertFalse(any('/evaluation/' in p or p.endswith('/evaluator.py') for p in gate['files']))
        self.assertEqual(len(c.read(self.work/'plan.json')),12)
        with self.assertRaises(FileNotFoundError):c.preflight(self.work)
        self.authorize_fake();gate=c.read(self.work/'execution-gate.json');gate['approved']=False;c.write(self.work/'execution-gate.json',gate)
        with self.assertRaisesRegex(RuntimeError,'gate closed'):c.preflight(self.work)
    def test_frozen_and_approval_tamper_rejected(self):
        self.authorize_fake();config=c.read(self.work/'model.json');config['model']='changed';c.write(self.work/'model.json',config)
        with self.assertRaisesRegex(RuntimeError,'Frozen input changed'):c.preflight(self.work)
        self.authorize_fake();approval=c.read(self.work/'approval.json');approval['max_usd']='6';c.write(self.work/'approval.json',approval)
        with self.assertRaisesRegex(RuntimeError,'paid scope missing'):c.preflight(self.work)
    def test_existing_progress_cannot_reset_or_resume(self):
        self.authorize_fake();c.write(self.work/'progress.json',[])
        with self.assertRaisesRegex(RuntimeError,'Prior launch'):c.preflight(self.work)
    def test_scripted_twelve_case_run_orders_and_closed_gate(self):
        self.authorize_fake()
        class Fake:
            def __init__(self,store,**kwargs):pass
            def call(self,rid,messages,tools=None):return {'content':'Scripted test output, not a measured answer.'}
        with patch.object(c,'Gateway',Fake):result=c.run(self.work)
        self.assertEqual(result['completed_cases'],12);self.assertEqual(result['drafts_generated'],12)
        self.assertEqual(result['finals_generated'],36);self.assertEqual(result['budget']['attempts'],0)
        self.assertFalse(c.read(self.work/'execution-gate.json')['approved'])
        store=Store(self.work/'state.sqlite')
        progress=c.read(self.work/'progress.json')
        for slot in progress:
            finals=[e['payload']['arm'] for e in store.events(slot['run_id']) if e['kind']=='branch_final']
            self.assertEqual(finals,slot['review_order'])
        self.assertEqual(len({tuple(s['review_order']) for s in progress}),6)
    def test_episode_failure_retains_remaining_denominator(self):
        self.authorize_fake()
        class Fake:
            def __init__(self,store,**kwargs):pass
            def call(self,*args,**kwargs):raise RuntimeError('Injected provider failure')
        with patch.object(c,'Gateway',Fake):result=c.run(self.work)
        self.assertEqual(result['failed_cases'],1);self.assertEqual(result['not_attempted_cases'],11)
        self.assertEqual(result['finals_generated'],0);self.assertEqual(result['budget']['attempts'],0)
        self.assertFalse(c.read(self.work/'execution-gate.json')['approved'])
    def test_gateway_isolated_directory_and_closed_gate_no_http(self):
        store=Store(self.work/'state.sqlite')
        with patch('apps.factory_lab.llm.dotenv_values',return_value={'OPENROUTER_API_KEY':'dummy-test'}):gateway=Gateway(store,work_dir=self.work)
        with patch('apps.factory_lab.llm.httpx.Client') as client:
            with self.assertRaisesRegex(RuntimeError,'Review gate closed'):gateway.call('test',[{'role':'user','content':'test'}])
            client.assert_not_called()
        self.assertEqual(store.budget()['attempts'],0)
        with self.assertRaises(ValueError):Gateway(store,work_dir='/tmp')

    def test_missing_billing_stops_same_episode_and_next_cases(self):
        self.authorize_fake()
        response=MagicMock();response.status_code=200
        response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':'Retained response with unknown billing'}}],'usage':{}}
        response.text=json.dumps(response.json.return_value)
        client=MagicMock();client.__enter__.return_value=client;client.post.return_value=response
        with patch('apps.factory_lab.llm.dotenv_values',return_value={'OPENROUTER_API_KEY':'dummy-test'}),patch('apps.factory_lab.llm.httpx.Client',return_value=client):
            result=c.run(self.work)
        self.assertEqual(client.post.call_count,1);self.assertEqual(result['budget']['attempts'],1)
        self.assertEqual(result['budget']['unresolved'],1);self.assertEqual(result['finals_generated'],0)
        self.assertEqual(result['not_attempted_cases'],11)
        self.assertTrue((self.work/'paid-stop.json').exists())
        self.assertEqual(len(list((self.work/'calls').glob('*-response.txt'))),1)
        # Even deleting the stop flag cannot refund/ignore the unresolved ledger.
        (self.work/'paid-stop.json').unlink()
        with patch('apps.factory_lab.llm.dotenv_values',return_value={'OPENROUTER_API_KEY':'dummy-test'}):gateway=Gateway(Store(self.work/'state.sqlite'),work_dir=self.work)
        with patch('apps.factory_lab.llm.httpx.Client') as forbidden:
            with self.assertRaisesRegex(RuntimeError,'Unresolved billing'):gateway.call('test',[{'role':'user','content':'test'}])
            forbidden.assert_not_called()

    def test_exclusive_launch_claim(self):
        self.authorize_fake()
        with (self.work/'.launch.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(RuntimeError,'already active'):c.run(self.work)
        self.assertFalse((self.work/'progress.json').exists())

if __name__=='__main__':unittest.main()
