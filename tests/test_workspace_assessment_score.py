"""Scripted scorer controls; not provider quality measurements."""
import json
from pathlib import Path
import tempfile
import unittest
from scripts.workspace_proposal_packets import freeze
from scripts.workspace_assessment_score import score


class ScoreTests(unittest.TestCase):
    def test_full_denominators_and_direction_disagreement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            freeze('research/workspace-proposal-quality-1/document-controls.json', root/'packets')
            rubric = 'research/workspace-proposal-quality-1/document-controls-rubric.json'
            packet = json.loads(json.loads((root/'packets/document_support-messages.json').read_text())[1]['content'])
            ids = [e['id'] for e in packet['existing_relations']]
            self.assertEqual(len(ids), 2)
            def response(aid, values):
                return {'case_id':'document_support', 'attempt_id':aid, 'status':'response',
                        'message':{'content':json.dumps({'relation_assessments':values})}}
            values = [{'id':key,'assessment':label,'evidence':['policy:dictionary.md:1']}
                      for key,label in zip(ids, ['supported','contradicted'])]
            attempts = [response('mixed', values), response('omitted', []),
                        response('invalid', values+values),
                        {'case_id':'document_deny','attempt_id':'failure','status':'failed','error':'timeout'}]
            path = root/'attempts.json';path.write_text(json.dumps({'attempts':attempts}))
            result = score(root/'packets', rubric, path)
            self.assertEqual(result['recorded_attempts'], 4)
            self.assertEqual(result['planned_cases'], 3)
            self.assertEqual(result['direction_outcomes'], {'agrees':1,'disagrees':1,'unassessed':2})
            self.assertEqual(result['case_attempt_states'], {'assessment_scored':2,'assessment_invalid':1,'execution_failed':1,'not_attempted':1})
            attempts.append(attempts[0]);path.write_text(json.dumps({'attempts':attempts}))
            with self.assertRaises(ValueError):score(root/'packets', rubric, path)

    def test_packet_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory);freeze('research/workspace-proposal-quality-1/document-controls.json',root/'packets')
            path = root/'attempts.json';path.write_text('{"attempts": []}')
            packet = root/'packets/document_support-messages.json'
            packet.write_text(packet.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):
                score(root/'packets','research/workspace-proposal-quality-1/document-controls-rubric.json',path)
