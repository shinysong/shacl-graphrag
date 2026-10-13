"""Bounded researcher-side planning, independent review and local verification.

No generated commands are executed. Research QA pipelines remain separate.
"""
import argparse
import fcntl
import hashlib
import json
import re
import subprocess
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'research/operations'
WORK = ROOT / '_workspace/research-ops-codex'
PHASES = ('plan', 'methods', 'implementation', 'synthesis', 'analysis')
CHECKS = {
    'unit-tests': ['uv', 'run', '--locked', 'python', '-m', 'unittest', 'discover', '-s', 'tests'],
    'e0-local': ['uv', 'run', '--locked', 'python', 'scripts/run_validation_experiment.py', '--local-only'],
}
ROLES = ('coordinator', 'methods', 'implementation')


def now():
    return datetime.now(UTC).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    # Rename within the same filesystem so a power loss cannot leave partial JSON.
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


@contextmanager
def lock(work):
    work.mkdir(parents=True, exist_ok=True)
    with (work / '.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another research job is running; try again after it finishes') from None
        yield


def validate_task(task):
    if set(task) != {'schema_version', 'id', 'goal', 'checks', 'context_files'}:
        raise ValueError('Unknown task fields; use a prose packet instead')
    if task.get('schema_version') != 1 or not re.fullmatch(r'[a-z0-9-]{1,64}', task.get('id', '')):
        raise ValueError('Invalid task ID/version')
    if not isinstance(task.get('goal'), str) or not task['goal'].strip():
        raise ValueError('Missing task goal')
    for key in ('checks', 'context_files'):
        if not isinstance(task.get(key), list) or not all(isinstance(x, str) for x in task[key]):
            raise ValueError(f'Invalid {key}')
    if len(task['checks']) != len(set(task['checks'])) or set(task['checks']) - CHECKS.keys():
        raise ValueError('Unknown or duplicate check ID')


def validate_config(config):
    if config.get('schema_version') != 2 or config.get('backend') != 'codex-native':
        raise ValueError('Only codex-native schema version 2 supported')
    if config.get('max_parallel_reviews') not in (1, 2):
        raise ValueError('Invalid parallel reviewer limit')
    for key in ('max_role_requests_per_job', 'max_role_requests_per_day',
                'max_context_bytes', 'check_timeout_seconds'):
        if type(config.get(key)) is not int or config[key] <= 0:
            raise ValueError(f'Invalid {key}')


def load_context(root, name):
    path = (root / name).resolve()
    # Explicit prose-only packets. No raw graph, archived gold, runs/, or credentials.
    allowed = ((root / 'research/operations/briefs').resolve(), (root / 'docs/setup').resolve())
    if path != (root / 'research/operations/brief.md').resolve() and not any(
            path.is_relative_to(p) for p in allowed):
        raise ValueError(f'Context path outside allowed prose directories: {name}')
    if path.suffix != '.md' or not path.is_file() or path.stat().st_size > 20000:
        raise ValueError('Context must be a Markdown packet of at most 20000 bytes')
    return path.read_text()


def verification_inputs(root=ROOT):
    paths = list((root / 'scripts').glob('*.py')) + list((root / 'tests').glob('*.py'))
    for directory in ('experiments/e0', 'experiments/gleif', 'experiments/yago'):
        paths.extend(p for p in (root / directory).glob('*') if p.suffix in ('.ttl', '.json', '.txt'))
    paths.extend(root / name for name in ('pyproject.toml', 'uv.lock'))
    return {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in sorted(paths) if p.is_file()}


