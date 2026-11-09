import copy
import unittest
from scripts.graphrag_anchor_candidates import inject_anchor


class AnchorCandidatesTest(unittest.TestCase):
    def base(self, ids=None, status='ok'):
        return dict(upstream_status=status, ordered_candidate_ids=list('abcdefgh') if ids is None else ids, error=None)

    def loc(self, status='resolved_unique', ids=None):
        return dict(status=status, candidate_chunk_ids=['z'] if ids is None else ids)

    def test_new_anchor_displaces_last(self):
        r = inject_anchor(self.base(), self.loc())
        self.assertEqual(r['ordered_candidate_ids'], list('zabcdefg'))
        self.assertEqual(r['anchor_audit']['displaced_candidate_ids'], ['h'])
        self.assertEqual(r['anchor_audit']['added_candidate_ids'], ['z'])

    def test_existing_anchor_moves_without_loss(self):
        r = inject_anchor(self.base(), self.loc(ids=['e']))
        self.assertEqual(r['ordered_candidate_ids'], list('eabcdfgh'))
        self.assertEqual(r['anchor_audit']['displaced_candidate_ids'], [])

    def test_all_unresolved_keep_base(self):
        for status,ids in [('locator_unsupported', []),('source_not_found', []),('source_invalid', []),('source_ambiguous',['x','y'])]:
            with self.subTest(status=status):
                r=inject_anchor(self.base(), self.loc(status,ids))
                self.assertEqual(r['ordered_candidate_ids'],list('abcdefgh'))
                self.assertFalse(r['anchor_audit']['applied'])
                self.assertEqual(r['anchor_audit']['locator_status'],status)

    def test_failure_is_not_rescued(self):
        r=inject_anchor(self.base([], 'retrieval_failure'),self.loc())
        self.assertEqual(r['ordered_candidate_ids'],[])
        self.assertEqual(r['upstream_status'],'retrieval_failure')
        self.assertFalse(r['anchor_audit']['applied'])

    def test_empty_success_accepts_anchor(self):
        self.assertEqual(inject_anchor(self.base([]),self.loc())['ordered_candidate_ids'],['z'])

    def test_no_mutation_and_same_input_parity(self):
        b=self.base();l=self.loc();before=copy.deepcopy((b,l))
        a=inject_anchor(b,l);e=inject_anchor(b,l)
        self.assertEqual(a,e);self.assertEqual((b,l),before)
        a['anchor_audit']['original_candidate_ids'].append('new')
        self.assertEqual((b,l),before)

    def test_invalid_contracts(self):
        cases=[(self.base(['a','a']),self.loc()),(self.base(list('abcdefghi')),self.loc()),
               (self.base(),self.loc(ids=[])),(self.base(),self.loc('source_invalid',['x'])),
               (self.base(),self.loc('source_ambiguous',['x'])),(self.base(),self.loc('bogus',[]))]
        for b,l in cases:
            with self.subTest(base=b,locator=l),self.assertRaises(ValueError):inject_anchor(b,l)


if __name__=='__main__':unittest.main()
