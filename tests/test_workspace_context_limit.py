"""Context guard recovery with scripted planner; no paid/model-quality claims."""
import json
from pathlib import Path
import tempfile
import unittest
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_workspace_question import Gateway

class ContextLimitTests(unittest.TestCase):
    def test_all_matches_saved_when_answer_input_too_large_and_replayed_without_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan={'calls':[{'tool':'source_rows','arguments':{'entry_id':'map:rows.csv:order','value':'A'}}],'unresolved':['Refund policy not checked']}
            gateway=Gateway([plan]);path=Path(tmp)/'db';service=WorkspaceService(path,question_gateway=gateway)
            content='order,description\n'+''.join('A,'+str(i)+'x'*900+'\n' for i in range(60))
            row=service.handle({'action':'create','domain':'commerce','title':'Large match','metadata':{'snapshot_id':'large','as_of':'2026-11-17','currency':'GBP'},'files':[{'name':'rows.csv','content':content}]})
            decisions=[{'entry_id':'map:rows.csv:'+c,'target':t,'status':'approved','note':'Authored diagnostic','interpretation':''} for c,t in [('order','items.order'),('description','products.name')]]
            row=service.handle({'action':'change','id':row['id'],'revision':1,'decisions':decisions})
            req={'action':'ask','id':row['id'],'revision':2,'request_key':'oversize','question':'Show all A lines'}
            op=service.handle(req)['operation'];self.assertEqual(op['state'],'failed')
            trace=op['result'];self.assertIsNone(trace['answer']);self.assertEqual(len(gateway.calls),1)
            self.assertEqual(trace['failure']['phase'],'answering');self.assertFalse(trace['failure']['call_sent'])
            self.assertFalse(trace['failure']['evidence_truncated']);self.assertGreater(trace['failure']['message_bytes'],38000)
            self.assertEqual(len(trace['evidence'][0]['result']['records']),60)
            self.assertEqual(trace['answer_input']['evidence'][0]['result']['records'],trace['evidence'][0]['result']['records'])
            self.assertEqual(trace['unresolved'],plan['unresolved'])
            reopened=WorkspaceService(path,question_gateway=gateway)
            self.assertTrue(reopened.handle(req)['reused']);self.assertEqual(len(gateway.calls),1)
            self.assertEqual(reopened.handle(req)['operation']['result'],trace)

    def test_large_catalog_is_discovered_in_pages_and_direct_rows_remain_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            gateway=Gateway([{'calls':[{'tool':'explore_repository','arguments':{'action':'overview'}}],'unresolved':[]},{'answer':'Observed source schema','citations':['e1'],'unresolved':[]}]);path=Path(tmp)/'db';service=WorkspaceService(path,question_gateway=gateway)
            ids=[str(i)+'x'*900 for i in range(60)]
            row=service.handle({'action':'create','domain':'commerce','title':'Large catalog','metadata':{'snapshot_id':'catalog','as_of':'2026-11-17','currency':'GBP'},'files':[{'name':'rows.csv','content':'identifier\n'+'\n'.join(ids)+'\n'}]})
            row=service.handle({'action':'change','id':row['id'],'revision':1,'decisions':[{'entry_id':'map:rows.csv:identifier','target':'items.id','status':'approved','note':'Authored diagnostic','interpretation':''}]})
            req={'action':'ask','id':row['id'],'revision':2,'request_key':'large-catalog','question':'?'}
            op=service.handle(req)['operation'];self.assertEqual(op['state'],'completed')
            trace=op['result'];self.assertNotIn('failure',trace)
            packet=json.loads(gateway.calls[0][1][1]['content'])
            self.assertEqual(packet['catalog']['source_lookup']['available_count'],1)
            self.assertLess(len(json.dumps(gateway.calls[0][1]).encode()),38000)
            self.assertEqual(trace['catalog']['source_lookup'][0]['identifiers'],ids)
            self.assertEqual(len(gateway.calls),2)
            reopened=WorkspaceService(path,question_gateway=gateway)
            replay=reopened.handle(req);self.assertTrue(replay['reused']);self.assertEqual(replay['operation']['result'],trace)
            from apps.factory_lab import workspace_lookup
            result=workspace_lookup.execute_rows(row['draft'],{'entry_id':'map:rows.csv:identifier','value':ids[0]})
            self.assertEqual(len(result['records']),1);self.assertEqual(len(gateway.calls),2)
