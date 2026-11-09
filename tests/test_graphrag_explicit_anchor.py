import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from graphrag_explicit_anchor import resolve, LOCATOR, COUPON, ROW

Q = '제공된 자료 안에서 PP1 작업표 2행의 값은?'


def corpus(records=None):
    records = records if records is not None else [('arbitrary-id', 'PP1', 2)]
    nodes, chunks = [], []
    for nid, coupon, row in records:
        source = dict(coupon=coupon, sheet=coupon, excel_row=row, archive_path='original.xlsx')
        text = json.dumps(source, ensure_ascii=False)
        nodes.append(dict(node_id=nid, node_type='annotation', source=source, text=text))
        chunks.append(dict(chunk_id='chunk-' + nid, chunk_type='node', node_id=nid, text=text))
    return dict(nodes=nodes, edges=[], chunks=chunks)


def raw(value):
    return json.dumps(value, ensure_ascii=False).encode()


def sync(c):
    for node, chunk in zip(c['nodes'], c['chunks']):
        node['text'] = chunk['text'] = json.dumps(node['source'], ensure_ascii=False)
    return raw(c)


class AnchorTest(unittest.TestCase):
    def test_contract_patterns(self):
        c = json.loads(Path('research/refined-hybrid-1/explicit-anchor-contract-v1.json').read_text())
        self.assertEqual(LOCATOR.pattern, c['locator']['anchored_regex'])
        self.assertEqual(COUPON.pattern, c['locator']['extra_mention_detectors']['coupon'])
        self.assertEqual(ROW.pattern, c['locator']['extra_mention_detectors']['row'])
        self.assertEqual(set(resolve(Q, raw(corpus()))), set(c['output']))

    def test_identity_spans_hashes_and_no_mutation(self):
        c = corpus(); before = copy.deepcopy(c); b = raw(c) + b'\n'
        r = resolve(Q, b)
        self.assertEqual(r['status'], 'resolved_unique')
        self.assertEqual(r['candidate_node_ids'], ['arbitrary-id'])
        self.assertEqual(r['candidate_chunk_ids'], ['chunk-arbitrary-id'])
        self.assertEqual(r['matched_text'], '제공된 자료 안에서 PP1 작업표 2행')
        self.assertEqual(Q[r['matched_span_start']:r['matched_span_end']], r['matched_text'])
        self.assertEqual(r['question_sha256'], hashlib.sha256(Q.encode()).hexdigest())
        self.assertEqual(r['source_sha256'], hashlib.sha256(b).hexdigest())
        self.assertEqual(c, before)

    def test_unsupported_precedence(self):
        questions = ['', Q.replace('2행', '0행'), Q.replace('2행', '-2행'),
                     Q.replace('2행', '02행'), Q.replace(' 작업표 ', '  작업표 '),
                     Q + ' PP1', Q + ' xPP10y', Q + ' 0행', Q + ' -3 행',
                     Q + ' 3\n행', '다른 표현 ' + Q, Q + 'x' * 4096]
        for q in questions:
            with self.subTest(q=q[:60]):
                r = resolve(q, b'not JSON')
                self.assertEqual(r['status'], 'locator_unsupported')
                self.assertIsNone(r['matched_text'])
                self.assertEqual(r['candidate_node_ids'], [])

    def test_tails_and_pp10(self):
        for tail in ('을 제외하세요', '과 다른 기록을 비교하세요', ' 값 300은?', '🙂'):
            with self.subTest(tail=tail):
                self.assertEqual(resolve('제공된 자료 안에서 PP1 작업표 2행' + tail,
                                         raw(corpus()))['status'], 'resolved_unique')
        self.assertEqual(resolve(Q.replace('PP1', 'PP10'), raw(corpus()))['status'], 'source_not_found')
        self.assertEqual(resolve(Q.replace('PP1', 'PP10'), raw(corpus([('a', 'PP10', 2)])))['status'], 'resolved_unique')

    def test_ambiguous_order_and_not_found(self):
        r = resolve(Q, raw(corpus([('z', 'PP1', 2), ('a', 'PP1', 2)])))
        self.assertEqual(r['status'], 'source_ambiguous')
        self.assertEqual(r['candidate_node_ids'], ['a', 'z'])
        self.assertEqual([x['node_id'] for x in r['source_locators']], ['a', 'z'])
        self.assertEqual(resolve(Q, raw(corpus([])))['status'], 'source_not_found')

    def test_invalid_metadata_including_unrelated(self):
        for key, value in [('excel_row', True), ('excel_row', 0), ('excel_row', 2.0),
                           ('coupon', 'PP0'), ('sheet', ''), ('archive_path', None)]:
            with self.subTest(key=key, value=value):
                c = corpus([('a', 'PP1', 2), ('b', 'PP2', 9)])
                c['nodes'][1]['source'][key] = value
                self.assertEqual(resolve(Q, sync(c))['status'], 'source_invalid')
        c = corpus(); del c['nodes'][0]['source']['excel_row']
        self.assertEqual(resolve(Q, sync(c))['status'], 'source_invalid')

    def test_invalid_source_and_nonannotation(self):
        for b in (b'{}', b'[]', b'\xff', b'{"nodes":[],"nodes":[]}', b'{"x":NaN}'):
            with self.subTest(b=b):
                r = resolve(Q, b)
                self.assertEqual(r['status'], 'source_invalid')
                self.assertIsNotNone(r['matched_text'])
        c = corpus(); c['nodes'][0]['node_type'] = 'dictionary'; c['nodes'][0]['source'] = {}
        self.assertEqual(resolve(Q, sync(c))['status'], 'source_not_found')
        c['chunks'] = []
        self.assertEqual(resolve(Q, raw(c))['status'], 'source_invalid')

    def test_invalid_caller(self):
        for q, b in [(None, b'{}'), (Q, '{}'), ('\ud800', b'{}')]:
            with self.subTest(q=repr(q)):
                with self.assertRaises((TypeError, UnicodeError)):
                    resolve(q, b)


if __name__ == '__main__':
    unittest.main()
