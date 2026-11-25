"""Prepare and explicitly execute one bounded, new semantic campaign.

Linux only. No service starts on import or prepare. The operator supplies verified
provider prices/full token ceilings, an owned already-running loopback catalog,
and separate paid authorization. Historical campaigns cannot be resumed here.
The outer supervisor owns its process tree, including bridge-created sessions.
Invoke as a standalone Linux command, not embedded in an application spawning
unrelated concurrent children: newly adopted children belong to this launch.
"""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time

from . import auto_ontology_bridge as bridge
from .extension_gateway import Config, Gateway, Model
from .extension_gateway_http import create_server, openrouter_transport
from .workspace_database import SQLiteSources

ROOT = Path(__file__).resolve().parents[2]
CHAT = 'openai/auto-ontology-reasoning'
EMBED = 'openai/auto-ontology-embedding'
FORMAT = 'auto-ontology-semantic-campaign-1'
CONFIG_KEYS = {'models', 'call_cap', 'per_call_nanodollars', 'total_nanodollars',
               'deadline_epoch', 'timeout_seconds', 'max_request_bytes',
               'max_response_bytes', 'chat_attempt_cap', 'embedding_attempt_cap'}
MODEL_KEYS = {'alias', 'actual_id', 'kind', 'provider', 'input_nanodollars_per_token',
              'output_nanodollars_per_token', 'max_input_tokens', 'max_output_tokens',
              'verification', 'reservation_nanodollars', 'billing_output_tokens'}
CODE = ('auto_ontology_semantic_cli.py', 'auto_ontology_bridge.py',
        'extension_gateway.py', 'extension_gateway_http.py', 'workspace_database.py')


class OperatorError(ValueError):
    """Controlled message; never include credentials or raw external exceptions."""


def require(value, message):
    if not value:
        raise OperatorError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise OperatorError('Nonfinite JSON number')
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def save(path, value):
    """Atomic durable private receipt; callers never serialize credential config."""
    path = Path(path)
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('wb') as stream:
        os.chmod(temporary, 0o600)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_file(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Private input must be a regular file')
    require(path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o077 == 0,
            'Private input must be operator-owned with mode 0600 or stricter')
    return path.resolve()


def budget_config(value):
    require(type(value) is dict and set(value) == {'format', 'config', 'wall_timeout_seconds', 'bridge_limits'},
            'Explicit budget envelope required; continuation is unsupported')
    require(value['format'] in ('auto-ontology-semantic-budget-1', 'auto-ontology-semantic-budget-2'), 'Unsupported budget format')
    data = value['config']
    extra = ({'reservation_accounting', 'inherited_attempts', 'inherited_reserved_nanodollars',
              'prior_ledger_path', 'prior_ledger_sha256', 'campaign_lock_path'}
             if value['format'] == 'auto-ontology-semantic-budget-2' else set())
    require(type(data) is dict and set(data) == CONFIG_KEYS | extra, 'All budget fields required')
    require(type(data['models']) is list and len(data['models']) == 2, 'Exactly two model aliases required')
    require(all(type(m) is dict and set(m) == MODEL_KEYS for m in data['models']), 'Explicit model fields required')
    models = tuple(Model(**m) for m in data['models'])
    require({m.alias: m.kind for m in models} == {CHAT: 'chat', EMBED: 'embedding'}, 'Unsupported alias or role')
    require(all(isinstance(m.verification, str) and len(m.verification.strip()) >= 8 and
                'REPLACE' not in m.verification for m in models), 'Supply reviewed pricing/ceiling evidence reference')
    cfg = Config(**{**data, 'models': models})
    cfg.validate()
    require(type(data['deadline_epoch']) in (float, int) and not isinstance(data['deadline_epoch'], bool),
            'Deadline must be an absolute UTC epoch number')
    require(1 <= cfg.call_cap <= 1000 and 1 <= cfg.chat_attempt_cap <= cfg.call_cap and
            1 <= cfg.embedding_attempt_cap <= cfg.call_cap, 'Explicit bounded role call caps required')
    require(cfg.timeout_seconds <= 120 and cfg.max_request_bytes <= 4*1024*1024 and
            cfg.max_response_bytes <= 16*1024*1024, 'Transport bounds exceed operator limits')
    wall = value['wall_timeout_seconds']
    require(type(wall) is int and cfg.timeout_seconds <= wall <= 1800, 'Wall timeout must be bounded and cover one request')
    require(type(value['bridge_limits']) is dict and set(value['bridge_limits']) == set(asdict(bridge.BridgeLimits())),
            'All bridge limits required')
    limits = bridge.BridgeLimits(**value['bridge_limits'])
    limits.validate()
    ceiling = bridge.BridgeLimits(timeout_seconds=1800)
    require(all(v <= asdict(ceiling)[k] for k, v in asdict(limits).items()) and limits.timeout_seconds <= wall,
            'Bridge limits exceed public launcher bounds')
    return cfg, limits


def clean_env():
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONNOUSERSITE': '1',
            'PYTHON_DOTENV_DISABLED': '1'}


