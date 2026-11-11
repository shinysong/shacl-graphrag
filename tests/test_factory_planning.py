import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from apps.factory_lab.planning import validate_interpretation, user_turns
from apps.factory_lab.agent import Runner
from apps.factory_lab.store import Store

class PlanningTests(unittest.TestCase):
    def plan(self):
        return {'goals':[{'text':'Compare options','source_turn':0,'quote':'O17'}],
            'constraints':[{'text':'No assignment changes','source_turn':0,'quote':'배정 변경 금지','state':'active'}],
            'user_reports':[], 'unknowns':['schedule unavailable'],
            'steps':[{'id':'S1','question':'Inspect order','tool':'inspect_entity','arguments':{'entity_id':'O17'},'depends_on':[],'status':'ready','reason':'Obtain source context'},
                     {'id':'S2','question':'Load check','tool':None,'arguments':None,'depends_on':['S1'],'status':'unsupported','reason':'No load tool'}],
            'clarifications':[]}
    def test_quotes_and_dag_and_arbitrary_queries(self):
        turns=['O17 배정 변경 금지']
        self.assertEqual(validate_interpretation(json.dumps(self.plan()),turns),self.plan())
        variants=[]
        p=self.plan();p['goals'][0]['quote']='invented';variants.append(p)
        p=self.plan();p['goals'][0]['source_turn']=True;variants.append(p)
        p=self.plan();p['steps'][0]['depends_on']=['S2'];variants.append(p)
        p=self.plan();p['steps'][0]['tool']='run_cypher';variants.append(p)
        p=self.plan();p['steps'][1]['tool']='inspect_entity';variants.append(p)
        for p in variants:
            with self.assertRaises((ValueError,TypeError)):validate_interpretation(json.dumps(p),turns)
    def test_duplicate_keys_and_limits(self):
        raw=json.dumps(self.plan())
        with self.assertRaises(ValueError):validate_interpretation(raw[:-1]+',"goals":[]}', ['O17 배정 변경 금지'])
        p=self.plan();p['unknowns']=['x']*9
        with self.assertRaises(ValueError):validate_interpretation(json.dumps(p), ['O17 배정 변경 금지'])
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'db');rid=s.create({'question':'x'*6001});s.status(rid,'completed','')
            with self.assertRaises(ValueError):user_turns(s,'y'*2000,rid)

    def test_semantically_wrong_but_valid_interpretation_is_not_repaired(self):
        p=self.plan();p['constraints'][0]['text']='Allocation changes are allowed'
        # A real quote does not prove correct interpretation; preserve for external scoring.
        self.assertEqual(validate_interpretation(json.dumps(p),['O17 배정 변경 금지']),p)
    def test_bounded_user_history_including_compare_parent(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'db');a=s.create({'question':'O18 하루 지연 가능','review':'compare'});s.status(a,'completed','')
            b=s.create({'question':'O18도 지연 불가','parent_id':a,'review':'self'});s.status(b,'completed','Untrusted assistant assertion')
            self.assertEqual(user_turns(s,'다시 비교',b),['O18 하루 지연 가능','O18도 지연 불가','다시 비교'])
            for i in range(4):
                c=s.create({'question':'more','parent_id':b});s.status(c,'completed','');b=c
            with self.assertRaises(ValueError):user_turns(s,'too many',b)
    def test_real_runner_stage_freeze_and_failure_no_repair(self):
        for malformed in (False,True):
            with self.subTest(malformed=malformed),tempfile.TemporaryDirectory() as d:
                s=Store(Path(d)/'db');plan=self.plan();calls=[]
                class G:
                    def run(self,*args):raise AssertionError('No graph call requested by stub')
                class L:
                    def __init__(self,store):pass
                    def call(self,rid,messages,tools=None):
                        calls.append(copy.deepcopy(messages))
                        if len(calls)==1:return {'content':'not JSON' if malformed else json.dumps(plan)}
                        return {'content':'Scripted answer, not LLM measurement'}
                r=Runner(s,G(),L);config={'question':'O17 배정 변경 금지','snapshot':'factory-v2','review':'compare','planning':True}
                rid=s.create(config);r.lock.acquire();r.cancel_flags[rid]=threading.Event();r.execute(rid,config)
                events=s.events(rid);kinds=[e['kind'] for e in events]
                if malformed:
                    self.assertEqual(len(calls),1);self.assertEqual(s.get(rid)['status'],'failed');self.assertIn('interpretation_raw',kinds);self.assertNotIn('draft',kinds)
                else:
                    self.assertEqual(s.get(rid)['status'],'completed');self.assertEqual(len(calls),5)
                    frozen=next(e['payload']['bundle'] for e in events if e['kind']=='evidence_frozen')
                    self.assertEqual(frozen['request_context']['interpretation'],plan)
                    self.assertEqual(calls[-1],calls[-2])
                    for message in calls[-3:]:self.assertIn('배정 변경 금지',message[1]['content'])
                self.assertEqual(s.budget()['attempts'],0)
    def test_runtime_cases_exclude_annotations_and_match_ids(self):
        p=Path('research/virtual-factory-llm-1/compound-requests');runtime=json.loads((p/'runtime.json').read_text());gold=json.loads((p/'evaluation-only.json').read_text())['items']
        self.assertEqual(len(runtime),9);self.assertEqual({r['id'] for r in runtime},{r['id'] for r in gold})
        self.assertEqual(sum(len(r['turns']) for r in runtime),12)
        for r in runtime:self.assertEqual(set(r),{'id','snapshot','turns'})

if __name__=='__main__':unittest.main()
