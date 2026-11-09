import copy,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
from unittest.mock import patch
from scripts import run_paired_review as r

class Paired(unittest.TestCase):
 def setUp(self):
  p=Path('_workspace/paired-campaign-20261104/config.json')
  if not p.exists():p=Path('research/answer-evidence-1/paired-campaign-config-v1.json')
  self.c=json.loads(p.read_text())
  self.p=self.c['providers'][0];self.t=datetime(2026,11,4,23,tzinfo=timezone.utc)
 def response(self,payload,content=None,cost='0.0001',finish='stop'):
  p=next(x for x in self.c['providers'] if x['model']==payload['model'])
  return 200,json.dumps({'model':p['model'],'provider':p['provider'],'usage':{'cost':cost,'prompt_tokens':100,'completion_tokens':100,'completion_tokens_details':{'reasoning_tokens':0}},'choices':[{'finish_reason':finish,'message':{'content':content or json.dumps({'answer':'bounded authored test','claims':[],'limitations':[]})}}]}).encode()
 def test_admission(self):
  l={'attempts':[]};r.admit(l,'a',Decimal('1'),self.t,self.c['deadline'])
  for slot,amount,instant in [('b',Decimal('1'),self.t),('a',Decimal('1'),self.t)]:
   with self.assertRaises(ValueError):r.admit(l,slot,amount,instant,self.c['deadline'])
  l['attempts'][0]['state']='resolved'
  with self.assertRaisesRegex(ValueError,'budget'):r.admit(l,'b',Decimal('9.1'),self.t,self.c['deadline'])
  with self.assertRaisesRegex(ValueError,'deadline'):r.admit(l,'b',Decimal('1'),datetime.fromisoformat(self.c['deadline']),self.c['deadline'])
 def test_pair_bindings_and_exclusive_restart(self):
  seen=[]
  def tx(p):seen.append(p);return self.response(p)
  with tempfile.TemporaryDirectory() as d:
   l=r.execute(self.c,Path(d),tx,lambda:self.t)
   self.assertGreater(len(seen),3)
   a=json.loads(seen[1]['messages'][1]['content']);b=json.loads(seen[2]['messages'][1]['content'])
   self.assertEqual(a['draft'],b['draft']);self.assertEqual(a['selected_context'],b['selected_context'])
   self.assertEqual(seen[1]['messages'][0],seen[2]['messages'][0])
   self.assertEqual(len(l['slots']),162)
   self.assertLessEqual(r.budget_used(l),Decimal('10'))
   with self.assertRaises(FileExistsError):r.execute(self.c,Path(d),tx,lambda:self.t)
 def test_unknown_cost_stops_all(self):
  with tempfile.TemporaryDirectory() as d:
   l=r.execute(self.c,Path(d),lambda p:self.response(p,cost=None),lambda:self.t)
   self.assertEqual(len(l['attempts']),1);self.assertEqual(l['attempts'][0]['state'],'unresolved')
   self.assertEqual(sum(x['state']=='not_attempted' for x in l['slots']),161)
 def test_transport_timeout_reserved(self):
  def tx(p):raise TimeoutError()
  with tempfile.TemporaryDirectory() as d:
   l=r.execute(self.c,Path(d),tx,lambda:self.t)
   self.assertEqual(len(l['attempts']),1);self.assertEqual(l['slots'][0]['state'],'execution_failure')
   self.assertGreater(Decimal(l['attempts'][0]['reserved_usd']),0)
 def test_malformed_draft_preserved_dependencies(self):
  with tempfile.TemporaryDirectory() as d:
   l=r.execute(self.c,Path(d),lambda p:self.response(p,content='{bad'),lambda:self.t)
   self.assertEqual(l['slots'][0]['state'],'output_failure')
   self.assertEqual([s['state'] for s in l['slots'][1:3]],['dependency_not_run']*2)
   self.assertTrue((Path(d)/'responses/000.raw.txt').exists())
 def test_report_failure_keeps_self(self):
  original=r.build_messages
  def build(*a,**k):
   if len(a)>2 and a[2]=='report':raise RuntimeError('authored checker failure')
   return original(*a,**k)
  with tempfile.TemporaryDirectory() as d,patch.object(r,'build_messages',side_effect=build):
   l=r.execute(self.c,Path(d),self.response,lambda:self.t)
   self.assertEqual(l['slots'][1]['state'],'completed');self.assertEqual(l['slots'][2]['state'],'input_failure')
 def test_assess_rejects_cost_route_usage(self):
  payload=r.make_payload([],self.p);data=json.loads(self.response(payload)[1])
  for key,val in [('provider','wrong'),('model','wrong')]:
   x=copy.deepcopy(data);x[key]=val
   with self.assertRaises(ValueError):r.assess(x,self.p,1000,Decimal('1'))
  for key,val in [('cost','NaN'),('cost','2'),('prompt_tokens',1001),('completion_tokens',2049)]:
   x=copy.deepcopy(data);x['usage'][key]=val
   with self.assertRaises((ValueError,ArithmeticError)):r.assess(x,self.p,1000,Decimal('1'))
 def test_input_envelope_and_universe(self):
  with self.assertRaises(ValueError):r.reservation([{'role':'user','content':'x'*33000}],self.p)
  x=copy.deepcopy(self.c);x['slots'][-1]=x['slots'][0]
  with self.assertRaises(ValueError):r.validate_config(x)
 def test_identity_order_and_cap(self):
  for key in ['inputs','providers']:
   c=copy.deepcopy(self.c);c[key][-1]=copy.deepcopy(c[key][0])
   with self.assertRaises(ValueError):r.validate_config(c)
  c=copy.deepcopy(self.c);c['slots'][0],c['slots'][1]=c['slots'][1],c['slots'][0]
  with self.assertRaises(ValueError):r.validate_config(c)
  c=copy.deepcopy(self.c);c['slots'][-1]=dict(c['slots'][0],slot_id='unique-but-duplicate-triple')
  with self.assertRaises(ValueError):r.validate_config(c)
  l={'attempts':[{'slot_id':str(i),'state':'resolved','reserved_usd':'0'} for i in range(162)]}
  with self.assertRaisesRegex(ValueError,'attempt_cap'):r.admit(l,'new',Decimal('0'),self.t,self.c['deadline'])
 def test_directory_failure_prevents_transport(self):
  with tempfile.TemporaryDirectory() as d,patch.object(r,'sync_dir',side_effect=OSError('sync failure')),patch('builtins.print'):
   tx=unittest.mock.Mock()
   with self.assertRaises(OSError):r.execute(self.c,Path(d),tx,lambda:self.t)
   tx.assert_not_called()
   self.assertTrue((Path(d)/'campaign-budget.json').exists())
 def test_atomic_sync_order(self):
  events=[]
  with tempfile.TemporaryDirectory() as d,patch.object(r.os,'replace',side_effect=lambda a,b:events.append('replace')),patch.object(r,'sync_dir',side_effect=lambda p:events.append('dirsync')):
   r.atomic(Path(d)/'x.json',{})
  self.assertEqual(events,['replace','dirsync'])
 def test_durable_reserved_before_transport(self):
  with tempfile.TemporaryDirectory() as d:
   def tx(payload):
    l=json.loads((Path(d)/'campaign-budget.json').read_text())
    self.assertEqual(l['attempts'][-1]['state'],'reserved')
    self.assertTrue(list((Path(d)/'responses').glob('*.request.json')))
    raise TimeoutError()
   l=r.execute(self.c,Path(d),tx,lambda:self.t)
   self.assertEqual(len(l['attempts']),1)
 def test_success_settlement_failure_no_refund(self):
  l={'attempts':[{'slot_id':'a','state':'resolved','status':'completed','reserved_usd':'8','reported_usd':'1'}]}
  self.assertEqual(r.budget_used(l),Decimal('1'))
  r.admit(l,'b',Decimal('9'),self.t,self.c['deadline'])
  self.assertEqual(r.budget_used(l),Decimal('10'))
  l['attempts'][1].update(state='resolved',status='output_failure',reported_usd='0.01')
  self.assertEqual(r.budget_used(l),Decimal('10'))
  with self.assertRaisesRegex(ValueError,'budget'):r.admit(l,'c',Decimal('.01'),self.t,self.c['deadline'])
if __name__=='__main__':unittest.main()


