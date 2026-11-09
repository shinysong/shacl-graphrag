import json,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from scripts.backend_updates import states,delta,UpdatingNative,run,input_digest,append_journal
from scripts.backend_inference import term,ANN,TAB,SC

class UpdateTests(unittest.TestCase):
    def test_sequence_preserves_alternate_until_second_delete(self):
        source={'nodes':[{'node_id':'PP6:2','node_type':'annotation'}],'edges':[]}
        seq=states(source)
        self.assertEqual(len(seq),8)
        self.assertEqual(len(delta(seq[0],seq[1])['deleted']),1)
        self.assertEqual(len(delta(seq[1],seq[2])['deleted']),1)
        self.assertEqual(len(delta(seq[2],seq[3])['added']),2)
        self.assertEqual(seq[0]['schema'],seq[-1]['schema'])
        self.assertEqual(input_digest(seq[0]),input_digest(seq[-1]))
    def test_mutation_count_zero_aborts(self):
        client=UpdatingNative('unit')
        with patch.object(client,'request',return_value=[{'changed':0}]):
            with self.assertRaisesRegex(RuntimeError,'mutation count'):client.update({'facts':[],'schema':[(ANN,SC,TAB)]},{'facts':[],'schema':[]})
    def test_partial_mutation_attempts_survive_later_failure(self):
        for failure in [[{'changed':0}],RuntimeError('response lost')]:
            client=UpdatingNative('unit')
            with tempfile.TemporaryDirectory() as td:
                path=Path(td)/'attempts.jsonl'
                with patch.object(client,'request',side_effect=[[{'changed':1}],failure]):
                    with self.assertRaises(RuntimeError):
                        client.update({'facts':[],'schema':[(ANN,SC,TAB),(TAB,SC,term('root'))]},{'facts':[],'schema':[]},journal=lambda row:append_journal(path,row),event='delete')
                rows=[json.loads(x) for x in path.read_text().splitlines()]
                self.assertEqual(len(rows),4)
                self.assertEqual(rows[0]['status'],'attempted');self.assertEqual(rows[1]['status'],'completed')
                self.assertEqual(rows[2]['status'],'attempted')
                self.assertIn(rows[3]['status'],('anomalous_count','outcome_unknown'))
    def test_load_failure_retains_plan_cleans_acquired_stores(self):
        class Fake:
            def __init__(self,*args):pass
            def load(self,*args):raise RuntimeError('injected load failure')
            def cleanup(self):return {'remaining':0}
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'source.json').write_text('{"nodes":[],"edges":[]}')
            with patch('scripts.backend_updates.UpdatingNative',Fake),patch('scripts.backend_updates.UpdatingNeptune') as neptune:
                with self.assertRaisesRegex(RuntimeError,'injected'):run(p/'source.json',p/'out',True)
                neptune.assert_not_called()
            self.assertEqual(len(json.loads((p/'out/plan.json').read_text())),160)
            self.assertTrue((p/'out/failure.json').exists())
            self.assertEqual(json.loads((p/'out/cleanup.json').read_text())[0]['receipt'],{'remaining':0})
if __name__=='__main__':unittest.main()
