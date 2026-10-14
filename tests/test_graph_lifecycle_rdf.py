import copy
import unittest

from scripts import verify_graph_lifecycle_rdf as rdf


class LifecycleRdfTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {'nodes': [{'id': i, 'kind': k} for i, k in
                                  [('p', 'Product'), ('s', 'Supplier'), ('r', 'Region'), ('c', 'Country')]],
                         'edges': [dict(id='a', s='p', t='s', kind='SUPPLIED_BY', role='backup'),
                                   dict(id='b', s='s', t='r', kind='LOCATED_IN', role=None),
                                   dict(id='d', s='r', t='c', kind='IN_COUNTRY', role=None)]}

    def test_rule_scope_and_edge_evidence(self):
        graph = rdf.as_rdf(self.snapshot)
        self.assertEqual(rdf.query(graph, 'p', ['primary']), {'countries': [], 'paths': []})
        answer = rdf.query(graph, 'p', ['primary', 'backup'])
        self.assertEqual(answer, {'countries': ['c'], 'paths': [dict(product='p', supplier='s', region='r', country='c', role='backup', supply_edge='a', location_edge='b', country_edge='d')]})
        self.assertEqual(rdf.query(graph, 'missing', ['backup'])['countries'], [])

    def test_removed_relation_and_type_do_not_leak(self):
        missing = copy.deepcopy(self.snapshot)
        missing['edges'] = missing['edges'][:-1]
        self.assertEqual(rdf.query(rdf.as_rdf(missing), 'p', ['backup'])['countries'], [])
        mistyped = copy.deepcopy(self.snapshot)
        mistyped['nodes'][-1]['kind'] = 'Region'
        self.assertEqual(rdf.query(rdf.as_rdf(mistyped), 'p', ['backup'])['countries'], [])

    def test_complete_matrix_rejects_omissions_duplicates_and_misbinding(self):
        from scripts.run_graph_lifecycle_study import plan_rows, CHECKPOINTS
        rows = plan_rows([100, 1000, 5000], 2)
        record = dict(sizes=[100, 1000, 5000], repeats=2, planned_rows=2880,
                      snapshots=[dict(size=n, repeat=r, checkpoint=c)
                                 for n in [100, 1000, 5000] for r in range(2) for c in CHECKPOINTS])
        snapshots, queries, identities = rdf.coverage(record, rows)
        self.assertEqual((snapshots, queries, len(identities)), (48, 960, 2880))
        for entries in ([], record['snapshots'][:-1], record['snapshots'] + record['snapshots'][:1]):
            with self.assertRaises(ValueError):
                rdf.coverage({**record, 'snapshots': entries}, rows)
        for entries in (rows[:-1], rows[:-1] + rows[:1], [{**rows[0], 'subject': 'unknown'}, *rows[1:]],
                        [{**rows[0], 'id': rows[1]['id']}, *rows[1:]]):
            with self.assertRaises(ValueError):
                rdf.coverage(record, entries)

    def test_identifier_roundtrip_and_role_rejection(self):
        name = 'p : / " 1'
        self.assertEqual(rdf.identifier(rdf.iri('entity', name), 'entity'), name)
        with self.assertRaises(ValueError):
            rdf.query(rdf.as_rdf(self.snapshot), 'p', ['invented'])


if __name__ == '__main__':
    unittest.main()
