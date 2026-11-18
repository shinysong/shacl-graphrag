import copy
import unittest
from experiments.query_contracts.core import CatalogIndex, execute, validate_plan
from experiments.factory_complexity.tools import Views, RDFStudyTools, SQLStudyTools

DIRECTORY = 'research/factory-complexity-1/development-001/runtime/case-01'
PLAN = {'obligations': {'impact': '영향 주문', 'candidate': '대체 설비', 'qualification': '자격 확인', 'delivery': '납기 가능성'}, 'steps': [
    {'id': 'impact', 'obligation': 'impact', 'tool': 'impacted_orders', 'binding': {'literal': 'M02', 'kind': 'Machine'}},
    {'id': 'candidates', 'obligation': 'candidate', 'tool': 'replacement_candidates', 'binding': {'step': 'impact', 'path': 'order.id'}},
    {'id': 'qualifications', 'obligation': 'qualification', 'tool': 'qualification_records', 'binding': {'step': 'candidates', 'path': 'machine.id'}},
]}

class QueryContractTests(unittest.TestCase):
    def setUp(self):
        self.sql = SQLStudyTools(Views(DIRECTORY))
        self.addCleanup(self.sql.close)
    def test_real_backend_parity_and_lineage(self):
        a = execute(PLAN, self.sql, max_calls=30)
        b = execute(PLAN, RDFStudyTools(Views(DIRECTORY)), max_calls=30)
        self.assertEqual(a['outputs'], b['outputs'])
        self.assertTrue(a['outputs']['qualifications'])
        for row in a['outputs']['qualifications']:
            self.assertIn('order', row['context']); self.assertEqual(len(row['lineage']), 3)
        self.assertEqual(a['obligations']['delivery']['status'], 'not_planned')
    def test_wrong_type_and_cycle(self):
        for path in ['machine.id', 'order.product']:
            p = copy.deepcopy(PLAN); p['steps'][1]['binding']['path'] = path
            with self.assertRaisesRegex(ValueError, 'incompatible_binding'): validate_plan(p)
        p = copy.deepcopy(PLAN); p['steps'][1]['binding']['step'] = 'qualifications'
        with self.assertRaisesRegex(ValueError, 'dependency'): validate_plan(p)
    def test_literal_type_not_just_declared(self):
        p = copy.deepcopy(PLAN); p['steps'][0]['binding']['literal'] = 'O17'
        r = execute(p, self.sql)
        self.assertEqual(r['calls'], [])
        self.assertIn('entity_type_not_verified', r['steps']['impact']['issues'])
    def test_budget_retains_unresolved(self):
        r = execute(PLAN, self.sql, max_calls=1)
        self.assertEqual(len(r['calls']), 1)
        self.assertIn('call_budget_exhausted', r['steps']['candidates']['issues'])
    def test_foreign_version_excluded(self):
        original = self.sql.run
        def wrong(*args):
            result = original(*args); result['source_sha256'] = 'wrong'; return result
        self.sql.run = wrong
        r = execute(PLAN, self.sql)
        self.assertEqual(r['outputs']['impact'], [])
        self.assertEqual(r['calls'][0]['status'], 'failed')
    def test_response_entity_binding(self):
        original = self.sql.run
        def wrong(*args):
            result = original(*args)
            for row in result['rows']: row['machine']['id'] = 'M99'
            return result
        self.sql.run = wrong
        r = execute(PLAN, self.sql)
        self.assertIn('response_entity_mismatch', r['steps']['impact']['issues'])
    def test_limit_propagates(self):
        original = self.sql.run
        def limited(*args):
            result = original(*args); result['limit_reached'] = True; return result
        self.sql.run = limited
        r = execute(PLAN, self.sql, max_calls=30)
        self.assertTrue(r['steps']['qualifications']['limited'])
    def test_lexical_index_determinism(self):
        index = CatalogIndex()
        a = index.search('설비 자격 제품 유효기간', 3)
        self.assertEqual(a, index.search('설비 자격 제품 유효기간', 3))
        self.assertEqual(len(a), 3)
        self.assertIn('qualification_records', [x['tool'] for x in a])
        with self.assertRaises(ValueError): index.search('test', 0)

