import unittest
from scripts.backend_query_scope import dependency
from scripts.backend_inference import TYPE, SC, SP


class QueryDependencyTests(unittest.TestCase):
    def test_alternate_path_change_remains_visible(self):
        state = {'facts': [('x', TYPE, 'A')], 'schema': [('A', SC, 'B'), ('B', SC, 'R'), ('A', SC, 'R')]}
        query = {'kind': 'type', 'target': 'R'}
        before = dependency(state, query)
        after = dependency({**state, 'schema': state['schema'][:-1]}, query)
        self.assertEqual(before['facts'], after['facts'])
        self.assertNotEqual(before['schema'], after['schema'])

    def test_empty_query_and_new_matching_fact(self):
        state = {'facts': [], 'schema': [('A', SC, 'R')]}
        q = {'kind': 'type', 'target': 'R'}
        self.assertEqual(dependency(state, q)['schema'], [])
        self.assertNotEqual(dependency(state, q), dependency({**state, 'facts': [('x', TYPE, 'A')]}, q))

    def test_relation_anchor_and_cycles(self):
        state = {'facts': [('x', 'p', 'y'), ('other', 'p', 'z')], 'schema': [('p', SP, 'r'), ('r', SP, 'p')]}
        d = dependency(state, {'kind': 'relation', 'target': 'r', 'start': 'x'})
        self.assertEqual(d['facts'], [('x', 'p', 'y')])
        self.assertEqual(len(d['schema']), 2)
        with self.assertRaises(ValueError):
            dependency(state, {'kind': 'unsupported', 'target': 'r'})
