import tempfile
import unittest
from pathlib import Path
from apps.factory_lab.workspace_service import WorkspaceService

class BufferTests(unittest.TestCase):
    def test_buffer_restart_no_approval_and_concurrent_stale_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';service=WorkspaceService(path)
            row=service.handle({'action':'example','domain':'commerce'})
            entry=row['draft']['entries'][0]
            content={'entries':[{'entry_id':entry['id'],'target':entry['target'],'status':'approved','note':'draft only','interpretation':''}],'policies':[]}
            request={'action':'save_review_buffer','id':row['id'],'revision':1,'generation':0,'content':content}
            result=service.handle(request)
            self.assertEqual(result['generation'],1)
            restarted=WorkspaceService(path);view=restarted.view(row['id'])
            self.assertEqual(view['review_buffer']['content'],content)
            self.assertEqual(view['draft'],row['draft'])
            self.assertEqual(view['revision'],1)
            with self.assertRaises(ValueError):restarted.handle(request)
            revised=restarted.handle({'action':'change','id':row['id'],'revision':1,'decisions':content['entries']})
            self.assertEqual(revised['revision'],2)
            self.assertEqual(revised['review_buffer']['revision'],1)
            with self.assertRaises(ValueError):restarted.handle({**request,'generation':1})
            with self.assertRaises(ValueError):restarted.handle({**request,'revision':2,'generation':1,'content':{'entries':[{'arbitrary':'value'}],'policies':[]}})
            self.assertEqual(restarted.view(row['id'])['review_buffer']['generation'],1)

    def test_comparison_buffer_is_unapproved_durable_and_source_bound(self):
        from tests.test_preparation import approved
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';service=WorkspaceService(path)
            row=service.store.create('Reviewed fields',approved());view=service.view(row['id'])
            entry_id,comparison=next(iter(view['policy_agreements'].items()))
            record={'entry_id':entry_id,'binding':comparison['binding'],'decision':'agrees','basis':'unresolved','rationale':''}
            content={'entries':[],'policies':[],'comparisons':[record]}
            request={'action':'save_review_buffer','id':row['id'],'revision':1,'generation':0,'content':content}
            service.handle(request)
            reopened=WorkspaceService(path);current=reopened.view(row['id'])
            self.assertEqual(current['review_buffer']['content'],content)
            self.assertEqual(current['policy_agreements'][entry_id]['state'],'unreviewed')
            self.assertEqual(current['draft'],row['draft'])
            with self.assertRaises(ValueError):reopened.handle(request)
            for records in ([record,record],[{**record,'binding':'0'*64}],[{**record,'entry_id':'missing'}]):
                with self.assertRaises(ValueError):reopened.handle({**request,'generation':1,'content':{**content,'comparisons':records}})
            self.assertEqual(reopened.view(row['id'])['review_buffer']['generation'],1)
            entry=next(e for e in row['draft']['entries'] if e['id']==entry_id)
            reopened.handle({'action':'change','id':row['id'],'revision':1,'decisions':[{'entry_id':entry_id,'status':'approved','target':entry['target'],'note':'','interpretation':'Revised scope'}]})
            with self.assertRaises(ValueError):reopened.handle({**request,'revision':2,'generation':1})
            self.assertEqual(reopened.view(row['id'])['review_buffer']['revision'],1)
