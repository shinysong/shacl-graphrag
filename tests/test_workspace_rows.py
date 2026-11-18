"""Authored development examples; not merchant-data accuracy evaluation."""
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_workspace_question import Gateway, FINAL


def prepared(service):
    row=service.handle({'action':'create','domain':'commerce','title':'Order lines',
        'metadata':{'snapshot_id':'lines','as_of':'2026-11-17','currency':'GBP'},
        'files':[{'name':'lines.csv','content':'order_no,description,private_note\nA,"first\nline",secret1\nA,second,secret2\n,blank,secret3\n'}]})
    return service.handle({'action':'change','id':row['id'],'revision':1,'decisions':[
        {'entry_id':'map:lines.csv:order_no','target':'items.order','status':'approved','note':'Reviewed reference, not unique ID','interpretation':''},
        {'entry_id':'map:lines.csv:description','target':'products.name','status':'approved','note':'Reviewed label','interpretation':''}]})


class RowLookupTests(unittest.TestCase):
    def test_repeated_reference_all_rows_locations_partial_approval_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';service=WorkspaceService(path);row=prepared(service)
            self.assertFalse(row['readiness']['ready']);self.assertEqual(row['lookup_catalog'],[])
            request={'action':'lookup','id':row['id'],'revision':2,'request_key':'rows',
                     'selection':{'entry_id':'map:lines.csv:order_no','value':'A'}}
            op=service.handle(request)['operation'];self.assertEqual(op['state'],'completed',op.get('error'))
            result=op['result'];self.assertEqual(result['status'],'matched_rows')
            self.assertEqual([r['source']['line_start'] for r in result['records']],[2,4])
            self.assertEqual([r['source']['line_end'] for r in result['records']],[3,4])
            self.assertEqual(result['records'][0]['values'],{'order_no':'A','description':'first\nline'})
            self.assertNotIn('secret',str(result));self.assertEqual(result['metadata']['currency'],'GBP')
            self.assertNotIn('shacl',result);self.assertNotIn('calculations',result)
            reopened=WorkspaceService(path);self.assertEqual(reopened.handle(request)['operation']['result'],result)
            for value,count in [('',1),('a',0)]:
                saved=reopened.handle({**request,'request_key':'value-'+value,'selection':{**request['selection'],'value':value}})['operation']
                self.assertEqual(len(saved['result']['records']),count)
            bad=reopened.handle({**request,'request_key':'unreviewed','selection':{'entry_id':'map:lines.csv:private_note','value':'secret1'}})['operation']
            self.assertEqual(bad['state'],'failed')
            revised=reopened.handle({'action':'change','id':row['id'],'revision':2,'decisions':[
                {'entry_id':'map:lines.csv:order_no','target':'items.order','status':'excluded','note':'Withdraw query scope','interpretation':''}]})
            self.assertEqual(revised['revision'],3)
            fresh=reopened.handle({**request,'revision':3,'request_key':'withdrawn'})['operation']
            self.assertEqual(fresh['state'],'failed')
            self.assertEqual(reopened.handle(request)['operation']['result'],result)

    def test_scripted_question_receives_actual_matched_rows_without_policy_readiness(self):
        plan={'calls':[{'tool':'source_rows','arguments':{'entry_id':'map:lines.csv:order_no','value':'A'}}],
              'unresolved':['Refund policy not checked']}
        with tempfile.TemporaryDirectory() as tmp:
            gateway=Gateway([plan,FINAL]);service=WorkspaceService(Path(tmp)/'db',question_gateway=gateway);row=prepared(service)
            request={'action':'ask','id':row['id'],'revision':2,'request_key':'q','question':'Show all A lines and refund eligibility'}
            op=service.handle(request)['operation'];self.assertEqual(op['state'],'completed',op.get('error'))
            evidence=op['result']['answer_input']['evidence'][0]['result']
            self.assertEqual(len(evidence['records']),2);self.assertEqual(evidence['lookup_kind'],'source_rows')
            self.assertEqual(op['result']['unresolved'],plan['unresolved']);self.assertEqual(len(gateway.calls),2)
            self.assertTrue(service.handle(request)['reused']);self.assertEqual(len(gateway.calls),2)
