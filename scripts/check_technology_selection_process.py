"""Disposable process-control tests; no performance fixtures/measurements."""
import json
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from technology_selection_process import supervise
from check_technology_selection_python import packet


def main():
    destination = Path(sys.argv[1]); destination.mkdir(parents=True, exist_ok=False)
    with nullcontext(destination) as tmp:
        root = Path(tmp)
        ok = supervise([sys.executable, '-c', 'print("ready")'], root/'ok')
        assert ok['status'] == 'completed' and ok['termination_confirmed']
        slow = supervise([sys.executable, '-c', 'import time; print("started",flush=True); time.sleep(10)'], root/'slow', wall_seconds=0.15, grace_seconds=0.05)
        assert slow['status'] == 'timeout' and slow['termination_confirmed'] and slow['elapsed_ns'] < 2_000_000_000
        flood = supervise([sys.executable, '-c', 'import sys; sys.stdout.write("x"*1000000); sys.stdout.flush()'], root/'flood', byte_limit=1024)
        assert flood['status'] == 'artifact_limit' and flood['bytes'] == 1024
        assert sum(p.stat().st_size for p in (root/'flood').iterdir()) == 1024
        failure = supervise([sys.executable, '-c', 'raise ValueError("preserved")'], root/'failure')
        assert failure['status'] == 'process_error' and b'preserved' in (root/'failure/stderr.log').read_bytes()
        skip = supervise([sys.executable, '-c', 'print(1)'], root/'skip', absolute_deadline=time.monotonic())
        assert skip['status'] == 'not_run' and not (root/'skip').exists()
        try:
            supervise([sys.executable, '-c', 'print(1)'], root/'ok')
        except FileExistsError: pass
        else: raise AssertionError('must preserve original attempt')
        p = packet()
        data = dict(packet=p, updates=dict(E=dict(operation='deactivate_incoming', product_id='X', revision='R1'), C=dict(operation='set_certificate_expiry', certificate_id='certificate', expires='2026-11-01')))
        source = root/'runtime.json'; source.write_text(json.dumps(data))
        result = supervise([sys.executable, 'scripts/technology_selection_worker.py', 'python_indexed', str(source)], root/'worker')
        events = [json.loads(line) for line in (root/'worker/stdout.log').read_text().splitlines()]
        assert result['status'] == 'completed', events
        assert events[-1]['event'] == 'complete' and events[-1]['queries'] == 114
        queries = [e for e in events if e['event'] == 'query']
        assert len(queries) == 114 and {e['phase'] for e in queries} == {'warmup','steady_1','steady_10','steady_100','post_E','post_C'}
        assert all(e['duration_ns'] >= 0 for e in queries)
        known = {}
        for event in queries:
            if 'answer' in event: known[event['digest']] = event['answer']
            assert event['digest'] in known
        assert len(known) == 3
        print('7 disposable checks passed; one handcrafted Python lifecycle/114 bundles; 0 performance fixture executions')


if __name__ == '__main__': main()
