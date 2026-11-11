import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
from apps.factory_lab.store import Store

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('diagnostic_execute',ROOT/'research/virtual-factory-llm-1/diagnostic/execute.py')
x=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(x)

class ExecutionTests(unittest.TestCase):
    def run_mock(self,fail=False,expired=False):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);deadline=(datetime.now(timezone.utc)+timedelta(minutes=-1 if expired else 5)).isoformat()
            (p/'session.json').write_text(json.dumps({'deadline':deadline}))
            (p/'model.json').write_text('{}')
            (p/'execution-gate.json').write_text(json.dumps({'files':{'research/virtual-factory-llm-1/diagnostic/execute.py':hashlib.sha256(Path(x.__file__).read_bytes()).hexdigest()}}))
            auth={'deadline':deadline,'max_attempts':36,'existing_total_cap_usd':'5.00','input_manifest_sha256':hashlib.sha256((x.INPUT/'artifact-sha256.json').read_bytes()).hexdigest()}
            (p/'auth.json').write_text(json.dumps(auth));calls=[]
            class Fake:
                def __init__(self,s):pass
                def call(self,rid,messages):
                    calls.append(messages)
                    if fail:raise RuntimeError('simulated provider failure')
                    return {'content':'mock answer'}
            with patch.object(x,'WORK',p),patch.object(x,'Store',lambda:Store(p/'state.sqlite')),patch.object(x,'Gateway',Fake):
                result=x.execute(p/'out',p/'auth.json')
            records=json.loads((p/'out/results.json').read_text())
            return result,records,calls
    def test_all_packets_one_attempt_and_messages_only(self):
        result,records,calls=self.run_mock()
        self.assertEqual(result['completed'],36);self.assertEqual(len(calls),36)
        for messages in calls:
            self.assertEqual([m['role'] for m in messages],['system','user'])
            self.assertNotIn('desired_change',json.loads(messages[1]['content']))
        self.assertTrue(all(r['status']=='completed' for r in records))
    def test_failure_stops_and_retains_denominator(self):
        result,records,calls=self.run_mock(fail=True)
        self.assertEqual(len(calls),1);self.assertEqual(result['failed'],1);self.assertEqual(result['not_attempted'],35)
        self.assertTrue(all(r['reason']=='stopped_after_failure' for r in records[1:]))
    def test_expired_window_no_calls(self):
        result,records,calls=self.run_mock(expired=True)
        self.assertEqual(len(calls),0);self.assertEqual(result['not_attempted'],36)
