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
