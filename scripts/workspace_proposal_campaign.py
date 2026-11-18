"""Frozen proposal packet execution; explicit operator authorization, no retries.

Authorization is an operator record, not proof of human identity. This module
never reads evaluation rubrics. Use export_attempts after interruption; execution
requires a fresh directory and cannot resume or overwrite an earlier campaign.
"""
import fcntl
import hashlib
import json
import os
import sqlite3
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apps.factory_lab.public_runtime import PublicGateway
from apps.factory_lab.store import Store, dumps
from scripts.workspace_proposal_preflight import inspect


def write_new(path, value):
    with path.open('x') as stream:
        stream.write(dumps(value))
        stream.flush()
        os.fsync(stream.fileno())


def export_attempts(directory):
    """Read retained runs only. Never recover, settle billing or call a gateway."""
    root = Path(directory)
    database = (root / 'state.sqlite').resolve()
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        runs = [dict(r) for r in connection.execute('SELECT * FROM runs ORDER BY created,id')]
        calls = [dict(r) for r in connection.execute('SELECT * FROM calls')]
    budget = {
        'attempts': len(calls),
        'reserved_nonrefunded_usd': str(sum((Decimal(r['reserved']) for r in calls), Decimal(0))),
        'reported_usd': str(sum((Decimal(str(json.loads(r['details']).get('cost') or 0)) for r in calls), Decimal(0))),
        'unresolved': sum(r['status'] == 'reserved' or json.loads(r['details']).get('cost') is None for r in calls),
    }
    records = []
    for run in runs:
        run['config'] = json.loads(run['config'])
        item = {'case_id': run['config']['case_id'], 'attempt_id': run['id'],
                'packet_sha256': run['config']['packet_sha256']}
        if run['status'] == 'completed':
            item.update(status='response', message=json.loads(run['answer']))
        else:
            item.update(status='failed', error=run['status'],
                        interruption_or_failure_does_not_imply_no_charge=True)
        records.append(item)
    return {'attempts': records, 'budget': budget,
            'scope': 'Recorded attempts only; absent cases remain not attempted. No semantic scoring.'}


def execute(packet_dir, endpoints_path, config, authorization, directory, key,
            gateway_factory=PublicGateway):
    """Run each frozen packet once. Caller must supply a genuinely approved scope."""
    report = inspect(packet_dir, endpoints_path, config)
    required = {'approved', 'approval_reference', 'deadline', 'config_sha256',
                'manifest_sha256', 'endpoints_sha256'}
    if set(authorization) != required or authorization['approved'] is not True:
        raise ValueError('Explicit bounded authorization record required')
    if not isinstance(authorization['approval_reference'], str) or not authorization['approval_reference'].strip():
        raise ValueError('Human approval reference required')
    for field in ('config_sha256', 'manifest_sha256', 'endpoints_sha256'):
        if authorization[field] != report[field]:
            raise ValueError('Authorization does not bind frozen scope')
    deadline = datetime.fromisoformat(authorization['deadline'])
    now = datetime.now(timezone.utc)
    if deadline.tzinfo is None or not now + timedelta(seconds=90) < deadline <= now + timedelta(hours=config['hours']):
        raise ValueError('Absolute deadline outside approved execution window')
    # Load and recheck every byte before creating a client; use this immutable
    # in-memory copy so source edits during execution cannot change later calls.
    packets = []
    for record in report['records']:
        raw = (Path(packet_dir) / (record['case_id'] + '-messages.json')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record['packet_sha256']:
            raise ValueError('Packet changed after preflight')
        packets.append((record, json.loads(raw)))
    root = Path(directory)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    with (root / 'campaign.lock').open('x') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        write_new(root / 'authorization.json', authorization)
        write_new(root / 'preflight.json', report)
        write_new(root / 'session.json', {
            'config_sha256': report['config_sha256'], 'deadline': deadline.isoformat(),
            'max_attempts': config['max_calls'], 'max_usd': str(config['max_usd'])})
        store = Store(root / 'state.sqlite')
        gateway = gateway_factory(store, root, config, key)
        for record, messages in packets:
            if datetime.now(timezone.utc) + timedelta(seconds=90) >= deadline:
                break
            # Committed case/run binding precedes any call, including failures.
            rid = store.create({'case_id': record['case_id'],
                                'packet_sha256': record['packet_sha256']})
            store.status(rid, 'running')
            try:
                message = gateway.call(rid, messages)
                if not isinstance(message, dict) or not isinstance(message.get('content'), str):
                    raise ValueError('Missing provider text message')
                store.status(rid, 'completed', dumps(message))
            except Exception as exc:
                # Avoid persisting exception text that might contain credentials.
                store.event(rid, 'campaign_failure', {'error_type': type(exc).__name__})
                store.status(rid, 'failed')
                break
        result = export_attempts(root)
        write_new(root / 'attempts.json', result)
        return result
