"""Source mention retrieval is evidence navigation, not semantic approval."""
import copy
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab.workspace_references import column_references
from apps.factory_lab.preparation_sources import inspect_sources
from apps.factory_lab.workspace_service import WorkspaceService


class ReferencesTests(unittest.TestCase):
    def test_boundaries_negation_locations_and_limit(self):
        files = [{'name':'orders.csv','content':'order_no\nA\n'},
                 {'name':'meaning.md','content':'refund_order_no only\n\norder_no is NOT a bin identifier.\nSecond line.\n\norder_no definition\n'}]
        draft={'sources':inspect_sources(files)};before=copy.deepcopy(draft)
        result=column_references(draft,limit=1)['orders.csv']['order_no']
        self.assertEqual(result['total'],2)
        self.assertEqual(len(result['matches']),1)
        match=result['matches'][0]
        self.assertEqual((match['line_start'],match['line_end']),(3,4))
        self.assertNotIn('text',match)
        self.assertEqual(draft['sources'][1]['paragraphs'][match['paragraph']-1]['text'],'order_no is NOT a bin identifier.\nSecond line.\n')
        self.assertEqual(match['sha256'],draft['sources'][1]['sha256'])
        self.assertEqual(draft,before)

    def test_revision_and_restart_do_not_regenerate_or_reapprove(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';service=WorkspaceService(path)
            files=[{'name':'orders.csv','content':'order_no\nA\n'},
                   {'name':'meaning.md','content':'order_no is not a bin code.'}]
            row=service.handle({'action':'create','domain':'commerce','title':'References','metadata':{'snapshot_id':'v1','as_of':'2026-11-17','currency':'KRW'},'files':files})
            original=copy.deepcopy(row['draft'])
            files[1]={'name':'meaning.md','content':'No named field here.'}
            latest=service.handle({'action':'refresh','id':row['id'],'revision':1,'files':files})
            self.assertEqual(latest['column_references']['orders.csv']['order_no']['total'],0)
            old=WorkspaceService(path).view(row['id'],1)
            self.assertEqual(old['draft'],original)
            self.assertEqual(old['column_references']['orders.csv']['order_no']['total'],1)
            self.assertTrue(all(e['status']=='pending' for e in old['draft']['entries']))