def init_job(template, work=WORK, root=ROOT, spec=SPEC):
    task = read(template)
    config = read(spec / 'config.json')
    validate_task(task)
    validate_config(config)
    texts = {name: load_context(root, name) for name in task['context_files']}
    packet = {'task': task, 'config': config, 'contexts': texts,
              'roles': {role: (spec / 'roles' / f'{role}.md').read_text() for role in ROLES},
              'check_commands': {key: CHECKS[key] for key in task['checks']},
              'verification_inputs': verification_inputs(root),
              'runner_sha256': digest(Path(__file__).read_bytes())}
    serialized = json.dumps(packet, sort_keys=True).encode()
    # Prevent accidentally copying known local credentials into a prose packet.
    for key, value in dotenv_values(root / '.env').items():
        if (value and len(value) > 10 and
            any(x in key.upper() for x in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD')) and
                value.encode() in serialized):
            raise ValueError('Known credential in task packet; remove it before creating a job')
    job_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-' + task['id'] + '-' + uuid.uuid4().hex[:6]
    directory = work / job_id
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / 'packet.json', packet)
    write(directory / 'state.json', {'job_id': job_id, 'created_at': now(),
          'status': 'queued', 'packet_sha256': digest(serialized),
          'backend': 'codex-native', 'role_requests': 0, 'steps': {}})
    return directory


def validate_result(result, phase=None):
    if not isinstance(result, dict) or set(result) != {'summary', 'decision', 'findings', 'tasks'}:
        raise ValueError('Invalid agent result keys')
    if not isinstance(result['summary'], str) or not result['summary'].strip():
        raise ValueError('Missing summary')
    if result['decision'] not in ('ready', 'revise', 'observe'):
        raise ValueError('Invalid decision')
    if phase == 'analysis' and result['decision'] != 'observe':
        raise ValueError('Analysis must report observations, not a new execution approval')
    if phase is not None and phase != 'analysis' and result['decision'] == 'observe':
        raise ValueError('Planning and review require ready or revise, not observe')
    for key in ('findings', 'tasks'):
        if not isinstance(result[key], list):
            raise TypeError(f'Invalid {key}')
    for finding in result['findings']:
        if not isinstance(finding, dict) or set(finding) != {'severity', 'evidence', 'recommendation'}:
            raise ValueError('Invalid finding')
        if finding['severity'] not in ('blocker', 'warning', 'info'):
            raise ValueError('Invalid severity')
        if not all(isinstance(finding[k], str) and finding[k].strip() for k in ('evidence', 'recommendation')):
            raise ValueError('Empty finding')
    for task in result['tasks']:
        if not isinstance(task, dict) or set(task) != {'owner', 'deliverable', 'verification'}:
            raise ValueError('Invalid handoff task')
        if not all(isinstance(x, str) and x.strip() for x in task.values()):
            raise ValueError('Empty task field')
    return result


def ready(result):
    return result['decision'] == 'ready' and not any(f['severity'] == 'blocker' for f in result['findings'])


CONTRACT = '''Return one JSON object with exactly these keys:
summary: nonempty string; decision: ready, revise, or observe;
findings: array of {severity: blocker|warning|info, evidence: string, recommendation: string};
tasks: array of {owner: string, deliverable: string, verification: string}.
Use observe for analysis; otherwise use ready if no blocker, or revise if a blocker exists.
No Markdown fences. Do not claim work you have not observed. All fields use English.
'''


def check_runner(command, output, timeout):
    # No shell or commands from agent outputs. Only registered static argv arrays.
    with (output / 'stdout.txt').open('w') as stdout, (output / 'stderr.txt').open('w') as stderr:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except BaseException as exc:
            import os
            import signal
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            if isinstance(exc, subprocess.TimeoutExpired):
                raise RuntimeError('CheckTimeout') from None  # noqa: TRY004 - timeout, not type validation
            raise
    if code:
        raise RuntimeError(f'CheckFailed: exit code {code}; see preserved logs')
    return {'command': command, 'exit_code': code, 'scope': 'local software check; not a benchmark'}



def frozen(directory, root=ROOT):
    state, packet = read(directory / 'state.json'), read(directory / 'packet.json')
    if digest(json.dumps(packet, sort_keys=True).encode()) != state['packet_sha256']:
        raise RuntimeError('Frozen packet changed; create a new job')
    if packet['runner_sha256'] != digest(Path(__file__).read_bytes()):
        raise RuntimeError('Runner changed; create a new job')
    if packet['verification_inputs'] != verification_inputs(root):
        raise RuntimeError('Verification inputs changed; create a new job')
    if packet['check_commands'] != {k: CHECKS[k] for k in packet['task']['checks']}:
        raise RuntimeError('Check registry changed; create a new job')
    validate_config(packet['config'])
    validate_task(packet['task'])
    # Completed output is frozen too, not merely copied into mutable state.
    for step in state['steps'].values():
        if step['status'] == 'completed':
            path = directory / step['result_path']
            if digest(path.read_bytes()) != step['result_sha256'] or read(path) != step['result']:
                raise RuntimeError('Recorded result changed; restore the original artifact')
    return state, packet


