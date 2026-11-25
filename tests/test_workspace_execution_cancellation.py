"""Local cancellation controls, authored fixtures only; no external service calls."""
import base64
from collections import deque
from pathlib import Path
import os

import pytest

from apps.factory_lab.open_ontologies_runner import reason_snapshot
from apps.factory_lab.workspace_reasoning import LocalReasoner, execute
from apps.factory_lab.workspace_store import WorkspaceStore, ExecutionCancelled
from test_workspace_query_contracts import setup_query, approve
from test_workspace_query_reachability import graph
from test_workspace_query_reasoning_service import prepared, approved


def native_fixture(tmp_path):
    marker = tmp_path / 'started'
    binary = tmp_path / 'native-fixture'
    binary.write_text('''#!/usr/bin/python3
import json, os, pathlib, sys, time
commands = json.load(sys.stdin)
pathlib.Path(commands[2]['args'][0]).write_text('<urn:a> <urn:p> <urn:b> .')
for name in ('load', 'reason', 'save'):
    print(json.dumps({'command':name,'result':{'fixpoint_reached':True}}), flush=True)
pathlib.Path(''' + repr(str(marker)) + ''').write_text(str(os.getpid()))
time.sleep(30)
''')
    binary.chmod(0o700)
    return binary, marker


@pytest.mark.parametrize('mode', ['cancel', 'exception', 'timeout'])
def test_owned_process_reaped_and_partial_evidence_retained(tmp_path, mode):
    binary, marker = native_fixture(tmp_path)
    def cancel():
        if not marker.exists():
            return False
        if mode == 'exception':
            raise RuntimeError('fixture callback failure')
        return mode == 'cancel'
    receipt = reason_snapshot(binary, b'<urn:a> <urn:p> <urn:b> .', timeout=1,
                              max_output_bytes=1024, cancel_requested=cancel)
    assert receipt['status'] == {'cancel':'cancelled', 'exception':'failed', 'timeout':'timed_out'}[mode]
    assert receipt['process_started'] and receipt['process_reaped']
    assert receipt['artifact_completeness'] == 'unverified_partial'
    assert receipt['closure_turtle'] and receipt['stdout']
    with pytest.raises(ProcessLookupError):
        os.kill(int(marker.read_text()), 0)


def test_native_prelaunch_cancel_does_not_start(tmp_path):
    binary, marker = native_fixture(tmp_path)
    receipt = reason_snapshot(binary, b'', cancel_requested=lambda: True)
    assert receipt['status'] == 'cancelled' and receipt['process_started'] is False
    assert not marker.exists()


def test_local_prelaunch_cancel_replays_without_running(tmp_path, monkeypatch):
    store = WorkspaceStore(tmp_path / 'store.sqlite')
    row = store.create('test', {})
    calls = []
    reasoner = LocalReasoner('/unused', runner=lambda *a, **kw: calls.append(a))
    checkpoint = store.checkpoint
    def reserve(oid, result):
        checkpoint(oid, result)
        store.request_cancel(row['id'], 'once')
    monkeypatch.setattr(store, 'checkpoint', reserve)
    args = (store, reasoner, row['id'], 1, 'once', base64.b64encode(b'').decode(), 'rdfs')
    result = execute(*args)
    assert result['operation']['state'] == 'cancelled' and not calls
    assert execute(*args)['reused'] and not calls


def test_legacy_injected_runner_no_retry_on_typeerror():
    calls = []
    def legacy(binary, raw, *, profile, timeout, max_output_bytes):
        calls.append(raw)
        raise TypeError('failure after launch')
    with pytest.raises(TypeError):
        LocalReasoner('/unused', runner=legacy).run(b'', 'rdfs', cancel_requested=lambda: False)
    assert calls == [b'']


