"""Observation currency is declared metadata, not implicit KRW or conversion."""
import tempfile
import unittest
from pathlib import Path
from apps.factory_lab import preparation as p
from apps.factory_lab.workspace_service import WorkspaceService
from tests.test_preparation import approved, example

class WorkspaceCurrencyTests(unittest.TestCase):
    def test_non_krw_observation_restore_lookup_and_decision_boundary(self):
        for currency in ('GBP','USD','unknown','mixed','not_applicable'):
            with self.subTest(currency=currency), tempfile.TemporaryDirectory() as directory:
                service=WorkspaceService(Path(directory)/'db.sqlite')
                _,metadata=example();metadata={**metadata,'currency':currency}
                draft=p.create([{'name':'merchant.csv','content':'InvoiceNo,Amount\nA1,12.50\nA1,9.99\n'},
                                {'name':'policy.md','content':'No operational policy supplied.'}],metadata)
                entry=next(e for e in draft['entries'] if e['kind']=='mapping' and e['source']['column']=='InvoiceNo')
                draft=p.change(draft,entry['id'],'approved','orders.id')
                restored=p.restore_draft(draft)
                self.assertEqual(restored['metadata']['currency'],currency)
                row=service.store.create('Merchant',restored)
                result=service.handle({'action':'lookup','id':row['id'],'revision':1,'request_key':'lookup',
                                       'selection':{'table':'orders','identifier':'A1'}})['operation']['result']
                self.assertEqual(result['metadata']['currency'],currency)
                self.assertEqual(len(result['records']),2)
                with self.assertRaisesRegex(ValueError,'KRW only'):p.materialize(restored)

    def test_currency_correction_versions_and_invalidates_approvals(self):
        draft=approved();files=[{'name':s['name'],'content':s['content']} for s in draft['sources']]
        refreshed=p.refresh(draft,files,metadata={**draft['metadata'],'currency':'GBP'})
        self.assertTrue(all(e['status']=='pending' for e in refreshed['entries']))
        self.assertEqual(refreshed['sources'],draft['sources'])
        self.assertEqual(p.restore_draft(refreshed)['metadata']['currency'],'GBP')
        for bad in ('gbp','',None,123,'GBP<script>'):
            with self.assertRaises(ValueError):p.create(files,{**draft['metadata'],'currency':bad})
