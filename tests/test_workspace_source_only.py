"""Raw reviewed columns must not masquerade as adapter fields."""
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_workspace_question import Gateway, FINAL

class SourceOnlyTests(unittest.TestCase):
    def test_unknown_columns_lookup_replay_and_withdrawal(self):
        plan={'calls':[{'tool':'source_rows','arguments':{'entry_id':'map:custom.csv:purchase_ref','value':'A'}}],'unresolved':['No refund policy checked']}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';g=Gateway([plan,FINAL]);service=WorkspaceService(path,question_gateway=g)
            row=service.handle({'action':'create','domain':'commerce','title':'Custom records','metadata':{'snapshot_id':'custom','as_of':'2026-11-17','currency':'GBP'},'files':[{'name':'custom.csv','content':'purchase_ref,internal_stage,private\nA,waiting,secret\nA,,secret2\n'}]})
            decisions=[{'entry_id':'map:custom.csv:'+c,'target':'source_only','status':'approved','note':'','interpretation':meaning} for c,meaning in [('purchase_ref','Merchant purchase reference; repeats per line'),('internal_stage','Internal processing label; not shipping status')]]
            with self.assertRaises(ValueError):
                service.handle({'action':'change','id':row['id'],'revision':1,'decisions':[{**decisions[0],'interpretation':''}]})
            row=service.handle({'action':'change','id':row['id'],'revision':1,'decisions':decisions})
            self.assertEqual(row['lookup_catalog'],[])
            self.assertFalse(row['readiness']['ready'])
            req={'action':'ask','id':row['id'],'revision':2,'request_key':'custom','question':'Show A processing records'}
            op=service.handle(req)['operation'];self.assertEqual(op['state'],'completed',op.get('error'))
            result=op['result']['answer_input']['evidence'][0]['result']
            self.assertEqual([r['values'] for r in result['records']],[{'purchase_ref':'A','internal_stage':'waiting'},{'purchase_ref':'A','internal_stage':''}])
            self.assertEqual(result['scope']['reviewed_target'],'source_only')
            self.assertNotIn('secret',str(result))
            reopened=WorkspaceService(path,question_gateway=g)
            self.assertEqual(reopened.handle(req)['operation']['result'],op['result']);self.assertEqual(len(g.calls),2)
            row=reopened.handle({'action':'change','id':row['id'],'revision':2,'decisions':[{**decisions[0],'status':'excluded','note':'Withdraw'}]})
            self.assertNotIn(decisions[0]['entry_id'],[c['entry_id'] for c in row['row_lookup_catalog']])
            self.assertEqual(reopened.handle(req)['operation']['result'],op['result'])
