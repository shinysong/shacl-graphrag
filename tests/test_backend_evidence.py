import json
from pathlib import Path
import tempfile
import unittest

from scripts.check_backend_evidence import coverage, sha, verify_cleanup, verify_manifest


class EvidenceTests(unittest.TestCase):
    def test_missing_duplicate_and_unplanned_slots_rejected(self):
        plan = [{'id': 1}, {'id': 2}]
        self.assertEqual(coverage(plan, list(reversed(plan)), ('id',)), 2)
        for rows in (plan[:1], [plan[0], plan[0]], [plan[0], {'id': 3}]):
            with self.assertRaises(ValueError):
                coverage(plan, rows, ('id',))
        with self.assertRaises(ValueError):
            coverage([plan[0], plan[0]], plan, ('id',))

    def test_mutated_answer_and_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / 'answers.json'
            artifact.write_text('{"answer": [1]}')
            manifest = {'answers.json': sha(artifact)}
            verify_manifest(root, manifest)
            artifact.write_text('{"answer": [2]}')
            with self.assertRaises(ValueError):
                verify_manifest(root, manifest)
            artifact.unlink()
            with self.assertRaises(ValueError):
                verify_manifest(root, manifest)

    def test_failed_nonempty_and_missing_cleanup_counts_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'cleanup.json'
            path.write_text(json.dumps([{'receipt': {'remaining': False}}]))
            self.assertEqual(verify_cleanup(path), 1)
            for row in ({'receipt': {'remaining': 1}}, {'receipt': {}}, {'status': 'failed', 'receipt': {'remaining': 0}}):
                path.write_text(json.dumps([row]))
                with self.assertRaises(ValueError):
                    verify_cleanup(path)
