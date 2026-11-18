"""Authored scoped-stock development checks, not live-model evaluation."""
import json
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab import workspace_stock
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_workspace_question import Gateway, FINAL


def prepared(service, rows='A,5,secret\n', stock_status='approved'):
    row = service.handle({'action': 'create', 'domain': 'commerce', 'title': 'Partial stock',
        'metadata': {'snapshot_id': 'inventory', 'as_of': '2026-11-17', 'currency': 'GBP'},
        'files': [{'name': 'warehouse.csv', 'content': 'code,units,private_note\n' + rows}]})
    return service.handle({'action': 'change', 'id': row['id'], 'revision': 1, 'decisions': [
        {'entry_id': 'map:warehouse.csv:code', 'target': 'skus.id', 'status': 'approved',
         'note': 'Reviewed SKU identity', 'interpretation': 'SKU identifier'},
        {'entry_id': 'map:warehouse.csv:units', 'target': 'skus.available', 'status': stock_status,
         'note': 'Recorded available units', 'interpretation': 'Units available in this snapshot only'}]})


class StockTests(unittest.TestCase):
    def test_partial_approval_comparison_parity_and_unknowns(self):
        for rows, qty, status, reason in [
            ('A,5,secret\n', 5, 'recorded_quantity_sufficient', None),
            ('A,5,secret\n', 6, 'recorded_quantity_insufficient', None),
            ('A,0,secret\n', 1, 'recorded_quantity_insufficient', None),
            ('A,,secret\n', 1, 'unknown', 'available_quantity_missing'),
            ('A,5.5,secret\n', 1, 'unknown', 'available_quantity_format_unsupported'),
            ('A,-1,secret\n', 1, 'unknown', 'available_quantity_format_unsupported'),
            ('B,5,secret\n', 1, 'unknown', 'not_found_in_selected_source'),
            ('A,5,secret\nA,5,secret\n', 1, 'unknown', 'ambiguous_sku_records')]:
            with self.subTest(rows=rows, qty=qty), tempfile.TemporaryDirectory() as tmp:
                service=WorkspaceService(Path(tmp)/'db'); row=prepared(service,rows)
                self.assertFalse(row['readiness']['ready'])
                result=workspace_stock.execute(row['draft'],{'sku':'A','quantity':qty})
                self.assertEqual(result['status'],status)
                self.assertNotIn('secret',json.dumps(result))
                if reason:
                    self.assertEqual(result['reason'],reason)
                    self.assertIsNone(result['validation'])
                else:
                    self.assertTrue(result['validation']['agrees_with_python'])
                    self.assertEqual(result['validation']['shacl_conforms'],status.endswith('_sufficient'))
                    self.assertEqual(result['records'][0]['source']['line_start'],2)
                self.assertEqual(result['metadata']['currency'],'GBP')
                self.assertIn('order approval',result['unchecked'])

    def test_unreviewed_and_invalid_request_do_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=WorkspaceService(Path(tmp)/'db'); row=prepared(service,stock_status='excluded')
            self.assertIsNone(workspace_stock.catalog(row['draft']))
            with self.assertRaises(ValueError):workspace_stock.execute(row['draft'],{'sku':'A','quantity':1})
            row=prepared(service)
            for qty in (True,0,-1,1.5,'2',1000000001):
                with self.assertRaises(ValueError):workspace_stock.execute(row['draft'],{'sku':'A','quantity':qty})

    def test_question_real_comparison_durable_replay_and_full_policy_guard(self):
        plan={'calls':[{'tool':'stock_check','arguments':{'sku':'A','quantity':6}},
                       {'tool':'replacement_proposal','arguments':{'item':'I1','replacement':'A',
                        'retain_discount':True,'free_shipping':True,'split':False,'promise_arrival':False}}],
              'unresolved':['Order substitution eligibility not established']}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db'; gateway=Gateway([plan,FINAL]); service=WorkspaceService(path,question_gateway=gateway)
            row=prepared(service)
            req={'action':'ask','id':row['id'],'revision':2,'request_key':'stock',
                 'question':'Are six A units recorded as available, and can I substitute them?'}
            op=service.handle(req)['operation']; self.assertEqual(op['state'],'completed',op.get('error'))
            evidence=op['result']['answer_input']['evidence']
            self.assertEqual(evidence[0]['result']['status'],'recorded_quantity_insufficient')
            self.assertEqual(evidence[1]['state'],'failed')
            self.assertEqual(len(gateway.calls),2)
            self.assertEqual(WorkspaceService(path).handle(req)['operation']['result'],op['result'])
            self.assertEqual(len(gateway.calls),2)
            revised=service.handle({'action':'change','id':row['id'],'revision':2,'decisions':[
                {'entry_id':'map:warehouse.csv:units','target':'skus.available','status':'excluded',
                 'note':'Withdraw availability interpretation','interpretation':''}]})
            self.assertIsNone(workspace_stock.catalog(revised['draft']))
            self.assertEqual(service.handle(req)['operation']['result'],op['result'])
