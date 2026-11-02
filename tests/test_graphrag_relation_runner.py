import unittest
from tests.test_graphrag_expand import fixture
from tests.test_graphrag_relation_pack import seed
from scripts.graphrag_relation_pack import relation_pack
from scripts.run_graphrag_relations import accounting

class RunnerControls(unittest.TestCase):
    def test_no_refill_after_first_eight_skip(self):
        s=fixture();b=seed(s,['node:A','node:B','node:C','node:D'])
        full=relation_pack(s,b,lambda t:1)
        excluded=full['candidate_chunk_ids'][8:]
        self.assertTrue(excluded)
        # node:E is candidate8, so it can be skipped without invalidating B input.
        skip=full['eligible_chunk_ids'][-1]
        self.assertNotIn(skip,b['selected_chunk_ids'])
        r=relation_pack(s,b,lambda t:5000 if skip in t else 1)
        self.assertEqual(r['status'],'ok');self.assertIn(skip,r['skipped_budget_ids'])
        self.assertFalse(set(excluded)&set(r['selected_chunk_ids']))
        self.assertEqual(accounting(b,r)['first8_excluded_ids'],excluded)

    def test_later_seed_displacement(self):
        s=fixture();b=seed(s,['edge:1','edge:3','edge:6','edge:7'])
        r=relation_pack(s,b,lambda t:1)
        self.assertEqual(r['status'],'ok')
        self.assertIn('edge:7',accounting(b,r)['displaced_seed_ids'])
        self.assertNotIn('edge:7',r['selected_chunk_ids'])

    def test_failed_expansion_not_first8_exclusion(self):
        r=dict(status='budget_error',candidate_chunk_ids=['a'],eligible_chunk_ids=[],selected_chunk_ids=[])
        self.assertEqual(accounting({'selected_chunk_ids':['a']},r),dict(displaced_seed_ids=['a'],first8_excluded_ids=[],candidate_selection_reached=False))
