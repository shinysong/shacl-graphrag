"""Invented fixture conversion checks; no server or experimental benchmark."""
import json
import unittest

from rdflib import RDF, XSD, Graph, Literal, URIRef

from scripts import check_gleif_cypher as n


class CypherTests(unittest.TestCase):
    def setUp(self):
        ids = ['A' * 18 + '01', 'B' * 18 + '02', 'C' * 18 + '03']
        self.dataset = {'entities': {x: {'lei': x, 'name': 'Fixture ' + x[0]} for x in ids}}
        self.parent = {'lei': ids[0], 'kind': 'parent', 'parent': ids[1], 'split': 'development'}
        self.exception = {'lei': ids[0], 'kind': 'exception', 'reason': 'NON_CONSOLIDATING', 'split': 'development'}
        self.subject = n.c.LEI[ids[0]]

    def simulated_rows(self, source):
        nodes, edges = n.to_lpg(source)
        selected = {str(self.subject)} | {e['o'] for e in edges if e['s'] == str(self.subject)}
        return [{**node, 'labels': ['GleifParity', *node['labels']],
                 'properties': {**node['properties'], 'id': node['id'], 'run_id': 'fixture'},
                 'parents': [e['o'] for e in edges if e['s'] == node['id']]}
                for node in nodes if node['id'] in selected]

    def test_all_variant_conversion_and_same_omissions(self):
        config = json.loads((n.c.FIX / 'config.json').read_text())
        for item in (self.parent, self.exception):
            for variant in config[item['kind'] + '_variants']:
                with self.subTest(variant=variant, kind=item['kind']):
                    source = n.c.build_case(self.dataset, item, variant)
                    expected = n.c.omit(n.c.old.retrieve(source, self.subject), self.subject, variant)
                    actual = n.c.omit(n.from_rows(self.simulated_rows(source)), self.subject, variant)
                    self.assertEqual(n.c.canonical(expected), n.c.canonical(actual))
                    self.assertEqual(n.digest(n.c.canonical(expected)), n.digest(n.c.canonical(actual)))

    def test_literal_multiplicity_datatype_language_and_lexical_form(self):
        graph = n.c.build_case(self.dataset, self.parent, 'clean')
        for literal in (Literal('법인', lang='ko'), Literal('corporation', lang='en'),
                        Literal('007', datatype=XSD.integer, normalize=False), Literal('plain')):
            graph.add((self.subject, n.c.EX.annotation, literal))
        actual = n.from_rows(self.simulated_rows(graph))
        self.assertEqual(n.c.canonical(graph), n.c.canonical(actual))
        nodes, edges = n.to_lpg(graph)
        self.assertEqual(len(edges), 1)
        self.assertTrue(all(isinstance(v, str) for node in nodes for v in node['properties'].values()))

    def test_mapping_rejects_unsupported_semantics(self):
        for triple in ((self.subject, RDF.type, n.c.EX.Unsupported),
                       (self.subject, n.c.EX.otherEdge, URIRef('urn:target'))):
            graph = Graph()
            graph.add(triple)
            with self.assertRaises(ValueError):
                n.to_lpg(graph)

    def test_local_only_no_redirect_target_or_userinfo(self):
        self.assertEqual(n.local_endpoint('http://127.0.0.1:17474'), 'http://127.0.0.1:17474/db/neo4j/tx/commit')
        for endpoint in ('https://127.0.0.1:7474', 'http://localhost:7474', 'http://example.com:7474',
                         'http://127.0.0.1:7474/path', 'http://user@127.0.0.1:7474',
                         'http://127.0.0.1:0', 'http://127.0.0.1:65536', 'http://127.0.0.1:7474?x=1'):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                n.local_endpoint(endpoint)

    def test_reserved_or_mixed_cohort_rejected(self):
        self.assertEqual(n.development_only({'cohort': [self.parent]}), [self.parent])
        for cohort in ([], [dict(self.parent, split='reserved')],
                       [self.parent, dict(self.exception, split='evaluation')]):
            with self.assertRaises(ValueError):
                n.development_only({'cohort': cohort})

    def test_queries_are_parameterized_and_cleanup_scoped(self):
        self.assertIn('$subject', n.QUERY)
        for query in (n.CREATE_NODES, n.CREATE_EDGES, n.QUERY, n.CLEANUP):
            self.assertIn('$run_id', query)
        self.assertEqual(n.CLEANUP, 'MATCH (n:GleifParity {run_id: $run_id}) DETACH DELETE n')


if __name__ == '__main__':
    unittest.main()
