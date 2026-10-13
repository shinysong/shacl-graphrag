"""Local recorder tests use explicitly fake test agent IDs, never real model reviews."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import research_ops as ops


class NativeOpsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name) / 'work'
        self.spec = Path(self.tmp.name) / 'spec'
        (self.spec / 'roles').mkdir(parents=True)
        self.config = {'schema_version': 2, 'backend': 'codex-native', 'max_parallel_reviews': 2,
                       'max_role_requests_per_job': 7, 'max_role_requests_per_day': 100,
                       'max_context_bytes': 28000, 'check_timeout_seconds': 180}
        ops.write(self.spec / 'config.json', self.config)
        for role in ops.ROLES:
            (self.spec / 'roles' / f'{role}.md').write_text('Review only the supplied bounded task.')
        self.task = Path(self.tmp.name) / 'task.json'
        ops.write(self.task, {'schema_version': 1, 'id': 'test-only', 'goal': 'Local recorder test',
                             'checks': ['unit-tests', 'e0-local'], 'context_files': []})
        self.job = ops.init_job(self.task, work=self.work, spec=self.spec)
        self.checked = []

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, phase, **kwargs):
        return ops.request_job(self.job, phase, work=self.work, **kwargs)

    def submit(self, phase, result=None, agent=None):
        result = result or {'summary': 'TEST FIXTURE ' + phase, 'decision': 'ready',
                            'findings': [], 'tasks': []}
        path = Path(self.tmp.name) / ('output-' + phase + '.json')
        ops.write(path, result)
        return ops.submit_job(self.job, phase, path, agent or ('test-reviewer-' + phase
                              if phase in ('methods', 'implementation') else 'test-main'), work=self.work)

    def phase(self, phase, **kwargs):
        self.request(phase)
        return self.submit(phase, **kwargs)

    def approved(self):
        for phase in ('plan', 'methods', 'implementation', 'synthesis'):
            self.phase(phase)

    def checker(self, command, output, timeout):
        self.checked.append(command)
        return {'exit_code': 0, 'command': command, 'scope': 'TEST FIXTURE'}

    def check(self, **kwargs):
        return ops.check_job(self.job, checker=self.checker, work=self.work, **kwargs)

    def test_full_cycle_records_five_requests_and_real_check_gate(self):
        self.approved()
        self.check()
        self.phase('analysis', result={'summary': 'TEST unit-tests exit code 0; e0-local exit code 0.',
                                      'decision': 'observe', 'findings': [], 'tasks': []})
        state = ops.read(self.job / 'state.json')
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(state['role_requests'], 5)
        self.assertEqual(len(self.checked), 2)
        self.assertNotIn('reserved_usd', state)
        self.check()
        self.assertEqual(len(self.checked), 2)

    def test_out_of_order_is_rejected_without_reserving(self):
        for phase in ('methods', 'implementation', 'synthesis', 'analysis'):
            with self.assertRaises(RuntimeError):
                self.request(phase)
        self.assertEqual(ops.read(self.job / 'state.json')['role_requests'], 0)

    def test_independent_review_packets_share_plan_but_not_each_other(self):
        self.phase('plan')
        method = ops.read(self.request('methods'))
        self.submit('methods')
        implementation = ops.read(self.request('implementation'))
        self.assertEqual(set(method['evidence']), {'plan'})
        self.assertEqual(set(implementation['evidence']), {'plan'})
        self.assertEqual(method['evidence'], implementation['evidence'])
        self.assertIn('fork_turns=none', method['dispatch'])

    def test_parallel_review_limit_one_and_two(self):
        self.config['max_parallel_reviews'] = 1
        ops.write(self.spec / 'config.json', self.config)
        self.job = ops.init_job(self.task, work=self.work, spec=self.spec)
        self.phase('plan')
        self.request('methods')
        with self.assertRaisesRegex(RuntimeError, 'ParallelReviewLimit'):
            self.request('implementation')
        self.submit('methods')
        self.request('implementation')
        self.submit('implementation')
        self.config['max_parallel_reviews'] = 2
        ops.write(self.spec / 'config.json', self.config)
        self.job = ops.init_job(self.task, work=self.work, spec=self.spec)
        self.phase('plan')
        self.request('methods')
        self.request('implementation')
        self.assertEqual(ops.read(self.job / 'state.json')['role_requests'], 3)

    def test_blocker_status_survives_other_review_and_synthesis(self):
        self.phase('plan')
        self.request('methods')
        self.request('implementation')
        self.submit('methods', result={'summary': 'TEST blocker', 'decision': 'revise',
            'findings': [], 'tasks': []})
        self.assertEqual(ops.read(self.job / 'state.json')['status'], 'needs_revision')
        self.submit('implementation')
        self.assertEqual(ops.read(self.job / 'state.json')['status'], 'needs_revision')
        self.request('synthesis')
        self.assertEqual(ops.read(self.job / 'state.json')['status'], 'needs_revision')
        self.submit('synthesis')
        self.assertEqual(ops.read(self.job / 'state.json')['status'], 'needs_revision')
        with self.assertRaises(RuntimeError):
            self.check()

    def test_reviewers_cannot_share_coordinator_or_other_reviewer_id(self):
        self.phase('plan')
        self.request('methods')
        with self.assertRaises(ValueError):
            self.submit('methods', agent='test-main')
        self.request('methods', retry=True)
        self.submit('methods')
        self.request('implementation')
        with self.assertRaises(ValueError):
            self.submit('implementation', agent='test-reviewer-methods')

    def test_synthesis_retains_coordinator_id(self):
        for phase in ('plan', 'methods', 'implementation'):
            self.phase(phase)
        self.request('synthesis')
        with self.assertRaises(ValueError):
            self.submit('synthesis', agent='another-main')

    def test_blocker_cannot_be_overridden_by_synthesis(self):
        self.phase('plan')
        self.phase('methods', result={'summary': 'TEST blocker', 'decision': 'revise',
            'findings': [{'severity': 'blocker', 'evidence': 'TEST unsupported repair',
                          'recommendation': 'Separate gold'}], 'tasks': []})
        self.phase('implementation')
        self.phase('synthesis')
        with self.assertRaises(RuntimeError):
            self.check()
        with self.assertRaises(RuntimeError):
            self.request('analysis')
        self.assertFalse(self.checked)

    def test_failed_check_prevents_analysis_and_preserves_attempt(self):
        self.approved()
        with self.assertRaises(RuntimeError):
            ops.check_job(self.job, checker=lambda *args: {'exit_code': 1}, work=self.work)
        with self.assertRaises(RuntimeError):
            self.request('analysis')
        with self.assertRaises(RuntimeError):
            self.check()
        self.check(retry=True)
        self.assertTrue((self.job / 'check-unit-tests/attempt-1').exists())
        self.assertTrue((self.job / 'check-unit-tests/attempt-2/result.json').exists())

    def test_rejected_output_and_provenance_preserved_across_retry(self):
        self.request('plan')
        with self.assertRaises(ValueError):
            self.submit('plan', result={'bad': 'TEST invalid'})
        with self.assertRaises(RuntimeError):
            self.request('plan')
        self.request('plan', retry=True)
        self.submit('plan')
        old = self.job / 'plan/attempt-1'
        self.assertTrue((old / 'submitted.json').exists())
        self.assertEqual(ops.read(old / 'provenance.json')['agent_id'], 'test-main')
        self.assertEqual(ops.read(self.job / 'state.json')['role_requests'], 2)

    def test_request_cannot_be_submitted_twice(self):
        self.phase('plan')
        with self.assertRaises(RuntimeError):
            self.submit('plan')
        with self.assertRaises(RuntimeError):
            self.request('plan', retry=True)

    def test_request_hash_prevents_instruction_tampering(self):
        path = self.request('plan')
        path.write_text('{}')
        with self.assertRaises(RuntimeError):
            self.submit('plan')

    def test_packet_hash_prevents_changes(self):
        packet = ops.read(self.job / 'packet.json')
        packet['task']['goal'] = 'Changed'
        ops.write(self.job / 'packet.json', packet)
        with self.assertRaises(RuntimeError):
            self.request('plan')

    def test_completed_result_hash_prevents_changes(self):
        self.phase('plan')
        (self.job / 'plan/attempt-1/result.json').write_text('{}')
        with self.assertRaises(RuntimeError):
            self.request('methods')

    def test_changed_verification_inputs_prevent_dispatch(self):
        with patch.object(ops, 'verification_inputs', return_value={'changed': 'hash'}), self.assertRaises(RuntimeError):
            self.request('plan')

    def test_daily_limit_spans_jobs_and_preserves_reservation(self):
        self.config['max_role_requests_per_day'] = 1
        ops.write(self.spec / 'config.json', self.config)
        first = ops.init_job(self.task, work=self.work, spec=self.spec)
        second = ops.init_job(self.task, work=self.work, spec=self.spec)
        ops.request_job(first, 'plan', work=self.work)
        with self.assertRaises(RuntimeError):
            ops.request_job(second, 'plan', work=self.work)
        ledger = ops.read(self.work / 'requests-ledger.json')
        self.assertEqual(sum(d['role_requests'] for d in ledger['days'].values()), 1)

    def test_job_limit_counts_retries(self):
        self.config['max_role_requests_per_job'] = 1
        ops.write(self.spec / 'config.json', self.config)
        self.job = ops.init_job(self.task, work=self.work, spec=self.spec)
        self.request('plan')
        with self.assertRaises(RuntimeError):
            self.request('plan', retry=True)

    def test_crash_after_reservation_does_not_restore_job_quota(self):
        self.config['max_role_requests_per_job'] = 1
        ops.write(self.spec / 'config.json', self.config)
        self.job = ops.init_job(self.task, work=self.work, spec=self.spec)
        original = ops.write
        def crash(path, value):
            if path == self.job / 'state.json':
                raise RuntimeError('TEST simulated crash')
            original(path, value)
        with patch.object(ops, 'write', side_effect=crash), self.assertRaises(RuntimeError):
            self.request('plan')
        with self.assertRaises(RuntimeError):
            self.request('plan')
        self.assertEqual(next(iter(ops.read(self.work / 'requests-ledger.json')['jobs'].values()))[
            'role_requests'], 1)

    def test_missing_ledger_does_not_restore_quota(self):
        self.request('plan')
        (self.work / 'requests-ledger.json').unlink()
        with self.assertRaises(RuntimeError):
            self.request('plan', retry=True)

    def test_analysis_reports_exact_check_exit_codes(self):
        self.approved()
        self.check()
        self.request('analysis')
        with self.assertRaises(ValueError):
            self.submit('analysis', result={'summary': 'unit-tests 1; e0-local 0',
                'decision': 'observe', 'findings': [], 'tasks': []})

    def test_analysis_decision_and_review_copy_guards(self):
        self.phase('plan')
        self.request('methods')
        plan = ops.read(self.job / 'state.json')['steps']['plan']['result']
        with self.assertRaises(ValueError):
            self.submit('methods', result=plan)
        with self.assertRaises(ValueError):
            ops.validate_result({'summary': 'TEST', 'decision': 'ready', 'findings': [],
                                 'tasks': []}, 'analysis')

    def test_allowlist_and_no_transport(self):
        with self.assertRaises(ValueError):
            ops.load_context(ROOT, '.env')
        source = Path(ops.__file__).read_text()
        for forbidden in ('import httpx', 'import openai', 'OPENROUTER_API_KEY', 'codex exec'):
            self.assertNotIn(forbidden, source)
        self.assertNotEqual(ops.WORK, ROOT / '_workspace/research-ops')
        self.assertEqual(set(ops.CHECKS), {'unit-tests', 'e0-local'})

    def test_unknown_commands_and_legacy_live_are_not_available(self):
        with patch.object(sys, 'argv', ['research_ops.py', 'run', 'foo', '--live']), self.assertRaises(SystemExit):
            ops.main()

    def test_exclusive_lock_prevents_parallel_mutations(self):
        with ops.lock(self.work), self.assertRaises(RuntimeError):
            self.request('plan')


if __name__ == '__main__':
    unittest.main()
