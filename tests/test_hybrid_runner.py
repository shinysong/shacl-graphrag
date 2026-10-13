"""Offline runner invariants, not model benchmark evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from scripts import run_hybrid_complexity as study


class HybridRunnerTests(unittest.TestCase):
    def test_post_only_vetoes_positive(self):
        check = {'decision': 'abstain', 'evidence_ids': ['r']}
        for decision, expected in [('allow', 'abstain'), ('deny', 'deny'), ('abstain', 'abstain')]:
            proposal = {'decision': decision, 'evidence_ids': []}
            self.assertEqual(study.veto(proposal, check, 'allow')['decision'], expected)
            self.assertEqual(proposal['decision'], decision)
        self.assertEqual(study.report_input({'decision': 'deny', 'atoms': {'path': 'fail'}, 'issues': [], 'gold': 'secret'}),
                         {'atoms': {'path': 'fail'}, 'issues': []})

    def test_independent_bounded_connectivity(self):
        records = [{'id': str(i), 'subject': a, 'object': b, 'relation': 'direct', 'status': 'ACTIVE', 'registration': 'PUBLISHED'}
                   for i, (a, b) in enumerate([('a','b'), ('b','c'), ('c','d'), ('x','y')])]
        for target, depth, decision in [('d',3,'reachable'), ('d',2,'not_reachable'), ('y',4,'not_reachable')]:
            case = {'contract': {'subject':'a','target':target,'max_hops':depth}, 'records': records}
            code, symbolic = study.gleif_checks(case)
            self.assertEqual(code['decision'], decision)
            self.assertEqual(symbolic['decision'], decision)
            self.assertIn('ASK', symbolic['query'])

    def test_wrong_citations_and_truth_are_outcomes(self):
        p = {'decision':'allow','evidence_ids':['invented']}
        study.validate_prediction(p, {'allow','deny','abstain'})
        score = study.scored(p, {'expected_decision':'allow','original_truth_decision':'deny'}, {'records':[]}, 'synthetic')
        self.assertTrue(score['contract_correct'])
        self.assertTrue(score['unsafe_positive'])
        self.assertFalse(score['citation_ids_exist'])

    def test_cost_reservation_and_unknown_cost_stop(self):
        for cost in (0.00001, None, -1, '0.1', float('nan'), 99):
            with self.subTest(cost=cost), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                ledger = root / '_workspace/expanded-study/campaign-budget.json'
                ledger.parent.mkdir(parents=True)
                ledger.write_text(json.dumps({'attempts':0,'reserved_usd':0,'reservations':[]}))
                output = root / 'run'
                output.mkdir()
                def handler(request):
                    self.assertEqual(json.loads(ledger.read_text())['attempts'], 1)
                    return httpx.Response(200, text=json.dumps({'usage': {'cost': cost}, 'choices': [{'message': {'content': '{"decision":"allow","evidence_ids":[]}'}, 'finish_reason':'stop'}]}))
                client = httpx.Client(transport=httpx.MockTransport(handler))
                with patch.object(study, 'ROOT', root), patch.object(study, 'dotenv_values', return_value={'OPENROUTER_API_KEY':'mock'}):
                    gateway = study.Gateway(output,calls=3,usd=.01,client=client)
                    if cost == .00001:
                        result, _ = gateway.generate({'records':[]}, output/'call')
                        self.assertEqual(result['decision'], 'allow')
                    else:
                        with self.assertRaises(study.UnknownCost):
                            gateway.generate({'records':[]}, output/'call')
                        self.assertTrue(gateway.coordinator.stopped.is_set())
                        self.assertEqual(gateway.coordinator.budget()['missing_cost'],1)
                    gateway.close()
                self.assertTrue((output/'call/request.json').exists())
                self.assertTrue((output/'call/response.json').exists())

    def test_offline_run_preserves_full_grid_and_freeze(self):
        cases, gold = study.core.generate_cases()
        with tempfile.TemporaryDirectory() as tmp, patch.object(study.core, 'generate_cases', return_value=(cases[:1],gold)):
            output = Path(tmp)/'run'
            with patch('sys.argv', ['runner','--output',str(output)]):
                study.main()
            record = json.loads((output/'record.json').read_text())
            self.assertEqual(record['planned_rows'],2)
            self.assertTrue(all(r['status']=='ok' for r in record['rows']))
            self.assertIn('inputs/scripts/prepare_hybrid_gleif.py',json.loads((output/'freeze.json').read_text()))

    def test_continuation_selects_only_requested_ids_and_rejects_unknown(self):
        cases,_ = study.core.generate_cases()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); ids=root/'ids.json';ids.write_text(json.dumps([cases[0]['id']]))
            out=root/'continued'
            with patch('sys.argv',['runner','--case-ids',str(ids),'--output',str(out)]):study.main()
            record=json.loads((out/'record.json').read_text())
            self.assertEqual(record['planned_rows'],2)
            self.assertEqual({r['case_id'] for r in record['rows']},{cases[0]['id']})
            ids.write_text('["unknown"]')
            with patch('sys.argv',['runner','--case-ids',str(ids),'--output',str(root/'bad')]):
                with self.assertRaisesRegex(ValueError,'InvalidContinuationIDs'):study.main()
