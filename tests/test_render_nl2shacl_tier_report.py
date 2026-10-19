"""Synthetic offline viewer checks; never read the active experiment ledger."""
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render_nl2shacl_tier_report import digest, run, sha


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.audit = self.root / 'audit.json'
        self.inputs = self.root / 'inputs.json'
        self.ledger = self.root / 'ledger.json'
        self.output = self.root / 'report.html'
        self.pairs = self.root / 'pairs.json'
        self.raw = '</script><img src=x onerror=alert(1)>'
        self.prompt = dict(model='openai/gpt-6-astra', id='case-1', language='ko', system_prompt='system', user_prompt='question')
        self.write(self.inputs, [self.prompt, dict(self.prompt, model='openai/gpt-6-luna')])
        self.write(self.pairs, {'pairs': [{'id': 'case-1', 'ko': 'question', 'en': 'question'}], 'license': 'CC BY-SA 4.0'})
        folder = self.root / 'generation' / 'call-0000'
        folder.mkdir(parents=True)
        (folder / 'output.ttl').write_text(self.raw)
        usage = {'cost': .0123, 'completion_tokens_details': {'reasoning_tokens': 0}}
        self.write(folder / 'response.json', {'model': self.prompt['model'], 'provider': 'test', 'usage': usage, 'choices': [{'message': {'content': self.raw}, 'finish_reason': 'length'}]})
        reservation = dict(self.prompt, status='completed', input_sha256=digest(self.prompt), reported_usd=.0123, upper_usd=.5, latency_seconds=1.25)
        self.write(self.ledger, {'attempts': 1, 'reservations': [reservation], 'output': str(folder.parent)})
        processed = self.root / 'processed.jsonl'
        self.write(processed, {'id': 'case-1-ko', 'reference_shacl': 'reference', 'output_shacl': self.raw})
        refsha = hashlib.sha256(b'reference').hexdigest()
        self.audit_data = dict(ledger=str(self.ledger), hashes={str(p): sha(p) for p in [self.ledger, folder / 'output.ttl', folder / 'response.json', processed]}, source_hashes={'reference.ttl': refsha}, upstream_runs=[{'model': self.prompt['model'], 'processed_input': str(processed)}], rows=[dict(model=self.prompt['model'], id='case-1', language='ko', status='completed', reservation_index=0, reported_usd=.0123, upper_usd=.5, usage=usage, provider='test', response_model=self.prompt['model'], finish_reason='length', classification='truncation', meta={'status': 'parse_failure'}, raw_sha256=sha(folder / 'output.ttl'), cleaned_sha256=sha(folder / 'output.ttl'), reference_sha256=refsha)])
        self.write(self.audit, self.audit_data)

    @staticmethod
    def write(path, value):
        path.write_text(json.dumps(value), encoding='utf-8')

    def report(self):
        return run(self.audit, self.inputs, self.ledger, self.output, self.pairs)

    def test_accounting_metadata_missing_and_safe_embedding(self):
        data = self.report()
        self.assertEqual(data['totals']['reported_usd'], '0.0123')
        self.assertEqual(data['totals']['reserved_usd'], '0.5')
        self.assertEqual(data['totals']['planned'], 2)
        self.assertEqual(data['rows'][0]['latency_seconds'], 1.25)
        self.assertEqual(data['rows'][0]['reasoning_tokens'], 0)
        self.assertEqual(data['rows'][0]['raw'], self.raw)
        self.assertEqual(data['rows'][0]['requirement'], 'question')
        self.assertEqual(data['rows'][1]['status'], 'unexecuted')
        html = self.output.read_text()
        self.assertNotIn(self.raw, html)
        self.assertIn('\\u003c/script\\u003e', html)
        self.assertNotIn('innerHTML', html)
        self.assertIn('의미적 정답률 미측정', html)
        self.assertIn('구조 일치 ≠ 의미 일치', html)
        self.assertIn('OpenAI · 프런티어', html)
        self.assertIn('OpenAI · 저비용', html)
        self.assertNotIn(' · 상위', html)
        self.assertNotIn(' · 하위', html)
        self.assertIn("['parse_failure','invalid_shape','runtime_exception','unknown']", html)
        self.assertIn('r.upstream?.structural?.isomorphic', html)
        with self.assertRaises(FileExistsError):
            self.report()

    def test_stale_audit_rejects_ledger_change(self):
        ledger = json.loads(self.ledger.read_text())
        ledger['reservations'][0]['latency_seconds'] = 99
        self.write(self.ledger, ledger)
        with self.assertRaisesRegex(ValueError, 'ledger hash mismatch'):
            self.report()
        self.assertFalse(self.output.exists())

    def test_artifact_change_fails_closed(self):
        (self.root / 'generation/call-0000/output.ttl').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'artifact hash mismatch'):
            self.report()

    def test_unresolved_reservation_fails_closed(self):
        ledger = json.loads(self.ledger.read_text())
        ledger['reservations'][0]['status'] = 'reserved'
        self.write(self.ledger, ledger)
        self.audit_data['hashes'][str(self.ledger)] = sha(self.ledger)
        self.write(self.audit, self.audit_data)
        with self.assertRaisesRegex(ValueError, 'not quiescent'):
            self.report()

    def test_frozen_prompt_change_fails_closed(self):
        self.write(self.inputs, [dict(self.prompt, user_prompt='changed')])
        with self.assertRaisesRegex(ValueError, 'Frozen input hash mismatch'):
            self.report()

    def test_audit_row_metadata_mismatch_fails_closed(self):
        self.audit_data['rows'][0]['usage']['cost'] = 9
        self.write(self.audit, self.audit_data)
        with self.assertRaisesRegex(ValueError, 'response mismatch'):
            self.report()

    def test_reference_content_mismatch_fails_closed(self):
        self.audit_data['rows'][0]['reference_sha256'] = '0' * 64
        self.write(self.audit, self.audit_data)
        with self.assertRaisesRegex(ValueError, 'content hash mismatch'):
            self.report()

    def test_wrong_requirement_fails_closed(self):
        self.write(self.pairs, {'pairs': [{'id': 'case-1', 'ko': 'another requirement'}]})
        with self.assertRaisesRegex(ValueError, 'Requirement does not match'):
            self.report()

    def test_original_upstream_result_is_bound_to_saved_artifact(self):
        old = self.root / 'processed.jsonl'
        processed = self.root / 'model_processed.jsonl'
        old.rename(processed)
        self.audit_data['hashes'].pop(str(old))
        self.audit_data['hashes'][str(processed)] = sha(processed)
        self.audit_data['upstream_runs'][0].update(processed_input=str(processed), status='completed')
        evaluation = self.root / 'upstream/model_eval.jsonl'
        evaluation.parent.mkdir()
        score = dict(id='case-1-ko', status='evaluated', validity={'parsing_valid': True}, structural={'isomorphic': False})
        self.write(evaluation, score)
        self.audit_data['hashes'][str(evaluation)] = sha(evaluation)
        self.audit_data['rows'][0]['upstream'] = {k: v for k, v in score.items() if k != 'id'}
        self.write(self.audit, self.audit_data)
        data = self.report()
        self.assertFalse(data['rows'][0]['upstream']['structural']['isomorphic'])
        self.output.unlink()
        self.audit_data['rows'][0]['upstream']['structural']['isomorphic'] = True
        self.write(self.audit, self.audit_data)
        with self.assertRaisesRegex(ValueError, 'upstream result mismatch'):
            self.report()

    def test_busy_ledger_fails_closed(self):
        with self.ledger.with_suffix('.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'Ledger is busy'):
                self.report()
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
