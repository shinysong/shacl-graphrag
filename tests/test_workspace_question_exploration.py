"""Scripted coordinator checks, not live answer efficacy measurements."""
import json
import unittest
from copy import deepcopy
from apps.factory_lab import preparation as p, workspace_question as q
from tests.test_preparation import example
from tests.workspace_fixtures import approved

class ExplorationQuestionTests(unittest.TestCase):
    def run_question(self,draft,responses):
        messages=[];snapshots=[];items=iter(responses)
        def call(packet):
            messages.append(deepcopy(packet));return {'content':json.dumps(next(items))}
        result=q.ask(draft,'Explain these data and the requested task',call,lambda v:snapshots.append(deepcopy(v)))
        return result,messages,snapshots

    def test_pending_overview_reaches_answer_with_citation(self):
        draft=p.create(*example());before=deepcopy(draft)
        result,messages,_=self.run_question(draft,[{'calls':[{'tool':'explore_repository','arguments':{'action':'overview'}}],'unresolved':[]},{'answer':'Source overview only','citations':['e1'],'unresolved':[]}])
        self.assertEqual(result['evidence'][0]['result']['source_count'],len(draft['sources']))
        packet=json.loads(messages[-1][1]['content']);self.assertEqual(packet['evidence'][0]['id'],'e1')
        self.assertEqual(draft,before);self.assertEqual(len(messages),2)

    def test_discovery_then_specific_samples_keeps_global_evidence_ids(self):
        draft=p.create(*example());entry=next(e for e in draft['entries'] if e['kind']=='mapping' and next(s for s in draft['sources'] if s['name']==e['source']['file']).get('rows'))
        actions=[{'action':'overview'},{'action':'list','source':entry['source']['file']},{'action':'detail','entry_id':entry['id']}]
        responses=[{'calls':[{'tool':'explore_repository','arguments':a}],'needs_followup':i<2,'unresolved':[]} for i,a in enumerate(actions)]
        responses.append({'answer':'Bounded saved examples','citations':['e1','e2','e3'],'unresolved':[]})
        result,messages,_=self.run_question(draft,responses)
        self.assertEqual(len(messages),4);self.assertEqual([e['id'] for e in result['evidence']],['e1','e2','e3'])
        self.assertEqual(result['evidence'][2]['result']['annotations']['review_status'],'pending')
        self.assertTrue(result['evidence'][2]['result']['samples'])
        self.assertEqual(len(json.loads(messages[2][1]['content'])['previous_evidence']),2)

    def test_compound_exploration_and_approved_lookup(self):
        result,_,snapshots=self.run_question(approved(),[{'calls':[{'tool':'explore_repository','arguments':{'action':'overview'}},{'tool':'source_lookup','arguments':{'table':'orders','identifier':'O1'}}],'unresolved':['Refund execution unsupported']},{'answer':'Overview and O1 recorded facts','citations':['e1','e2'],'unresolved':[]}])
        self.assertEqual(result['evidence'][1]['state'],'completed')
        self.assertTrue(any(v.get('phase')=='retrieving' and len(v['evidence'])==2 and v['evidence'][1]['state']=='running' for v in snapshots))
        self.assertIn('Refund execution unsupported',result['unresolved'])

    def test_pending_exploration_does_not_authorize_business_lookup(self):
        result,_,_=self.run_question(p.create(*example()),[{'calls':[{'tool':'explore_repository','arguments':{'action':'overview'}},{'tool':'source_lookup','arguments':{'table':'orders','identifier':'O1'}}],'unresolved':[]},{'answer':'Schema inspected; order lookup failed','citations':['e1'],'unresolved':['Order approval needed']}])
        self.assertEqual(result['evidence'][1]['state'],'failed');self.assertIn('source absence has not been established',result['unresolved'][0])

    def test_no_tool_plan_reports_execution_scope(self):
        result,messages,_=self.run_question(p.create(*example()),[{'calls':[],'unresolved':['Unsupported action']},{'answer':'Uploaded data exist; this action is unsupported','citations':[],'unresolved':['Unsupported action']}])
        packet=json.loads(messages[-1][1]['content']);self.assertGreater(packet['execution_scope']['source_count'],0)
        self.assertEqual(packet['execution_scope']['no_evidence_reason'],'no_tool_selected')

    def test_large_catalog_navigation_is_bounded_not_silent_full_catalog(self):
        raw={'source_rows':[{'entry_id':str(i),'description':'x'*1000} for i in range(100)],'explore_repository':{'name':'explore_repository'}}
        compact=q.navigation_catalog(raw);self.assertEqual(compact['source_rows']['available_count'],100)
        page=q.catalog_page(raw,{'tool':'source_rows','offset':4});self.assertEqual(page['items'][0]['entry_id'],'4');self.assertEqual(page['next_offset'],8)
        self.assertEqual(len(raw['source_rows']),100)

    def test_explicit_resolution_preserves_history_and_unsupported_part(self):
        plan={'calls':[{'tool':'explore_repository','arguments':{'action':'overview'}}], 'unresolved':['Inspect source structure','Issue a refund']}
        final={'answer':'Observed structure; refund unavailable','citations':['e1'],'unresolved':['Issue a refund'], 'resolved_requirements':[{'requirement':'Inspect source structure','citations':['e1'],'explanation':'Overview returned the saved sources'}]}
        result,_,_=self.run_question(approved(),[plan,final])
        self.assertEqual(result['unresolved'],['Issue a refund'])
        self.assertEqual(result['planning_unresolved'],plan['unresolved'])
        self.assertEqual(result['plans'][0]['unresolved'],plan['unresolved'])
        self.assertEqual(result['resolution_authority'],'model_interpretation_not_verified_truth')

    def test_resolution_cannot_reference_unknown_or_uncited_evidence(self):
        plan={'calls':[{'tool':'explore_repository','arguments':{'action':'overview'}}], 'unresolved':['Inspect']}
        for citations in ([],['e999']):
            final={'answer':'Observed','citations':['e1'],'unresolved':[], 'resolved_requirements':[{'requirement':'Inspect','citations':citations,'explanation':'Claim'}]}
            with self.assertRaises(ValueError):self.run_question(approved(),[plan,final])

    def test_resolution_binding_boundaries_do_not_certify_semantics(self):
        from apps.factory_lab.workspace_requirement_review import reconcile
        item={'requirement':'Inspect','citations':['e1'],'explanation':'A model claim, not a semantic proof'}
        base={'answer':'Claim','citations':['e1'],'unresolved':[], 'resolved_requirements':[item]}
        # A semantically unsupported declaration is intentionally not repaired by an oracle.
        self.assertEqual(reconcile(['Inspect'],base,{'e1'})['unresolved'],[])
        variants=[]
        uncited=deepcopy(base);uncited['resolved_requirements'][0]['citations']=['e2'];variants.append((uncited,{'e1','e2'}))
        duplicate=deepcopy(base);duplicate['resolved_requirements'].append(deepcopy(item));variants.append((duplicate,{'e1'}))
        conflicting=deepcopy(base);conflicting['unresolved']=['Inspect'];variants.append((conflicting,{'e1'}))
        variants.append((base,set()))  # failed evidence is absent from successful evidence IDs
        for final,valid in variants:
            with self.subTest(final=final,valid=valid),self.assertRaises(ValueError):
                reconcile(['Inspect'],final,valid)
