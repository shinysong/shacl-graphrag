"""Scripted software controls, not measured LLM answers or efficacy."""
import copy
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from apps.factory_lab.agent import Runner, SYSTEM
from apps.factory_lab.store import Store
from apps.factory_lab.branching import freeze_bundle, final_packet
from apps.factory_lab.evidence import canonical, model_evidence
from apps.factory_lab.store import dumps

class BranchTests(unittest.TestCase):
    def execute(self, failure=None, cancel=False, tool_failure=False):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        store=Store(Path(directory.name)/'state.sqlite')
        class Graph:
            count=0
            def run(self,version,name,args):
                self.count+=1
                if tool_failure:raise RuntimeError('Synthetic graph error')
                return {'tool':name,'arguments':args,'rows':[], 'evidence_id':'E1',
                        'query':'TRANSPORT_QUERY', 'backend':'BACKEND_NAME',
                        'integrity':{'transport':'AUDIT_ONLY'}}
        class Gateway:
            def __init__(self,store):self.calls=[]
            def call(self,rid,messages,tools=None):
                self.calls.append((copy.deepcopy(messages),tools))
                n=len(self.calls)
                if n==1:return {'tool_calls':[{'id':'t','function':{'name':'impacted_orders','arguments':'{"machine_id":"M02"}'}}]}
                if n==2:return {'content':'Actual-path scripted draft [E1]'}
                if n==failure:raise RuntimeError('Scripted provider failure')
                if cancel and n==3:runner.cancel_flags[rid].set()
                return {'content':f'Scripted final {n} [E1]'}
        graph=Graph();gateway=Gateway(store)
        runner=Runner(store,graph,lambda _:gateway)
        config={'question':'M02?', 'snapshot':'factory-v2','review':'compare'}
        rid=store.create(config);runner.cancel_flags[rid]=threading.Event();runner.lock.acquire()
        runner.execute(rid,config)
        return store,rid,graph,gateway,runner

    def test_one_retrieval_three_frozen_isolated_finals(self):
        store,rid,graph,gateway,runner=self.execute()
        self.assertEqual(graph.count,1);self.assertEqual(len(gateway.calls),5)
        self.assertEqual(store.get(rid)['status'],'completed')
        events=store.events(rid)
        frozen=next(e['payload'] for e in events if e['kind']=='evidence_frozen')
        self.assertEqual(frozen['bundle']['draft'],'Actual-path scripted draft [E1]')
        finals=[e for e in events if e['kind']=='branch_final']
        self.assertEqual([e['payload']['arm'] for e in finals],['self','python','shacl'])
        self.assertTrue(all(e['payload']['bundle_sha256']==frozen['sha256'] for e in finals))
        self.assertTrue(all(tools is None for _,tools in gateway.calls[2:]))
        self.assertEqual(gateway.calls[3],gateway.calls[4])
        self.assertNotIn('Scripted final 3',str(gateway.calls[3:]))
        self.assertEqual(Store(store.path).events(rid),events)
        self.assertEqual(store.budget()['attempts'],0)
        self.assertEqual(frozen['bundle']['evidence'][0]['query'],'TRANSPORT_QUERY')
        for messages,_ in gateway.calls[1:]:
            self.assertNotIn('TRANSPORT_QUERY',str(messages))
            self.assertNotIn('BACKEND_NAME',str(messages))
            self.assertNotIn('AUDIT_ONLY',str(messages))
        from apps.factory_lab.planning import user_turns
        self.assertEqual(user_turns(store,'next',rid),['M02?','next'])

    def test_failure_keeps_denominator_and_prevents_remaining_calls(self):
        store,rid,graph,gateway,_=self.execute(failure=4)
        events=store.events(rid)
        self.assertEqual(store.get(rid)['status'],'failed')
        self.assertEqual(len(gateway.calls),4)
        plan=next(e['payload'] for e in events if e['kind']=='comparison_plan')
        self.assertEqual(len(plan['arms']),3)
        self.assertEqual([e['payload']['arm'] for e in events if e['kind']=='branch_final'],['self'])
        self.assertEqual([e['payload']['arm'] for e in events if e['kind']=='branch_failed'],['python'])
        self.assertNotIn('comparison_completed',[e['kind'] for e in events])

    def test_tool_failure_is_visible_but_not_successful_evidence(self):
        store,rid,_,gateway,_=self.execute(tool_failure=True)
        events=store.events(rid)
        self.assertEqual(len([e for e in events if e['kind']=='tool_failed']),1)
        self.assertFalse(any(e['kind']=='tool_completed' for e in events))
        frozen=next(e['payload'] for e in events if e['kind']=='evidence_frozen')
        self.assertEqual(frozen['bundle']['evidence'],[])
        message=json.loads(next(m['content'] for m in gateway.calls[1][0] if m['role']=='tool'))
        self.assertEqual(message['error'],'RuntimeError')
        self.assertIn('not evidence of source absence',message['message'])

    def test_cancel_retains_completed_branch_and_stops(self):
        store,rid,_,gateway,_=self.execute(cancel=True)
        self.assertEqual(store.get(rid)['status'],'cancelled')
        self.assertEqual(len(gateway.calls),3)
        self.assertEqual(len([e for e in store.events(rid) if e['kind']=='branch_final']),1)

    def test_frozen_detached_and_tamper_rejected(self):
        evidence=[];frozen=freeze_bundle('q','draft',evidence,SYSTEM,{'sha256':'test'})
        evidence.append({'external':'mutation'})
        self.assertEqual(frozen['bundle']['evidence'],[])
        frozen['bundle']['draft']='edited'
        with self.assertRaises(ValueError):final_packet(frozen,'self')

    def test_backend_prompt_parity_preserves_row_order_and_scope(self):
        left={'tool':'find_entities','arguments':{'query':'M'},'rows':[{'id':'M02','name':'B'},{'id':'M01','name':'A'}],
              'source_sha256':'same','scope':'selected','limit_reached':True,'query':'cypher','backend':'neo4j'}
        right=copy.deepcopy(left)
        right['rows']=[dict(reversed(list(row.items()))) for row in right['rows']]
        right.update(query='sparql',backend='neptune',integrity={'verified':True})
        self.assertEqual(canonical(model_evidence(left)),canonical(model_evidence(right)))
        a=freeze_bundle('q','draft',[left],SYSTEM,{})
        b=freeze_bundle('q','draft',[right],SYSTEM,{})
        self.assertNotEqual(a['sha256'],b['sha256'])  # Audit transport differs.
        self.assertEqual(final_packet(a,'self')[1],final_packet(b,'self')[1])
        content=json.loads(final_packet(a,'self')[1][1]['content'])['evidence'][0]
        self.assertEqual([r['id'] for r in content['rows']],['M02','M01'])
        self.assertTrue(content['limit_reached'])
        self.assertEqual(content['scope'],'selected')

    def test_legacy_bundle_preserved_and_unknown_contract_rejected(self):
        frozen=freeze_bundle('q','draft',[{'query':'legacy query','rows':[]}],SYSTEM,{})
        del frozen['bundle']['model_evidence_contract']
        frozen['sha256']=hashlib.sha256(dumps(frozen['bundle']).encode()).hexdigest()
        self.assertIn('legacy query',final_packet(frozen,'self')[1][1]['content'])
        frozen['bundle']['model_evidence_contract']='future-contract'
        frozen['sha256']=hashlib.sha256(dumps(frozen['bundle']).encode()).hexdigest()
        with self.assertRaises(ValueError):final_packet(frozen,'self')

    def test_saved_backend_evidence_has_identical_model_bytes(self):
        root=Path(__file__).resolve().parents[1]/'research/virtual-factory-llm-1'
        count=0
        for path in sorted((root/'backend-parity-002').glob('neptune_sparql-factory-*.json')):
            suffix=path.name.removeprefix('neptune_sparql-')
            neptune=json.loads(path.read_text())
            neo4j=json.loads((root/'backend-parity-001'/('neo4j_cypher-'+suffix)).read_text())
            rdflib=json.loads((root/'backend-parity-002'/('rdflib_sparql-'+suffix)).read_text())
            self.assertEqual(canonical(model_evidence(neptune)),canonical(model_evidence(neo4j)))
            self.assertEqual(canonical(model_evidence(neptune)),canonical(model_evidence(rdflib)))
            count+=1
        self.assertEqual(count,48)

