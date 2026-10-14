import copy
import unittest
from scripts import run_refresh_fallback_study as f
from scripts import run_semantic_guard_study as g
from scripts import run_shared_semantics_study as base


class RefreshFallbackTests(unittest.TestCase):
    def fixture(self, *args, **kwargs):
        original, initial=base.baseline(24,17)
        snapshot=args[0] if args else kwargs.get('snapshot','initial')
        fault=args[1] if len(args)>1 else kwargs.get('fault','clean')
        subject=args[2] if len(args)>2 else kwargs.get('subject','p0')
        source,config=base.snapshot(original,initial,snapshot)
        deployed=base.deploy('shared_json_projection',source,config,original,initial,fault,'audit')
        installed=deployed['configs']['shared'];actuals={}
        for t in g.TASKS:
            evidence=base.retrieve_json(deployed['data'],installed,subject,True)
            actuals[t]=dict(evidence=evidence,output=base.decide(evidence,installed,t))
        publisher=copy.deepcopy(config)
        if fault=='common_wrong_mapping':publisher['location_field']='tax_country'
        packet=g.make_packet(actuals,deployed['configs'],publisher,source,original if fault=='stale_projection' else source,subject,deployed['projection'],deployed['provenance']['projected_location_field'])
        packet['subject']=subject
        return packet,source,config

    def test_failed_refresh_keeps_valid_countries_not_stale_recommendation(self):
        packet,_,_=self.fixture('cost_change','stale_projection','p4')
        calls=[]
        def fetch():
            calls.append(1);raise f.refresh.SourceUnavailable('outage')
        result=f.runtime_policy(packet,g.CATALOGS['documented'],fetch)
        self.assertEqual(len(calls),1)
        self.assertTrue(result['allowed']['countries']);self.assertTrue(result['allowed']['audit'])
        self.assertFalse(result['allowed']['recommend'])
        self.assertEqual(result['fallback_selected'],dict(countries=True,audit=True,recommend=False))
        self.assertEqual(result['actuals'],packet['actuals'])

    def test_mixed_outputs_rechecked_for_cross_conflict(self):
        packet,_,_=self.fixture(subject='p4')
        refreshed=copy.deepcopy(packet)
        refreshed['actuals']['countries']['output']['value']=['C2']
        result=f.preserve_valid(packet,refreshed,dict(countries=True,audit=False,recommend=True),True,g.CATALOGS['documented'])
        self.assertTrue(result['fallback_selected']['audit'])
        self.assertFalse(result['allowed']['audit'])
        self.assertEqual(result['checks']['audit']['cross']['status'],'conflict')

    def test_semantic_failure_never_bypassed(self):
        packet,_,_=self.fixture(fault='common_wrong_mapping')
        def forbidden():self.fail('semantic conflict must not fetch')
        result=f.runtime_policy(packet,g.CATALOGS['documented'],forbidden)
        self.assertFalse(any(result['allowed'].values()))
        self.assertFalse(any(result['fallback_selected'].values()))