def result_for(state, phase):
    step = state['steps'].get(phase, {})
    if step.get('status') != 'completed':
        raise RuntimeError(f'Dependency incomplete: {phase}')
    return step['result']


def evidence_for(state, phase, packet):
    if phase == 'plan':
        return {}
    plan = result_for(state, 'plan')
    if not ready(plan):
        raise RuntimeError('Plan requires revision; create a new job')
    if phase in ('methods', 'implementation'):
        return {'plan': plan}
    reviews = {role: result_for(state, role) for role in ('methods', 'implementation')}
    if phase == 'synthesis':
        return {'plan': plan, 'reviews': reviews}
    synthesis = result_for(state, 'synthesis')
    if not all(ready(r) for r in (plan, *reviews.values(), synthesis)):
        raise RuntimeError('Reviewer blocker cannot be overridden')
    checks = {key: result_for(state, 'check-' + key) for key in packet['task']['checks']}
    if any(check['exit_code'] != 0 for check in checks.values()):
        raise RuntimeError('Failed checks prevent analysis')
    return {'synthesis': synthesis, 'checks': checks}


def reserve(directory, state, config, work):
    path = work / 'requests-ledger.json'
    ledger = read(path) if path.exists() else {}
    job = ledger.get('jobs', {}).get(state['job_id'])
    if state['role_requests'] and job is None:
        raise RuntimeError('Missing durable request ledger; restore it before retrying')
    day = datetime.now(UTC).date().isoformat()
    daily = ledger.setdefault('days', {}).setdefault(day, {'role_requests': 0})
    job = ledger.setdefault('jobs', {}).setdefault(state['job_id'], {'role_requests': 0})
    if (job['role_requests'] >= config['max_role_requests_per_job'] or
            daily['role_requests'] >= config['max_role_requests_per_day']):
        raise RuntimeError('RequestLimit: reservations retained across failures and retries')
    job['role_requests'] += 1
    daily['role_requests'] += 1
    # Save reservation before request generation. A crash cannot restore the quota.
    write(path, ledger)
    state['role_requests'] = job['role_requests']
    write(directory / 'state.json', state)


def new_attempt(directory, phase, old):
    attempts = [int(p.name.split('-')[1]) for p in (directory / phase).glob('attempt-*')
                if p.is_dir() and re.fullmatch(r'attempt-\d+', p.name)]
    number = max([old.get('attempts', 0), *attempts]) + 1
    output = directory / phase / f'attempt-{number}'
    output.mkdir(parents=True, exist_ok=False)
    return number, output


def has_blocker(state):
    return any(step.get('status') == 'completed' and not ready(step['result'])
               for phase, step in state['steps'].items()
               if phase in ('plan', 'methods', 'implementation', 'synthesis'))