class CompetingSelectionTests(unittest.TestCase):
    def setUp(self):
        from experiments.query_contracts.competing import CompetingTools
        self.sql = SQLStudyTools(Views(DIRECTORY)); self.addCleanup(self.sql.close)
        self.backends = [CompetingTools(self.sql), CompetingTools(RDFStudyTools(Views(DIRECTORY)))]
    def test_competitors_actual_queries_differ_and_match_backends(self):
        results = {}
        for tool,args in [('assigned_machines',{'order_id':'O17'}),('replacement_candidates',{'order_id':'O17'}),('current_qualification_records',{'machine_id':'M03'}),('expired_qualification_records',{'machine_id':'M03'}),('qualification_records',{'machine_id':'M03'})]:
            a,b = [backend.run('factory-v3',tool,args) for backend in self.backends]
            self.assertEqual(a['rows'],b['rows']);results[tool]=a['rows']
        self.assertEqual([r['machine']['id'] for r in results['assigned_machines']],['M02'])
        self.assertEqual(len(results['replacement_candidates']),3)
        self.assertEqual([r['qualification']['id'] for r in results['current_qualification_records']],['Q03R'])
        self.assertEqual([r['qualification']['id'] for r in results['expired_qualification_records']],['Q03'])
        self.assertEqual(len(results['qualification_records']),2)
    def test_no_current_qualification_is_empty_not_absent_source(self):
        for backend in self.backends:
            r=backend.run('factory-v3','current_qualification_records',{'machine_id':'M02'})
            self.assertEqual(r['rows'],[]); self.assertIn('not order eligibility',r['scope'])
    def test_query_parameter_injection_stays_literal(self):
        for backend in self.backends:
            with self.assertRaises(ValueError):backend.run('factory-v3','assigned_machines',{'order_id':'O17','query':'DROP'})
            self.assertEqual(backend.run('factory-v3','assigned_machines',{'order_id':"O17' OR 1=1"})['rows'],[])
    def test_type_filter_cannot_verify_semantic_intent(self):
        from experiments.query_contracts.selection import select
        # Both candidates have same input kind; wrong meaning cannot be blocked by types.
        catalog=[{'tool':'assigned_machines','description':'same'},{'tool':'replacement_candidates','description':'same'},{'tool':'qualification_records','description':'different'}]
        request={'tasks':[{'id':'a','text':'same','binding':{'literal':'O17','kind':'Order'}}]}
        for constrained in (False,True):
            r=select(request,catalog,constrained)
            self.assertEqual(r['decisions'][0]['selected_tool'],'assigned_machines')
            self.assertEqual(r['intent_correctness'],'unverified')
    def test_type_filter_uses_same_top3_and_retains_wrong_baseline(self):
        from experiments.query_contracts.selection import select
        catalog=[{'tool':'qualification_records','description':'자격'},{'tool':'replacement_candidates','description':'자격 후보'},{'tool':'impacted_orders','description':'기타'}]
        request={'tasks':[{'id':'a','text':'자격','binding':{'literal':'O17','kind':'Order'}}]}
        a=select(request,catalog);b=select(request,catalog,True)
        self.assertEqual(a['decisions'][0]['ranked'],b['decisions'][0]['ranked'])
        self.assertEqual(a['decisions'][0]['selected_tool'],'qualification_records')
        self.assertFalse(a['structurally_valid']);self.assertTrue(b['structurally_valid'])
    def test_zero_overlap_retains_unplanned(self):
        from experiments.query_contracts.selection import select
        catalog=[{'tool':t,'description':'abc'} for t in ('impacted_orders','replacement_candidates','qualification_records')]
        r=select({'tasks':[{'id':'x','text':'zzzz','binding':{'literal':'M03','kind':'Machine'}}]},catalog,True)
        self.assertIsNone(r['decisions'][0]['selected_tool']);self.assertEqual(r['plan']['steps'],[])
    def test_scorer_failed_slot_denominator(self):
        from scripts.score_query_selection import score
        rubric={'accepted_tools':{'r1':{'a':['impacted_orders'],'b':[]}}}
        slots=[{'arm':arm,'backend':backend,'request_id':'r1','status':'failed'} for arm in ('top1','typed_top3') for backend in ('sqlite','rdflib')]
        r=score({'slots':slots},rubric)
        for c in r['summaries'].values():self.assertEqual(c['obligations'],2);self.assertEqual(c['unscored_failure'],2)
    def test_setup_failure_retains_all_unattempted_slots(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from scripts.query_selection_diagnostic import main
        directory='research/query-contracts-1/selection-development-001'
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'result.json'
            argv=['query_selection_diagnostic','--requests',directory+'/requests.json','--catalog',directory+'/catalog.json','--views',DIRECTORY,'--output',str(output)]
            with patch('sys.argv',argv),patch('scripts.query_selection_diagnostic.Views',side_effect=ValueError('injected bad view')):
                with self.assertRaisesRegex(ValueError,'injected bad view'):main()
            result=json.loads(output.read_text())
            self.assertEqual(result['setup_status'],'failed')
            self.assertEqual(len(result['slots']),24)
            self.assertTrue(all(s['status']=='unattempted' for s in result['slots']))

class ModelSelectionPreparationTests(unittest.TestCase):
    def setUp(self):
        import json
        from pathlib import Path
        self.requests=json.loads(Path('research/query-contracts-1/model-selection-001/requests.json').read_text())
        self.catalog=json.loads(Path('research/query-contracts-1/selection-development-001/catalog.json').read_text())['catalog']
    def test_prompt_controls_and_no_gold(self):
        import json
        from experiments.query_contracts.model_selection import packet
        request=self.requests[0]
        a=packet(request,self.catalog,'full_catalog');b=packet(request,self.catalog,'retrieved')
        self.assertEqual(a['rankings'],b['rankings'])
        self.assertEqual(a['messages'][0],b['messages'][0])
        self.assertTrue(all(len(v)==6 for v in a['presented_tools'].values()))
        self.assertTrue(all(len(v)==3 for v in b['presented_tools'].values()))
        self.assertNotIn('accepted_tools',json.dumps(a));self.assertNotIn('scoring.json',json.dumps(b))
    def test_parse_preserves_null_and_rejects_missing_tasks(self):
        import json
        from experiments.query_contracts.model_selection import packet,parse
        request=self.requests[0];prepared=packet(request,self.catalog,'full_catalog')
        choices=[{'id':t['id'],'tool':None,'reason':'no matching query'} for t in request['tasks']]
        self.assertEqual(parse(request,prepared,{'content':json.dumps({'decisions':choices})}),choices)
        with self.assertRaises(ValueError):parse(request,prepared,{'content':json.dumps({'decisions':choices[:-1]})})
    def test_wrong_type_retained_raw_but_checked_veto(self):
        from experiments.query_contracts.model_selection import plans
        request=self.requests[0]
        decisions=[{'id':t['id'],'tool':'qualification_records','reason':'test'} for t in request['tasks']]
        p=plans(request,decisions)
        self.assertEqual(len(p['raw']['steps']),3);self.assertEqual(len(p['checked']['steps']),1)
        self.assertEqual(len(p['rejections']),2)
    def test_outside_shortlist_is_retained_as_failure_not_repaired(self):
        import json
        from experiments.query_contracts.model_selection import packet,parse
        request=self.requests[0];prepared=packet(request,self.catalog,'retrieved')
        task=request['tasks'][0]
        outside=next(c['tool'] for c in self.catalog if c['tool'] not in prepared['presented_tools'][task['id']])
        items=[{'id':t['id'],'tool':outside if t['id']==task['id'] else None,'reason':'test'} for t in request['tasks']]
        with self.assertRaisesRegex(ValueError,'outside'):parse(request,prepared,{'content':json.dumps({'decisions':items})})
    def test_prepare_closed_shared_scope_and_no_resume(self):
        import tempfile,json
        from pathlib import Path
        from experiments.query_contracts.model_campaign import ROOT,prepare,preflight
        (ROOT/'_workspace').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
            work=Path(tmp)/'campaign';cost=prepare(work)
            self.assertEqual(cost['calls'],32);self.assertEqual(cost['derived_conditions'],48)
            self.assertFalse(json.loads((work/'execution-gate.json').read_text())['approved'])
            with self.assertRaisesRegex(RuntimeError,'gate closed'):preflight(work)
            with self.assertRaises(FileExistsError):prepare(work)
            self.assertFalse((work/'state.sqlite').exists())
    def test_scripted_runner_shared_ledger_and_gate_closure(self):
        import json,tempfile
        from pathlib import Path
        from datetime import datetime,timezone,timedelta
        from unittest.mock import patch
        from experiments.query_contracts.model_campaign import ROOT,prepare,run,read,write,sha
        class FakeGateway:
            def __init__(self,store,work_dir):self.store=store;self.session=read(Path(work_dir)/'session.json')
            def call(self,rid,messages):
                cid=self.store.reserve(rid,'0.01',self.session);self.store.settle(cid,'completed',{'cost':'0.001'})
                request=json.loads(messages[1]['content'])['request']
                return {'content':json.dumps({'decisions':[{'id':t['id'],'tool':None,'reason':'scripted test only'} for t in request['tasks']]})}
        for broken in (False,True):
            (ROOT/'_workspace').mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
                work=Path(tmp)/'campaign';prepare(work)
                session=read(work/'session.json');start=datetime.now(timezone.utc)
                session.update(status='authorized',started_at=start.isoformat(),deadline=(start+timedelta(hours=1)).isoformat());write(work/'session.json',session)
                approval={k:session[k] for k in ('campaign_id','max_attempts','max_usd','deadline')};approval.update(approved=True,human_message='SCRIPTED TEST ONLY; no real calls');write(work/'approval.json',approval)
                gate=read(work/'execution-gate.json');gate.update(approved=True,approval_sha256=sha(work/'approval.json'));write(work/'execution-gate.json',gate)
                if broken:
                    class BrokenGateway(FakeGateway):
                        def call(self,*args):super().call(*args);return {'content':'invalid-json'}
                    gateway=BrokenGateway
                else:gateway=FakeGateway
                with patch('experiments.query_contracts.model_campaign.Gateway',gateway):result=run(work)
                self.assertEqual(result['budget']['attempts'],1 if broken else 32)
                self.assertEqual(result['status'],'stopped' if broken else 'completed')
                self.assertEqual(sum(s['status']=='unattempted' for s in result['slots']),31 if broken else 0)
                self.assertFalse(read(work/'execution-gate.json')['approved'])
                for p in work.glob('*/execution-gate.json'):self.assertFalse(read(p)['approved'])

class CatalogScaleTests(unittest.TestCase):
    def setUp(self):
        import json
        from pathlib import Path
        from experiments.query_contracts.catalog_scale import catalog
        from experiments.factory_complexity.tools import Views
        from experiments.query_contracts.scale_campaign import DATA, VIEWS
        self.catalog = catalog(72)
        self.requests = json.loads((DATA/'runtime/development.json').read_text())
        self.snapshot = Views(VIEWS).snapshot('factory-v3')[0]

    def test_nested_catalogs_add_distinct_executable_predicates(self):
        from experiments.query_contracts.catalog_scale import catalog
        self.assertEqual(catalog(6),catalog(24)[:6])
        self.assertEqual(catalog(24),self.catalog[:24])
        self.assertEqual(len({c['tool'] for c in self.catalog}),72)
        predicates={(c['implementation']['kind'],c['implementation']['subject'],c['implementation']['scope']) for c in self.catalog if 'implementation' in c}
        self.assertEqual(len(predicates),66)

    def test_all_new_queries_match_independent_python_predicates(self):
        from experiments.query_contracts.catalog_scale import RecordTools
        records=RecordTools(self.snapshot)
        try:
            all_rows=[dict(r) for r in records.db.execute('SELECT * FROM records')]
            for contract in self.catalog[6:]:
                spec=contract['implementation']; ident=next(k for k,v in records.entities.items() if v==spec['subject'])
                actual=records.run(contract,{'literal':ident,'kind':spec['subject']})['rows']
                expected=[r for r in all_rows if r['kind']==spec['kind'] and r['subject_id']==ident and r['subject_kind']==spec['subject'] and
                          (spec['scope']=='all' or (r['valid_until']<self.snapshot['as_of'] if spec['scope']=='expired' else r['valid_from']<=self.snapshot['as_of']<=r['valid_until']))]
                self.assertEqual(actual,sorted(expected,key=lambda r:r['id']))
        finally:records.close()

    def test_boundary_dates_future_and_wrong_subject(self):
        from experiments.query_contracts.catalog_scale import RecordTools
        records=RecordTools(self.snapshot)
        try:
            contract=self.catalog[7] # Machine current MaintenanceRecord
            ident=next(k for k,v in records.entities.items() if v=='Machine')
            records.db.execute('UPDATE records SET valid_from=?,valid_until=? WHERE kind=? AND subject_id=?',
                               (self.snapshot['as_of'],self.snapshot['as_of'],'MaintenanceRecord',ident))
            self.assertEqual(len(records.run(contract,{'literal':ident,'kind':'Machine'})['rows']),3)
            with self.assertRaises(ValueError):records.run(contract,{'literal':ident,"kind":'Order'})
            with self.assertRaises(ValueError):records.run(contract,{'literal':ident+"' OR 1=1",'kind':'Machine'})
        finally:records.close()

    def test_same_metadata_across_arms_and_no_gold(self):
        from experiments.query_contracts.catalog_scale import packet
        import json
        a=packet(self.requests[0],self.catalog,'full_catalog');b=packet(self.requests[0],self.catalog,'retrieved')
        pa=json.loads(a['messages'][1]['content']);pb=json.loads(b['messages'][1]['content'])
        by_id={c['tool']:c for c in pa['catalog']}
        self.assertTrue(all(c==by_id[c['tool']] for c in pb['catalog']))
        self.assertEqual(a['messages'][0],b['messages'][0])
        self.assertEqual(pa['request'],pb['request'])
        self.assertIsNone(a['input_tokens'])
        self.assertNotIn('accepted_tools',json.dumps(a));self.assertNotIn('implementation',json.dumps(pb['catalog']))
        self.assertEqual(len(a['presented_tools']['assigned']),72)
        self.assertEqual(len(b['presented_tools']['assigned']),3)

    def test_checker_preserves_same_type_semantic_error_and_blocks_type_error(self):
        from experiments.query_contracts.catalog_scale import checked_choices
        request=self.requests[0]
        choices=[{'id':t['id'],'tool':tool,'reason':'test'} for t,tool in zip(request['tasks'],['replacement_candidates','qualification_records'])]
        result=checked_choices(request,choices,self.catalog)
        self.assertEqual(result[0]['tool'],'replacement_candidates')
        self.assertIsNone(result[1]['tool']);self.assertEqual(result[1]['rejection'],'incompatible_input_kind')

    def test_scorer_inclusion_model_error_null_and_false_veto_separate(self):
        from experiments.query_contracts.scale_scoring import score
        from experiments.query_contracts.catalog_scale import packet
        import copy
        request=self.requests[0];p=packet(request,self.catalog,'retrieved')
        p['presented_tools']={'assigned':['assigned_machines'],'alternatives':['qualification_records']}
        slot={'request':request,'packet':p,'size':72,'arm':'retrieved','model':'fake','status':'completed','input_bytes':123,
              'decisions':[{'id':'assigned','tool':'assigned_machines'},{'id':'alternatives','tool':None}],
              'checked_decisions':[{'id':'assigned','tool':None,'rejection':'INJECTED FALSE VETO'},{'id':'alternatives','tool':None,'rejection':None}]}
        rubric={'accepted_tools':{request['id']:{'assigned':['assigned_machines'],'alternatives':['replacement_candidates']}}}
        result=score({'status':'completed','slots':[slot]},rubric)['groups'][0]
        self.assertEqual(result['candidate_hit'],1);self.assertEqual(result['supported_tasks'],2)
        self.assertEqual(result['unnecessary_null'],1);self.assertEqual(result['model_error_with_candidate'],0)
        self.assertEqual(result['checked_correct_blocked'],1);self.assertIsNone(result['reported_usd'])
        slot['status']='failed'
        result=score({'status':'stopped','slots':[slot]},rubric)['groups'][0]
        self.assertEqual(result['planned_tasks'],2);self.assertEqual(result['unscored_tasks'],2)
        self.assertEqual(result['scored_tasks'],0);self.assertEqual(result['failed_requests'],1)

    def test_closed_prepare_does_not_read_rubrics_or_call_gateway(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from experiments.query_contracts.scale_campaign import prepare,preflight,ROOT,read
        def no_labels(path):
            self.assertNotIn('rubric',str(path));self.assertNotIn('/evaluation/',str(path));return read(path)
        (ROOT/'_workspace').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
            work=Path(tmp)/'campaign'
            with patch('experiments.query_contracts.scale_campaign.read',side_effect=no_labels):p=prepare(work,'development')
            self.assertEqual(p['attempts'],36);self.assertTrue(p['context_fits']);self.assertTrue(p['fits_cap'])
            self.assertFalse(read(work/'execution-gate.json')['approved'])
            with self.assertRaisesRegex(RuntimeError,'closed'):preflight(work)
            self.assertFalse((work/'state.sqlite').exists())
            with self.assertRaises(FileExistsError):prepare(work)

    def _authorize_test(self,work):
        from datetime import datetime,timezone,timedelta
        from experiments.query_contracts.scale_campaign import read,write,sha
        s=read(work/'session.json');now=datetime.now(timezone.utc)
        s.update(status='authorized',started_at=now.isoformat(),deadline=(now+timedelta(hours=1)).isoformat());write(work/'session.json',s)
        a={k:s[k] for k in ('campaign_id','max_attempts','max_usd','deadline','split')};a.update(approved=True,human_message='TEST ONLY no API');write(work/'approval.json',a)
        g=read(work/'execution-gate.json');g.update(approved=True,approval_sha256=sha(work/'approval.json'));write(work/'execution-gate.json',g)

    def test_runtime_change_rejected_before_ledger(self):
        import tempfile
        from pathlib import Path
        from experiments.query_contracts.scale_campaign import prepare,preflight,ROOT,read,write
        (ROOT/'_workspace').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
            w=Path(tmp)/'campaign';prepare(w,'development');self._authorize_test(w)
            config=read(w/'model-0/model.json');config['max_tokens']=1;write(w/'model-0/model.json',config)
            with self.assertRaisesRegex(RuntimeError,'Frozen runtime changed'):preflight(w)
            self.assertFalse((w/'state.sqlite').exists())

    def test_scripted_campaign_counts_usage_and_stops_on_malformed_reply(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import patch
        from experiments.query_contracts.scale_campaign import prepare,run,ROOT,read
        class FakeGateway:
            def __init__(self,store,work_dir):self.store=store;self.session=read(Path(work_dir)/'session.json')
            def call(self,rid,messages):
                cid=self.store.reserve(rid,'0.01',self.session)
                details={'cost':'0.001','usage':{'prompt_tokens':123,'completion_tokens':45},'model':'fake'}
                self.store.settle(cid,'completed',details);self.store.event(rid,'llm_completed',details)
                request=json.loads(messages[1]['content'])['request']
                return {'content':json.dumps({'decisions':[{'id':t['id'],'tool':None,'reason':'SCRIPTED ONLY'} for t in request['tasks']]})}
        for broken in (False,True):
            (ROOT/'_workspace').mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
                w=Path(tmp)/'campaign';prepare(w,'development');self._authorize_test(w)
                class Broken(FakeGateway):
                    def call(self,*args):super().call(*args);return {'content':'MALFORMED'}
                with patch('experiments.query_contracts.scale_campaign.Gateway',Broken if broken else FakeGateway), patch('experiments.query_contracts.scale_campaign.STUDY_LEDGER',w/'test-state.sqlite'), patch('experiments.query_contracts.scale_campaign.STUDY_LOCK',w/'test.lock'):result=run(w)
                self.assertEqual(result['budget']['attempts'],1 if broken else 36)
                self.assertEqual(result['status'],'stopped' if broken else 'completed')
                self.assertEqual(sum(s['status']=='unattempted' for s in result['slots']),35 if broken else 0)
                self.assertFalse(read(w/'execution-gate.json')['approved'])
                self.assertTrue(all(not read(p)['approved'] for p in w.glob('*/execution-gate.json')))
                self.assertEqual(result['slots'][0]['calls'][0]['usage']['prompt_tokens'],123)

    def test_shared_study_ledger_prevents_new_folder_reset(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from experiments.query_contracts.scale_campaign import prepare,preflight,ROOT,Store
        (ROOT/'_workspace').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
            root=Path(tmp);w=root/'campaign';prepare(w,'development');self._authorize_test(w)
            shared=root/'shared.sqlite';Store(shared).create({'prior':'preserved'})
            with patch('experiments.query_contracts.scale_campaign.STUDY_LEDGER',shared):
                with self.assertRaisesRegex(RuntimeError,'Existing ledger'):preflight(w)

    def test_backend_setup_failure_preserves_all_slots_and_closes_gate(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from experiments.query_contracts.scale_campaign import prepare,run,ROOT,read
        (ROOT/'_workspace').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
            w=Path(tmp)/'campaign';prepare(w,'development');self._authorize_test(w)
            with patch('experiments.query_contracts.scale_campaign.STUDY_LEDGER',w/'test.sqlite'),patch('experiments.query_contracts.scale_campaign.STUDY_LOCK',w/'test.lock'),patch('experiments.query_contracts.scale_campaign.Views',side_effect=ValueError('injected setup failure')):
                result=run(w)
            self.assertEqual(result['status'],'stopped');self.assertEqual(result['budget']['attempts'],0)
            self.assertEqual(len(result['slots']),36);self.assertTrue(all(s['status']=='unattempted' for s in result['slots']))
            self.assertFalse(read(w/'execution-gate.json')['approved'])

    def test_split_manifest_frozen_no_evaluation_scoring(self):
        import hashlib,json
        from experiments.query_contracts.scale_campaign import DATA
        manifest=json.loads((DATA/'manifest.json').read_text())
        for name,expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((DATA/name).read_bytes()).hexdigest(),expected)
        evaluation=json.loads((DATA/'runtime/evaluation.json').read_text())
        self.assertFalse({r['id'] for r in evaluation}.intersection(r['id'] for r in self.requests))
        # No selector, retrieval or labels are inspected for evaluation requests.
        self.assertEqual(len(evaluation),6)

    def test_real_gateway_mocked_truncation_retains_known_and_unknown_billing(self):
        import tempfile,json,httpx
        from pathlib import Path
        from unittest.mock import patch,MagicMock
        from experiments.query_contracts.scale_campaign import prepare,run,ROOT,read
        from experiments.query_contracts.scale_scoring import score
        for cost in ('0.001',None):
            (ROOT/'_workspace').mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
                w=Path(tmp)/'campaign';prepare(w,'development');self._authorize_test(w)
                response=httpx.Response(200,json={'model':'scripted-network-free', 'provider':'mock',
                    'usage':{'cost':cost,'prompt_tokens':123,'completion_tokens':45},
                    'choices':[{'finish_reason':'length','message':{'content':'truncated'}}]},
                    request=httpx.Request('POST','https://example.invalid'))
                client=MagicMock();client.__enter__.return_value.post.return_value=response
                with patch('experiments.query_contracts.scale_campaign.STUDY_LEDGER',w/'test.sqlite'),patch('experiments.query_contracts.scale_campaign.STUDY_LOCK',w/'test.lock'),patch('apps.factory_lab.llm.dotenv_values',return_value={'OPENROUTER_API_KEY':'SCRIPTED-NO-NETWORK'}),patch('apps.factory_lab.llm.httpx.Client',return_value=client):
                    result=run(w)
                self.assertEqual(result['status'],'stopped');self.assertEqual(result['budget']['attempts'],1)
                self.assertEqual(result['budget']['unresolved'],0 if cost is not None else 1)
                self.assertEqual(sum(s['status']=='unattempted' for s in result['slots']),35)
                failed=next(s for s in result['slots'] if s['status']=='failed')
                self.assertEqual(failed['calls'][0]['cost'],cost)
                self.assertEqual(failed['calls'][0]['usage']['prompt_tokens'],123)
                self.assertEqual(failed['calls'][0]['status'],'failed')
                self.assertEqual(result['budget']['reserved_nonrefunded_usd'],failed['calls'][0]['reserved_nonrefunded_usd'])
                rubric=read(ROOT/'research/query-contracts-1/catalog-scale-001/evaluation/development-rubric.json')
                summary=score(result,rubric)
                measured=next(g for g in summary['groups'] if g['failed_requests']==1)
                self.assertEqual(measured['reported_usd'],cost)
                self.assertEqual(measured['prompt_tokens'],123)
                self.assertEqual(measured['completion_tokens'],45)
                self.assertEqual(measured['usage_measured_calls'],1)
                self.assertFalse(read(w/'execution-gate.json')['approved'])

class CompoundCompositionTests(unittest.TestCase):
    def setUp(self):
        import json
        from pathlib import Path
        from experiments.query_contracts.composition_campaign import VIEWS,CATALOG
        from experiments.factory_complexity.tools import Views,RDFStudyTools
        from experiments.query_contracts.competing import CompetingTools
        self.tools=CompetingTools(RDFStudyTools(Views(VIEWS)))
        self.catalog=json.loads(CATALOG.read_text())['catalog']
        self.plan=json.loads(Path('research/query-contracts-1/authored-request.json').read_text())
        self.plan['model_unplanned']=[{'id':'delivery','reason':'no schedule service'}]
        self.visible=[c['tool'] for c in self.catalog]
        self.requirements=[{'id':k,'text':v} for k,v in self.plan['obligations'].items()]

    def test_model_decomposition_not_oracle_completed(self):
        import json
        from experiments.query_contracts.composition import parse_decomposition
        # Omission remains an observed model interpretation; no gold fills it in.
        req=parse_decomposition({'content':json.dumps({'requirements':[{'id':'one','text':'partial interpretation'}]})})
        self.assertEqual(len(req),1)
        with self.assertRaises(ValueError):parse_decomposition({'content':'{"requirements":[]}'})

    def test_planner_constructs_bindings_and_receives_same_fields(self):
        import json
        from experiments.query_contracts.composition import planning_packet
        a=planning_packet('original question',self.requirements,{},self.catalog,'full')
        b=planning_packet('original question',self.requirements,{},self.catalog,'retrieved')
        self.assertEqual(a['messages'][0],b['messages'][0])
        pa=json.loads(a['messages'][1]['content']);pb=json.loads(b['messages'][1]['content'])
        self.assertNotIn('steps',pa);self.assertNotIn('binding',pa)
        by={c['tool']:c for c in a['catalog']}
        self.assertTrue(all(c==by[c['tool']] for c in b['catalog']))
        self.assertEqual(pa['requirements'],pb['requirements'])

    def test_real_dag_chaining_retains_order_context_and_lineage(self):
        from experiments.query_contracts.composition import execute_plan
        r=execute_plan(self.plan,self.tools,self.visible)
        self.assertTrue(r['calls']);self.assertTrue(all(c['status']=='completed' for c in r['calls']))
        qualified=r['outputs']['qualifications'];self.assertTrue(qualified)
        self.assertTrue(all(len(x['lineage'])==3 for x in qualified))
        self.assertTrue(all('order' in x['context'] for x in qualified))
        self.assertGreater(len({x['context']['order']['id'] for x in qualified}),1)
        self.assertLessEqual(len(r['calls']),12)

    def test_wrong_dependency_preserved_and_checked_without_replacement(self):
        import copy
        from experiments.query_contracts.composition import checked_plan,execute_plan
        wrong=copy.deepcopy(self.plan);wrong['steps'][1]['binding']['path']='machine.id'
        raw=execute_plan(wrong,self.tools,self.visible)
        checked,rejected=checked_plan(wrong,self.visible)
        self.assertEqual(wrong['steps'][1]['tool'],'replacement_candidates')
        self.assertTrue(any('entity_type_not_verified' in s['issues'] for s in raw['steps'].values()))
        self.assertTrue(rejected);self.assertEqual(len(checked['steps']),1)

    def test_unplanned_report_is_not_semantic_completeness(self):
        from experiments.query_contracts.composition import execute_plan,report
        result=report(self.plan,execute_plan(self.plan,self.tools,self.visible),[])
        self.assertEqual(result['requirements']['delivery']['status'],'not_planned')
        self.assertTrue(all(r['semantic_satisfaction'].startswith('unverified') for r in result['requirements'].values()))
        self.assertIn('undeclared',result['scope'])

    def test_final_citations_are_outcomes_not_oracle_rejection(self):
        import json
        from experiments.query_contracts.composition import parse_answer
        body={'answer':'wrong citation retained','coverage':[{'id':r['id'],'status':'answered','evidence':['E999'],'explanation':'test'} for r in self.requirements],'additional_unresolved':[]}
        answer=parse_answer({'content':json.dumps(body)},self.requirements,{'calls':[]})
        self.assertEqual(len(answer['citation_reference_errors']),4)
        self.assertEqual(answer['answer'],body['answer'])

    def _test_model_file(self,root):
        import json
        from experiments.query_contracts.composition_campaign import ROOT
        config=json.loads((ROOT/'research/query-contracts-1/model-selection-001/models.json').read_text())[0]
        config['max_tokens']=3072
        path=root/'test-model.json';path.write_text(json.dumps(config));return path

    def _approve_mock(self,w):
        from datetime import datetime,timezone,timedelta
        from experiments.query_contracts.composition_campaign import read,write,sha
        s=read(w/'session.json');now=datetime.now(timezone.utc)
        if s['deadline'] is None:s.update(started_at=now.isoformat(),deadline=(now+timedelta(hours=1)).isoformat())
        s['status']='authorized';write(w/'session.json',s)
        a={k:s[k] for k in ('campaign_id','max_attempts','max_usd','deadline')};a.update(approved=True,human_message='TEST ONLY');write(w/'approval.json',a)
        g=read(w/'execution-gate.json');g.update(approved=True,approval_sha256=sha(w/'approval.json'));write(w/'execution-gate.json',g)

    def test_raw_input_only_closed_prepare(self):
        import tempfile
        from pathlib import Path
        from experiments.query_contracts.composition_campaign import prepare,preflight,ROOT,read
        (ROOT/'_workspace').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
            w=Path(tmp)/'campaign';p=prepare(w,self._test_model_file(Path(tmp)))
            self.assertEqual(p['max_attempts'],24);self.assertTrue(p['fits_cap'])
            self.assertTrue(all(set(q)=={'id','question'} for q in read(w/'questions.json')))
            self.assertFalse(read(w/'execution-gate.json')['approved'])
            self.assertTrue(all('rubric' not in p for p in read(w/'execution-gate.json')['files']))
            with self.assertRaisesRegex(RuntimeError,'closed'):preflight(w)

    def test_scripted_complete_pipeline_all_three_arms_or_billed_failure(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import patch
        from experiments.query_contracts.composition_campaign import prepare,run,ROOT,read
        original_plan=self.plan
        requirements=self.requirements
        class FakeGateway:
            def __init__(self,store,work_dir):self.store=store;self.session=read(Path(work_dir)/'session.json')
            def call(self,rid,messages):
                cid=self.store.reserve(rid,'0.01',self.session);self.store.settle(cid,'completed',{'cost':'0.001','usage':{'prompt_tokens':100,'completion_tokens':100}})
                stage=self.store.get(rid)['config']['stage']
                if stage=='decompose':body={'requirements':requirements}
                elif stage=='plan':body={'steps':original_plan['steps'],'unplanned':original_plan['model_unplanned']}
                else:body={'answer':'SCRIPTED ONLY','coverage':[{'id':r['id'],'status':'unresolved','evidence':[],'explanation':'scripted'} for r in requirements],'additional_unresolved':[]}
                return {'content':json.dumps(body)}
        for broken in (False,True):
            (ROOT/'_workspace').mkdir(exist_ok=True)
            with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
                w=Path(tmp)/'campaign';prepare(w,self._test_model_file(Path(tmp)));self._approve_mock(w)
                class Broken(FakeGateway):
                    def call(self,*args):super().call(*args);return {'content':'invalid-json'}
                with patch('experiments.query_contracts.composition_campaign.Gateway',Broken if broken else FakeGateway),patch('experiments.query_contracts.composition_campaign.LEDGER',w/'test.sqlite'),patch('experiments.query_contracts.composition_campaign.LOCK',w/'test.lock'):
                    result=run(w)
                self.assertEqual(result['budget']['attempts'],1 if broken else 24)
                self.assertEqual(result['status'],'stopped' if broken else 'completed')
                self.assertFalse(read(w/'execution-gate.json')['approved'])
                if not broken:
                    self.assertEqual(sum(len(c['arms']) for c in result['cases']),12)
                    self.assertTrue(all('answer' in a for c in result['cases'] for a in c['arms'].values()))
                    self.assertTrue(all(c['arms']['retrieved']['raw_plan']==c['arms']['checked']['raw_plan'] for c in result['cases']))
                else:self.assertEqual(result['cases'][0]['stages'][0]['calls'][0]['cost'],'0.001')


    def test_non_scalar_binding_is_step_issue_and_independent_step_continues(self):
        import copy,json
        from experiments.query_contracts.composition import parse_plan,execute_plan,checked_plan
        plan=copy.deepcopy(self.plan)
        plan['steps'][1]['binding']['path']='machine'
        plan['steps'].append({'id':'independent','obligation':'qualification','tool':'qualification_records','binding':{'literal':'M01','kind':'Machine'}})
        parsed=parse_plan({'content':json.dumps({'steps':plan['steps'],'unplanned':plan['model_unplanned']})},self.requirements)
        result=execute_plan(parsed,self.tools,self.visible)
        self.assertIn('non_scalar_output_binding',result['steps']['candidates']['issues'])
        self.assertTrue(result['outputs']['independent'])
        self.assertEqual(parsed['steps'][1]['binding']['path'],'machine')
        checked,rejected=checked_plan(parsed,self.visible)
        self.assertTrue(rejected);self.assertIn('independent',[s['id'] for s in checked['steps']])

    def test_one_code_fence_is_transport_only_and_prose_is_not_repaired(self):
        from experiments.query_contracts.composition import response_json
        self.assertEqual(response_json({'content':'```json\n{"x":1}\n```'}),{'x':1})
        with self.assertRaises(ValueError):response_json({'content':'Explanation\n```json\n{"x":1}\n```'})
        with self.assertRaises(ValueError):response_json({'content':'```json\n{"x":}\n```'})

    def test_manual_format_recovery_reuses_two_responses_without_refund_or_new_window(self):
        import tempfile,json,httpx,hashlib
        from pathlib import Path
        from unittest.mock import patch,MagicMock
        from experiments.query_contracts.composition_campaign import prepare,prepare_format_recovery,run,ROOT,read
        requirements=self.requirements;plan=self.plan
        def fake_post(url,headers,json):
            import json as codec
            system=json['messages'][0]['content']
            if 'enumerate each distinct' in system:body={'requirements':requirements};fence=False
            elif 'Create an ordered query DAG' in system:body={'steps':plan['steps'],'unplanned':plan['model_unplanned']};fence=True
            else:body={'answer':'SCRIPTED ONLY','coverage':[{'id':r['id'],'status':'unresolved','evidence':[],'explanation':'scripted'} for r in requirements],'additional_unresolved':[]};fence=False
            text=codec.dumps(body);text='```json\n'+text+'\n```' if fence else text
            return httpx.Response(200,json={'model':'mock','provider':'mock','usage':{'cost':'0.001','prompt_tokens':100,'completion_tokens':100},'choices':[{'finish_reason':'stop','message':{'content':text}}]},request=httpx.Request('POST','https://example.invalid'))
        (ROOT/'_workspace').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'_workspace') as tmp:
            root=Path(tmp);old=root/'old';new=root/'new';prepare(old,self._test_model_file(root));self._approve_mock(old)
            client=MagicMock();client.__enter__.return_value.post.side_effect=fake_post
            with patch('experiments.query_contracts.composition_campaign.LEDGER',root/'shared.sqlite'),patch('experiments.query_contracts.composition_campaign.LOCK',root/'shared.lock'),patch('apps.factory_lab.llm.dotenv_values',return_value={'OPENROUTER_API_KEY':'SCRIPTED-NO-NETWORK'}),patch('apps.factory_lab.llm.httpx.Client',return_value=client):
                with patch('experiments.query_contracts.composition_campaign.parse_plan',side_effect=ValueError('old strict parser rejected code fence')):
                    failed=run(old)
                self.assertEqual(failed['budget']['attempts'],2);self.assertEqual(failed['status'],'stopped')
                original_hash=hashlib.sha256((old/'progress.json').read_bytes()).hexdigest()
                prepare_format_recovery(old,new);self._approve_mock(new);result=run(new)
                self.assertEqual(result['status'],'completed');self.assertEqual(result['budget']['attempts'],24)
                self.assertEqual(client.__enter__.return_value.post.call_count,24)
                self.assertEqual(read(old/'session.json')['deadline'],read(new/'session.json')['deadline'])
                self.assertEqual(hashlib.sha256((old/'progress.json').read_bytes()).hexdigest(),original_hash)
                self.assertEqual(result['cases'][0]['stages'][1]['status'],'reused_format_normalized')
                self.assertEqual(result['cases'][0]['stages'][1]['original_status'],'failed')
                self.assertFalse(read(new/'execution-gate.json')['approved'])