def upstream_identity(root, executable):
    root, executable = Path(root).resolve(), Path(executable).absolute()
    require(root.is_dir() and executable.is_file() and os.access(executable, os.X_OK), 'Installed upstream unavailable')
    def git(*args):
        p = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                           env=clean_env(), timeout=15, check=True)
        return p.stdout.decode().strip()
    require(git('rev-parse', 'HEAD') == bridge.UPSTREAM_COMMIT, 'Upstream commit differs from bridge pin')
    require(not git('status', '--porcelain', '--untracked-files=all'), 'Upstream checkout must be clean')
    files = [root/'uv.lock', executable.resolve()]
    cfg = executable.parent.parent/'pyvenv.cfg'
    require(cfg.is_file(), 'Installed upstream virtual environment metadata unavailable')
    files.append(cfg)
    return {'commit': bridge.UPSTREAM_COMMIT, 'files': {str(p): digest(p) for p in files}}


def code_identity():
    paths = [Path(__file__).parent/name for name in CODE] + [ROOT/'uv.lock', Path(sys.executable).resolve()]
    return {str(p.resolve()): digest(p) for p in paths}


def source_identity(registry_path, source_id, limits):
    require(Path(registry_path).is_dir(), 'Existing source registry required')
    registry = SQLiteSources(registry_path, max_bytes=limits.max_source_bytes)
    record = registry._record(source_id)
    require(record.get('source_id') == source_id, 'Registry record identity differs from requested source')
    raw = registry._data(record)
    require(len(raw) <= limits.max_source_bytes, 'Source exceeds semantic byte bound')
    # Mirror the bridge's semantic preflight without upstream imports/network.
    rows = {}
    deadline = time.monotonic() + 10
    with registry._connection(raw) as conn:
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        require(not conn.execute("SELECT 1 FROM sqlite_master WHERE type='view' LIMIT 1").fetchone(), 'Views unsupported')
        tables = registry._catalog(conn)
        require(len(tables) <= limits.max_tables, 'Too many source tables')
        for name, columns in tables.items():
            require('"' not in name and len(columns) <= limits.max_columns_per_table, 'Unsupported source schema')
            quoted = '"' + name + '"'
            rows[name] = conn.execute('SELECT count(*) FROM ' + quoted).fetchone()[0]
            require(rows[name] <= limits.max_rows_per_table, 'Source exceeds semantic row bound')
            for row in conn.execute('SELECT * FROM ' + quoted):
                require(time.monotonic() <= deadline, 'Semantic preflight timed out')
                require(all(not isinstance(v, (str, bytes)) or
                            len(v.encode() if isinstance(v, str) else v) <= limits.max_cell_bytes for v in row),
                        'Source exceeds semantic cell bound')
    return {'source_id': source_id, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
            'registry_record_sha256': digest(Path(registry_path)/(source_id+'.json')),
            'per_table_rows': rows, 'sampled': False}


