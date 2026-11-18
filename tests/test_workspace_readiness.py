"""Preparation navigation checks, not eligibility or model quality."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from apps.factory_lab import workspace_readiness as readiness
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_workspace_stock import prepared
from tests.workspace_fixtures import compared, approved


class ReadinessTests(unittest.TestCase):
    def test_partial_stock_independent_and_report_readonly(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=WorkspaceService(Path(tmp)/'db');row=prepared(service)
            before=deepcopy(row['draft']);report=row['task_readiness']
            self.assertEqual(report['capabilities']['stock_check'],1)
            self.assertEqual(report['capabilities']['source_rows'],2)
            self.assertTrue(any(i['code']=='currency' for i in report['replacement']['issues']))
            self.assertTrue(any(i['code']=='pending' for i in report['replacement']['issues']))
            self.assertFalse(any(i['subject'].startswith('cases.') for i in report['replacement']['issues']))
            self.assertEqual(readiness.describe(before),report)
            self.assertEqual(service.store.get(row['id'])['draft'],before)
            entry=next(e for e in before['entries'] if e['target']=='skus.available')
            updated=service.handle({'action':'change','id':row['id'],'revision':row['revision'],'decisions':[{'entry_id':entry['id'],'status':'excluded','target':entry['target'],'note':'Withdraw','interpretation':entry['interpretation']}]})
            self.assertEqual(updated['task_readiness']['capabilities']['stock_check'],0)
            self.assertEqual(service.view(row['id'],row['revision'])['task_readiness'],report)

    def test_full_setup_is_not_execution_approval(self):
        draft=compared(approved());report=readiness.describe(draft)['replacement']
        self.assertEqual(report['state'],'execution_checks_remaining',report)
        self.assertIn('source value types',report['unchecked'])
        duplicate=deepcopy(next(e for e in draft['entries'] if e['kind']=='mapping' and e['target']=='skus.id'))
        duplicate['id']='diagnostic-duplicate';draft['entries'].append(duplicate)
        report=readiness.describe(draft)['replacement']
        self.assertTrue(any(i['code']=='field_multiple' and i['subject']=='skus.id' for i in report['issues']))
        self.assertTrue(any(i['code']=='policy_agreement' for i in report['issues']))
