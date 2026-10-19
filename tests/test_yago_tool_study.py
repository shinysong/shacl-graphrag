import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_yago_tool_study as s

class Fake:
    def __init__(self,calls):self.calls=iter(calls)
    def generate(self,messages,specs,path):
        name,args=next(self.calls)
        return {'role':'assistant','tool_calls':[{'id':'x','type':'function','function':{'name':name,'arguments':json.dumps(args)}}]},{}

class TestYagoToolStudy(unittest.TestCase):
    def test_input_allowlist_and_hashes(self):
        people,source,m=s.inputs()
        self.assertEqual(len(people),4)
        self.assertTrue(all(set(p)=={'subject','name'} for p in people))
        self.assertEqual(s.sha(s.FIX/'schema.ttl'),m['source']['files']['schema']['turtle_sha256'])
    def test_mandatory_gate_without_gold_repair(self):
        finish={'status':'answer','value':'urn:wrong','citations':['wrong'],'explanation':'wrong outcome preserved'}
        calls=[('query',{'query':'q','interpretation':'i'}),('finish',finish),('validate',{}),('finish',finish)]
        with tempfile.TemporaryDirectory() as d,patch.object(s.local,'query',return_value={'status':'ok','evidence_turtle':'<urn:s> <urn:p> <urn:o> .'}),patch.object(s.local,'validate_evidence',return_value={'status':'fail','conforms':False}):
            out=Path(d)/'case';r=s.episode(Fake(calls),out,{'name':'x','subject':'urn:s'},'C',{'data':'','schema':'','taxonomy':''})
            self.assertEqual(r['status'],'finished');self.assertEqual(r['answer']['value'],'urn:wrong')
            self.assertEqual(r['counts']['model_calls'],4)
            self.assertIn('ValidationRequiredForCurrentEvidence',(out/'events.jsonl').read_text())
    def test_new_query_invalidates_validation(self):
        f={'status':'unknown','value':None,'citations':[],'explanation':'unknown'}
        q=('query',{'query':'q','interpretation':'i'})
        calls=[q,('validate',{}),q,('finish',f),('validate',{}),('finish',f)]
        with tempfile.TemporaryDirectory() as d,patch.object(s.local,'query',return_value={'status':'ok','evidence_turtle':'<urn:s> <urn:p> <urn:o> .'}),patch.object(s.local,'validate_evidence',return_value={'status':'pass','conforms':True}):
            r=s.episode(Fake(calls),Path(d)/'case',{'name':'x','subject':'urn:s'},'C',{'data':'','schema':'','taxonomy':''})
            self.assertEqual(r['counts']['model_calls'],6);self.assertEqual(r['counts']['checks'],2)
    def test_daily_ledger_and_unresolved_reservation(self):
        with tempfile.TemporaryDirectory() as d:
            old=Path(d)/'old.json';old.write_text(json.dumps({'reservations':[{'at':s.stamp()}]*500}))
            g=object.__new__(s.Gateway);g.ledger=Path(d)/'new.json';g.output=Path(d)/'run'
            with patch.object(s,'OLD_LEDGER',old):
                with self.assertRaises(s.BudgetStop):g.reserve(.01)
                self.assertFalse(g.ledger.exists())
                old.write_text('{"reservations":[]}');self.assertEqual(g.reserve(.01),0)
                with self.assertRaises(s.BudgetStop):g.reserve(.01)
                self.assertEqual(json.loads(g.ledger.read_text())['attempts'],1)

if __name__=='__main__':unittest.main()