def prepare(*, registry, source_id, upstream_root, upstream_python, postgres_config,
            budget, output, request_id, authorization_reference):
    require(sys.platform == 'linux', 'Linux process supervision required')
    require(isinstance(request_id, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', request_id), 'Explicit request ID required')
    require(isinstance(authorization_reference, str) and 8 <= len(authorization_reference) <= 1000 and
            'REPLACE' not in authorization_reference, 'Explicit new-campaign authorization reference required')
    output = Path(output).resolve()
    require(not output.exists() and not output.is_symlink(), 'Output must be a new private directory')
    pg = private_file(postgres_config)
    budget_path = Path(budget).resolve()
    value = read_json(budget_path)
    cfg, limits = budget_config(value)
    require(time.time() + cfg.timeout_seconds < cfg.deadline_epoch, 'Campaign deadline expired or too close')
    registry, upstream_root, upstream_python = Path(registry).resolve(), Path(upstream_root).resolve(), Path(upstream_python).absolute()
    manifest = {'format': FORMAT, 'campaign_kind': 'new_only_no_continuation', 'request_id': request_id,
                'authorization_reference': authorization_reference, 'output': str(output),
                'ledger': str(output/'campaign.sqlite'), 'registry': str(registry),
                'upstream_root': str(upstream_root), 'upstream_python': str(upstream_python),
                'budget_path': str(budget_path), 'budget_sha256': digest(budget_path), 'budget': value,
                'postgres_config_path': str(pg), 'postgres_config_sha256': digest(pg),
                'source': source_identity(registry, source_id, limits),
                'upstream': upstream_identity(upstream_root, upstream_python), 'code_hashes': code_identity(),
                'role_routing': {'REASONING': CHAT, 'NON_REASONING': CHAT, 'RERANK': CHAT, 'EMBED': EMBED},
                'scope': 'One semantic invocation; whole bounded registered snapshot; no documents or automatic approval',
                'limitations': ['Provider evidence supplied by operator, not automatically authenticated.',
                    'Reservations are nonrefunded ceilings, not reported charges.',
                    'Native return does not establish semantic completeness or truth.',
                    'Linux process supervision is not an OS network sandbox.',
                    'No prior campaign may be reset or silently renewed using this new-campaign command.']}
    os.umask(0o077)
    output.mkdir(mode=0o700, parents=False)
    save(output/'manifest.json', manifest)
    return {'status': 'prepared_not_executed', 'manifest': str(output/'manifest.json'),
            'manifest_sha256': digest(output/'manifest.json')}


def validate_bindings(manifest):
    require(manifest['format'] == FORMAT and manifest['campaign_kind'] == 'new_only_no_continuation', 'Unsupported campaign')
    cfg, limits = budget_config(manifest['budget'])
    require(time.time() + cfg.timeout_seconds < cfg.deadline_epoch, 'Campaign deadline expired or too close')
    require(digest(manifest['budget_path']) == manifest['budget_sha256'] and
            read_json(manifest['budget_path']) == manifest['budget'], 'Budget file changed')
    require(digest(private_file(manifest['postgres_config_path'])) == manifest['postgres_config_sha256'], 'Private catalog config changed')
    require(code_identity() == manifest['code_hashes'], 'Launcher or dependency code changed')
    require(upstream_identity(manifest['upstream_root'], manifest['upstream_python']) == manifest['upstream'], 'Upstream identity changed')
    require(source_identity(manifest['registry'], manifest['source']['source_id'], limits) == manifest['source'], 'Registered source changed')
    require(manifest['role_routing'] == {'REASONING': CHAT, 'NON_REASONING': CHAT, 'RERANK': CHAT, 'EMBED': EMBED},
            'Role routing changed')
    return cfg, limits


def catalog_config(manifest):
    data = read_json(manifest['postgres_config_path'])
    require(type(data) is dict and set(data) == {'postgres'}, 'Catalog file must contain postgres only')
    # Validates loopback, fields and types; does not connect or log values.
    bridge.child_environment(data, 'catalog')
    return data


def catalog_ready(data):
    # Connection only at execute, before the provider credential is read.
    pg = data['postgres']
    with socket.create_connection((pg['host'], pg['port']), timeout=2):
        pass


def proc_record(pid):
    try:
        raw = Path('/proc')/str(pid)/'stat'
        tail = raw.read_text().rsplit(')', 1)[1].split()
        return {'pid': int(pid), 'ppid': int(tail[1]), 'start': int(tail[19]), 'state': tail[0]}
    except (FileNotFoundError, ProcessLookupError):
        return None


def proc_table():
    result = {}
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            record = proc_record(int(path.name))
            if record:
                result[record['pid']] = record
    return result


def set_subreaper(enabled):
    require(sys.platform == 'linux', 'Linux subreaper required')
    libc = ctypes.CDLL(None, use_errno=True)
    old = ctypes.c_int()
    require(libc.prctl(37, ctypes.byref(old), 0, 0, 0) == 0, 'Cannot inspect subreaper state')
    require(libc.prctl(36, int(enabled), 0, 0, 0) == 0, 'Cannot configure subreaper')
    return old.value


def kill_owned_tree(process, baseline, root_identity, *, timeout=5):
    """Freeze then kill/reap descendants, including newly adopted setsid children.

    Standalone launcher owns all new direct children after baseline. Every signal
    checks /proc starttime to avoid signaling a reused PID. Unknown cleanup fails.
    """
    owned = {}
    if root_identity:
        owned[process.pid] = root_identity
    errors = []
    deadline = time.monotonic() + timeout
    stable = 0
    while time.monotonic() < deadline and stable < 2:
        table = proc_table()
        before = len(owned)
        for pid, record in table.items():
            if record['ppid'] == os.getpid() and (pid, record['start']) not in baseline:
                if pid in owned and owned[pid]['start'] != record['start']:
                    errors.append('owned_pid_identity_changed')
                else:
                    owned[pid] = record
        changed = True
        while changed:
            changed = False
            for pid, record in table.items():
                parent = table.get(record['ppid'])
                if (parent and record['ppid'] in owned and parent['start'] == owned[record['ppid']]['start'] and pid not in owned):
                    owned[pid] = record
                    changed = True
        for pid, identity in list(owned.items()):
            current = proc_record(pid)
            if current and current['start'] == identity['start']:
                try:
                    os.kill(pid, signal.SIGSTOP)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    errors.append(type(exc).__name__)
        stable = stable + 1 if len(owned) == before else 0
        time.sleep(.02)
    for pid, identity in reversed(list(owned.items())):
        current = proc_record(pid)
        if current and current['start'] == identity['start']:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as exc:
                errors.append(type(exc).__name__)
    while time.monotonic() < deadline:
        process.poll()
        for pid in owned:
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass
        alive = [pid for pid, identity in owned.items()
                 if (current := proc_record(pid)) and current['start'] == identity['start']]
        adopted = [r for r in proc_table().values() if r['ppid'] == os.getpid() and (r['pid'], r['start']) not in baseline]
        if not alive and not adopted:
            return {'verified': not errors, 'owned_identities': list(owned.values()), 'errors': errors, 'remaining': []}
        time.sleep(.02)
    return {'verified': False, 'owned_identities': list(owned.values()), 'errors': errors,
            'remaining': [r for r in proc_table().values() if r['ppid'] == os.getpid() and (r['pid'], r['start']) not in baseline]}


def supervise(command, secret, output, wall_seconds, deadline_epoch, *, interruption=None):
    """Offline-testable process seam. Command must be a trusted local worker.

    The provider credential is written only to an inherited pipe. No real key is
    inherited in env/argv/files. Tests inject a fake command and fake secret.
    """
    require(threading.current_thread() is threading.main_thread(), 'Standalone main-thread launcher required')
    old_subreaper = set_subreaper(True)
    baseline = {(r['pid'], r['start']) for r in proc_table().values() if r['ppid'] == os.getpid()}
    process = None
    root_identity = None
    record = {'status': 'launching', 'cleanup': {'verified': False}}
    old_handlers = {}
    stopped = []
    def interrupt(signum, frame):
        stopped.append(signum)
    for signum in (signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, interrupt)
    began = time.monotonic()
    try:
        env = clean_env()
        with (output/'worker.stdout').open('xb') as stdout, (output/'worker.stderr').open('xb') as stderr:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                       cwd=ROOT, env=env, start_new_session=True)
            root_identity = proc_record(process.pid)
            record['pid'] = process.pid
            record['process_start_identity'] = root_identity
            save(output/'process.json', record)
            # Validated secret is < PIPE_BUF, so one write cannot wait on a full pipe.
            try:
                process.stdin.write(secret.encode('ascii'))
                process.stdin.close()
            except BrokenPipeError:
                pass
            while True:
                code = process.poll()
                if code is not None:
                    record.update(status='exited', returncode=code)
                    break
                if stopped or (interruption is not None and interruption()):
                    record.update(status='interrupted', signal=stopped[0] if stopped else None)
                    break
                if time.monotonic()-began >= wall_seconds or time.time() >= deadline_epoch:
                    record['status'] = 'wall_or_absolute_timeout'
                    break
                time.sleep(.05)
    except BaseException as exc:
        record.update(status='supervision_failed', error_class=type(exc).__name__)
    finally:
        try:
            if process is not None:
                record['cleanup'] = kill_owned_tree(process, baseline, root_identity)
                record['returncode'] = process.poll()
            else:
                record['cleanup'] = {'verified': True, 'owned_identities': [], 'remaining': []}
        except BaseException as exc:
            record['cleanup'] = {'verified': False, 'error_class': type(exc).__name__}
            # Best effort after an inspection failure; never relabel this as verified.
            if process is not None:
                try:
                    current = proc_record(process.pid)
                    if current and root_identity and current['start'] == root_identity['start']:
                        os.killpg(process.pid, signal.SIGKILL)
                    record['cleanup']['fallback'] = kill_owned_tree(process, baseline, root_identity, timeout=2)
                except BaseException as fallback:
                    record['cleanup']['fallback_error_class'] = type(fallback).__name__
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)
        try:
            set_subreaper(bool(old_subreaper))
        except BaseException as exc:
            record['cleanup']['verified'] = False
            record['cleanup']['restore_error_class'] = type(exc).__name__
        record['elapsed_seconds'] = time.monotonic()-began
        save(output/'process.json', record)
    return record


