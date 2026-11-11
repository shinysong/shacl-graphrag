"""Synthetic development software controls, no measured model answers."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from experiments.factory_complexity.fixtures import make_case,write_cases,digest
from experiments.factory_complexity.tools import Views,RDFStudyTools,SQLStudyTools,CATALOG,NOTICE
from experiments.factory_complexity.evaluator import decisions,expected_selected_flags
from apps.factory_lab.evidence import canonical,model_evidence
from apps.factory_lab.review import review
from apps.factory_lab.agent import Runner
from apps.factory_lab.store import Store
from experiments.factory_complexity.scaling import expand,triple_count,write_runtime,logical

REQUESTS=[('find_entities',{'text':'자격'}),('find_entities',{'text':'not-present'}),
 ('inspect_entity',{'entity_id':'M01'}),('inspect_entity',{'entity_id':'Q03R'}),
 ('inspect_entity',{'entity_id':'missing'}),('impacted_orders',{'machine_id':'M02'}),
 ('compare_impacted_orders',{'machine_id':'M02'}),
 ('replacement_candidates',{'order_id':'O17'}),('replacement_candidates',{'order_id':'O18'}),
 ('qualification_records',{'machine_id':'M01'}),('qualification_records',{'machine_id':'M02'}),
 ('qualification_records',{'machine_id':'M03'})]

class ComplexityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)/'study';cls.catalog=write_cases(cls.root)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_twelve_cells_sql_rdf_and_independent_checker_reference(self):
        for cell in self.catalog:
            views=Views(self.root/'runtime'/cell['id']);rdf=RDFStudyTools(views);sql=SQLStudyTools(views)
            try:
                evidence=[]
                for tool,args in REQUESTS:
                    with self.subTest(cell=cell['id'],tool=tool):
                        a=rdf.run('factory-v3',tool,args);b=sql.run('factory-v3',tool,args)
                        self.assertEqual(canonical(model_evidence(a)),canonical(model_evidence(b)))
                        # Avoid counting duplicated inspect+qualification records in the census.
                        if tool in ('replacement_candidates','qualification_records'):evidence.append(a)
                py=review(evidence,'python');sh=review(evidence,'shacl')
                self.assertEqual(py['flags'],sh['flags'])
                self.assertEqual(py['flags'],expected_selected_flags(views.data['factory-v3']))
            finally:sql.close()

    def test_absent_omitted_same_visible_view_different_source(self):
        for family in ('Q1','Q2','Q3','Q4'):
            absent=make_case(family,'A');omitted=make_case(family,'O')
            self.assertEqual(absent['question'],omitted['question'])
            self.assertEqual(absent['views'],omitted['views'])
            self.assertNotEqual(digest(absent['sources']['factory-v3']),digest(omitted['sources']['factory-v3']))
            self.assertFalse(absent['evaluation']['source_target_present'])
            self.assertTrue(omitted['evaluation']['source_target_present'])

    def test_model_observations_differ_only_in_opaque_source_identity(self):
        def without_source_identity(value):
            if isinstance(value,dict):return {k:without_source_identity(v) for k,v in value.items() if k!='source_sha256'}
            if isinstance(value,list):return [without_source_identity(v) for v in value]
            return value
        for start in (1,4,7,10):
            a=SQLStudyTools(Views(self.root/'runtime'/f'case-{start+1:02d}'))
            o=SQLStudyTools(Views(self.root/'runtime'/f'case-{start+2:02d}'))
            try:
                for tool,args in REQUESTS:
                    left=model_evidence(a.run('factory-v3',tool,args));right=model_evidence(o.run('factory-v3',tool,args))
                    self.assertNotIn('view_sha256',canonical(left));self.assertNotIn('view_sha256',canonical(right))
                    self.assertEqual(without_source_identity(left),without_source_identity(right))
                    self.assertNotEqual(left['source_sha256'],right['source_sha256'])
            finally:a.close();o.close()

    def test_runtime_does_not_read_historical_source(self):
        views=Views(self.root/'runtime'/'case-01')
        with patch('apps.factory_lab.graph.snapshot',side_effect=AssertionError('historical read')),patch('apps.factory_lab.rdf_graph.snapshot',side_effect=AssertionError('historical read')):
            rdf=RDFStudyTools(views);sql=SQLStudyTools(views)
            try:
                for tool,args in REQUESTS:
                    self.assertEqual(model_evidence(rdf.run('factory-v3',tool,args)),model_evidence(sql.run('factory-v3',tool,args)))
            finally:sql.close()

    def test_omission_applies_to_all_query_paths(self):
        for cell in self.catalog:
            if cell['state']!='O':continue
            views=Views(self.root/'runtime'/cell['id']);graph=SQLStudyTools(views)
            try:
                self.assertEqual(graph.run('factory-v3','inspect_entity',{'entity_id':cell['target']})['rows'],[])
                self.assertEqual(graph.run('factory-v3','find_entities',{'text':cell['target']})['rows'],[])
                self.assertTrue(any(n['id']==cell['target'] for n in json.loads((self.root/'evaluation'/cell['id']/'factory-v3.json').read_text())['nodes']))
            finally:graph.close()

    def test_new_order_is_outside_qualification_checker(self):
        views=Views(self.root/'runtime'/'case-07');graph=SQLStudyTools(views)
        try:
            evidence=graph.run('factory-v3','compare_impacted_orders',{'machine_id':'M02'})
            before,current=evidence['rows']
            self.assertNotIn('O20',[r['order']['id'] for r in before['rows']])
            self.assertIn('O20',[r['order']['id'] for r in current['rows']])
            for arm in ('python','shacl'):
                report=review([evidence],arm)
                self.assertEqual(report['assessment'],'not_assessed')
        finally:graph.close()

    def test_partial_records_not_combined_and_whole_record_matters(self):
        yes=decisions(make_case('Q4','C')['sources']['factory-v3'])
        no=decisions(make_case('Q4','A')['sources']['factory-v3'])
        key='O18|M01|CAP-CUT'
        self.assertEqual(yes['candidates'][key]['applicable_record_ids'],['Q01B'])
        self.assertFalse(no['candidates'][key]['eligible_within_policy'])
        self.assertTrue(no['candidates']['O17|M01|CAP-CUT']['eligible_within_policy'])

    def test_manifest_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            import shutil
            target=Path(d)/'runtime';shutil.copytree(self.root/'runtime'/'case-01',target)
            p=target/'factory-v3.json';data=json.loads(p.read_text());data['nodes'][0]['status']='wrong';p.write_text(json.dumps(data))
            with self.assertRaises(ValueError):Views(target)

    def test_real_runner_injection_and_no_evaluator_in_prompt(self):
        views=Views(self.root/'runtime'/'case-07');graph=SQLStudyTools(views)
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'state.sqlite');seen=[]
            class Gateway:
                def call(self,rid,messages,tools=None):
                    seen.append(copy.deepcopy(messages))
                    if len(seen)==1:
                        self.assert_catalog=tools
                        return {'tool_calls':[{'id':'one','function':{'name':'compare_impacted_orders','arguments':'{"machine_id":"M02"}'}}]}
                    return {'content':'Scripted software control, not a measured LLM answer [E1]'}
            gateway=Gateway()
            runner=Runner(store,graph,lambda _:gateway,snapshot_resolver=views.snapshot,tool_catalog=CATALOG,source_notice=NOTICE)
            config={'question':views.manifest['question'],'snapshot':'factory-v3','review':'compare','planning':False}
            rid=store.create(config);runner.cancel_flags[rid]=threading.Event();runner.lock.acquire();runner.execute(rid,config)
            self.assertEqual(store.get(rid)['status'],'completed')
            self.assertEqual(len(seen),5)
            self.assertEqual(gateway.assert_catalog,CATALOG)
            self.assertNotIn('source_target_present',canonical(seen));self.assertNotIn('case-07',canonical(seen))
            self.assertNotIn('eligible_within_policy',canonical(seen));self.assertNotIn('source_absent',canonical(seen))
            for field in ('family','state','target'):
                self.assertNotIn('"'+field+'":',canonical(seen))
            with self.assertRaises(ValueError):runner.start(config|{'planning':True})
            self.assertEqual(store.budget()['attempts'],0)
        graph.close()

    def test_unrelated_size_preserves_relevant_queries(self):
        original=make_case('Q2','C')['views']['factory-v3']
        source=expand(original,target_triples=1000)
        self.assertGreaterEqual(triple_count(source),1000)
        self.assertLess(triple_count(source),1022)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_runtime(root/'small',original);write_runtime(root/'large',source)
            small=SQLStudyTools(Views(root/'small'));large=SQLStudyTools(Views(root/'large'))
            try:
                from experiments.factory_complexity.scaling import REQUESTS as fixed
                self.assertEqual(logical([small.run('factory-v3',t,a) for t,a in fixed]),logical([large.run('factory-v3',t,a) for t,a in fixed]))
            finally:small.close();large.close()

    def test_limit_saturation_is_not_completeness(self):
        for size in (29,30,31):
            data=expand(make_case('Q2','C')['views']['factory-v3'],candidate_count=size)
            with tempfile.TemporaryDirectory() as d:
                write_runtime(Path(d)/'runtime',data);views=Views(Path(d)/'runtime')
                rdf=RDFStudyTools(views);sql=SQLStudyTools(views)
                try:
                    a=rdf.run('factory-v3','replacement_candidates',{'order_id':'O17'})
                    b=sql.run('factory-v3','replacement_candidates',{'order_id':'O17'})
                    self.assertEqual(model_evidence(a),model_evidence(b))
                    self.assertEqual(len(a['rows']),min(size,30));self.assertEqual(a['limit_reached'],size>=30)
                    self.assertIn('not source completeness',a['scope'])
                finally:sql.close()

    def test_scale_keeps_completed_query_before_later_failure(self):
        from experiments.factory_complexity.scaling import measure
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'measurement';original=RDFStudyTools.query;calls=[]
            def failing(adapter,*args):
                calls.append(args)
                if len(calls)==2:
                    saved=json.loads((dest/'result.json').read_text())
                    self.assertEqual(saved['status'],'started');self.assertEqual(len(saved['rows']),1)
                    self.assertTrue((dest/saved['rows'][0]['evidence_file']).exists())
                    raise RuntimeError('Injected query failure')
                return original(adapter,*args)
            with patch.object(RDFStudyTools,'query',failing):
                with self.assertRaisesRegex(RuntimeError,'Injected query failure'):measure(dest,'unrelated',1000)
            saved=json.loads((dest/'result.json').read_text());self.assertEqual(saved['status'],'failed')
            self.assertEqual(len(saved['rows']),1)

    def test_scale_timeout_denominator_and_partial_logs(self):
        import subprocess
        from scripts import factory_complexity_scale as driver
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'run'
            def timeout(command,**kwargs):
                plan=json.loads((dest/'plan.json').read_text())
                self.assertEqual(sum(s['status']=='running' for s in plan),1)
                raise subprocess.TimeoutExpired(command,240,output=b'partial stdout',stderr=b'partial stderr')
            with patch('sys.argv',['scale','--output',str(dest)]),patch.object(driver.subprocess,'run',side_effect=timeout):
                self.assertEqual(driver.main(),1)
            plan=json.loads((dest/'plan.json').read_text())
            self.assertEqual(len(plan),6);self.assertTrue(all(s['status']=='timeout' for s in plan))
            self.assertEqual(len(list(dest.glob('*.stdout.txt'))),6)
            self.assertTrue(all(p.read_text()=='partial stderr' for p in dest.glob('*.stderr.txt')))

if __name__=='__main__':unittest.main()
