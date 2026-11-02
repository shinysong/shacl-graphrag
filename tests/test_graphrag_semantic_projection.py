import sys
import json
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from graphrag_semantic_projection import project

class ProjectionTests(unittest.TestCase):
    def fixture(self):
        payload={'id':'W:2','coupon':'W','sheet':'W','excel_row':2,
                 'header_rows':[{'cells':[{'cell':'A1','value':'setting'},{'cell':'B1','value':'note'}]}],
                 'cells':[{'cell':'A2','value':3},{'cell':'B2','value':'long value'}],
                 'dictionary_refs':{'setting':'W:code:3'},'sha256':'privatehash','archive_path':'original/path'}
        return {'chunks':[{'chunk_id':'node:W:2','chunk_type':'node','text':json.dumps(payload)}]}
    def test_fields_and_provenance(self):
        source=self.fixture();before=json.dumps(source)
        rows=project(source,lambda s:len(s.split()))
        text=rows[0]['search_text']
        self.assertIn('setting [A2] = 3',text)
        self.assertIn('setting reference = W:code:3',text)
        self.assertNotIn('privatehash',text)
        self.assertEqual(json.dumps(source),before)
    def test_field_boundaries_context_repeated(self):
        rows=project(self.fixture(),lambda s:len(s.split()),limit=15)
        self.assertGreater(len(rows),1)
        lines=[line for r in rows for line in r['field_lines']]
        self.assertEqual(len(lines),3)
        self.assertEqual(len(set(lines)),3)
        for r in rows:self.assertIn('Excel row=2',r['search_text']);self.assertLessEqual(r['token_count'],15)
    def test_atomic_overflow_fails(self):
        with self.assertRaises(ValueError):project(self.fixture(),lambda s:999)
    def test_duplicate_parents_fail(self):
        source=self.fixture();source['chunks']*=2
        with self.assertRaises(ValueError):project(source,lambda s:1)
    def test_parent_hash_and_order_stable(self):
        self.assertEqual(project(self.fixture(),len,limit=200),project(self.fixture(),len,limit=200))

if __name__=='__main__':unittest.main()
