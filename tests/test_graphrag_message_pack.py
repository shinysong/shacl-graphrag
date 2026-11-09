import copy
import hashlib
import json
import unittest
from scripts.graphrag_message_pack import pack_base, base_messages
from scripts.graphrag_check import canonical_bytes


def source(texts):
    nodes, chunks = [], []
    for i,text in enumerate(texts):
        payload = {'value': text}; encoded=json.dumps(payload,ensure_ascii=False)
        nodes.append(dict(node_id=str(i), node_type='dictionary',source=payload,text=encoded))
        chunks.append(dict(chunk_id='c'+str(i),chunk_type='node',node_id=str(i),text=encoded))
    return dict(nodes=nodes,edges=[],chunks=chunks)


def evidence(serialized):
    return json.loads(json.loads(serialized)[1]['content'])['evidence']


class PackTest(unittest.TestCase):
    def test_token_boundary_and_continue(self):
        s=source(['large','small']); before=copy.deepcopy(s)
        def count(raw):
            e=evidence(raw)
            return 3073 if any('large' in c['text'] for c in e) else 3072
        r=pack_base('질문',['c0','c1'],s,count)
        self.assertEqual(r['status'],'ok'); self.assertEqual(r['selected_chunk_ids'],['c1'])
        self.assertEqual(r['skipped_budget_ids'],['c0']);self.assertEqual(r['base']['tokens'],3072)
        self.assertEqual(s,before);self.assertEqual(r['selected_chunks'],[s['chunks'][1]])
        self.assertEqual(r['base']['sha256'],hashlib.sha256(r['base']['serialized'].encode()).hexdigest())
        self.assertFalse(r['generator_ready'])

    def test_overhead_and_empty(self):
        s=source(['x'])
        self.assertEqual(pack_base('q',['c0'],s,lambda _:3073)['status'],'overhead_budget_error')
        self.assertEqual(pack_base('q',['c0'],s,lambda raw:3073 if evidence(raw) else 1)['status'],'evidence_budget_error')
        self.assertEqual(pack_base('q',[],s,lambda _:1)['status'],'evidence_budget_error')

    def test_utf8_byte_boundary(self):
        # Exact serialized-byte boundary independent of token counting.
        s=source(['x']);empty_len=len(canonical_bytes(base_messages('',s['chunks'])))
        q='가'+('a'*(48000-empty_len-3))
        r=pack_base(q,['c0'],s,lambda _:1)
        self.assertEqual(r['status'],'ok');self.assertEqual(r['base']['bytes'],48000)
        r=pack_base(q+'a',['c0'],s,lambda _:1)
        self.assertEqual(r['status'],'evidence_budget_error')

    def test_invalid_and_upstream(self):
        s=source(['x']*9)
        for ids in (['c0','c0'],['unknown'],['c'+str(i) for i in range(9)]):
            with self.subTest(ids=ids):
                self.assertEqual(pack_base('q',ids,s,lambda _:1)['status'],'input_error')
        self.assertEqual(pack_base(None,None,None,None,'failed')['status'],'upstream_error')
        def bad(raw):return True if evidence(raw) else 1
        r=pack_base('q',['c0'],s,bad);self.assertEqual(r['status'],'input_error');self.assertEqual(r['selected_chunks'],[])

    def test_message_shape_and_all_candidates(self):
        s=source(['x']*8);r=pack_base('원문',['c'+str(i) for i in range(8)],s,lambda _:1)
        self.assertEqual(len(r['selected_chunks']),8)
        user=json.loads(r['base']['messages'][1]['content'])
        self.assertEqual(user,dict(question='원문',evidence=s['chunks'],validation=None))
        self.assertEqual(r['base']['serialized'].encode(),canonical_bytes(r['base']['messages']))


if __name__=='__main__':unittest.main()
