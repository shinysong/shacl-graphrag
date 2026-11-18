"""Manual source relationships: persistence and invalidation, not model quality."""
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab import preparation as p
from apps.factory_lab.workspace_service import WorkspaceService


class ManualRelations(unittest.TestCase):
    def test_pending_replay_and_refresh(self):
        files=[{'name':'p.csv','content':'purchase_ref\nP-17\n'},
               {'name':'s.csv','content':'parent_purchase\nP-17\n'}]
        d=p.create(files,{'snapshot_id':'manual','as_of':'2026-11-17','currency':'GBP'})
        field=d['entries'][0]
        d=p.change(d,field['id'],'approved','source_only','','Purchase reference')
        before=p.digest(d)
        source={'file':'p.csv','column':'purchase_ref'};target={'file':'s.csv','column':'parent_purchase'}
        added=p.add_relation(d,source,target,'Shipment points to purchase')
        self.assertEqual(p.digest(d),before)
        relation=added['entries'][-1]
        self.assertEqual(relation['status'],'pending')
        self.assertEqual(added['entries'][:-1],d['entries'])
        self.assertEqual(p.restore_draft(added),added)
        approved=p.change(added,relation['id'],'approved',relation['target'],'','Purchase of shipment')
        self.assertEqual(p.refresh(approved,files)['entries'][-1]['status'],'approved')
        changed=p.refresh(approved,[files[0],{**files[1],'content':'parent_purchase\nP-18\n'}])
        self.assertEqual(changed['entries'][-1]['status'],'pending')
        self.assertEqual(changed['entries'][-1]['id'],relation['id'])
        self.assertEqual(p.restore_draft(changed),changed)
        removed=p.refresh(approved,files[:1]);self.assertFalse(any(e['kind']=='relation' for e in removed['entries']))
        for a,b,why in [(source,target,'duplicate'),(target,source,'reverse'),(source,source,'same'),(source,{'file':'s.csv','column':'absent'},'bad'),(source,target,'')]:
            with self.assertRaises(ValueError):p.add_relation(added,a,b,why)

    def test_retarget_identity_and_refresh_collisions(self):
        files=[{'name':'a.csv','content':'x,y\nA,B\n'},
               {'name':'b.csv','content':'z,w\nA,B\n'}]
        d=p.create(files,{'snapshot_id':'manual','as_of':'2026-11-17','currency':'GBP'})
        a={'file':'a.csv','column':'x'};b={'file':'b.csv','column':'z'}
        d=p.add_relation(d,a,b,'First');first=d['entries'][-1]['id']
        target={'file':'b.csv','column':'w','sha256':d['sources'][1]['sha256']}
        d=p.change(d,first,'pending',target)
        d=p.add_relation(d,a,b,'Second');second=d['entries'][-1]['id']
        self.assertNotEqual(first,second)
        d=p.change(d,second,'pending',target)
        refreshed=p.refresh(d,files)
        self.assertTrue({first,second}<={e['id'] for e in refreshed['entries']})
        self.assertEqual(p.restore_draft(refreshed),refreshed)
        d=p.change(d,first,'pending',{'file':'a.csv','column':'y','sha256':d['sources'][0]['sha256']})
        refreshed=p.refresh(d,files)
        self.assertTrue({first,second}<={e['id'] for e in refreshed['entries']})
        self.assertEqual(p.restore_draft(refreshed),refreshed)

    def test_service_restart_export_and_stale_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';service=WorkspaceService(path)
            view=service.handle({'action':'create','title':'Manual','domain':'commerce',
                'files':[{'name':'p.csv','content':'purchase_ref\nP-17\n'},{'name':'s.csv','content':'parent_purchase\nP-17\n'}],
                'metadata':{'snapshot_id':'manual','as_of':'2026-11-17','currency':'GBP'}})
            req={'action':'add_relation','id':view['id'],'revision':1,
                 'source':{'file':'p.csv','column':'purchase_ref'},'target':{'file':'s.csv','column':'parent_purchase'},'reason':'Purchase reference'}
            result=service.handle(req)
            self.assertEqual(result['revision'],2);self.assertEqual(result['relation_catalog'],[])
            restarted=WorkspaceService(path)
            self.assertEqual(restarted.view(view['id'])['draft'],result['draft'])
            with self.assertRaises(ValueError):restarted.handle(req)
            bundle=restarted.handle({'action':'export','id':view['id'],'revision':2})
            imported=restarted.handle({'action':'import','title':'Imported','bundle':bundle})
            self.assertEqual(imported['draft'],result['draft']);self.assertEqual(imported['operations'],[])
