import unittest
from scripts.backend_inference import build_variants,external_closure,answer,QUERIES,term,ANN,TAB,ALT,ROOT,SC,TYPE
from scripts.run_ontology_reasoning_study import json_closure

class BackendInferenceTests(unittest.TestCase):
    def test_alternative_support_survives_one_deletion(self):
        facts=[(term('a'),TYPE,ANN)]
        schema=[(ANN,SC,TAB),(TAB,SC,ROOT),(ANN,SC,ALT),(ALT,SC,ROOT)]
        for removed,expected in [(set(),[term('a')]),({(ANN,SC,TAB)},[term('a')]),({(ANN,SC,TAB),(ANN,SC,ALT)},[])]:
            current=[x for x in schema if x not in removed]
            py,_=json_closure(current,facts)
            self.assertEqual(answer(py,QUERIES[0]),expected)
            self.assertEqual(answer(external_closure(facts,current),QUERIES[0]),expected)
    def test_cycle_and_unrelated_class(self):
        facts=[(term('a'),TYPE,ANN)];schema=[(ANN,SC,TAB),(TAB,SC,ANN),(TAB,SC,ROOT)]
        py,_=json_closure(schema,facts);rdf=external_closure(facts,schema)
        for result in [py,rdf]:
            self.assertEqual(answer(result,QUERIES[0]),[term('a')]);self.assertEqual(answer(result,QUERIES[1]),[])
    def test_fixture_metadata_separates_controlled_omission(self):
        source={'nodes':[{'node_id':'PP6:2','node_type':'annotation'}],'edges':[{'subject':'PP6:2','field':'defect','target':'PP6:defect_code:4'}]}
        variants=build_variants(source)
        self.assertEqual(len(variants),8);self.assertEqual(len({v['id'] for v in variants}),8)
        self.assertIn('not natural source absence',variants[-1]['change_basis'])
        self.assertEqual(len(variants[0]['facts'])-len(variants[-1]['facts']),1)

class CleanupBoundaryTests(unittest.TestCase):
    def test_cleanup_failure_aborts_remaining_plan(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import patch
        from scripts.backend_inference import run
        for receipt in [{'remaining':1},RuntimeError('cleanup failure')]:
            class Fake:
                def load(self,*a):pass
                def query(self,*a):return []
                def cleanup(self):
                    if isinstance(receipt,Exception):raise receipt
                    return receipt
            with tempfile.TemporaryDirectory() as td:
                p=Path(td);(p/'source.json').write_text('{"nodes":[],"edges":[]}')
                from scripts.backend_parity import CUTOFF
                import datetime
                frozen_time=CUTOFF-datetime.timedelta(hours=1)
                with patch('scripts.backend_inference.NeoStore',return_value=Fake()),patch('scripts.backend_inference.NeptuneStore') as neptune,patch('scripts.backend_inference.dt.datetime') as clock:
                    clock.now.return_value=frozen_time
                    with self.assertRaisesRegex(RuntimeError,'unresolved cleanup'):run(p/'source.json',p/'out',True)
                    neptune.assert_not_called()
                rows=(p/'out/results.jsonl').read_text().splitlines()
                self.assertEqual(len(rows),20)
                self.assertEqual(len(json.loads((p/'out/plan.json').read_text())),224)
                self.assertEqual(json.loads((p/'out/cleanup.json').read_text())[0]['status'],'failed')
    def test_verified_empty_cleanup(self):
        from unittest.mock import Mock
        from scripts.backend_inference import verified_cleanup
        for value in [0,False]:
            store=Mock();store.cleanup.return_value={'remaining':value}
            self.assertEqual(verified_cleanup(store),{'remaining':value})

if __name__=='__main__':unittest.main()
