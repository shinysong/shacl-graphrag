"""Scripted plans and actual row execution; not model-quality evidence."""
import json
import unittest
from apps.factory_lab import preparation as p,workspace_question as q


def fixture(rows):
    d=p.create([{'name':'returns.csv','content':'ticket,purchase,private\n'+rows},
                {'name':'parcels.csv','content':'purchase,parcel\nP17,S1\nP17,S2\n'}],
               {'snapshot_id':'bindings','as_of':'2026-11-17','currency':'GBP'})
    for e in list(d['entries']):
        if e['kind']=='mapping' and e['source']['column']!='private':
            d=p.change(d,e['id'],'approved','source_only','','Source field')
    return d


def run(d,ref=None,first='R7'):
    plan={'calls':[{'tool':'source_rows','arguments':{'entry_id':'map:returns.csv:ticket','value':first}},
                   {'tool':'source_rows','arguments':{'entry_id':'map:parcels.csv:purchase','value':ref or {'from_evidence':'e1','column':'purchase'}}}], 'unresolved':[]}
    replies=iter([plan,{'answer':'Scripted response','citations':[],'unresolved':[]}]);checkpoints=[]
    trace=q.ask(d,'Find parcels for return R7',lambda m:{'content':json.dumps(next(replies))},lambda t:checkpoints.append(json.loads(json.dumps(t))))
    return trace,checkpoints


class BindingTests(unittest.TestCase):
    def test_actual_rows_and_checkpoint_provenance(self):
        t,saved=run(fixture('R7,P17,secret\nR7,P17,hidden\n'))
        e=t['evidence'][1]
        self.assertEqual(e['state'],'completed')
        self.assertEqual([r['values']['parcel'] for r in e['result']['records']],['S1','S2'])
        self.assertEqual(e['arguments']['value'],{'from_evidence':'e1','column':'purchase'})
        self.assertEqual(e['resolved_arguments']['value'],'P17')
        self.assertEqual(len(e['binding']['records']),2)
        self.assertTrue(any(x['evidence'][-1].get('binding') and x['evidence'][-1]['state']=='running' for x in saved if x['evidence']))
        self.assertEqual(t['answer_input']['evidence'],t['evidence'])
        self.assertNotIn('secret',json.dumps(t['answer_input']))

    def test_absent_blank_ambiguous_unreviewed_and_forward_preserved(self):
        cases=[('R7,P17,x\nR7,P18,y\n',None,'R7'),('R7,,x\n',None,'R7'),
               ('R7,P17,x\n',None,'missing'),('R7,P17,x\n',{'from_evidence':'e1','column':'private'},'R7'),
               ('R7,P17,x\n',{'from_evidence':'e2','column':'purchase'},'R7')]
        for rows,ref,first in cases:
            with self.subTest(rows=rows,ref=ref,first=first):
                t,_=run(fixture(rows),ref,first)
                e=t['evidence'][1];self.assertEqual(e['state'],'failed')
                self.assertEqual(e['failure_kind'],'unresolved_binding');self.assertNotIn('result',e)
                self.assertTrue(t['unresolved']);self.assertEqual(t['plan']['unresolved'],[])
                self.assertEqual(t['answer_input']['unresolved'],t['unresolved'])
