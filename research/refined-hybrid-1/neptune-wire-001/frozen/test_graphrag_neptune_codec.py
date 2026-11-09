"""Protocol fixtures only: these tests do not execute Neptune."""
import json
import unittest
from urllib.parse import parse_qs
from scripts.graphrag_neptune_codec import QUERY, MAX_BYTES, outgoing_request, outgoing_response


def row():
    edge = {'subject': 's', 'edge_id': 'e', 'target': 't'}
    return {**edge, 'chunk_id': 'edge:e', 'payload': json.dumps(edge)}


class NeptuneCodecTests(unittest.TestCase):
    def test_parameter_binding(self):
        unusual = "x' RETURN 1 // &한글"
        request = outgoing_request('test-run', [unusual, unusual])
        form = parse_qs(request['body'].decode())
        self.assertEqual(form['query'], [QUERY])
        self.assertNotIn(unusual, QUERY)
        self.assertEqual(json.loads(form['parameters'][0]), {'run':'test-run', 'starts':[unusual]})
        self.assertEqual(request['path'], '/openCypher')

    def test_empty_and_valid(self):
        self.assertEqual(outgoing_response(200, b'{"results":[]}', []), [])
        self.assertEqual(outgoing_response(200, json.dumps({'results':[row()]}).encode(), ['s']), [row()])

    def test_failed_or_malformed(self):
        for status, body in [(500,b'{}'),(200,b'{'),(200,b'{"results":[],"results":[]}'),
                             (200,b'{"results":[],"error":"failed"}'),(200,b'x'*(MAX_BYTES+1)),
                             (200,b'{"results":[null]}')]:
            with self.subTest(status=status, size=len(body)), self.assertRaises(ValueError):
                outgoing_response(status,body,['s'])

    def test_identity_and_duplicates(self):
        bad = row();bad['target'] = 'wrong'
        for rows, starts in [([bad],['s']),([row(),row()],['s']),([row()],['other'])]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                outgoing_response(200,json.dumps({'results':rows}).encode(),starts)

    def test_frontier_and_namespace(self):
        for ns, starts in [('bad namespace',[]),('ok',[None]),('ok',['x']*329),('ok','s')]:
            with self.subTest(ns=ns), self.assertRaises(ValueError):
                outgoing_request(ns,starts)

    def test_order(self):
        r=row();r['edge_id']='a';r['chunk_id']='edge:a';r['payload']=json.dumps({'subject':'s','edge_id':'a','target':'t'})
        with self.assertRaises(ValueError):
            outgoing_response(200,json.dumps({'results':[row(),r]}).encode(),['s'])
