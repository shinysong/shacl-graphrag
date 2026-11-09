import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.backend_parity import (SQLStore,RDFStore,NeoStore,NeptuneStore,uri,val,check_pattern,execute)

class BackendParityTests(unittest.TestCase):
    def test_bgp_join_and_missing_are_sets(self):
        triples=[(uri('a'),uri('link'),uri('b')),(uri('b'),uri('value'),val('x"\\\n한글'))]
        results=[]
        for cls in [SQLStore,RDFStore]:
            s=cls();s.load(triples)
            results.append(s.query([[uri('a'),uri('link'),'?o'],['?o',uri('value'),'?v']],['?v']))
            self.assertEqual(s.query([[uri('a'),uri('missing'),'?v']],['?v']),[])
            s.cleanup()
        self.assertEqual(results[0],results[1]);self.assertEqual(results[0],[{'?v':val('x"\\\n한글')}])
    def test_reused_edge_bgp_compiles_separate_match(self):
        patterns=[[uri('a'),uri('p'),'?o'],[uri('a'),uri('p'),'?o']]
        n=NeoStore('backend-reuse')
        with patch.object(n,'request',return_value=[{'o':uri('b')}]) as request:
            self.assertEqual(n.query(patterns,['?o']),[{'?o':uri('b')}])
            self.assertEqual(request.call_args.args[0].count('MATCH '),2)
        for cls in [SQLStore,RDFStore]:
            s=cls();s.load([(uri('a'),uri('p'),uri('b'))])
            self.assertEqual(s.query(patterns,['?o']),[{'?o':uri('b')}])
            s.cleanup()
    def test_null_string_number_preserved(self):
        triples=[(uri(str(i)),uri('v'),val(v)) for i,v in enumerate([None,'null',1,1.0,'1'])]
        s=SQLStore();s.load(triples)
        self.assertEqual(len(s.query([['?s',uri('v'),'?v']],['?v'])),5)
    def test_reject_malformed_query(self):
        for patterns,project in [([[uri('a'),uri('p'),'?v']],['?missing']),([[uri('a'),uri('p'),'?v']],['?v','?v']),([[val('badsubject'),uri('p'),'?v']],['?v'])]:
            with self.assertRaises(ValueError):check_pattern(patterns,project)
    def test_no_cleanup_unowned_neo(self):
        n=NeoStore('backend-test')
        with patch.object(n,'request',return_value=[{'count':1}]) as request:
            with self.assertRaises(ValueError):n.load([])
            self.assertEqual(n.cleanup(),{'namespace_not_owned':True})
            self.assertEqual(request.call_count,1)
    def test_no_cleanup_unowned_neptune(self):
        n=object.__new__(NeptuneStore);n.owned=False
        with patch.object(n,'request') as request:
            self.assertEqual(n.cleanup(),{'namespace_not_owned':True});request.assert_not_called()
    def test_failure_retained_and_other_backend_runs(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'source.json').write_text('{"nodes":[],"edges":[]}')
            (root/'queries.json').write_text(json.dumps([{'id':'Q','question_type':'Q','scope':'test','patterns':[[uri('a'),uri('p'),'?v']],'project':['?v']}]))
            with patch.object(SQLStore,'load',side_effect=RuntimeError('injected')):
                execute(root/'source.json',root/'queries.json',root/'out')
            rows=[json.loads(x) for x in (root/'out/results.jsonl').read_text().splitlines()]
            self.assertEqual([r['status'] for r in rows],['dependency_not_run','completed'])
            self.assertEqual(len(json.loads((root/'out/plan.json').read_text())),2)
            self.assertEqual(len(json.loads((root/'out/cleanup.json').read_text())),2)

if __name__=='__main__':unittest.main()
