import tempfile
from copy import deepcopy
from apps.factory_lab import preparation as p
import unittest
from pathlib import Path
from apps.factory_lab.workspace_service import WorkspaceService
from tests.workspace_fixtures import approved, compared
from tests.test_preparation import example
from tests.test_preparation_history import review

class WorkspaceServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'workspace.sqlite'
        self.service=WorkspaceService(self.path)
    def tearDown(self):self.temp.cleanup()

    def test_user_proposal_without_cases_file_runs_real_engine_and_is_durable(self):
        files,metadata=example()
        draft=compared(review(p.create([f for f in files if f['name']!='cases.csv'],metadata)))
        row=self.service.store.create('Own source tables',draft)
        proposal={'item':'I1','replacement':'S2','retain_discount':True,
                  'free_shipping':True,'split':False,'promise_arrival':True}
        request={'action':'propose','id':row['id'],'revision':1,'request_key':'proposal-1','proposal':proposal}
        outcome=self.service.handle(request)
        self.assertEqual(outcome['operation']['state'],'completed')
        result=outcome['operation']['result']
        self.assertEqual(result['preparation']['proposal'],proposal)
        self.assertEqual(result['preparation']['parameter_origin'],'user_input')
        self.assertTrue(result['answer'])
        self.assertTrue(result['shacl'])
        self.assertNotIn('cases.csv',[s['name'] for s in result['preparation']['sources']])
        restarted=WorkspaceService(self.path)
        self.assertEqual(restarted.handle(request)['operation']['result'],result)
        self.assertTrue(restarted.handle(request)['reused'])
        with self.assertRaises(ValueError):
            restarted.handle({**request,'proposal':{**proposal,'replacement':'S3'}})
        failed=restarted.handle({**request,'request_key':'bad-proposal','proposal':{**proposal,'replacement':'missing'}})
        self.assertEqual(failed['operation']['state'],'failed')
        self.assertEqual(len(restarted.store.operations(row['id'])),2)

    def test_unfinished_draft_restart_group_atomicity_and_diff(self):
        row=self.service.handle({'action':'example','domain':'commerce'})
        key=row['id'];entry=row['draft']['entries'][0]
        decision={'entry_id':entry['id'],'status':'approved','target':entry['target'],'note':'','interpretation':''}
        bad={**decision,'entry_id':'missing'}
        with self.assertRaises(ValueError):
            self.service.handle({'action':'change','id':key,'revision':1,'decisions':[decision,bad]})
        self.assertEqual(self.service.store.get(key)['revision'],1)
        changed=self.service.handle({'action':'change','id':key,'revision':1,'decisions':[decision]})
        self.assertEqual(changed['revision'],2)
        files=[{'name':s['name'],'content':s['content']} for s in changed['draft']['sources']]
        files.append({'name':'extra.md','content':'Review additional applicability.'})
        self.service.handle({'action':'refresh','id':key,'revision':2,'files':files})
        restarted=WorkspaceService(self.path)
        recovered=restarted.handle({'action':'get','id':key,'revision':None})
        self.assertEqual(recovered['revision'],3)
        self.assertTrue(all(e['status']=='pending' for e in recovered['draft']['entries']))
        diff=restarted.handle({'action':'diff','id':key,'before':2,'after':3})
        self.assertEqual(diff['added'],['extra.md'])
        self.assertTrue(diff['review_required'])
        exported=restarted.handle({'action':'export','id':key,'revision':3})
        self.assertFalse(exported['review_resolved'])

    def test_actual_engine_result_survives_restart_and_request_is_not_reexecuted(self):
        row=self.service.store.create('Reviewed example',approved());key=row['id']
        request={'action':'execute','id':key,'revision':1,'request_key':'once','case_id':'ready'}
        first=self.service.handle(request)
        self.assertEqual(first['operation']['state'],'completed')
        self.assertEqual(first['operation']['result']['workspace']['revision'],1)
        restarted=WorkspaceService(self.path)
        again=restarted.handle(request)
        self.assertTrue(again['reused'])
        self.assertEqual(again['operation']['result'],first['operation']['result'])
        failed=restarted.handle({**request,'request_key':'bad','case_id':'missing'})
        self.assertEqual(failed['operation']['state'],'failed')
        self.assertTrue(restarted.handle({**request,'request_key':'bad','case_id':'missing'})['reused'])

    def test_identical_reupload_preserves_approvals_but_real_change_invalidates(self):
        row=self.service.store.create('Reviewed example',approved());key=row['id']
        view=self.service.view(key)
        self.assertTrue(view['readiness']['ready'])
        self.assertIn('ready',[c['id'] for c in view['cases']])
        self.assertIn('orders.id',view['mapping_targets'])
        files=[{'name':s['name'],'content':s['content']} for s in reversed(row['draft']['sources'])]
        same=self.service.handle({'action':'refresh','id':key,'revision':1,'files':files})
        self.assertEqual(same['revision'],1)
        self.assertEqual(same['draft'],row['draft'])
        self.assertTrue(same['readiness']['ready'])
        # Even a byte-level policy edit must not inherit previous approval.
        document=next(f for f in files if f['name'].endswith('.md'))
        document['content']+='\n'
        changed=self.service.handle({'action':'refresh','id':key,'revision':1,'files':files})
        self.assertEqual(changed['revision'],2)
        self.assertFalse(changed['readiness']['ready'])
        self.assertEqual(changed['cases'],[])
        self.assertTrue(all(e['status']=='pending' for e in changed['draft']['entries']))
        self.assertEqual(self.service.store.get(key,1)['draft'],row['draft'])
        # A stale client cannot use the no-op shortcut to evade concurrency checks.
        with self.assertRaisesRegex(ValueError,'reload'):
            self.service.handle({'action':'refresh','id':key,'revision':1,
                                 'files':[{'name':s['name'],'content':s['content']} for s in row['draft']['sources']]})

    def test_working_export_import_is_new_workspace_without_execution_history(self):
        row=self.service.handle({'action':'example','domain':'commerce'})
        bundle=self.service.handle({'action':'export','id':row['id'],'revision':1})
        restored=self.service.handle({'action':'import','title':'Restored draft','bundle':bundle})
        self.assertNotEqual(restored['id'],row['id'])
        self.assertEqual(restored['draft']['entries'],row['draft']['entries'])
        self.assertEqual(restored['operations'],[])
        self.assertFalse(restored['readiness']['ready'])
        bundle['draft']['metadata']['snapshot_id']='tampered'
        with self.assertRaisesRegex(ValueError,'digest'):
            self.service.handle({'action':'import','title':'Bad','bundle':bundle})

    def test_metadata_only_refresh_invalidates_and_preserves_prior_snapshot(self):
        row=self.service.store.create('Reviewed example',approved());key=row['id']
        files=[{'name':s['name'],'content':s['content']} for s in row['draft']['sources']]
        metadata={**row['draft']['metadata'],'snapshot_id':'later','as_of':'2030-01-01'}
        updated=self.service.handle({'action':'refresh','id':key,'revision':1,'files':files,'metadata':metadata})
        self.assertEqual(updated['revision'],2)
        self.assertEqual(updated['draft']['metadata'],metadata)
        self.assertTrue(all(e['status']=='pending' for e in updated['draft']['entries']))
        self.assertEqual(self.service.store.get(key,1)['draft'],row['draft'])
        self.assertEqual(p.restore_draft(updated['draft']),updated['draft'])
        diff=self.service.handle({'action':'diff','id':key,'before':1,'after':2})
        self.assertEqual(diff['changed'],[])
        self.assertEqual(diff['metadata_before'],row['draft']['metadata'])
        self.assertEqual(diff['metadata_after'],metadata)
        same=self.service.handle({'action':'refresh','id':key,'revision':2,'files':files,'metadata':metadata})
        self.assertEqual(same['revision'],2)
        for bad in (None,{}, {**metadata,'as_of':'bad'}):
            with self.assertRaises(ValueError):
                self.service.handle({'action':'refresh','id':key,'revision':2,'files':files,'metadata':bad})
        self.assertEqual(self.service.store.get(key)['revision'],2)

    def test_later_policy_can_be_reviewed_after_explicit_date_refresh(self):
        files=[{'name':'policy.md','content':'2030-01-01부터 할인 전 금액 기준 무료배송 정책 적용.'}]
        metadata={'snapshot_id':'early','as_of':'2029-01-01','currency':'KRW'}
        row=self.service.handle({'action':'create','domain':'commerce','title':'Policy date',
                                 'files':files,'metadata':metadata})
        e=row['draft']['entries'][0]
        decision={'entry_id':e['id'],'status':'approved','target':'shipping','note':'',
                  'interpretation':'Reviewed applicability'}
        with self.assertRaisesRegex(ValueError,'later than'):
            self.service.handle({'action':'change','id':row['id'],'revision':1,'decisions':[decision]})
        self.service.handle({'action':'refresh','id':row['id'],'revision':1,'files':files,
                             'metadata':{**metadata,'snapshot_id':'current','as_of':'2030-01-01'}})
        reviewed=self.service.handle({'action':'change','id':row['id'],'revision':2,'decisions':[decision]})
        self.assertEqual(reviewed['draft']['entries'][0]['status'],'approved')
        self.assertFalse(reviewed['readiness']['ready'])  # Date applicability does not invent missing tables.

    def test_rehashed_malformed_import_does_not_add_or_replace_workspace(self):
        row=self.service.handle({'action':'example','domain':'commerce'})
        original=self.service.handle({'action':'export','id':row['id'],'revision':1})
        for field,value in [('entries',[None]),('sources',None),('metadata',[]),('saved_suggestions',[{'source':[]}])]:
            bundle=deepcopy(original);bundle['draft'][field]=value
            bundle['digest']=p.digest(bundle['draft'])
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.service.handle({'action':'import','title':'Malformed','bundle':bundle})
        self.assertEqual(len(self.service.store.list()),1)
        self.assertEqual(self.service.store.get(row['id'])['draft'],row['draft'])

    def test_malformed_advisory_annotations_rejected_before_persistence(self):
        row=self.service.handle({'action':'example','domain':'commerce'})
        original=self.service.handle({'action':'export','id':row['id'],'revision':1})
        for value in [None, {'questions':1}, {'questions':[{}]},
                      {'related_policy_statements':1},
                      {'related_policy_statements':[None]},
                      {'related_policy_statements':[{'entry_id':'fake'}]},
                      {'related_policy_count':True}]:
            bundle=deepcopy(original)
            # Rehashing and matching both copies must not bypass shape checks.
            for field in ('saved_suggestions','entries'):
                bundle['draft'][field][0]['extraction']=value
            bundle['digest']=p.digest(bundle['draft'])
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.service.handle({'action':'import','title':'Malformed','bundle':bundle})
        self.assertEqual(len(self.service.store.list()),1)
        self.assertEqual(self.service.store.get(row['id'])['draft'],row['draft'])
