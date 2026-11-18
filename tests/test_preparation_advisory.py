"""Authored development cases, not a representative extraction benchmark."""
import unittest
from apps.factory_lab import preparation as p
from apps.factory_lab.preparation_advisory import AdvisoryGenerator
from tests.test_preparation import example

class AdvisoryTests(unittest.TestCase):
    def draft(self,files):return p.create(files,example()[1],generator=AdvisoryGenerator())
    def test_nonstandard_names_use_table_context_without_approval(self):
        d=self.draft([{'name':'export_001.csv','content':'주문번호,주문상태,쿠폰번호,요청도착일\nO1,unshipped,C1,2026-11-17\n'},
                      {'name':'export_002.csv','content':'주문항목번호,order_no,옵션번호,수량\nI1,O1,S1,2\n'}])
        mappings={e['source']['file']+':'+e['source']['column']:e for e in d['entries'] if e['kind']=='mapping'}
        self.assertEqual(mappings['export_001.csv:주문번호']['target'],'orders.id')
        self.assertEqual(mappings['export_002.csv:order_no']['target'],'items.order')
        self.assertTrue(all(e['status']=='pending' for e in d['entries']))
        self.assertTrue(any(e['kind']=='relation' for e in d['entries']))
        self.assertEqual(p.restore_draft(d)['entries'],d['entries'])

    def test_similar_name_and_ambiguous_context_remain_unresolved(self):
        d=self.draft([{'name':'unknown.csv','content':'order_no,sku_id,refund_order_no\nO1,S1,R1\n'}])
        maps=[e for e in d['entries'] if e['kind']=='mapping']
        self.assertTrue(all(e['target']=='' for e in maps))
        refund=next(e for e in maps if e['source']['column']=='refund_order_no')
        self.assertEqual(refund['extraction']['candidates'],[])
        self.assertTrue(refund['extraction']['questions'])

    def test_policy_questions_surface_missing_basis_dates_and_exceptions(self):
        d=self.draft([{'name':'policy.md','content':'무료배송은 5만원 이상.\n\n쿠폰은 할인 전 3만원 이상. 단, 일부 상품 제외.'}])
        entries=d['entries']
        self.assertTrue(any('할인 후' in q for q in entries[0]['extraction']['questions']))
        self.assertTrue(any('언제부터' in q for q in entries[0]['extraction']['questions']))
        self.assertTrue(any('예외' in q for q in entries[1]['extraction']['questions']))
        self.assertTrue(all(e['status']=='pending' for e in entries))
        self.assertEqual(p.restore_draft(d)['entries'],d['entries'])

    def test_policy_differences_have_source_links_without_precedence_decision(self):
        d=self.draft([{'name':'old.md','content':'무료배송은 할인 전 5만원 이상. 2026-10-01부터 적용.'},
                      {'name':'new.md','content':'무료배송은 할인 후 7만원 이상. 2026-11-01부터 적용.'}])
        for e in d['entries']:
            refs=e['extraction']['related_policy_statements']
            self.assertEqual(len(refs),1)
            self.assertEqual(e['extraction']['related_policy_count'],1)
            self.assertIn('basis',refs[0]['different_fields'])
            self.assertIn('effective_dates',refs[0]['different_fields'])
            source=next(s for s in d['sources'] if s['name']==refs[0]['file'])
            self.assertEqual(refs[0]['sha256'],source['sha256'])
            self.assertEqual(e['status'],'pending')
        self.assertEqual(p.restore_draft(d)['entries'],d['entries'])

    def test_policy_comparisons_bound_display_without_losing_denominator(self):
        content='\n\n'.join(f'무료배송은 할인 전 {n}만원 이상.' for n in range(1,11))
        d=self.draft([{'name':'policies.md','content':content}])
        for e in d['entries']:
            self.assertEqual(e['extraction']['related_policy_count'],9)
            self.assertEqual(len(e['extraction']['related_policy_statements']),8)
