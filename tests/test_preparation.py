"""Development fixtures exercise review state, not automatic semantic accuracy."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from apps.factory_lab import preparation as p

ROOT = Path(__file__).resolve().parents[1]


def example():
    directory = ROOT/'examples/data_preparation/commerce'
    files = [{'name':f.name,'content':f.read_bytes().decode('utf-8')}
             for f in sorted(directory.iterdir()) if f.suffix in ('.csv','.md')]
    metadata = json.loads((directory/'snapshot.json').read_text())
    metadata.pop('schema_version')
    return files, metadata


def approved():
    d = p.create(*example())
    for entry in list(d['entries']):
        target = entry['target']
        if entry['kind']=='mapping':
            d = p.change(d,entry['id'],'approved',target)
        elif entry['kind']=='relation':
            # Values alone are not declared relationships; commerce checks explicit refs.
            d = p.change(d,entry['id'],'excluded',target,'Candidate inspected; no additional join requested')
        else:
            d = p.change(d,entry['id'],'approved',target or 'context',
                         interpretation=p.POLICIES[target]['meaning'] if target else 'Authored fixture title/effective date only')
    return d


class PreparationCapacityTests(unittest.TestCase):
    def test_mapping_entry_limit_before_relation_generation(self):
        headers = ','.join(f'field{i}' for i in range(64))
        files = [{'name':f't{i}.csv','content':headers+'\n'} for i in range(17)]
        with self.assertRaisesRegex(ValueError, '1024 review entries'):
            p.create(files, example()[1])


class PreparationTests(unittest.TestCase):
    def test_factory_csv_bundle_executes_existing_selected_evidence_checker(self):
        from apps.factory_lab.preparation_service import PreparationService
        service=PreparationService()
        response=service.handle({'action':'example','adapter':'factory-csv-1'})
        d=response['draft']
        for entry in list(d['entries']):
            target=entry['target']
            if entry['kind']=='mapping':
                d=p.change(d,entry['id'],'approved',target)
            elif entry['kind']=='relation':
                d=p.change(d,entry['id'],'excluded',target,'Explicit links are supplied separately')
            else:
                d=p.change(d,entry['id'],'approved',target or 'context',interpretation=response['contracts'][target]['meaning'] if target else 'Fixture title')
        bundle=p.freeze(d)
        result=p.execute(bundle,'qualification')
        self.assertEqual(result['domain'],'factory')
        self.assertEqual(result['projection']['rows_after'],1)
        self.assertEqual(len(result['evidence']),2)
        self.assertEqual(result['preparation']['bundle_sha256'],bundle['sha256'])
        self.assertIn('LLM 답변이 아닙니다',result['answer'])

    def test_roundtrip_exact_source_and_existing_shop(self):
        d = approved()
        expected = json.loads((ROOT/'examples/commerce_lab/shop.json').read_text())
        self.assertEqual(p.materialize(d),expected)
        bundle = p.freeze(d)
        restored = p.restore(json.loads(json.dumps(bundle)))
        self.assertEqual(p.materialize(restored),expected)
        result = p.execute(bundle,'approval')
        self.assertEqual(result['preparation']['bundle_sha256'],bundle['sha256'])

    def test_pending_and_unsupported_cannot_execute(self):
        d = p.create(*example())
        with self.assertRaisesRegex(ValueError,'Unresolved'): p.freeze(d)
        e = next(e for e in d['entries'] if e['kind']=='policy')
        with self.assertRaises(ValueError): p.change(d,e['id'],'approved','unsupported',interpretation='Taxes')

    def test_changed_policy_invalidates_approvals(self):
        d = approved()
        files, _ = example()
        index = next(i for i,f in enumerate(files) if f['name']=='policies.md')
        files[index] = {**files[index], 'content':files[index]['content']+'\n새 정책은 별도 확인합니다.\n'}
        refreshed = p.refresh(d,files)
        self.assertTrue(all(e['status']=='pending' for e in refreshed['entries']))
        self.assertTrue(any('previous_decision' in e for e in refreshed['entries']))
        with self.assertRaises(ValueError): p.freeze(refreshed)
        self.assertEqual(p.refresh(d,example()[0])['entries'],d['entries'])

    def test_tampered_source_or_data_rejected(self):
        bundle = p.freeze(approved())
        altered = deepcopy(bundle)
        altered['payload']['data']['skus'][0]['price'] = 1
        with self.assertRaisesRegex(ValueError,'hash'): p.restore(altered)
        altered['sha256'] = p.digest(altered['payload'])
        with self.assertRaisesRegex(ValueError,'Materialized'): p.restore(altered)

    def test_missing_mapping_and_bad_boolean(self):
        d = approved()
        mapping = next(e for e in d['entries'] if e['kind']=='mapping' and e['target']=='skus.price')
        d = p.change(d,mapping['id'],'excluded',mapping['target'],'No usable price source')
        with self.assertRaisesRegex(ValueError,'required mappings'): p.freeze(d)
        with self.assertRaises(ValueError): p._convert('yes',bool)
        self.assertIsNone(p._convert('',(int,type(None))))

    def test_ambiguous_policy_keeps_missing_basis_and_exception(self):
        hint = p.policy_hint('5만 원 이상 무료배송. 단, 제주 지역은 제외. 2026-12-01부터 적용.')
        self.assertEqual(hint['basis'],'unresolved')
        self.assertEqual(hint['effective_dates'],['2026-12-01'])
        self.assertTrue(hint['exceptions'])
        self.assertEqual(hint['target'],'shipping')
        self.assertEqual(hint['scope_candidates'],['단, 제주 지역은 제외.'])
        self.assertEqual(p.policy_hint('무료배송입니다.')['scope_candidates'],[])

    def test_conflicting_or_future_policy_cannot_claim_supported_execution(self):
        for text in ['할인 후 5만 원 이상 무료배송.', '무료배송. 단, 제주 지역은 제외.', '2027-01-01부터 무료배송.']:
            with self.subTest(text=text):
                files,meta=example()
                files.append({'name':'new-policy.md','content':text})
                d=p.create(files,meta)
                entry=next(e for e in d['entries'] if e['source']['file']=='new-policy.md')
                with self.assertRaises(ValueError):
                    p.change(d,entry['id'],'approved','shipping',interpretation='Apply shipping')
