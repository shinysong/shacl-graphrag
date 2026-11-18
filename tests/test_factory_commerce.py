import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
import httpx
from apps.factory_lab.commerce import load, check_data, run_case, review, DEFAULT
from apps.factory_lab.public_runtime import Demo
from apps.factory_lab.public_server import make_server

class CommerceTests(unittest.TestCase):
    def run_modified(self,change,case='ready'):
        d,_=load();change(d)
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'shop.json';p.write_text(json.dumps(d));return run_case(case,p)
    def test_approval_proposal_and_basket_preserved(self):
        r=run_case('approval');codes={c['code'] for c in r['shacl']['results']}
        self.assertEqual(codes,{'consent','discount_ok','arrival_ok'})
        self.assertEqual(r['calculations']['after_subtotal'],90000)
        self.assertEqual(r['calculations']['discount'],0)
        self.assertEqual([i['id'] for i in r['facts']['unchanged_items']],['I2'])
        self.assertEqual(len(r['query']['rows']),2)
        self.assertEqual(set(r['shacl']['same_policy_python_flags']),codes)
    def test_ready_unknown_and_actual_owl(self):
        ready=run_case('ready');self.assertTrue(ready['shacl']['conforms']);self.assertFalse(ready['unresolved'])
        unknown=run_case('unknown');self.assertTrue(unknown['shacl']['conforms']);self.assertEqual(len(unknown['unresolved']),2)
        self.assertEqual(len(ready['owl']['witnesses']),1);self.assertFalse(ready['owl']['proof_trace_available'])
        self.assertIn('urn:commerce:Footwear',ready['owl']['inferred_ntriples'])
        self.assertIn('LLM',ready['answer'])
    def test_policy_fact_changes_and_isolation(self):
        r=self.run_modified(lambda d:d['coupons'][0].update(minimum=200000))
        self.assertIn('discount_ok',[x['code'] for x in r['shacl']['results']])
        r=self.run_modified(lambda d:d['orders'][0].update(status='shipped'))
        self.assertIn('status',[x['code'] for x in r['shacl']['results']])
        r=self.run_modified(lambda d:d['skus'][2].update(available=0))
        self.assertIn('stock_ok',[x['code'] for x in r['shacl']['results']])
    def test_approval_must_match_order_sku_and_discount(self):
        def change(d):
            d['approvals'].append({'id':'A1','order':'O1','sku':'S2','discount':10000,'status':'approved'})
        r=self.run_modified(change,'approval');self.assertNotIn('discount_ok',[x['code'] for x in r['shacl']['results']]);self.assertEqual(r['calculations']['discount'],10000)
        def wrong(d):
            d['approvals'].append({'id':'A1','order':'O1','sku':'S3','discount':10000,'status':'approved'})
        r=self.run_modified(wrong,'approval');self.assertIn('discount_ok',[x['code'] for x in r['shacl']['results']])
    def test_date_contract_and_no_promise_applicability(self):
        for field,value in [('arrival','20261120'),('arrival','2026-W47-5')]:
            with self.assertRaises(ValueError):self.run_modified(lambda d:d['skus'][2].update({field:value}))
        with self.assertRaises(ValueError):self.run_modified(lambda d:d.update(as_of=20261117))
        def late(d):
            d['skus'][2]['arrival']='2026-11-21'
            d['cases'][1]['promise_arrival']=False
        r=self.run_modified(late)
        self.assertNotIn('arrival_ok',[x['code'] for x in r['shacl']['results']])
        self.assertFalse(r['delivery_assessment']['confirmed_within_requested_date'])
        self.assertIn('요청일 이후',r['answer'])
        r=self.run_modified(lambda d:d['skus'][2].update(arrival='2026-11-21'))
        self.assertIn('arrival_ok',[x['code'] for x in r['shacl']['results']])

    def test_import_rejects_invalid_and_unsupported(self):
        changes=[lambda d:d['items'][0].update(sku='missing'),lambda d:d['skus'][0].update(price=True),lambda d:d['skus'][0].update(price=-1),lambda d:d['skus'][0].update(arrival='bad-date'),lambda d:d['items'].append(copy.deepcopy(d['items'][0])),lambda d:d.update(secret='no'),lambda d:d['skus'][0].update(warehouse='W2'),lambda d:d['products'][0].update(category='Unknown')]
        for change in changes:
            d,_=load();change(d)
            with self.assertRaises((ValueError,TypeError)):check_data(d)
    def test_http_custom_data_gates_and_no_paid_calls(self):
        with tempfile.TemporaryDirectory() as t:
            d,_=load();d['snapshot_id']='my-shop';p=Path(t)/'custom.json';p.write_text(json.dumps(d))
            demo=Demo(Path(t)/'runs');s=make_server(demo,0,p);thread=threading.Thread(target=s.serve_forever,daemon=True);thread.start()
            try:
                base=f'http://127.0.0.1:{s.server_port}'
                with httpx.Client(base_url=base) as c:
                    token=c.get('/api/config').json()['csrf'];headers={'X-CSRF-Token':token}
                    self.assertEqual(c.get('/api/commerce').json()['snapshot'],'my-shop')
                    self.assertEqual(c.post('/api/commerce',json={'case_id':'ready'}).status_code,403)
                    r=c.post('/api/commerce',json={'case_id':'ready'},headers=headers);self.assertEqual(r.status_code,200);self.assertEqual(r.json()['source']['snapshot'],'my-shop')
                    self.assertEqual(c.post('/api/commerce',json={'case_id':'missing'},headers=headers).status_code,400)
                    demo.lock.acquire()
                    try:self.assertEqual(c.post('/api/commerce',json={'case_id':'ready'},headers=headers).status_code,409)
                    finally:demo.lock.release()
                    self.assertEqual(c.get('/api/config').json()['budget']['attempts'],0)
            finally:s.shutdown();s.server_close();thread.join()
