"""Offline capture isolation/failure checks; never provider quality tests."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.workspace_proposal_packets import freeze


class PacketTests(unittest.TestCase):
    def test_expectations_excluded_and_failure_denominator_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'cases.json'
            source.write_text(json.dumps({'cases':[
                {'id':'bad','files':[{'name':'x.csv','content':'id,id\nA,B\n'}]},
                {'id':'good','files':[{'name':'x.csv','content':'id\nA\n'}],
                 'expectations':{'secret_gold':'DO_NOT_SEND_THIS'}}]}))
            report=freeze(source,root/'out')
            self.assertEqual(report['attempted_cases'],2)
            self.assertEqual([r['state'] for r in report['records']],
                             ['capture_failed','captured_before_response'])
            text=(root/'out/good-messages.json').read_text()
            self.assertNotIn('DO_NOT_SEND_THIS',text)
            self.assertNotIn('expectations',json.loads(json.loads(text)[1]['content']))
            self.assertFalse((root/'out/bad-messages.json').exists())
            self.assertFalse(report['paid_execution_ready'])
            with self.assertRaises(FileExistsError):freeze(source,root/'out')

    def test_document_controls_keep_tables_constant_and_hide_case_names(self):
        source=Path('research/workspace-proposal-quality-1/document-controls.json')
        cases=json.loads(source.read_text())['cases']
        self.assertTrue(all(c['files'][:2]==cases[0]['files'][:2] for c in cases))
        with tempfile.TemporaryDirectory() as directory:
            report=freeze(source,Path(directory)/'out')
            packets=[]
            for row in report['records']:
                messages=json.loads((Path(directory)/'out'/(row['id']+'-messages.json')).read_text())
                self.assertNotIn(row['id'],json.dumps(messages))
                packets.append(json.loads(messages[1]['content']))
            self.assertTrue(all(p['sources'][:2]==packets[0]['sources'][:2] for p in packets))
            self.assertTrue(all(p['existing_relations']==packets[0]['existing_relations'] for p in packets))