def request_job(directory, phase, *, retry=False, work=WORK, root=ROOT):
    if phase not in PHASES:
        raise ValueError('Unknown phase')
    with lock(work):
        state, packet = frozen(directory, root)
        evidence = evidence_for(state, phase, packet)
        old = state['steps'].get(phase, {})
        if old.get('status') == 'completed':
            raise RuntimeError('Completed phase is reused; no new request')
        if old and not retry:
            raise RuntimeError('Existing request: inspect attempts before explicit --retry')
        if phase in ('methods', 'implementation'):
            active = sum(step.get('status') == 'requested' for key, step in state['steps'].items()
                         if key in ('methods', 'implementation') and key != phase)
            if active >= packet['config']['max_parallel_reviews']:
                raise RuntimeError('ParallelReviewLimit: wait for an outstanding reviewer before requesting another')
        role = phase if phase in ('methods', 'implementation') else 'coordinator'
        instruction = ('Analyze observed checks; decision must be observe. Name every check ID '
                       'and its actual exit code in summary.' if phase == 'analysis' else
                       'Checks have NOT run yet. Use ready or revise; never claim tests passed.')
        payload = {'phase': phase, 'role': role, 'task': packet['task'],
                   'contexts': packet['contexts'], 'evidence': evidence,
                   'instructions': packet['roles'][role] + '\n' + instruction + '\n' + CONTRACT,
                   'dispatch': ('Use a separate current-session Codex subagent with fork_turns=none. '
                                'Give it only this request and preserve its actual agent ID.'
                                if role != 'coordinator' else
                                'The main current-session Codex agent handles this phase.'),
                   'provenance_note': 'Agent IDs are operator-supplied, not authenticated by this recorder.',
                   'packet_sha256': state['packet_sha256']}
        if len(json.dumps(payload, ensure_ascii=False).encode()) > packet['config']['max_context_bytes']:
            raise RuntimeError('ContextLimit')
        reserve(directory, state, packet['config'], work)
        number, output = new_attempt(directory, phase, old)
        payload['output_path'] = str(output / 'agent-output.json')
        write(output / 'request.json', payload)
        state['steps'][phase] = {'status': 'requested', 'attempts': number,
                                'request_path': str((output / 'request.json').relative_to(directory)),
                                'request_sha256': digest((output / 'request.json').read_bytes()),
                                'started_at': now()}
        state['status'] = 'needs_revision' if has_blocker(state) else 'awaiting_codex'
        write(directory / 'state.json', state)
        return output / 'request.json'


def complete_step(directory, state, key, output, result, **extra):
    write(output / 'result.json', result)
    state['steps'][key].update(status='completed', result=result,
        result_path=str((output / 'result.json').relative_to(directory)),
        result_sha256=digest((output / 'result.json').read_bytes()), finished_at=now(), **extra)


def report(directory, state):
    lines = ['# Codex research operations handoff', '', f"Status: {state['status']}",
             f"Recorded logical role requests: {state['role_requests']}", '',
             'This local recorder does not call a model or calculate Codex account billing.',
             'Agent IDs are supplied by the operator; independent review remains a human-audited claim.',
             'Local checks are software verification, not QA benchmark results.', '']
    for key, step in state['steps'].items():
        lines += [f'## {key}', '', f"Status: {step['status']}", '']
        if 'result' in step:
            lines += ['```json', json.dumps(step['result'], ensure_ascii=False, indent=2), '```', '']
    (directory / 'handoff.md').write_text('\n'.join(lines))


def submit_job(directory, phase, result_path, agent_id, *, work=WORK, root=ROOT):
    if phase not in PHASES or not isinstance(agent_id, str) or not agent_id.strip():
        raise ValueError('Supply a phase and actual current-session agent ID')
    with lock(work):
        state, packet = frozen(directory, root)
        step = state['steps'].get(phase, {})
        if step.get('status') != 'requested':
            raise RuntimeError('Generate a new request before submitting')
        output = (directory / step['request_path']).parent
        request_path = output / 'request.json'
        if digest(request_path.read_bytes()) != step['request_sha256']:
            raise RuntimeError('Frozen request changed; restore it before submitting')
        # Keep rejected raw bytes as evidence, even if parsing or attribution fails.
        raw = result_path.read_bytes()
        (output / 'submitted.json').write_bytes(raw)
        write(output / 'provenance.json', {'agent_id': agent_id, 'submitted_at': now(),
              'attribution': 'operator-supplied; not authenticated',
              'request_sha256': step['request_sha256']})
        try:
            evidence = evidence_for(state, phase, packet)
            result = validate_result(json.loads(raw), phase)
            coordinator = state.get('coordinator_agent_id')
            reviewer_ids = {s['agent_id'] for k, s in state['steps'].items()
                            if k in ('methods', 'implementation') and s.get('status') == 'completed'}
            if phase in ('methods', 'implementation'):
                if agent_id == coordinator or agent_id in reviewer_ids:
                    raise ValueError('Reviewers must have distinct IDs from each other and coordinator')
                if result == evidence['plan']:
                    raise ValueError('Reviewer repeated the plan verbatim')
            elif coordinator and agent_id != coordinator:
                raise ValueError('Coordinator phases must retain the main agent ID')
            if phase == 'analysis':
                for key, check in evidence['checks'].items():
                    if not re.search(re.escape(key) + r'[^.;\n]*\b' +
                                     re.escape(str(check['exit_code'])) + r'\b', result['summary']):
                        raise ValueError('Analysis must name each check and its observed exit code')
            complete_step(directory, state, phase, output, result, agent_id=agent_id)
            if phase == 'plan':
                state['coordinator_agent_id'] = agent_id
            state['status'] = ('completed' if phase == 'analysis' else
                               'needs_revision' if has_blocker(state) else 'awaiting_codex')
        except Exception as exc:
            step.update(status='rejected', error_type=type(exc).__name__)
            state['status'] = 'failed'
            write(directory / 'state.json', state)
            report(directory, state)
            raise
        write(directory / 'state.json', state)
        report(directory, state)
        return state


