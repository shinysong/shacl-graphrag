import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_preparation import approved

class WithdrawTests(unittest.TestCase):
    def test_stale_unaccepted_request_is_tombstoned_and_late_execution_not_run(self):
        with tempfile.TemporaryDirectory() as directory:
            service=WorkspaceService(Path(directory)/'db.sqlite')
            row=service.store.create('test',approved())
            draft=row['draft'];draft['metadata']['snapshot_id']='new-version'
            service.store.save(row['id'],draft,1)
            execute={'action':'execute','id':row['id'],'revision':1,'request_key':'old','case_id':'ready'}
            with self.assertRaises(ValueError):service.handle(execute)
            withdraw={'action':'withdraw_pending','id':row['id'],'revision':1,'request_key':'old',
                      'kind':'fixed_case','request':{'case_id':'ready'}}
            response=service.handle(withdraw)
            self.assertTrue(response['withdrawn'])
            self.assertEqual(response['operation']['state'],'cancelled')
            service=WorkspaceService(Path(directory)/'db.sqlite')
            self.assertEqual(service.handle(execute)['operation']['state'],'cancelled')
            self.assertEqual(len(service.store.operations(row['id'])),1)
            self.assertFalse(service.handle(withdraw)['withdrawn'])
            with self.assertRaises(ValueError):service.handle({**withdraw,'request':{'case_id':'other'}})

    def test_existing_running_operation_is_not_cancelled(self):
        with tempfile.TemporaryDirectory() as directory:
            service=WorkspaceService(Path(directory)/'db.sqlite')
            row=service.store.create('test',approved())
            op,_=service.store.begin(row['id'],1,'key','fixed_case',{'case_id':'ready'})
            response=service.handle({'action':'withdraw_pending','id':row['id'],'revision':1,'request_key':'key',
                                     'kind':'fixed_case','request':{'case_id':'ready'}})
            self.assertFalse(response['withdrawn'])
            self.assertEqual(response['operation']['state'],'running')
            service.store.finish(op['id'],'completed',result={'answer':'original'})
            response=service.handle({'action':'withdraw_pending','id':row['id'],'revision':1,'request_key':'key',
                                     'kind':'fixed_case','request':{'case_id':'ready'}})
            self.assertEqual(response['operation']['result'],{'answer':'original'})

    def test_concurrent_withdraw_and_begin_share_single_reservation(self):
        with tempfile.TemporaryDirectory() as directory:
            service=WorkspaceService(Path(directory)/'db.sqlite')
            row=service.store.create('test',approved())
            def reserve(cancel):return service.store.begin(row['id'],1,'race','fixed_case',{'case_id':'ready'},cancel_unstarted=cancel)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(reserve,[False,True]))
            self.assertEqual(sum(created for _,created in results),1)
            self.assertEqual(results[0][0]['id'],results[1][0]['id'])
            self.assertEqual(len(service.store.operations(row['id'])),1)

    def test_generation_withdraw_never_calls_gateway_and_cannot_adopt(self):
        with tempfile.TemporaryDirectory() as directory:
            class Gateway:
                config={'model':'never-called'}
                def call(self,*args):raise AssertionError('Withdrawn generation must not call provider')
            service=WorkspaceService(Path(directory)/'db.sqlite',Gateway())
            row=service.store.create('test',approved())
            response=service.handle({'action':'withdraw_pending','id':row['id'],'revision':1,'request_key':'gen',
                                     'kind':'model_suggestions','request':{'draft_digest':row['digest']}})
            late=service.handle({'action':'suggest','id':row['id'],'revision':1,'request_key':'gen'})
            self.assertEqual(late['operation']['state'],'cancelled')
            with self.assertRaises(ValueError):
                service.handle({'action':'adopt_suggestions','id':row['id'],'revision':1,'operation_id':response['operation']['id']})
