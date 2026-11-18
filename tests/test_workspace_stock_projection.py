"""Bounded stock evidence projection and durable replay, scripted model only."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab import workspace_question, workspace_stock
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_workspace_question import Gateway
from tests.test_workspace_stock import prepared


class StockProjectionTests(unittest.TestCase):
    def test_compound_request_retains_full_results_but_sends_selected_evidence(self):
        ids=[f'S{i:03d}_'+('x'*75) for i in range(120)]
        rows=''.join(f'{sku},5,unused\n' for sku in ids)
        calls=[{'tool':'stock_check','arguments':{'sku':ids[i],'quantity':i+4}} for i in range(4)]
        gateway=Gateway([{'calls':calls,'unresolved':['Order approval not checked']},
                         {'answer':'Scripted quantity comparison','citations':['e1','e2','e3','e4'],'unresolved':[]}])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db'; service=WorkspaceService(path,question_gateway=gateway);row=prepared(service,rows)
            request={'action':'ask','id':row['id'],'revision':2,'request_key':'four-stock',
                     'question':'Compare requested units for the four SKU selections.'}
            op=service.handle(request)['operation'];self.assertEqual(op['state'],'completed',op.get('error'))
            result=op['result'];full=result['evidence'];sent=json.loads(gateway.calls[1][1][1]['content'])
            self.assertEqual(sent,result['answer_input'])
            self.assertEqual(len(gateway.calls),2)
            # The old unprojected packet for this same trace exceeds the declared
            # byte limit; no old/extra provider call is made to measure this.
            old_packet={**sent,'evidence':full}
            old_bytes=len(json.dumps([{'role':'system','content':workspace_question.ANSWER},
                {'role':'user','content':json.dumps(old_packet,ensure_ascii=False)}],ensure_ascii=False).encode())
            self.assertGreater(old_bytes,38000)
            self.assertLessEqual(len(json.dumps(gateway.calls[1][1],ensure_ascii=False).encode()),38000)
            for actual,projected in zip(full,sent['evidence']):
                source=actual['result'];dest=projected['result']
                self.assertEqual(len(source['scope']['identifiers']),120)
                self.assertIn('report_turtle',source['validation'])
                expected=copy.deepcopy(source);expected['scope'].pop('identifiers')
                for key in ['data_turtle','shapes_turtle','report_turtle']:expected['validation'].pop(key)
                self.assertEqual(dest,expected)
                self.assertEqual(projected['answer_projection']['excluded_paths'],[
                    'scope.identifiers','validation.data_turtle','validation.shapes_turtle','validation.report_turtle'])
            self.assertEqual(WorkspaceService(path).handle(request)['operation']['result'],result)
            self.assertEqual(len(gateway.calls),2)

    def test_unknown_duplicate_records_preserved_and_input_not_mutated(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=WorkspaceService(Path(tmp)/'db');row=prepared(service,'A,5,x\nA,,y\n')
            evidence=[{'id':'e1','state':'completed','result':workspace_stock.execute(row['draft'],{'sku':'A','quantity':3})},
                      {'id':'e2','state':'failed','error':'original failure'}]
            before=copy.deepcopy(evidence);projected=workspace_question.answer_evidence(evidence)
            self.assertEqual(evidence,before)
            self.assertEqual(projected[0]['result']['records'],evidence[0]['result']['records'])
            self.assertEqual(projected[0]['result']['reason'],'ambiguous_sku_records')
            self.assertIsNone(projected[0]['result']['validation'])
            self.assertEqual(projected[0]['answer_projection']['excluded_paths'],['scope.identifiers'])
            self.assertEqual(projected[1],evidence[1])
