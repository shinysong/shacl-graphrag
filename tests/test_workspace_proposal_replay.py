"""Saved response replay is offline admissibility, not semantic evaluation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.workspace_proposal_packets import freeze
from scripts.workspace_proposal_replay import replay, ReplayMismatch


class ReplayTests(unittest.TestCase):
    def fixture(self,root):
        report=freeze('research/workspace-proposal-quality-1/document-controls.json',root/'packets')
        raw=(root/'packets/document_support-messages.json').read_bytes()
        packet=json.loads(json.loads(raw)[1]['content'])
        response={'choices':[{'id':e['id'],'target':'','reason':'Authored unknown meaning'} for e in packet['entries']]}
        return report,response

    def test_full_admissibility_distinct_from_label_score(self):
        with tempfile.TemporaryDirectory() as tmp, patch('httpx.Client',side_effect=AssertionError('No network')):
            root=Path(tmp);manifest,response=self.fixture(root)
            digest=manifest['records'][0]['messages_sha256']
            base={'case_id':'document_support','packet_sha256':digest,'status':'response'}
            attempts=[base|{'attempt_id':'valid','message':{'content':json.dumps(response)}},
                      base|{'attempt_id':'invalid','message':{'content':'{"relation_assessments":[]}'}}]
            deny=manifest['records'][1]
            attempts.append({'case_id':deny['id'],'packet_sha256':deny['messages_sha256'],'attempt_id':'failed','status':'failed'})
            path=root/'attempts.json';path.write_text(json.dumps({'attempts':attempts}))
            result=replay(root/'packets',path)
            self.assertEqual(result['states'],{'pending_draft_created':1,'proposal_rejected':1,'execution_failed':1,'not_attempted':1})
            draft=result['results'][0]['draft']
            self.assertTrue(all(e['status']=='pending' for e in draft['entries']))
            self.assertEqual(json.loads(path.read_text())['attempts'],attempts)
            attempts[0]['packet_sha256']='wrong';path.write_text(json.dumps({'attempts':attempts}))
            with self.assertRaises(ReplayMismatch):replay(root/'packets',path)

    def test_source_drift_rejected_even_without_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            path=root/'attempts.json';path.write_text('{"attempts":[]}')
            source=root/'packets/input.json';source.write_bytes(source.read_bytes()+b' ')
            with self.assertRaises(ReplayMismatch):replay(root/'packets',path)
