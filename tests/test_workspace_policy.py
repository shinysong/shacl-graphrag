"""Policy selection preserves sources and blocks ambiguous fixed-adapter execution."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from apps.factory_lab import preparation as p, workspace_policy as policy
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_preparation import example
from tests.test_preparation_history import review


class WorkspacePolicyTests(unittest.TestCase):
    def draft(self):
        files, metadata = example()
        document = next(f for f in files if f['name'].endswith('.md'))
        files.append({'name':'second-policy.md','content':document['content']})
        return review(p.create(files,metadata))

    def test_multiple_approvals_block_and_resolution_preserves_history(self):
        draft = self.draft()
        original = deepcopy(draft)
        groups = policy.groups(draft)
        self.assertTrue(groups)
        with self.assertRaisesRegex(ValueError,'applicable policy'):
            policy.require_unambiguous(draft)
        for group in groups:
            draft = policy.resolve(draft,group['target'],group['entries'][0]['id'],
                                   'Applies to this snapshot; other source is superseded.')
        policy.require_unambiguous(draft)
        self.assertEqual(draft['sources'],original['sources'])
        self.assertGreater(len(draft['review_history']),len(original['review_history']))
        restored=p.restore_draft(draft)
        self.assertEqual(restored['entries'],draft['entries'])
        for group in policy.groups(restored):
            self.assertEqual(sum(e['status']=='approved' for e in group['entries']),1)

    def test_service_failure_is_retained_and_selection_is_versioned(self):
        with tempfile.TemporaryDirectory() as directory:
            service=WorkspaceService(Path(directory)/'work.sqlite')
            row=service.store.create('Policies',self.draft())
            result=service.handle({'action':'execute','id':row['id'],'revision':1,
                                   'request_key':'ambiguous','case_id':'ready'})
            self.assertEqual(result['operation']['state'],'failed')
            group=service.view(row['id'])['policy_groups'][0]
            request={'action':'resolve_policy','id':row['id'],'revision':1,
                     'target':group['target'],'selected_id':group['entries'][0]['id'],
                     'rationale':'Reviewed current applicability and superseded source.'}
            for invalid in ({'rationale':''},{'selected_id':'missing'}):
                with self.assertRaises(ValueError):service.handle({**request,**invalid})
                self.assertEqual(service.store.get(row['id'])['revision'],1)
            updated=service.handle(request)
            self.assertEqual(updated['revision'],2)
            self.assertEqual(service.store.get(row['id'],1)['draft'],row['draft'])
            with self.assertRaises(ValueError):service.handle(request)
            self.assertEqual(len(service.store.operations(row['id'])),1)
