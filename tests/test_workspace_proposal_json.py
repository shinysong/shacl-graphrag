"""Complete envelope handling, not semantic correction or provider-quality tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from apps.factory_lab import preparation
from apps.factory_lab.preparation_model import ModelProposalGenerator,decode_proposal
from scripts.workspace_proposal_packets import freeze
from scripts.workspace_proposal_replay import replay

class ProposalJSONTests(unittest.TestCase):
    def test_complete_envelope_preserves_pending_schema_and_saved_message(self):
        files=[{'name':'x.csv','content':'id\nA\n'}]
        for wrap in (lambda s:s,lambda s:'```json\n'+s+'\n```',lambda s:' \n```\r\n'+s+'\r\n```\n '):
            calls=[]
            content=wrap(json.dumps({'choices':[{'id':'map:x.csv:id','target':'source_only','reason':'Meaning needs human review'}]}))
            def call(messages):calls.append(messages);return {'content':content}
            with self.subTest(content=content[:10]),patch('httpx.Client',side_effect=AssertionError('No network')):
                draft=preparation.create(files,{'snapshot_id':'json','as_of':'2026-11-19','currency':'KRW'},ModelProposalGenerator(call,'saved'))
                self.assertEqual(len(calls),1)
                entry=draft['entries'][0]
                self.assertEqual(entry['status'],'pending')
                self.assertEqual(entry['interpretation'],'')
                self.assertEqual(entry['target'],'source_only')
                self.assertEqual(entry['extraction']['response_format'],'json' if content.startswith('{') else 'json_fence')
                self.assertEqual(preparation.restore_draft(draft)['entries'],draft['entries'])
    def test_fragments_prose_foreign_fences_truncation_and_approval_rejected(self):
        valid='{"choices":[]}'
        for value in ('Here is JSON: '+valid,'```json\n'+valid,'```python\n'+valid+'\n```',
                      '```json\n'+valid+'\n```\nExplanation','```json\n'+valid+'\n```\n```json\n'+valid+'\n```',
                      '```json\n'+valid+' '+valid+'\n```','{"choices":',None,'x'*256001):
            with self.subTest(value=str(value)[:30]),self.assertRaises(ValueError):decode_proposal(value)
        for choice in ({'target':'source_only','status':'approved'},{'target':'invented.field'}):
            content='```json\n'+json.dumps({'choices':[{'id':'map:x.csv:id','reason':'Untrusted model',**choice}]})+'\n```'
            calls=[]
            def call(messages):calls.append(messages);return {'content':content}
            with self.subTest(choice=choice),self.assertRaises(ValueError):
                preparation.create([{'name':'x.csv','content':'id\nA\n'}],{'snapshot_id':'x','as_of':'2026-11-19','currency':'KRW'},ModelProposalGenerator(call,'saved-invalid'))
            self.assertEqual(len(calls),1)
    def test_explicit_replay_does_not_change_attempt_bytes(self):
        with tempfile.TemporaryDirectory() as tmp,patch('httpx.Client',side_effect=AssertionError('No network')):
            root=Path(tmp);manifest=freeze('research/workspace-proposal-quality-1/document-controls.json',root/'packets')
            raw=(root/'packets/document_support-messages.json').read_bytes();packet=json.loads(json.loads(raw)[1]['content'])
            content='```json\n'+json.dumps({'choices':[{'id':e['id'],'target':'','reason':'Unverified'} for e in packet['entries']]})+'\n```'
            attempts={'attempts':[{'case_id':'document_support','attempt_id':'saved','packet_sha256':manifest['records'][0]['messages_sha256'],'status':'response','message':{'content':content}}]}
            path=root/'attempts.json';path.write_text(json.dumps(attempts));original=path.read_bytes()
            result=replay(root/'packets',path)
            self.assertEqual(result['states'],{'pending_draft_created':1,'not_attempted':2})
            self.assertEqual(path.read_bytes(),original)
