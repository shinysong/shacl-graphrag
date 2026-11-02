import copy
import unittest
from unittest.mock import patch
from scripts.run_graphrag_reports import attach_report
from scripts.graphrag_check import canonical_bytes
import hashlib

class ReportTests(unittest.TestCase):
    def envelope(self):
        return dict(question_id='q',status='ok',selected_chunks=[],selected_chunk_ids=[],evidence_sha256=hashlib.sha256(b'[]').hexdigest(),evidence_bytes=2)
    def test_no_reads_and_unchanged_envelope(self):
        e=self.envelope();before=copy.deepcopy(e)
        with patch('builtins.open',side_effect=AssertionError('read')),patch('pathlib.Path.open',side_effect=AssertionError('read')),patch('socket.socket',side_effect=AssertionError('network')):
            r=attach_report(e,lambda text:len(text))
        self.assertEqual(e,before);self.assertEqual(r['evidence'],before)
        self.assertEqual(r['report']['results'][0]['status'],'unknown')
        self.assertEqual(r['report_bytes'],len(canonical_bytes(r['report'])))
        self.assertFalse(r['combined_generator_budget_enforced'])
    def test_upstream_failure_preserved(self):
        e=self.envelope();e['status']='budget_error';r=attach_report(e,lambda text:1)
        self.assertEqual(r['report']['status'],'error');self.assertEqual(r['report']['results'],[])
        self.assertEqual(r['evidence']['status'],'budget_error')
    def test_report_cannot_add_evidence(self):
        e=self.envelope();report={'evidence_sha256':e['evidence_sha256'],'results':[{'evidence_ids':['node:missing']}]}
        with patch('scripts.run_graphrag_reports.check_evidence',return_value=report):
            with self.assertRaises(ValueError):attach_report(e,lambda text:1)
    def test_report_cap_and_bad_count(self):
        e=self.envelope()
        with patch('scripts.run_graphrag_reports.check_evidence',return_value={'x':'a'*32000}):
            with self.assertRaises(ValueError):attach_report(e,lambda text:1)
        with self.assertRaises(ValueError):attach_report(e,lambda text:True)
