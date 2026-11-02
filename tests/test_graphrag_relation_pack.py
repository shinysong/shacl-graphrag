import copy
import hashlib
import unittest
from tests.test_graphrag_expand import fixture
from scripts.graphrag_expand import canonical
from scripts.graphrag_relation_pack import relation_pack


def seed(source, ids):
    chunks={c['chunk_id']:c for c in source['chunks']}
    selected=[chunks[x] for x in ids];raw=canonical(selected)
    return dict(status='ok',selected_chunks=selected,selected_chunk_ids=ids,
                seed_chunk_ids=ids,evidence_bytes=len(raw),
                evidence_sha256=hashlib.sha256(raw).hexdigest())


class RelationPackingTests(unittest.TestCase):
    def test_parity_order_and_nonmutation(self):
        s=fixture(); b=seed(s,['edge:4']); before=copy.deepcopy((s,b))
        c=relation_pack(s,b,lambda t:len(t)//10+1)
        e=relation_pack(s,b,lambda t:len(t)//10+1,'sqlite')
        self.assertEqual(c['status'],'ok')
        self.assertEqual(c['selected_chunk_ids'],['edge:4','node:B','node:D','edge:5','node:A','edge:6','node:E'])
        for k in c:
            if k!='backend':self.assertEqual(c[k],e[k])
        self.assertEqual((s,b),before)

    def test_bad_seed_payload_ids_hash_and_upstream(self):
        s=fixture(); original=seed(s,['edge:4'])
        for field,value in [('seed_chunk_ids',['node:A']),('selected_chunk_ids',['node:A']),('evidence_sha256','bad'),('evidence_bytes',1),('status','failed')]:
            b=copy.deepcopy(original);b[field]=value
            self.assertEqual(relation_pack(s,b,lambda t:1)['status'],'retrieval_error')
        b=copy.deepcopy(original);b['selected_chunks'][0]['text']='{}'
        raw=canonical(b['selected_chunks']);b.update(evidence_bytes=len(raw),evidence_sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(relation_pack(s,b,lambda t:1)['status'],'retrieval_error')

    def test_first_eight_and_no_refill(self):
        s=fixture();b=seed(s,['node:A','node:B','node:C','node:D'])
        r=relation_pack(s,b,lambda t:1)
        self.assertGreater(len(r['candidate_chunk_ids']),8)
        self.assertEqual(r['eligible_chunk_ids'],r['candidate_chunk_ids'][:8])
        self.assertEqual(r['selected_chunk_ids'],r['eligible_chunk_ids'])

    def test_skip_oversize_continue(self):
        s=fixture();b=seed(s,['edge:4'])
        def count(t):
            return 5000 if 'node:B' in t else 1
        r=relation_pack(s,b,count)
        self.assertEqual(r['status'],'ok');self.assertIn('node:B',r['skipped_budget_ids'])
        self.assertNotIn('node:B',r['selected_chunk_ids']);self.assertIn('node:D',r['selected_chunk_ids'])

    def test_invalid_token_count(self):
        for n in (True,0,4097):
            self.assertEqual(relation_pack(fixture(),seed(fixture(),['node:A']),lambda t:n)['status'],'retrieval_error')

if __name__=='__main__':unittest.main()