def ledger_summary(path):
    """Aggregate accounting only; never export raw prompts or responses."""
    if not Path(path).exists():
        return {'ledger_present': False, 'attempts': 0, 'reserved_nanodollars': 0,
                'unresolved_attempts': 0, 'reported_cost_usd': None, 'reported_cost_status': 'no_attempts'}
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=2) as db:
        count, reserved = db.execute('SELECT COUNT(*),COALESCE(SUM(reserved),0) FROM attempts').fetchone()
        unresolved = db.execute('SELECT COUNT(*) FROM attempts a LEFT JOIN completions c ON a.id=c.attempt WHERE c.attempt IS NULL').fetchone()[0]
        failed = db.execute('SELECT COUNT(*) FROM completions WHERE error IS NOT NULL').fetchone()[0]
        cost, known = Decimal(0), 0
        for (usage,) in db.execute('SELECT usage FROM completions'):
            try:
                value = json.loads(usage or 'null')
                item = value.get('cost') if isinstance(value, dict) else None
                if item is None or isinstance(item, bool):
                    continue
                amount = Decimal(str(item))
                if amount.is_finite() and amount >= 0:
                    cost += amount
                    known += 1
            except (ValueError, TypeError, InvalidOperation):
                pass
    return {'ledger_present': True, 'attempts': count, 'reserved_nanodollars': reserved,
            'unresolved_attempts': unresolved, 'failed_completions': failed,
            'reported_cost_usd': str(cost) if known else None, 'reported_cost_records': known,
            'missing_reported_cost_records': count-known,
            'reported_cost_status': 'complete_provider_reports_not_invoice' if known == count and count else 'incomplete_or_unreported',
            'reservations_refunded': False}


