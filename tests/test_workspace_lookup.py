import tempfile
import unittest
from pathlib import Path
from apps.factory_lab.workspace_service import WorkspaceService


class LookupTests(unittest.TestCase):
    def test_partial_review_lookup_preserves_scope_duplicates_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=WorkspaceService(Path(tmp)/'db.sqlite')
            row=service.handle({'action':'create','domain':'commerce','title':'Merchant CSV',
                'metadata':{'snapshot_id':'merchant','as_of':'2026-11-17','currency':'KRW'},
                'files':[{'name':'export.csv','content':'주문번호,주문상태,내부메모\n가-01,출고대기,미검토 비밀\n중복,첫째,메모\n중복,둘째,메모\n'},
                         {'name':'policy.md','content':'할인 기준은 담당자에게 확인.'}]})
            key=row['id']
            self.assertEqual(row['lookup_catalog'],[])
            decisions=[]
            for column,target in [('주문번호','orders.id'),('주문상태','orders.status')]:
                decisions.append({'entry_id':'map:export.csv:'+column,'target':target,'status':'approved','note':'','interpretation':''})
            row=service.handle({'action':'change','id':key,'revision':1,'decisions':decisions})
            self.assertFalse(row['readiness']['ready'])
            self.assertEqual(row['lookup_catalog'][0]['table'],'orders')
            request={'action':'lookup','id':key,'revision':2,'request_key':'one',
                     'selection':{'table':'orders','identifier':'가-01'}}
            result=service.handle(request)['operation']['result']
            self.assertEqual(result['status'],'found')
            self.assertEqual(result['records'][0]['values'],{'id':'가-01','status':'출고대기'})
            self.assertNotIn('미검토 비밀',str(result))
            self.assertIn('coupon',result['unreviewed_fields'])
            self.assertNotIn('shacl',result)
            for identifier,status,count in [('중복','ambiguous_identifier',2),('없는값','not_found_in_source',0)]:
                outcome=service.handle({**request,'request_key':identifier,'selection':{'table':'orders','identifier':identifier}})
                self.assertEqual(outcome['operation']['result']['status'],status)
                self.assertEqual(len(outcome['operation']['result']['records']),count)
            restarted=WorkspaceService(Path(tmp)/'db.sqlite')
            self.assertTrue(restarted.handle(request)['reused'])
            self.assertEqual(restarted.handle(request)['operation']['result'],result)
            bad=restarted.handle({**request,'request_key':'bad','selection':{'table':'skus','identifier':'가-01'}})
            self.assertEqual(bad['operation']['state'],'failed')
