import copy
import unittest
from decimal import Decimal
from scripts.run_answer_campaign import reserve, assess, strict, load_inputs, payload, RESERVE

class CampaignTests(unittest.TestCase):
    def test_no_refund_duplicate_unresolved_deadline_caps(self):
        ledger={'attempts':[]}
        a=reserve(ledger,'one','2026-11-03T14:00:00+00:00')
        with self.assertRaises(ValueError): reserve(ledger,'two','2026-11-03T14:00:00+00:00')
        a.update(state='resolved',reported_usd='0')
        with self.assertRaises(ValueError): reserve(ledger,'one','2026-11-03T14:00:00+00:00')
        with self.assertRaises(ValueError): reserve(ledger,'two','2026-11-03T21:13:15+00:00')
        for i in range(71): reserve(ledger,str(i),'2026-11-03T14:00:00+00:00')['state']='resolved'
        self.assertEqual(sum(Decimal(x['reserved_usd']) for x in ledger['attempts']),Decimal('.72'))
        with self.assertRaises(ValueError): reserve(ledger,'extra','2026-11-03T14:00:00+00:00')
    def test_response_failures_not_answers(self):
        d={'model':'openai/gpt-4o-mini','provider':'OpenAI','usage':{'cost':.001,'prompt_tokens':100,'completion_tokens':50},'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}
        schema={'type':'object','required':['status']}
        self.assertEqual(assess(d,schema)['status'],'schema_error')
        d['choices'][0]['finish_reason']='length'
        self.assertEqual(assess(d,schema)['status'],'truncated')
        for cost in [None,-1,.02,float('nan')]:
            bad=copy.deepcopy(d);bad['usage']['cost']=cost
            with self.assertRaises(Exception): assess(bad,schema)
        d['provider']='Azure'
        with self.assertRaises(ValueError): assess(d,schema)
    def test_json_and_inputs(self):
        for s in ['{"a":1,"a":2}','{"a":NaN}']:
            with self.assertRaises(ValueError):strict(s)
        rows=load_inputs();self.assertEqual(len(rows),72)
        for r in rows:
            p=payload(r);self.assertEqual(p['max_tokens'],2048)
            self.assertFalse(p['provider']['allow_fallbacks'])
            self.assertEqual(p['provider']['only'],['openai'])
if __name__=='__main__':unittest.main()