def worker_run(manifest, secret, *, transport=openrouter_transport):
    """Internal worker; tests may inject transport, production CLI never does."""
    cfg, limits = validate_bindings(manifest)
    pg = catalog_config(manifest)
    output = Path(manifest['output'])
    ledger = Path(manifest['ledger'])
    require(not ledger.exists(), 'New campaign ledger required')
    # Claim ledger creation exclusively; Gateway initializes this owned empty file.
    with ledger.open('xb'):
        pass
    os.chmod(ledger, 0o600)
    dummy = secrets.token_urlsafe(32)
    gateway = Gateway(ledger, cfg, secret, transport)
    server = None
    thread = None
    receipt = {'status': 'worker_started', 'approval': 'not_granted'}
    try:
        server = create_server(gateway, dummy, concurrency=1)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config = {**pg, 'gateway': {'endpoint': f'http://127.0.0.1:{server.server_address[1]}/v1',
                  'token': dummy, 'chat_model': CHAT, 'embedding_model': EMBED},
                  'request_id': manifest['request_id'], 'reservation_id': 'campaign:'+digest(output/'manifest.json')}
        result = bridge.invoke(SQLiteSources(manifest['registry']), manifest['source']['source_id'],
            output_root=output/'invocations', upstream_root=manifest['upstream_root'],
            python_executable=manifest['upstream_python'], operator_config=config, mode='semantic', limits=limits)
        receipt.update(status=result['status'], invocation_receipt=result)
        if result['status'] == 'returned_requires_review':
            require(result['source_id'] == manifest['source']['source_id'] and
                    result['source_sha256'] == manifest['source']['sha256'], 'Native source binding differs')
            require(source_identity(manifest['registry'], manifest['source']['source_id'], limits) == manifest['source'],
                    'Registered source changed during invocation')
        save(output/'worker-result.json', receipt)
        return 0 if result['status'] == 'returned_requires_review' else 1
    except BaseException as exc:
        receipt.update(status='worker_failed', error_class=type(exc).__name__)
        save(output/'worker-result.json', receipt)
        return 1
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        gateway.close()


