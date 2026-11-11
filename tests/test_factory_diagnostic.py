"""Offline authored diagnostic controls, not answer efficacy tests."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('diagnostic', ROOT/'research/virtual-factory-llm-1/diagnostic/build.py')
diag=importlib.util.module_from_spec(spec);spec.loader.exec_module(diag)

class DiagnosticTests(unittest.TestCase):
    def test_expected_flags_and_cross_record_conjunction(self):
        cases={c['id']:c for c in diag.authored_cases()}
        expected={'assignment':[],'eligible':[],'expired':['qualification-not-applicable'],
                  'split_records':['qualification-not-applicable'],'retrieval_gap':['qualification-not-retrieved'],
                  'outside_policy':[]}
        for cid,c in cases.items():
            for mode in ('python','shacl'):
                r=diag.review(c['evidence'],mode)
                self.assertEqual([f['code'] for f in r['flags']],expected[cid],(cid,mode))
                if cid=='assignment':self.assertEqual(r['assessment'],'not_assessed')
        split=deepcopy(cases['split_records']['evidence'])
        split[1]['rows'][1]['qualification']['product']='P-A'
        for mode in ('python','shacl'):
            self.assertEqual(diag.review(split,mode)['flags'],[])

    def test_source_absence_unobservable_to_selected_evidence(self):
        case=next(c for c in diag.authored_cases() if c['id']=='retrieval_gap')
        self.assertTrue(any(n['id']=='Q01' for n in case['source']['nodes']))
        original=deepcopy(case['evidence'])
        case['source']['nodes']=[n for n in case['source']['nodes'] if n['id']!='Q01']
        case['source']['edges']=[e for e in case['source']['edges'] if 'Q01' not in e]
        self.assertEqual(case['evidence'],original)
        self.assertEqual(diag.review(original,'python')['flags'],diag.review(case['evidence'],'shacl')['flags'])

    def test_frozen_pairs_and_no_evaluator_leakage(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'new';summary=diag.build(out)
            self.assertEqual(summary,{'cases':6,'authored_drafts':12,'packets':36,'checker_pairs':6,'llm_calls':0,'db_calls':0})
            manifest=json.loads((out/'evaluator/manifest.json').read_text())
            groups={}
            for row in manifest:
                packet=json.loads((out/row['packet']).read_text())
                self.assertEqual(set(packet),{'messages'})
                user=json.loads(packet['messages'][1]['content'])
                self.assertEqual(set(user),{'question','as_of','policy','draft','evidence','review_report'})
                self.assertNotIn('engine',user['review_report'])
                self.assertEqual(diag.digest({k:v for k,v in user.items() if k!='review_report'}),row['common_input_sha256'])
                groups.setdefault((row['case_id'],row['draft_type']),[]).append(row)
            for rows in groups.values():
                self.assertEqual(len({r['common_input_sha256'] for r in rows}),1)
                p=next(r for r in rows if r['arm']=='python');s=next(r for r in rows if r['arm']=='shacl')
                self.assertEqual(p['messages_sha256'],s['messages_sha256'])
            with self.assertRaises(FileExistsError):diag.build(out)

if __name__=='__main__':unittest.main()
