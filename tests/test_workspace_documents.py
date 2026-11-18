"""Document evidence retrieval, not business-policy correctness."""
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab import workspace_documents as documents
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_workspace_question import Gateway, FINAL

class DocumentTests(unittest.TestCase):
    def test_approved_text_question_replay_withdrawal(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';service=WorkspaceService(path)
            row=service.handle({'action':'create','domain':'commerce','title':'Policy','metadata':{'snapshot_id':'v1','as_of':'2026-11-17','currency':'GBP'},'files':[{'name':'policy.md','content':'Shipping is free above GBP 60. Islands excluded.\n\nOther unreviewed clause.'}]})
            entry=row['draft']['entries'][0];eid=entry['id']
            self.assertEqual(documents.catalog(row['draft']),[])
            with self.assertRaises(ValueError):documents.execute(row['draft'],{'entry_id':eid})
            decision={'entry_id':eid,'status':'approved','target':'context','note':'','interpretation':'Reference text only'}
            row=service.handle({'action':'change','id':row['id'],'revision':1,'decisions':[decision]})
            gateway=Gateway([{'calls':[{'tool':'source_document','arguments':{'entry_id':eid}}],'unresolved':['Applicability not checked']},FINAL]);service.question_gateway=gateway
            request={'action':'ask','id':row['id'],'revision':2,'request_key':'doc','question':'What does the shipping document say?'}
            op=service.handle(request)['operation'];self.assertEqual(op['state'],'completed',op.get('error'))
            evidence=op['result']['answer_input']['evidence'][0]['result']
            self.assertEqual(evidence['source'],entry['source'])
            self.assertIn('Islands excluded.',evidence['source']['text'])
            self.assertIn('policy_calculation',evidence['unchecked'])
            self.assertNotIn('Other unreviewed clause',str(op['result']['catalog']))
            self.assertEqual(WorkspaceService(path).handle(request)['operation']['result'],op['result'])
            row=service.handle({'action':'change','id':row['id'],'revision':2,'decisions':[{**decision,'status':'excluded','note':'withdrawn'}]})
            self.assertEqual(documents.catalog(row['draft']),[])
            with self.assertRaises(ValueError):documents.execute(row['draft'],{'entry_id':eid})
            self.assertEqual(len(gateway.calls),2)

    def test_direct_lookup_without_gateway_and_revocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';service=WorkspaceService(path)
            row=service.handle({'action':'create','domain':'commerce','title':'Direct','metadata':{'snapshot_id':'v1','as_of':'2026-11-17','currency':'GBP'},'files':[{'name':'policy.md','content':'Returns require review.'}]})
            eid=row['draft']['entries'][0]['id'];decision={'entry_id':eid,'status':'approved','target':'context','interpretation':'Reference only','note':''}
            row=service.handle({'action':'change','id':row['id'],'revision':1,'decisions':[decision]})
            request={'action':'lookup','id':row['id'],'revision':2,'request_key':'direct','selection':{'entry_id':eid}}
            op=service.handle(request)['operation'];self.assertEqual(op['state'],'completed')
            self.assertEqual(op['result']['mode'],'source_document')
            self.assertEqual(op['result']['workspace']['revision'],2)
            self.assertEqual(WorkspaceService(path).handle(request)['operation']['result'],op['result'])
            row=service.handle({'action':'change','id':row['id'],'revision':2,'decisions':[{**decision,'status':'excluded','note':'Withdraw'}]})
            self.assertEqual(row['document_catalog'],[])
            failed=service.handle({**request,'revision':3,'request_key':'new'})['operation']
            self.assertEqual(failed['state'],'failed')
            self.assertEqual(service.handle(request)['operation']['result'],op['result'])