if __name__=='__main__':unittest.main()

class CoverageTests(unittest.TestCase):
    def selected(self):
        from apps.factory_lab.rdf_graph import RDFLibGraph
        # Use the existing actual RDFLib adapter, no server or API calls.
        graph=RDFLibGraph()
        return [graph.run('factory-v3', 'inspect_entity', {'entity_id':eid}) | {'evidence_id':f'E{i}'}
                for i,eid in enumerate(['M03','O17','O18'],1)]

    def test_alternate_path_and_no_cross_product(self):
        from apps.factory_lab import coverage
        evidence=self.selected();snap={'version':'factory-v3','sha256':evidence[0]['source_sha256'],'as_of':evidence[0]['as_of']}
        targets=[{'order_id':'O17','machine_id':'M03','quote':'q'},{'order_id':'O18','machine_id':'M03','quote':'q'}]
        a=coverage.review(evidence,'python',targets,snap);b=coverage.review(evidence,'shacl',targets,snap)
        self.assertEqual(a['flags'],b['flags']);self.assertEqual(a['candidate_count'],2)
        self.assertEqual([t['status'] for t in a['coverage']['targets']],['checked','checked'])
        self.assertEqual(coverage.review(evidence,'python',[],snap)['candidate_count'],0)
        # Removing the order's positive requirement relation does not mean it fails.
        e=copy.deepcopy(evidence);e[1]['rows']=[]
        r=coverage.review(e,'python',targets,snap)
        self.assertEqual(r['coverage']['targets'][0]['status'],'not_assessed')
        self.assertEqual(r['candidate_count'],1)
        # Provenance mismatch is explicit and never supplemented from source.
        e=copy.deepcopy(evidence);e[0]['source_sha256']='other'
        r=coverage.review(e,'python',targets,snap)
        self.assertEqual(r['coverage']['rejected_evidence_ids'],['E1'])
        self.assertEqual(r['candidate_count'],0)
        e=copy.deepcopy(evidence);e.append(copy.deepcopy(e[0]))
        e[-1]['rows'][0]['entity']['status']='conflicting'
        self.assertEqual(coverage.review(e,'python',targets,snap)['candidate_count'],0)
        frozen=freeze_bundle('q','draft',evidence,SYSTEM,snap,review_targets=targets)
        p,pm=final_packet(frozen,'python');s,sm=final_packet(frozen,'shacl')
        self.assertEqual(pm,sm)
        legacy=freeze_bundle('q','draft',evidence,SYSTEM,snap)
        self.assertEqual(final_packet(legacy,'python')[0]['candidate_count'],0)
        self.assertNotIn('coverage',final_packet(legacy,'python')[0])
        self.assertEqual(final_packet(frozen,'self')[0]['checked_candidates'],[])

    def test_declaration_attribution_not_semantic_truth(self):
        from apps.factory_lab import coverage
        target={'order_id':'O17','machine_id':'M03','quote':'검토'}
        self.assertEqual(coverage.declarations({'targets':[target]},['검토해주세요']),[target])
        with self.assertRaises(ValueError):coverage.declarations({'targets':[target]},['다른 질문'])
        with self.assertRaises(ValueError):coverage.declarations({'targets':[target]*25},['검토'])
        with self.assertRaises(ValueError):coverage.declarations({'targets':[target|{'gold':True}]},['검토'])

    def test_scripted_declaration_is_not_graph_evidence(self):
        from apps.factory_lab import coverage
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'state.sqlite')
            class Graph:
                def run(self,*args):raise AssertionError('Declaration must not query graph')
            class Gateway:
                count=0
                def call(self,rid,messages,tools=None):
                    self.count+=1
                    if self.count==1:
                        self.has_declaration=any(t['function']['name']==coverage.TOOL_NAME for t in tools)
                        return {'tool_calls':[{'id':'target','function':{'name':coverage.TOOL_NAME,'arguments':json.dumps({'targets':[{'order_id':'O17','machine_id':'M03','quote':'검토'}]})}}]}
                    return {'content':'Scripted only'}
            gateway=Gateway();runner=Runner(store,Graph(),lambda _:gateway,coverage_review=True)
            config={'question':'검토','snapshot':'factory-v3','review':'compare'}
            rid=store.create(config);runner.cancel_flags[rid]=threading.Event();runner.lock.acquire();runner.execute(rid,config)
            self.assertEqual(store.get(rid)['status'],'completed');self.assertTrue(gateway.has_declaration)
            events=store.events(rid)
            self.assertFalse(any(e['kind']=='tool_completed' for e in events))
            frozen=next(e['payload']['bundle'] for e in events if e['kind']=='evidence_frozen')
            self.assertEqual(frozen['evidence'],[]);self.assertEqual(len(frozen['review_targets']),1)
            reports=[e['payload']['report'] for e in events if e['kind']=='branch_report']
            self.assertTrue(all(r['assessment']=='not_assessed' for r in reports))
            self.assertEqual(store.budget()['attempts'],0)

    def test_catalog_isolation_and_planning_start(self):
        from unittest.mock import patch
        from apps.factory_lab.graph import TOOLS
        original=copy.deepcopy(TOOLS)
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'state.sqlite')
            first=Runner(store,coverage_review=True);second=Runner(store,coverage_review=True)
            legacy=Runner(store)
            self.assertEqual(TOOLS,original);self.assertEqual(legacy.tool_catalog,original)
            self.assertEqual(first.tool_catalog,second.tool_catalog)
            self.assertEqual(len(first.tool_catalog),len(original)+1)
            with patch('apps.factory_lab.agent.threading.Thread'):
                rid=first.start({'question':'검토','snapshot':'factory-v3','review':'compare','planning':True})
            self.assertTrue(store.get(rid)['config']['planning']);first.lock.release()
