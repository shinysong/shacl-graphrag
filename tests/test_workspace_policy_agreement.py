"""Human comparisons persist without becoming automatic truth checks."""
import unittest
from copy import deepcopy
from apps.factory_lab import preparation as p, policy_agreement as a
from apps.factory_lab.workspace_diff import decision_changes
from tests.test_preparation import example
from tests.test_preparation_history import review


class PolicyAgreementTests(unittest.TestCase):
    def setUp(self):
        files, metadata = example()
        self.draft = review(p.create(files, metadata))
        self.entry = next(e for e in self.draft['entries'] if e['kind']=='policy' and e['target']=='shipping')

    def record(self, decision='agrees', basis='before_discount'):
        return a.review(self.draft,self.entry['id'],a.status(self.draft,self.entry['id'])['binding'],
                        decision,basis,'Compared the source threshold, scope and before-discount calculation.')

    def test_replay_and_difference_preserve_human_judgment(self):
        result=self.record()
        restored=p.restore_draft(result)
        self.assertEqual(restored['entries'],result['entries'])
        self.assertEqual(a.status(restored,self.entry['id'])['state'],'agrees')
        self.assertEqual(result['sources'],self.draft['sources'])
        self.assertIn('agreement',decision_changes(self.draft,result)[0]['changed_fields'])
        changed=a.review(result,self.entry['id'],a.status(result,self.entry['id'])['binding'],
                         'discrepant','before_discount','Document and table values disagree; correction is still needed.')
        self.assertEqual(a.status(p.restore_draft(changed),self.entry['id'])['state'],'discrepant')
        self.assertEqual(changed['review_history'][-1]['agreement']['decision'],'agrees')

    def test_changed_mapping_or_interpretation_makes_record_stale(self):
        result=self.record()
        mapping=next(e for e in result['entries'] if e['target']=='shipping_policies.minimum')
        changed=p.change(result,mapping['id'],'pending',mapping['target'])
        self.assertEqual(a.status(p.restore_draft(changed),self.entry['id'])['state'],'stale')
        changed=p.change(result,self.entry['id'],'approved','shipping',interpretation='Different applicability scope')
        self.assertEqual(a.status(p.restore_draft(changed),self.entry['id'])['state'],'stale')
        with self.assertRaisesRegex(ValueError,'inputs changed'):
            a.review(changed,self.entry['id'],a.status(result,self.entry['id'])['binding'],
                     'agrees','before_discount','Attempt to reuse an obsolete screen.')

    def test_ambiguous_basis_and_pending_inputs_cannot_confirm(self):
        for basis in ('unresolved','after_discount','not_applicable'):
            with self.assertRaises(ValueError):self.record(basis=basis)
        self.assertEqual(a.status(self.record('unresolved','unresolved'),self.entry['id'])['state'],'unresolved')
        mapping=next(e for e in self.draft['entries'] if e['target']=='shipping_policies.minimum')
        self.draft=p.change(self.draft,mapping['id'],'pending',mapping['target'])
        with self.assertRaises(ValueError):self.record()

    def test_refresh_retains_old_comparison_as_history_not_current(self):
        result=self.record()
        files=[{'name':s['name'],'content':s['content']} for s in result['sources']]
        files.append({'name':'new-policy.md','content':'Additional policy scope remains under review.'})
        changed=p.refresh(result,files)
        entry=next(e for e in changed['entries'] if e['id']==self.entry['id'])
        self.assertNotIn('agreement',entry)
        self.assertEqual(entry['previous_decision']['agreement']['decision'],'agrees')
        self.assertEqual(p.restore_draft(changed)['entries'],changed['entries'])
        malformed=deepcopy(result)
        next(e for e in malformed['entries'] if e['id']==self.entry['id'])['agreement']['binding']='bad'
        with self.assertRaises(ValueError):p.restore_draft(malformed)

    def test_service_versioning_restart_export_and_obsolete_request(self):
        import tempfile
        from pathlib import Path
        from apps.factory_lab.workspace_service import WorkspaceService
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'work.sqlite'
            service=WorkspaceService(path)
            row=service.store.create('Policy review',self.draft)
            observed=service.view(row['id'])['policy_agreements'][self.entry['id']]
            request={'action':'compare_policy','id':row['id'],'revision':1,'entry_id':self.entry['id'],
                     'binding':observed['binding'],'decision':'discrepant','basis':'before_discount',
                     'rationale':'Document and table threshold differ; do not consider agreement resolved.'}
            result=service.handle(request)
            self.assertEqual(result['revision'],2)
            self.assertEqual(result['policy_agreements'][self.entry['id']]['state'],'discrepant')
            self.assertEqual(service.store.get(row['id'],1)['draft'],row['draft'])
            with self.assertRaises(ValueError):service.handle(request)
            reopened=WorkspaceService(path)
            self.assertEqual(reopened.view(row['id'])['policy_agreements'],result['policy_agreements'])
            bundle=reopened.handle({'action':'export','id':row['id'],'revision':2})
            imported=reopened.handle({'action':'import','title':'Imported comparison','bundle':bundle})
            self.assertEqual(imported['policy_agreements'],result['policy_agreements'])

    def test_guard_blocks_unreviewed_discrepant_and_stale_but_lookup_remains(self):
        from apps.factory_lab import workspace_policy, workspace_lookup
        from tests.workspace_fixtures import compared
        with self.assertRaisesRegex(ValueError,'agreement'):workspace_policy.require_ready(self.draft)
        result=compared(self.draft)
        workspace_policy.require_ready(result)
        result=a.review(result,self.entry['id'],a.status(result,self.entry['id'])['binding'],
                        'discrepant','before_discount','Document and CSV differ.')
        with self.assertRaisesRegex(ValueError,'discrepant'):workspace_policy.require_ready(result)
        observed=workspace_lookup.execute(result,{'table':'orders','identifier':'O1'})
        self.assertEqual(observed['mode'],'source_lookup')
        result=compared(self.draft)
        result=p.change(result,self.entry['id'],'approved','shipping',interpretation='Revised scope')
        with self.assertRaisesRegex(ValueError,'stale'):workspace_policy.require_ready(result)

    def test_alternate_reference_column_requires_new_scope_comparison(self):
        import csv, io
        from apps.factory_lab import workspace_policy, workspace_lookup
        from tests.workspace_fixtures import compared
        files,metadata=example()
        source=next(f for f in files if f['name']=='orders.csv')
        reader=csv.DictReader(io.StringIO(source['content']));rows=list(reader)
        output=io.StringIO();writer=csv.DictWriter(output,fieldnames=[*reader.fieldnames,'alternate_shipping'])
        writer.writeheader()
        for row in rows:writer.writerow({**row,'alternate_shipping':row['shipping_policy']})
        source['content']=output.getvalue()
        draft=p.create(files,metadata)
        for entry in list(draft['entries']):
            if entry['kind']=='mapping' and not entry['target']:
                draft=p.change(draft,entry['id'],'excluded','','Unused alternate column')
            elif entry['kind']=='relation':draft=p.change(draft,entry['id'],'excluded',entry['target'],'Candidate only')
            else:draft=p.change(draft,entry['id'],'approved',entry['target'] or 'context',interpretation='Authored fixture scope')
        draft=compared(draft)
        old=deepcopy(draft)
        shipping=next(e for e in draft['entries'] if e['kind']=='policy' and e['target']=='shipping')
        original=next(e for e in draft['entries'] if e['kind']=='mapping' and e['target']=='orders.shipping_policy')
        alternate=next(e for e in draft['entries'] if e['source'].get('column')=='alternate_shipping' and e['kind']=='mapping')
        draft=p.change(draft,original['id'],'excluded','','Replaced by alternate reference')
        draft=p.change(draft,alternate['id'],'approved','orders.shipping_policy')
        self.assertEqual(draft['sources'],old['sources'])
        self.assertEqual(p.materialize(draft),p.materialize(old))
        restored=p.restore_draft(draft)
        self.assertEqual(a.status(restored,shipping['id'])['state'],'stale')
        self.assertEqual(a.status(restored,shipping['id'])['record'],a.status(old,shipping['id'])['record'])
        with self.assertRaisesRegex(ValueError,'stale'):workspace_policy.require_ready(restored)
        self.assertEqual(workspace_lookup.execute(restored,{'table':'orders','identifier':'O1'})['mode'],'source_lookup')
        workspace_policy.require_ready(compared(restored))
        scope=a.status(restored,shipping['id'])['inputs']['scope_mappings']
        self.assertTrue(any(e['id']==alternate['id'] and e['target']=='orders.shipping_policy' for e in scope))
