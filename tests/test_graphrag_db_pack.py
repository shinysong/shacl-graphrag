import unittest
from tests.test_graphrag_expand import fixture
from tests.test_graphrag_relation_pack import seed
from scripts.graphrag_expand import canonical,expand as original
from scripts.graphrag_db_expand import expand
from scripts.graphrag_db_pack import relation_pack
from scripts.graphrag_relation_pack import relation_pack as original_pack
class Fake:
    def outgoing(self,starts):
        return [dict(subject=e['subject'],edge_id=e['edge_id'],target=e['target'],chunk_id='edge:'+e['edge_id'],payload=canonical(e).decode()) for e in sorted(fixture()['edges'],key=lambda e:(e['subject'],e['edge_id'])) if e['subject'] in starts]
class Tests(unittest.TestCase):
    def test_cycles_order_and_caps(self):
        for depth in (0,1,3):
            for cap in (2,32):
                a=original(fixture(),['node:A','edge:4'],max_depth=depth,max_candidates=cap);b=expand(fixture(),['node:A','edge:4'],max_depth=depth,max_candidates=cap,db=Fake())
                self.assertEqual({k:v for k,v in a.items() if k!='backend'},{k:v for k,v in b.items() if k!='backend'})
    def test_packing_parity(self):
        s=fixture();b=seed(s,['edge:4']);a=original_pack(s,b,lambda t:len(t)//10+1);n=relation_pack(s,b,lambda t:len(t)//10+1,db=Fake())
        self.assertEqual({k:v for k,v in a.items() if k!='backend'},{k:v for k,v in n.items() if k!='backend'})
    def test_missing_db_edges_not_filled(self):
        db=Fake();db.outgoing=lambda starts:[]
        self.assertEqual(expand(fixture(),['node:A'],db=db)['selected_chunk_ids'],['node:A'])
    def test_duplicate_and_wrong_endpoint_rejected(self):
        for mode in ('duplicate','wrong'):
            db=Fake();rows=db.outgoing(['A'])
            if mode=='duplicate':rows+=rows
            else:rows[0]['target']='Z'
            db.outgoing=lambda starts:rows
            self.assertEqual(expand(fixture(),['node:A'],db=db)['status'],'retrieval_error')
