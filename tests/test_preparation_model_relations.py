"""Scripted model boundary probes, not relationship extraction accuracy."""
import json
import unittest
from copy import deepcopy
from apps.factory_lab import preparation as p, workspace_relations
from apps.factory_lab.preparation_model import ModelProposalGenerator

FILES=[{'name':'purchases.csv','content':'purchase_ref\nP1\n'},
       {'name':'returns.csv','content':'original_purchase\nP9\n'},
       {'name':'definitions.md','content':'original_purchase refers to purchase_ref; exports cover different periods.'}]
META={'snapshot_id':'model-relation','as_of':'2026-11-17','currency':'GBP'}
REL={'source':'map:returns.csv:original_purchase','target':'map:purchases.csv:purchase_ref',
     'reason':'Scripted source definition; overlapping export records unavailable',
     'evidence':['policy:definitions.md:1'],'questions':['Do these exports cover the same period?']}

class ModelRelationTests(unittest.TestCase):
    def create(self, relations, files=FILES):
        calls=[];self.calls=calls
        def call(messages):
            calls.append(messages)
            packet=json.loads(messages[1]['content'])
            return {'content':json.dumps({'choices':[{'id':e['id'],'target':'source_only' if e['kind']=='mapping' else '',
                'reason':'Scripted review only'} for e in packet['entries']], 'relations':relations})}
        return p.create(files,META,ModelProposalGenerator(call,'scripted-relations')),calls

    def test_zero_overlap_pending_restore_and_explicit_approval(self):
        draft,calls=self.create([REL])
        relation=next(e for e in draft['entries'] if e['kind']=='relation')
        self.assertEqual(relation['source']['column'],'original_purchase')
        self.assertEqual(relation['status'],'pending')
        self.assertNotIn('overlap',relation)
        self.assertEqual(workspace_relations.catalog(draft),[])
        restored=p.restore_draft(draft)
        self.assertEqual(draft['entries'],restored['entries']);self.assertEqual(len(calls),1)
        self.assertEqual(relation['extraction']['source_evidence'][0]['line_start'],1)
        for e in list(restored['entries']):
            if e['kind']=='mapping':restored=p.change(restored,e['id'],'approved','source_only','','Human raw column meaning')
        self.assertEqual(workspace_relations.catalog(restored),[])
        restored=p.change(restored,relation['id'],'approved',relation['target'],'','Human confirms reference; unmatched exports')
        result=workspace_relations.execute(restored,{'relation_id':relation['id'],'value':'P9'})
        self.assertEqual(result['record_counts'],{'source':1,'target':0})
        self.assertEqual(len(calls),1)
        bad=deepcopy(draft);bad['saved_suggestions'][-1]['target']['sha256']='0'*64
        with self.assertRaises(ValueError):p.restore_draft(bad)

    def test_invalid_relations_fail_without_retry(self):
        bads=[None,[REL]*33,[REL,REL]]
        for changes in ({'source':'missing'},{'target':'policy:definitions.md:1'},
                        {'target':REL['source']},{'status':'approved'},{'reason':''},
                        {'questions':['']},{'evidence':['missing']}):
            bads.append([{**REL,**changes}])
        for value in bads:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):self.create(value)
                self.assertEqual(len(self.calls),1)

    def test_duplicate_local_pair_keeps_one_entry_and_local_reason(self):
        files=[{'name':'a.csv','content':'id\nA\n'},{'name':'b.csv','content':'id\nA\n'}]
        rel={**REL,'source':'map:a.csv:id','target':'map:b.csv:id','evidence':[]}
        draft,_=self.create([rel],files)
        selected=[e for e in draft['entries'] if e['kind']=='relation' and e['source']['file']=='a.csv']
        self.assertEqual(len(selected),1)
        self.assertIn('overlapping',selected[0]['extraction']['local_advisory']['reason'])
        self.assertEqual(selected[0]['reason'],rel['reason'])
        self.assertEqual(p.restore_draft(draft)['entries'],draft['entries'])
