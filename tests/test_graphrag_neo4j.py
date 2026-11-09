import unittest
from scripts.graphrag_neo4j import Neo4jSource

class AdapterTests(unittest.TestCase):
    def test_endpoint_boundary(self):
        for endpoint in ['https://remote:7474','http://localhost:7474','http://127.0.0.1:0','http://127.0.0.1:65536','http://127.0.0.1:7474/path']:
            with self.assertRaises(ValueError):Neo4jSource(endpoint,'run')
    def test_parameterized_frontier(self):
        db=Neo4jSource('http://127.0.0.1:17474','run');calls=[]
        db.query=lambda statement,**params:calls.append((statement,params)) or []
        attack="id' RETURN 1 //"
        db.outgoing(['B',attack,'B'])
        self.assertNotIn(attack,calls[0][0]);self.assertEqual(calls[0][1]['starts'],sorted(['B',attack]))
    def test_reject_populated_namespace(self):
        from tests.test_graphrag_expand import fixture
        db=Neo4jSource('http://127.0.0.1:17474','run');calls=[]
        db.query=lambda statement,**params:calls.append(statement) or [{'count':1}]
        with self.assertRaises(ValueError):db.load(fixture())
        self.assertEqual(len(calls),1)