def check_job(directory, *, retry=False, checker=check_runner, work=WORK, root=ROOT):
    with lock(work):
        state, packet = frozen(directory, root)
        approved = [result_for(state, p) for p in ('plan', 'methods', 'implementation', 'synthesis')]
        if not all(ready(r) for r in approved):
            raise RuntimeError('Reviewer blocker cannot be overridden; create a new job')
        for key in packet['task']['checks']:
            phase = 'check-' + key
            old = state['steps'].get(phase, {})
            if old.get('status') == 'completed':
                continue
            if old and not retry:
                raise RuntimeError('Interrupted/failed check: inspect logs before --retry')
            number, output = new_attempt(directory, phase, old)
            state['steps'][phase] = {'status': 'running', 'attempts': number}
            state['status'] = 'checking'
            write(directory / 'state.json', state)
            try:
                result = checker(CHECKS[key], output, packet['config']['check_timeout_seconds'])
                if result.get('exit_code') != 0:
                    raise RuntimeError('Failed check; see preserved logs')
                complete_step(directory, state, phase, output, result)
            except BaseException as exc:
                state['steps'][phase].update(status='failed', error_type=type(exc).__name__)
                state['status'] = 'failed'
                write(directory / 'state.json', state)
                report(directory, state)
                raise
            write(directory / 'state.json', state)
        if state['status'] != 'completed':
            state['status'] = 'awaiting_analysis'
        write(directory / 'state.json', state)
        report(directory, state)
        return state


def resolve_job(job_id, work=WORK):
    if not re.fullmatch(r'[a-zA-Z0-9-]+', job_id):
        raise ValueError('Use the job ID printed by init, not a path')
    path = work / job_id
    if not (path / 'state.json').is_file():
        raise ValueError('Unknown native Codex job ID; historical API jobs remain under research-ops')
    return path


def main():
    parser = argparse.ArgumentParser(description='Local Codex collaboration recorder; no model/API calls.')
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('task', type=Path)
    request = sub.add_parser('request')
    request.add_argument('job_id')
    request.add_argument('phase', choices=PHASES)
    request.add_argument('--retry', action='store_true')
    submit = sub.add_parser('submit')
    submit.add_argument('job_id')
    submit.add_argument('phase', choices=PHASES)
    submit.add_argument('result', type=Path)
    submit.add_argument('--agent-id', required=True)
    check = sub.add_parser('check')
    check.add_argument('job_id')
    check.add_argument('--retry', action='store_true')
    status = sub.add_parser('status')
    status.add_argument('job_id', nargs='?')
    args = parser.parse_args()
    if args.command == 'init':
        with lock(WORK):
            print(init_job(args.task).name)
    elif args.command == 'request':
        print(request_job(resolve_job(args.job_id), args.phase, retry=args.retry))
    elif args.command == 'submit':
        print(json.dumps(submit_job(resolve_job(args.job_id), args.phase, args.result, args.agent_id)))
    elif args.command == 'check':
        print(json.dumps(check_job(resolve_job(args.job_id), retry=args.retry)))
    else:
        paths = [resolve_job(args.job_id) / 'state.json'] if args.job_id else sorted(WORK.glob('*/state.json'))
        for path in paths:
            state = read(path)
            print(json.dumps({k: state[k] for k in ('job_id', 'status', 'backend', 'role_requests')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