def test_sqlite_progress_cancellation_is_not_timeout(setup_query):
    engine, draft, relations, *_ = setup_query
    contract = approve(setup_query)
    polls = 0
    def cancel():
        nonlocal polls
        polls += 1
        return polls >= 20
    with pytest.raises(ExecutionCancelled) as err:
        engine.execute(draft, contract, {'status':'ready'}, relations=relations, cancel_requested=cancel)
    assert err.value.evidence['status'] == 'cancelled'
    assert engine.execute(draft, contract, {'status':'ready'}, relations=relations)['rows']


def test_python_traversal_cancellation_retains_found_rows(graph, monkeypatch):
    from apps.factory_lab import workspace_query_reachability as traversal
    engine, draft, relations, spec, _ = graph()
    pending = engine.propose(draft, spec, relations=relations, origin={})
    contract = engine.approve(draft, pending, relations=relations, actor='test', note='fixture', revision=1, human_confirmed=True)
    should_cancel = False
    class ObservedQueue(deque):
        def popleft(self):
            nonlocal should_cancel
            item = super().popleft()
            if item[1] > 0:
                should_cancel = True
            return item
    monkeypatch.setattr(traversal, 'deque', ObservedQueue)
    with pytest.raises(ExecutionCancelled) as err:
        engine.execute(draft, contract, {'seed':0,'kind':'fs'}, relations=relations, cancel_requested=lambda: should_cancel)
    assert err.value.evidence['rows']
    assert err.value.evidence['closure_complete'] is False


def test_source_reasoning_cancel_preserves_raw_receipt_and_replays(prepared):
    service, row, call, _, _ = prepared
    _, approval = approved(prepared)
    calls = []
    def runner(binary, raw, **kwargs):
        calls.append(raw)
        service.store.request_cancel(row['id'], 'reason-cancel')
        return {'status':'cancelled', 'stdout':'partial evidence'}
    service.local_reasoner.runner = runner
    outcome = call('database_reasoning_execute', 'reason-cancel', approval_operation_id=approval['id'])
    assert outcome['state'] == 'cancelled'
    assert outcome['result']['receipt']['stdout'] == 'partial evidence'
    assert not outcome['result']['eligible']
    assert call('database_reasoning_execute', 'reason-cancel', approval_operation_id=approval['id']) == outcome
    assert len(calls) == 1


def test_query_service_cancel_durable_and_replay(prepared, monkeypatch):
    from apps.factory_lab import workspace_query_service as query_service
    service, row, call, execution, _ = prepared
    approval_id = execution['request']['approval_operation_id']
    polls = 0
    def callback(store, oid):
        def poll():
            nonlocal polls
            polls += 1
            if polls == 20:
                store.request_cancel(row['id'], 'query-cancel')
            return store.cancel_requested(oid)
        return poll
    monkeypatch.setattr(query_service, 'cancellation_callback', callback)
    outcome = call('database_query_execute', 'query-cancel', approval_operation_id=approval_id, parameters={})
    assert outcome['state'] == 'cancelled', outcome
    assert outcome['result']['artifact']['status'] == 'cancelled'
    count = polls
    assert call('database_query_execute', 'query-cancel', approval_operation_id=approval_id, parameters={}) == outcome
    assert polls == count


def test_natural_failure_does_not_poll_late_cancel(tmp_path, monkeypatch):
    binary, _ = native_fixture(tmp_path)
    class AlreadyExited:
        returncode = 7
        pid = -1
        def poll(self): return self.returncode
        def wait(self): return self.returncode
    monkeypatch.setattr('apps.factory_lab.open_ontologies_runner.subprocess.Popen', lambda *a, **kw: AlreadyExited())
    calls = []
    def cancel():
        calls.append(True)
        return len(calls) > 1
    receipt = reason_snapshot(binary, b'', cancel_requested=cancel)
    assert receipt['status'] == 'failed' and receipt['exit_code'] == 7
    assert calls == [True]
    assert receipt['termination'] == {'cause': None, 'signal_sent': False, 'signal': None}
