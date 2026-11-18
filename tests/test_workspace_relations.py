"""Authored one-hop comparison cases, not a semantic-join benchmark."""
import unittest
from copy import deepcopy
from apps.factory_lab import preparation as p, workspace_relations as relations
from apps.factory_lab.preparation_advisory import AdvisoryGenerator


def fixture():
    draft=p.create([{'name':'orders.csv','content':'order_id,status,private\nA,paid,secret\nB,paid,secret\n'},
                    {'name':'lines.csv','content':'order_id,sku\nA,S1\nA,S2\nC,S3\n,missing\n'}],
                   {'snapshot_id':'relation-test','as_of':'2026-11-17','currency':'GBP'},generator=AdvisoryGenerator())
    for e in list(draft['entries']):
        if e['kind']=='mapping' and e['source']['column']!='private':
            draft=p.change(draft,e['id'],'approved','source_only','', 'Original column for exact lookup')
    entry=next(e for e in draft['entries'] if e['kind']=='relation' and e['source']['file']=='lines.csv' and e['target']['file']=='orders.csv')
    draft=p.change(draft,entry['id'],'approved',entry['target'],'','Line order reference to order export; inspect duplicates')
    return draft,entry['id']


class RelationTests(unittest.TestCase):
    def test_duplicates_missing_and_provenance(self):
        draft,rid=fixture();before=deepcopy(draft)
        result=relations.execute(draft,{'relation_id':rid,'value':'A'})
        self.assertEqual(result['record_counts'],{'source':2,'target':1})
        self.assertEqual(result['matching_pair_count'],2)
        self.assertEqual([r['values']['sku'] for r in result['sides']['source']['records']],['S1','S2'])
        self.assertNotIn('secret',str(result));self.assertEqual(draft,before)
        self.assertEqual(result['sides']['source']['records'][0]['source']['line_start'],2)
        missing=relations.execute(draft,{'relation_id':rid,'value':'C'})
        self.assertEqual(missing['status'],'missing_on_selected_side')
        self.assertEqual(missing['record_counts'],{'source':1,'target':0})
        self.assertEqual(relations.execute(p.restore_draft(draft),{'relation_id':rid,'value':'A'}),result)

    def test_review_and_nonblank_requirements(self):
        draft,rid=fixture()
        for value in ('',' ',None):
            with self.assertRaises(ValueError):relations.execute(draft,{'relation_id':rid,'value':value})
        entry=next(e for e in draft['entries'] if e['id']==rid)
        withdrawn=p.change(draft,rid,'excluded',entry['target'],'Do not use','')
        with self.assertRaises(ValueError):relations.execute(withdrawn,{'relation_id':rid,'value':'A'})
        missing_meaning=p.change(draft,rid,'approved',entry['target'],'','')
        self.assertEqual(relations.catalog(missing_meaning),[])
        endpoint=next(e for e in draft['entries'] if e['kind']=='mapping' and e['source']['file']=='lines.csv' and e['source']['column']=='order_id')
        withdrawn=p.change(draft,endpoint['id'],'excluded',endpoint['target'],'Withdraw',endpoint['interpretation'])
        with self.assertRaises(ValueError):relations.execute(withdrawn,{'relation_id':rid,'value':'A'})

    def test_direct_service_replay_revocation_and_no_auto_execution(self):
        import tempfile
        from pathlib import Path
        from apps.factory_lab.workspace_service import WorkspaceService
        with tempfile.TemporaryDirectory() as tmp:
            draft,rid=fixture();path=Path(tmp)/'db';service=WorkspaceService(path)
            row=service.store.create('Comparison',draft);view=service.view(row['id'])
            self.assertEqual(view['operations'],[])
            self.assertEqual(len(view['relation_catalog']),1)
            request={'action':'lookup','id':row['id'],'revision':1,'request_key':'compare','selection':{'relation_id':rid,'value':'A'}}
            op=service.handle(request)['operation'];self.assertEqual(op['state'],'completed',op.get('error'))
            self.assertEqual(op['result']['record_counts'],{'source':2,'target':1})
            self.assertEqual(WorkspaceService(path).handle(request)['operation']['result'],op['result'])
            entry=next(e for e in draft['entries'] if e['id']==rid)
            service.handle({'action':'change','id':row['id'],'revision':1,'decisions':[{'entry_id':rid,'status':'excluded','target':entry['target'],'interpretation':entry['interpretation'],'note':'Withdraw'}]})
            failed=service.handle({**request,'revision':2,'request_key':'new'})['operation']
            self.assertEqual(failed['state'],'failed')
            self.assertEqual(service.handle(request)['operation']['result'],op['result'])