def execute(manifest_path, expected_sha256, *, authorize_paid_execution=False,
            secret_reader=None, worker_command=None, ready_check=None, interruption=None):
    """Explicit new invocation. Injection seams exist only for offline Python tests."""
    require(authorize_paid_execution, 'Explicit --authorize-paid-execution required')
    require(sys.platform == 'linux', 'Linux process supervision required')
    path = private_file(manifest_path)
    require(re.fullmatch(r'[a-f0-9]{64}', expected_sha256 or '') and digest(path) == expected_sha256, 'Manifest hash differs')
    manifest = read_json(path)
    output = path.parent
    require(path.name == 'manifest.json' and str(output) == manifest['output'] and
            manifest['ledger'] == str(output/'campaign.sqlite'), 'Manifest/output binding differs')
    require(output.stat().st_uid == os.getuid() and output.stat().st_mode & 0o077 == 0, 'Output directory must remain private')
    require(not (output/'campaign.sqlite').exists(), 'Ledger already exists; continuation unsupported')
    os.umask(0o077)
    # Never remove this claim, even after failure: retry requires a newly reviewed campaign.
    with (output/'execution.claim').open('xb') as claim:
        claim.write((expected_sha256+'\n').encode())
        claim.flush()
        os.fsync(claim.fileno())
    receipt = {'format': FORMAT, 'status': 'preflight', 'manifest_sha256': expected_sha256,
               'request_id': manifest['request_id'], 'authorization_reference': manifest['authorization_reference'],
               'campaign_kind': 'new_only_no_continuation', 'approval': 'not_granted',
               'execution_kind': 'offline_injected_worker' if worker_command else 'actual_semantic_invocation',
               'started_epoch': time.time(), 'provider_secret_read': False}
    save(output/'execution.json', receipt)
    try:
        cfg, _ = validate_bindings(manifest)
        data = catalog_config(manifest)
        (ready_check or catalog_ready)(data)
        require(time.time()+cfg.timeout_seconds < cfg.deadline_epoch, 'Deadline expired during preflight')
        secret = (secret_reader or (lambda: os.environ.get('OPENROUTER_API_KEY', '')))()
        require(type(secret) is str and 1 <= len(secret) <= 2048 and secret.isascii() and
                all(32 < ord(c) < 127 for c in secret) and secret != 'fakekey', 'Parent provider credential required')
        receipt['provider_secret_read'] = True
        receipt['status'] = 'running'
        save(output/'execution.json', receipt)
        command = worker_command or [sys.executable, '-m', 'apps.factory_lab.auto_ontology_semantic_cli',
                                     '_worker', '--manifest', str(path), '--manifest-sha256', expected_sha256]
        process = supervise(command, secret, output, manifest['budget']['wall_timeout_seconds'],
                            cfg.deadline_epoch, interruption=interruption)
        del secret
        receipt['process'] = process
        receipt['status'] = 'returned_requires_review' if (process['status'] == 'exited' and process.get('returncode') == 0 and
                                                          process['cleanup']['verified']) else 'failed_or_interrupted'
        # A fixture cannot masquerade as an actual upstream success.
        if worker_command:
            receipt['status'] = 'offline_fixture_returned' if receipt['status'] == 'returned_requires_review' else receipt['status']
        elif receipt['status'] == 'returned_requires_review':
            result = read_json(output/'worker-result.json')
            require(result['status'] == 'returned_requires_review' and result['approval'] == 'not_granted', 'Native result unavailable')
            receipt['invocation_id'] = result['invocation_receipt']['invocation_id']
    except BaseException as exc:
        receipt.update(status='failed_or_interrupted', error_class=type(exc).__name__)
    finally:
        try:
            receipt['accounting'] = ledger_summary(output/'campaign.sqlite')
            if receipt['accounting']['unresolved_attempts']:
                receipt['status'] = 'failed_or_interrupted'
            if receipt['status'] == 'returned_requires_review' and not receipt['accounting']['ledger_present']:
                receipt['status'] = 'failed_or_interrupted'
        except BaseException as exc:
            receipt['accounting'] = {'status': 'unavailable', 'error_class': type(exc).__name__,
                                     'costs': 'unknown_preserve_ledger_no_refund'}
            receipt['status'] = 'failed_or_interrupted'
        receipt['finished_epoch'] = time.time()
        save(output/'execution.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare', help='Offline freeze; no credential read, gateway, service or paid call')
    for name in ('registry', 'upstream-root', 'upstream-python', 'postgres-config', 'budget', 'output'):
        prep.add_argument('--'+name, type=Path, required=True)
    for name in ('source-id', 'request-id', 'authorization-reference'):
        prep.add_argument('--'+name, required=True)
    run = commands.add_parser('execute', help='One explicitly authorized new paid campaign; never resume')
    run.add_argument('--manifest', type=Path, required=True)
    run.add_argument('--manifest-sha256', required=True)
    run.add_argument('--authorize-paid-execution', action='store_true')
    worker = commands.add_parser('_worker', help=argparse.SUPPRESS)
    worker.add_argument('--manifest', type=Path, required=True)
    worker.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            result = prepare(**{k: v for k, v in vars(args).items() if k != 'command'})
        elif args.command == 'execute':
            result = execute(args.manifest, args.manifest_sha256, authorize_paid_execution=args.authorize_paid_execution)
        else:
            os.umask(0o077)
            require(digest(args.manifest) == args.manifest_sha256, 'Worker manifest differs')
            manifest = read_json(args.manifest)
            require((Path(manifest['output'])/'execution.claim').read_text().strip() == args.manifest_sha256, 'Parent launch claim missing')
            # Actual key arrives only through inherited stdin. Never read dotenv/env here.
            secret = sys.stdin.buffer.read(2049).decode('ascii')
            require(1 <= len(secret) <= 2048, 'Bounded credential pipe required')
            return worker_run(manifest, secret)
        print(json.dumps(result if args.command == 'prepare' else {
            'status': result['status'], 'receipt': str(args.manifest.parent/'execution.json'),
            'accounting': result['accounting']}, indent=2))
        return 0 if result['status'] in ('prepared_not_executed', 'returned_requires_review') else 1
    except (Exception, KeyboardInterrupt):
        parser.exit(1, 'Semantic operator request rejected or failed; inspect private retained artifacts.\n')


if __name__ == '__main__':
    raise SystemExit(main())
