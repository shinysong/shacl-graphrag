"""Offline audit fixtures; no model/API calls and no production artifact writes."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_nl2shacl_multimodel import run

PREFIX = '@prefix ex: <urn:test:> . @prefix sh: <http://www.w3.org/ns/shacl#> . '
VALID = PREFIX + 'ex:S a sh:NodeShape ; sh:property [sh:path ex:p ; sh:minCount 1] .'
INVALID = PREFIX + 'ex:S a sh:NodeShape ; sh:property [sh:path ex:p ; sh:minCount "one"] .'


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.generation = self.root / 'separate-generation'
        self.generation.mkdir()
        self.ledger = self.root / 'ledger.json'
        self.output = self.root / 'audit.json'
        files = {'framework/NL2SHACL-Translator/postprocess.py':
                 'ID_PREFIX_TO_SUBSET = {"case": "case-dataset"}\ndef cleanup_output(raw):\n    return raw.strip().removeprefix("```turtle\\n").removesuffix("```").strip()\n',
                 'framework/Shapes-Evaluation/run_evaluation.py': '# Fixture CLI mocked below\n',
                 'dataset/case-dataset/shacl/case-1.ttl': VALID}
        pins = {}
        for name, content in files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            pins[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.source / 'source-hashes.json').write_text(json.dumps(pins))
        self.items = []

    def add(self, model='vendor/model', language='en', raw=VALID, status='completed', finish='stop'):
        index = len(self.items)
        self.items.append(dict(model=model, language=language, id='case-1', status=status))
        folder = self.generation / f'call-{index:04d}'
        folder.mkdir()
        (folder / 'output.ttl').write_text(raw)
        (folder / 'response.json').write_text(json.dumps({'model': model, 'choices': [{'message': {'content': raw}, 'finish_reason': finish}]}))
        self.ledger.write_text(json.dumps({'output': str(self.generation), 'reservations': self.items}))
        return folder

    def audit(self, upstream=False):
        return run(self.ledger, self.output, self.source, upstream)

    def test_raw_meta_cleaned_and_model_pair_denominators(self):
        self.add(raw=VALID)
        self.add(language='ko', raw=INVALID)
        self.add(model='vendor/other', raw='```turtle\n' + VALID + '\n```')
        result = self.audit()
        self.assertEqual([x['meta']['status'] for x in result['rows']], ['meta_conformant', 'invalid_shape', 'parse_failure'])
        self.assertTrue(result['rows'][2]['postprocessing_changed_nonwhitespace'])
        pair = result['summary']['paired'][0]
        self.assertEqual(pair['completed_en_ko_pairs'], 1)
        self.assertEqual(pair['raw_meta_conformant_on_completed_pairs'], {'en': 1, 'ko': 0})
        self.assertEqual(result['paid_calls'], 0)
        processed = list((self.root / 'audit-artifacts').glob('*processed.jsonl'))
        self.assertEqual(len(processed), 2)
        self.assertTrue(all('reference_shacl' in json.loads(p.read_text().splitlines()[0]) for p in processed))
        with self.assertRaises(FileExistsError):
            self.audit()

    def test_noncompleted_outputs_never_scored_and_truncation_is_separate(self):
        self.add(status='failed', raw=VALID)
        self.add(language='ko', raw='broken', finish='length')
        self.add(model='vendor/other', status='reserved')
        rows = self.audit()['rows']
        self.assertEqual([r['classification'] for r in rows], ['provider_failure', 'truncation', 'noncompleted'])
        self.assertEqual(rows[0]['meta']['status'], 'not_evaluated')
        self.assertEqual(rows[1]['meta']['status'], 'parse_failure')

    def test_missing_completed_artifact_fails_closed(self):
        folder = self.add()
        (folder / 'response.json').unlink()
        with self.assertRaises(FileNotFoundError):
            self.audit()
        self.assertFalse(self.output.exists())

    def test_modified_reference_fails_closed(self):
        self.add()
        (self.source / 'dataset/case-dataset/shacl/case-1.ttl').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            self.audit()

    def test_raw_artifact_mismatch_fails_closed(self):
        folder = self.add()
        (folder / 'output.ttl').write_text(INVALID)
        with self.assertRaisesRegex(ValueError, 'Raw response/output mismatch'):
            self.audit()

    def test_duplicate_reservation_fails_closed(self):
        self.add()
        self.add()
        with self.assertRaisesRegex(ValueError, 'Duplicate reservation'):
            self.audit()

    def test_upstream_cli_uses_only_original_structural_mode(self):
        self.add()
        def mock_cli(command, **kwargs):
            self.assertEqual(command[-2:], ['--run', 'structural'])
            self.assertNotIn('--normalize', command)
            path = Path(command[command.index('--input') + 1])
            destination = Path(command[command.index('--output_dir') + 1])
            destination.mkdir()
            source = json.loads(path.read_text())
            score = dict(id=source['id'], status='evaluated', validity=dict(parsing_valid=True, spec_valid=True, vocab_valid=True), structural=dict(isomorphic=True))
            (destination / path.name.replace('_processed', '_eval')).write_text(json.dumps(score) + '\n')
            return SimpleNamespace(returncode=0, stdout='done', stderr='')
        with patch('audit_nl2shacl_multimodel.subprocess.run', side_effect=mock_cli):
            result = self.audit(True)
        group = result['summary']['model_language'][0]
        self.assertEqual(group['upstream_gated_structural_isomorphism'], 1)
        self.assertEqual(result['upstream_runs'][0]['exit_code'], 0)

    def test_upstream_failure_preserves_logs_without_success_summary(self):
        self.add()
        with patch('audit_nl2shacl_multimodel.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout='', stderr='fixture failed')):
            with self.assertRaisesRegex(RuntimeError, 'logs preserved'):
                self.audit(True)
        self.assertFalse(self.output.exists())
        self.assertEqual((self.root / 'audit-artifacts/model000.stderr.txt').read_text(), 'fixture failed')


if __name__ == '__main__':
    unittest.main()
