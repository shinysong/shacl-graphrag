import tempfile
import unittest
from pathlib import Path
from apps.factory_lab import preparation as p
from apps.factory_lab.workspace_diff import decision_changes
from apps.factory_lab.workspace_service import WorkspaceService

META={'snapshot_id':'review-diff','as_of':'2026-11-17','currency':'KRW'}


class DiffTests(unittest.TestCase):
    def test_decision_only_revision_reports_interpretation_without_source_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=WorkspaceService(Path(tmp)/'db.sqlite')
            row=service.handle({'action':'create','title':'Diff','domain':'commerce','metadata':META,
                               'files':[{'name':'orders.csv','content':'id,status\nO1,unshipped\n'},
                                        {'name':'policy.md','content':'할인 전 금액 기준 무료배송.'}]})
            e=next(e for e in row['draft']['entries'] if e['kind']=='policy')
            decision={'entry_id':e['id'],'target':'shipping','status':'approved',
                      'interpretation':'Applies to standard delivery','note':'Reviewed'}
            service.handle({'action':'change','id':row['id'],'revision':1,'decisions':[decision]})
            service.handle({'action':'change','id':row['id'],'revision':2,'decisions':[
                {**decision,'interpretation':'Applies to domestic standard delivery only'}]})
            diff=service.handle({'action':'diff','id':row['id'],'before':2,'after':3})
            self.assertEqual(diff['changed'],[])
            self.assertEqual(len(diff['decision_changes']),1)
            item=diff['decision_changes'][0]
            self.assertEqual(item['changed_fields'],['interpretation'])
            self.assertEqual(item['before']['interpretation'],decision['interpretation'])
            self.assertEqual(item['after']['interpretation'],'Applies to domestic standard delivery only')
            same=service.handle({'action':'diff','id':row['id'],'before':3,'after':3})
            self.assertEqual(same['decision_changes'],[])

    def test_relation_ordinals_do_not_establish_identity(self):
        files=[{'name':name,'content':'id\nshared\n'} for name in ('a.csv','b.csv','c.csv')]
        before=p.create(files,META)
        after=p.create(list(reversed(files)),META)
        # Same hypotheses in different generator order have no decision changes.
        self.assertEqual(decision_changes(before,after),[])
        removed=p.create(files[:1],META)
        changes=decision_changes(before,removed)
        self.assertTrue(any(c['change']=='removed' and c['kind']=='relation' for c in changes))
