import copy,json,unittest
from pathlib import Path
from rdflib import Graph
from scripts.graphrag_shacl_binding import shacl_binding
from scripts.graphrag_check import canonical_bytes
import hashlib

def envelope(a,t=None):
    values=[a]+([t] if t else []);chunks=[dict(chunk_type='node',chunk_id='node:'+v['id'],node_id=v['id'],text=json.dumps(v)) for v in values];raw=canonical_bytes(chunks)
    return dict(status='ok',selected_chunks=chunks,selected_chunk_ids=[x['chunk_id'] for x in chunks],evidence_sha256=hashlib.sha256(raw).hexdigest(),evidence_bytes=len(raw))
def pair():
    a=dict(id='P:1',coupon='P',archive_path='book',sha256='hash',dictionary_refs={'defect':'P:d:1'},values={'defect':1})
    t=dict(id='P:d:1',coupon='P',archive_path='book',sha256='hash',code=1,sheet='defect_code')
    return a,t
class Tests(unittest.TestCase):
    def check(self,a,t,status,conforms):
        e=envelope(a,t);before=copy.deepcopy(e);r,_,_,_=shacl_binding(e,Graph().parse('research/refined-hybrid-1/shapes/binding-pairs.ttl'))
        self.assertTrue(r['parity']);self.assertEqual(r['results'][0]['status'],status);self.assertEqual(r['raw_conforms'],conforms);self.assertEqual(e,before)
    def test_pass_and_internally_consistent_false_input(self):
        a,t=pair();self.check(a,t,'pass',True);a['values']['defect']=999;t['code']=999;self.check(a,t,'pass',True)
    def test_missing_target(self):
        a,t=pair();self.check(a,None,'unknown',False)
    def test_missing_and_conflict_precedence(self):
        a,t=pair();del t['sha256'];self.check(a,t,'unknown',False);t['code']=2;self.check(a,t,'violation',False)
    def test_typed_code_difference(self):
        a,t=pair();t['code']='1';self.check(a,t,'violation',False)
    def test_no_bindings(self):
        a,t=pair();del a['dictionary_refs'];r,_,_,_=shacl_binding(envelope(a),Graph().parse('research/refined-hybrid-1/shapes/binding-pairs.ttl'));self.assertEqual(r['no_bindings_status'],'unknown');self.assertTrue(r['raw_conforms'])
