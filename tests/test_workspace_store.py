"""Persistence/recovery checks; no model-quality or user-study claim."""
import tempfile
import unittest
from unittest.mock import patch
from apps.factory_lab import workspace_store as ws
from pathlib import Path
from apps.factory_lab.workspace_store import WorkspaceStore


class WorkspaceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'workspaces.sqlite'
        self.store=WorkspaceStore(self.path)
    def tearDown(self): self.temp.cleanup()

    def test_version_references_do_not_decode_results(self):
        one=self.store.create('one',{})
        other=self.store.create('other',{})
        old,_=self.store.begin(one['id'],1,'old','query',{})
        self.store.save(one['id'],{'new':True},1)
        current,_=self.store.begin(one['id'],2,'current','query',{})
        self.store.begin(other['id'],1,'other','query',{})
        with self.store.connect() as db:
            db.execute('UPDATE operations SET result=?',('malformed',))
        self.assertEqual(self.store.historical_operation_ids(one['id'],2),[old['id']])
        self.assertEqual(self.store.historical_operation_ids(one['id'],1),[current['id']])

    def test_history_page_metadata_and_stable_cursor(self):
        row=self.store.create('history',{})
        ids=[]
        for n in range(25):
            op,_=self.store.begin(row['id'],1,str(n),'query',{'private':'request'})
            ids.append(op['id'])
            self.store.finish(op['id'],'completed',{'large':'x'*10000})
        first=self.store.operation_page(row['id'])
        self.assertEqual(first['operation_count'],25)
        self.assertEqual(len(first['operations']),20)
        self.assertTrue(all('result' not in r and 'request' not in r for r in first['operations']))
        self.store.begin(row['id'],1,'new','query',{})
        rest=self.store.operation_page(row['id'],first['operations_next'])
        self.assertEqual([r['id'] for r in first['operations']+rest['operations']],list(reversed(ids)))
        self.assertIsNone(rest['operations_next'])
        for value in (True,0,-1,'20'):
            with self.assertRaises(ValueError):self.store.operation_page(row['id'],value)
        with self.assertRaises(ValueError):self.store.operation_page('missing')

    def test_single_operation_is_scoped_and_does_not_decode_other_results(self):
        one=self.store.create('one',{})
        two=self.store.create('two',{})
        wanted,_=self.store.begin(one['id'],1,'wanted','query',{'question':'Q'})
        self.store.finish(wanted['id'],'completed',{'answer':'A'})
        unrelated,_=self.store.begin(one['id'],1,'unrelated','query',{})
        # Poison an unrelated result to prove this path never decodes it.
        with self.store.connect() as db:
            db.execute('UPDATE operations SET result=? WHERE id=?',('invalid json',unrelated['id']))
        record=WorkspaceStore(self.path).operation(one['id'],wanted['id'])
        self.assertEqual(record['request'],{'question':'Q'})
        self.assertEqual(record['result'],{'answer':'A'})
        self.assertEqual(record['state'],'completed')
        for key,oid in ((two['id'],wanted['id']),(one['id'],'missing')):
            with self.assertRaisesRegex(ValueError,'Unknown operation'):
                self.store.operation(key,oid)

    def test_restart_immutable_revision_and_duplicate_save(self):
        row=self.store.create('Shop',{'source':'original','pending':True})
        same=self.store.save(row['id'],row['draft'],1)
        self.assertEqual(same['revision'],1)
        self.store.save(row['id'],{'source':'changed','pending':True},1)
        restarted=WorkspaceStore(self.path)
        self.assertEqual(restarted.get(row['id'])['draft']['source'],'changed')
        self.assertEqual(restarted.get(row['id'],1)['draft'],row['draft'])
        with self.assertRaisesRegex(ValueError,'reload'):
            restarted.save(row['id'],{},1)

    def test_archive_is_reversible_and_does_not_delete_history(self):
        row=self.store.create('Shop',{'pending':True})
        self.store.archive(row['id'])
        self.assertEqual(self.store.list(),[])
        self.assertEqual(len(self.store.list(archived=True)),1)
        self.assertEqual(self.store.get(row['id'])['draft'],row['draft'])
        with self.assertRaises(ValueError):self.store.save(row['id'],{},1)
        self.store.archive(row['id'],False)
        self.assertEqual(len(self.store.list()),1)

    def test_operation_idempotency_recovery_and_no_automatic_retry(self):
        row=self.store.create('Shop',{})
        op,new=self.store.begin(row['id'],1,'request-1','query',{'question':'Q'})
        self.assertTrue(new)
        repeated,new=self.store.begin(row['id'],1,'request-1','query',{'question':'Q'})
        self.assertFalse(new);self.assertEqual(op['id'],repeated['id'])
        with self.assertRaises(ValueError):self.store.begin(row['id'],1,'request-1','query',{'question':'other'})
        restarted=WorkspaceStore(self.path)
        self.assertEqual(restarted.recover_interrupted(),1)
        recovered,new=restarted.begin(row['id'],1,'request-1','query',{'question':'Q'})
        self.assertFalse(new);self.assertEqual(recovered['state'],'interrupted')
        with self.assertRaises(ValueError):restarted.finish(op['id'],'completed',{})
        second,new=restarted.begin(row['id'],1,'request-2','query',{'question':'Q'})
        restarted.finish(second['id'],'completed',{'answer':'A'})
        saved,new=restarted.begin(row['id'],1,'request-2','query',{'question':'Q'})
        self.assertFalse(new);self.assertIn('A',saved['result'])

    def test_execution_requires_current_revision(self):
        row=self.store.create('Shop',{})
        self.store.save(row['id'],{'new':1},1)
        with self.assertRaises(ValueError):self.store.begin(row['id'],1,'old','query',{})

    def test_quota_preserves_data_and_noop_or_duplicate_recovery(self):
        row=self.store.create('Shop',{'source':'original'})
        with patch.object(ws,'MAX_REVISIONS',1):
            self.assertEqual(self.store.save(row['id'],row['draft'],1)['revision'],1)
            with self.assertRaisesRegex(ValueError,'revision limit'):
                self.store.save(row['id'],{'new':True},1)
        op,_=self.store.begin(row['id'],1,'key','query',{})
        with patch.object(ws,'MAX_OPERATIONS',1):
            self.assertFalse(self.store.begin(row['id'],1,'key','query',{})[1])
            with self.assertRaisesRegex(ValueError,'execution limit'):
                self.store.begin(row['id'],1,'next','query',{})
        with patch.object(ws,'MAX_STORED_BYTES',1):
            with self.assertRaisesRegex(ValueError,'storage limit'):
                self.store.finish(op['id'],'completed',{'large':'result'})
            self.store.finish(op['id'],'failed',error='Result cannot be stored; inspect quota')
        self.assertEqual(self.store.get(row['id'])['draft'],row['draft'])
        self.assertEqual(self.store.operations(row['id'])[0]['state'],'failed')

    def test_future_database_schema_is_not_silently_modified(self):
        with self.store.connect() as db:db.execute('PRAGMA user_version=99')
        with self.assertRaisesRegex(ValueError,'database version'):WorkspaceStore(self.path)
        with self.store.connect() as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],99)

    def test_unserializable_or_large_input_does_not_create_workspace(self):
        for invalid in ({'n':float('nan')},{'text':'\ud800'}):
            with self.assertRaises(ValueError):self.store.create('bad',invalid)
        with patch.object(ws,'MAX_DOCUMENT_BYTES',8):
            with self.assertRaises(ValueError):self.store.create('large',{'source':'long input'})
        self.assertEqual(self.store.list(),[])

    def test_result_replacement_counts_only_growth_and_failure_keeps_checkpoint(self):
        row=self.store.create('Shop',{})
        op,_=self.store.begin(row['id'],1,'quota','query',{})
        evidence={'evidence':'already saved'}
        self.store.checkpoint(op['id'],evidence)
        limit=sum(len(ws.encode(x).encode()) for x in ({},{},evidence))
        with patch.object(ws,'MAX_STORED_BYTES',limit):
            self.store.checkpoint(op['id'],evidence)
            with self.assertRaisesRegex(ValueError,'storage limit'):
                self.store.checkpoint(op['id'],{'evidence':'larger than the previous committed checkpoint'})
            self.store.finish(op['id'],'completed',evidence)
        op2,_=self.store.begin(row['id'],1,'quota2','query',{})
        self.store.checkpoint(op2['id'],evidence)
        with patch.object(ws,'MAX_STORED_BYTES',1):
            self.store.fail_preserving_checkpoint(op2['id'],'Latest trace not saved')
        saved=next(x for x in self.store.operations(row['id']) if x['id']==op2['id'])
        self.assertEqual(saved['state'],'failed')
        self.assertEqual(saved['result'],evidence)
        with self.assertRaisesRegex(ValueError,'terminal'):
            self.store.fail_preserving_checkpoint(op2['id'],'Do not overwrite terminal state')
