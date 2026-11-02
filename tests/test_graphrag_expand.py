"""Software fixtures only; no question/reference-answer access."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from scripts.graphrag_expand import canonical, expand


def fixture():
    nodes = [{'node_id': n, 'text': json.dumps({'id': n, 'label': '한글'})}
             for n in 'ABCDEZ']
    edges = [{'edge_id': eid, 'subject': s, 'target': t}
             for eid, s, t in [('2', 'A', 'C'), ('1', 'A', 'B'),
                               ('4', 'B', 'D'), ('3', 'C', 'D'),
                               ('5', 'D', 'A'), ('6', 'D', 'E'), ('7', 'Z', 'A')]]
    chunks = [dict(chunk_id='node:' + n['node_id'], chunk_type='node', **n) for n in nodes]
    chunks += [dict(chunk_id='edge:' + e['edge_id'], chunk_type='edge',
                    edge_id=e['edge_id'], text=json.dumps(e)) for e in edges]
    return dict(nodes=nodes, edges=edges, chunks=chunks)


class ExpansionTests(unittest.TestCase):
    def test_ordered_bfs_parity_with_branch_cycle_and_no_inverse(self):
        expected = ['node:A', 'edge:1', 'node:B', 'edge:2', 'node:C',
                    'edge:4', 'node:D', 'edge:3', 'edge:5', 'edge:6', 'node:E']
        results = [expand(fixture(), ['node:A'], backend=b, max_depth=3)
                   for b in ('adjacency', 'sqlite')]
        for result in results:
            self.assertEqual(result['status'], 'ok')
            self.assertEqual(result['selected_chunk_ids'], expected)
            self.assertEqual(result['evidence_sha256'], hashlib.sha256(canonical(result['selected_chunks'])).hexdigest())
            self.assertEqual(result['evidence_bytes'], len(canonical(result['selected_chunks'])))
        self.assertEqual(results[0]['selected_chunks'], results[1]['selected_chunks'])
        self.assertEqual(results[0]['evidence_sha256'], results[1]['evidence_sha256'])

    def test_edge_seed_endpoints_before_expansion(self):
        for backend in ('adjacency', 'sqlite'):
            self.assertEqual(expand(fixture(), ['edge:4'], backend, max_depth=0)['selected_chunk_ids'],
                             ['edge:4', 'node:B', 'node:D'])
            self.assertEqual(expand(fixture(), ['edge:4'], backend)['selected_chunk_ids'],
                             ['edge:4', 'node:B', 'node:D', 'edge:5', 'node:A', 'edge:6', 'node:E'])

    def test_seed_order_and_duplicates(self):
        for backend in ('adjacency', 'sqlite'):
            r = expand(fixture(), ['node:C', 'node:A', 'node:C'], backend, max_depth=0)
            self.assertEqual(r['seed_chunk_ids'], ['node:C', 'node:A'])
            self.assertEqual(r['selected_chunk_ids'], r['seed_chunk_ids'])
            r = expand(fixture(), ['node:A', 'missing'], backend)
            self.assertEqual(r['status'], 'retrieval_error')
            self.assertEqual(r['candidate_chunk_ids'], ['node:A'])
            self.assertEqual(r['selected_chunks'], [])

    def test_budget_caps_preserve_candidates(self):
        for backend in ('adjacency', 'sqlite'):
            normal = expand(fixture(), ['node:A'], backend)
            for kwargs in ({'max_candidates': 4}, {'max_evidence_bytes': normal['evidence_bytes'] - 1}):
                r = expand(fixture(), ['node:A'], backend, **kwargs)
                self.assertEqual(r['status'], 'budget_error')
                self.assertEqual(r['candidate_chunk_ids'], normal['candidate_chunk_ids'])
                self.assertEqual(r['selected_chunks'], [])
                self.assertEqual(r['selected_chunk_ids'], [])
                self.assertEqual(r['evidence_bytes'], 2)
                self.assertEqual(r['evidence_sha256'], hashlib.sha256(b'[]').hexdigest())
            self.assertEqual(expand(fixture(), ['node:A'], backend,
                                   max_evidence_bytes=normal['evidence_bytes'], max_candidates=5)['status'], 'ok')

    def test_source_integrity_rejects_dangling_and_mismatched_records(self):
        cases = []
        c = fixture(); c['nodes'].pop(); cases.append(c)
        c = fixture(); c['chunks'].pop(); cases.append(c)
        c = fixture(); c['edges'][0]['target'] = 'unknown'; cases.append(c)
        c = fixture(); c['edges'].append(copy.deepcopy(c['edges'][0])); cases.append(c)
        c = fixture(); c['chunks'].append(copy.deepcopy(c['chunks'][0])); cases.append(c)
        c = fixture(); c['chunks'][-1]['text'] = '{}'; cases.append(c)
        c = fixture(); c['chunks'][0]['text'] = 'null'; cases.append(c)
        c = fixture(); c['nodes'][0]['text'] = '{}'; cases.append(c)
        for c in cases:
            for backend in ('adjacency', 'sqlite'):
                with self.subTest(backend=backend, case=cases.index(c)):
                    r = expand(c, ['node:A'], backend)
                    self.assertEqual(r['status'], 'retrieval_error')
                    self.assertEqual(r['selected_chunks'], [])

    def test_configuration_errors_and_empty_evidence(self):
        for kwargs in ({'max_depth': -1}, {'max_depth': 4}, {'max_depth': True},
                       {'max_candidates': 129}, {'max_candidates': 0},
                       {'max_evidence_bytes': -1}, {'backend': 'other'}):
            self.assertEqual(expand(fixture(), ['node:A'], **kwargs)['status'], 'retrieval_error')
        for seeds in ('node:A', [None], [{}]):
            self.assertEqual(expand(fixture(), seeds)['status'], 'retrieval_error')
        self.assertEqual(expand(fixture(), [])['selected_chunks'], [])
        self.assertEqual(expand(fixture(), [], max_evidence_bytes=1)['status'], 'budget_error')

    def test_no_input_mutation_or_python_file_network_reads(self):
        c = fixture(); original = copy.deepcopy(c)
        with patch('builtins.open', side_effect=AssertionError('file read')), \
             patch('socket.socket', side_effect=AssertionError('network')):
            for backend in ('adjacency', 'sqlite'):
                r = expand(c, ['node:A'], backend)
                self.assertEqual(r['status'], 'ok')
                r['selected_chunks'][0]['text'] = 'modified'
        self.assertEqual(c, original)


if __name__ == '__main__':
    unittest.main()
