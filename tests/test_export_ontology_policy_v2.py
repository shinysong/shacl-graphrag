import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import export_ontology_policy_v2 as exporter


class PolicyExportTests(unittest.TestCase):
    def test_only_direction_and_version_change_without_touching_source(self):
        original_bytes = exporter.SOURCE.read_bytes()
        original = json.loads(original_bytes)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'v2'
            manifest = exporter.export(output)
            revised = json.loads((output / 'runtime.json').read_bytes())
            self.assertEqual(manifest['case_count'], 18)
            self.assertEqual(manifest['status'], 'completed')
            self.assertEqual(exporter.sha((output / 'runtime.json').read_bytes()), manifest['runtime_sha256'])
            for before, after in zip(original, revised, strict=True):
                old_policy = before['runtime']['public_policies']
                new_policy = after['runtime']['public_policies']
                old_tail = old_policy['impact']['rule'].split('.', 1)[1]
                new_tail = new_policy['impact']['rule'].split('.', 1)[1]
                self.assertEqual(old_tail, new_tail)
                self.assertIn('part_of from subject to object', new_policy['impact']['rule'])
                self.assertIn('contains from object to subject', new_policy['impact']['rule'])
                self.assertNotEqual(old_policy['version'], new_policy['version'])
                new_policy['impact']['rule'] = old_policy['impact']['rule']
                new_policy['version'] = old_policy['version']
                self.assertEqual(before, after)
        self.assertEqual(original_bytes, exporter.SOURCE.read_bytes())

    def test_rejects_modified_source_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'tampered.json'
            source.write_bytes(exporter.SOURCE.read_bytes() + b' ')
            output = Path(directory) / 'v2'
            with self.assertRaisesRegex(ValueError, 'SourceHashMismatch'):
                exporter.export(output, source)
            self.assertFalse(output.exists())

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'v2'
            exporter.export(output)
            prior = {p.name: p.read_bytes() for p in output.iterdir()}
            with self.assertRaises(FileExistsError):
                exporter.export(output)
            self.assertEqual(prior, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_interrupted_write_is_retained_as_failed(self):
        original_open = Path.open
        def fail_runtime(path, *args, **kwargs):
            if path.name == 'runtime.json':
                raise OSError('simulated disk failure')
            return original_open(path, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'v2'
            with patch.object(Path, 'open', fail_runtime):
                with self.assertRaises(OSError):
                    exporter.export(output)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'failed')
            self.assertEqual(manifest['error_type'], 'OSError')
            with self.assertRaises(FileExistsError):
                exporter.export(output)
