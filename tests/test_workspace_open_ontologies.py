"""Process-boundary fixtures only; these scripts are NOT upstream reasoning."""
import json
from pathlib import Path
import tempfile
import unittest

from apps.factory_lab.open_ontologies_runner import PROCESS_FILE_BYTES, reason_snapshot


class ReasoningBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.binary = Path(self.tmp.name) / 'fake-engine'

    def script(self, body):
        self.binary.write_text('#!/usr/bin/python3\n' + body)
        self.binary.chmod(0o700)
        return self.binary

    def success(self, fixpoint=True):
        return self.script('''import json,sys,os
from pathlib import Path
commands=json.load(sys.stdin)
assert 'OPENROUTER_API_KEY' not in os.environ
assert '--no-connect' in sys.argv
source=Path(commands[0]['args'][0]).read_text()
Path(commands[2]['args'][0]).write_text(source)
args=commands[1]['args'];cert=Path(args[args.index('--certificate')+1]);cert.mkdir()
(cert/'derivations.tsv').write_text('mock-only')
for i,c in enumerate(commands):
 print(json.dumps({'seq':i,'command':c['command'],'result':{'fixpoint_reached':FIXPOINT}}))
'''.replace('FIXPOINT', repr(fixpoint)))

    def test_fixed_commands_and_raw_receipt(self):
        result = reason_snapshot(self.success(), b'<urn:a> <urn:b> <urn:c> .')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['approval'], 'not_granted')
        self.assertEqual(result['certificate_verification'], 'not_run')
        self.assertEqual(result['derivation_artifacts']['derivations.tsv']['text'], 'mock-only')
        self.assertEqual(result['asserted_turtle'], result['closure_turtle'])

    def test_incomplete_closure_never_completed(self):
        self.assertEqual(reason_snapshot(self.success(False), b'')['status'], 'partial')

    def test_bad_json_and_native_failure_retained(self):
        self.script('import sys\nprint("not json")\nprint("native error",file=sys.stderr)\nsys.exit(1)\n')
        result = reason_snapshot(self.binary, b'')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('native error', result['stderr'])
        self.assertIn('not json', result['stdout'])

    def test_timeout_retains_partial_output(self):
        self.script('''import json,sys,time
from pathlib import Path
commands=json.load(sys.stdin)
Path(commands[2]['args'][0]).write_text('partial closure')
args=commands[1]['args'];cert=Path(args[args.index('--certificate')+1]);cert.mkdir()
(cert/'derivations.tsv').write_text('partial derivation')
print("partial",flush=True)
time.sleep(5)
''')
        result = reason_snapshot(self.binary, b'', timeout=1)
        self.assertEqual(result['status'], 'timed_out')
        self.assertIn('partial', result['stdout'])
        self.assertEqual(result['closure_turtle'], 'partial closure')
        self.assertEqual(result['derivation_artifacts']['derivations.tsv']['text'], 'partial derivation')
        self.assertEqual(result['artifact_completeness'], 'unverified_partial')

    def test_service_output_limit_is_explicit_and_not_a_complete_receipt(self):
        self.script('import sys\nprint("x" * 4096)\n')
        result = reason_snapshot(self.binary, b'', max_output_bytes=1024)
        self.assertEqual(result['limits']['file_bytes'], PROCESS_FILE_BYTES)
        self.assertEqual(result['limits']['returned_file_bytes'], 1024)
        self.assertEqual(result['limits']['total_disk_quota'], 'not_enforced')
        self.assertTrue(result['output_limit_reached'])
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['artifact_completeness'], 'unverified_partial')
        self.assertLessEqual(len(result['stdout'].encode()), 1024)
        self.assertEqual(result['events'], [])
        self.assertEqual(result['output_files']['stdout']['file_bytes'], 4097)
        self.assertTrue(result['output_files']['stdout']['truncated'])

    def test_scratch_larger_than_return_limit_does_not_block_small_receipt(self):
        self.success()
        with self.binary.open('a') as script:
            script.write("\nPath('scratch.db').write_bytes(b'x' * (1024 * 1024))\n")
        result = reason_snapshot(self.binary, b'<urn:a> <urn:b> <urn:c> .', max_output_bytes=1024)
        self.assertEqual(result['status'], 'completed')
        self.assertFalse(result['output_limit_reached'])
        self.assertEqual(result['exit_code'], 0)

    def test_scratch_file_ceiling_still_enforced(self):
        self.script('''import resource
from pathlib import Path
print('started', flush=True)
assert resource.getrlimit(resource.RLIMIT_FSIZE) == (16777216, 16777216)
assert resource.getrlimit(resource.RLIMIT_AS) == (2147483648, 2147483648)
with Path('scratch.db').open('wb') as stream:
 stream.truncate(16777217)
''')
        result = reason_snapshot(self.binary, b'', max_output_bytes=1024)
        self.assertEqual(result['status'], 'failed')
        self.assertNotEqual(result['exit_code'], 0)
        self.assertIn('started', result['stdout'])

    def test_oversized_artifacts_retain_only_prefix_and_fail(self):
        for target in ('stderr', 'closure', 'certificate'):
            with self.subTest(target=target):
                self.success()
                extra = {
                    'stderr': "sys.stderr.write('x' * 4096)",
                    'closure': "Path(commands[2]['args'][0]).write_bytes(b'x' * 4096)",
                    'certificate': "(cert/'derivations.tsv').write_bytes(b'x' * 4096)",
                }[target]
                with self.binary.open('a') as script:
                    script.write('\n' + extra + '\n')
                result = reason_snapshot(self.binary, b'', max_output_bytes=1024)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['exit_code'], 0)
                self.assertEqual(result['artifact_completeness'], 'unverified_partial')
                self.assertTrue(result['output_limit_reached'])
                key = {'stderr': 'stderr', 'closure': 'closure.ttl',
                       'certificate': 'certificate/derivations.tsv'}[target]
                self.assertEqual(result['output_files'][key], {
                    'file_bytes': 4096, 'retained_bytes': 1024, 'truncated': True,
                    'limit_reached': True, 'sha256_scope': 'retained_prefix'})
                text = (result['stderr'] if target == 'stderr' else result['closure_turtle']
                        if target == 'closure' else result['derivation_artifacts']['derivations.tsv']['text'])
                self.assertEqual(text, 'x' * 1024)

    def test_timeout_with_oversized_stream_retains_timeout_and_prefix(self):
        self.script("import time\nprint('x' * 4096, flush=True)\ntime.sleep(5)\n")
        result = reason_snapshot(self.binary, b'', timeout=1, max_output_bytes=1024)
        self.assertEqual(result['status'], 'timed_out')
        self.assertTrue(result['output_limit_reached'])
        self.assertEqual(result['stdout'], 'x' * 1024)
        self.assertEqual(result['events'], [])

    def test_invalid_output_limits_do_not_start_process(self):
        for limit in (True, 0, 1023, 16777217):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                reason_snapshot(self.binary, b'', max_output_bytes=limit)

    def test_oversized_input_or_unadvertised_profile_rejected(self):
        for kwargs in ({'profile':'owl-dl'}, {'timeout':0}, {'timeout':True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                reason_snapshot(self.binary, b'', **kwargs)
        with self.assertRaises(ValueError):
            reason_snapshot(self.binary, b'x' * 1_000_001)


if __name__ == '__main__':
    unittest.main()
