"""One resident algorithm process. Reads runtime packet only, never scorer files."""
import sys
import json
import time
import resource
import hashlib
from pathlib import Path


def emit(event, **fields):
    print(json.dumps(dict(event=event, **fields), sort_keys=True, separators=(',', ':')), flush=True)


def main():
    resource.setrlimit(resource.RLIMIT_AS, (1536*1024*1024, 1536*1024*1024))
    emit('phase', phase='imports')
    start = time.perf_counter_ns()
    arm_name, input_path = sys.argv[1:]
    if arm_name == 'python_indexed':
        from technology_selection_python import PythonArm as Arm
    elif arm_name == 'sqlite_recursive':
        from technology_selection_sqlite import SQLiteArm as Arm
    elif arm_name == 'rdf_owl_shacl':
        from technology_selection_rdf import RDFArm as Arm
    else:
        raise ValueError('unknown arm')
    emit('imports', duration_ns=time.perf_counter_ns()-start)
    start = time.perf_counter_ns(); data = json.loads(Path(input_path).read_text())
    emit('input', duration_ns=time.perf_counter_ns()-start)
    emit('phase', phase='prepare')
    start = time.perf_counter_ns(); arm = Arm(data['packet'])
    emit('prepare', duration_ns=time.perf_counter_ns()-start, normalization_ns=arm.normalization_ns, setup_ns=arm.setup_ns)
    seen = set(); completed = 0
    def query(phase, iteration):
        nonlocal completed
        start = time.perf_counter_ns(); answer = arm.query(); elapsed = time.perf_counter_ns()-start
        payload = json.dumps(answer, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        extra = dict(answer=answer) if digest not in seen else {}
        seen.add(digest); completed += 1
        emit('query', phase=phase, iteration=iteration, duration_ns=elapsed, digest=digest, **extra)
        return elapsed
    emit('phase', phase='warmup'); query('warmup', 0)
    for batch in (1, 10, 100):
        phase = f'steady_{batch}'; emit('phase', phase=phase)
        total = sum(query(phase, i) for i in range(batch))
        emit('batch', phase=phase, queries=batch, query_sum_ns=total)
    for label in ('E', 'C'):
        if label == 'C':
            emit('phase', phase='reset')
            start = time.perf_counter_ns()
            if hasattr(arm, 'close'): arm.close()
            arm = Arm(data['packet'])
            emit('reset', duration_ns=time.perf_counter_ns()-start)
        emit('phase', phase='update_'+label)
        start = time.perf_counter_ns(); details = arm.update(data['updates'][label])
        emit('update', phase=label, duration_ns=time.perf_counter_ns()-start, details=details)
        query('post_'+label, 0)
    if hasattr(arm, 'close'): arm.close()
    emit('complete', queries=completed, ru_maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


if __name__ == '__main__':
    try:
        main()
    except MemoryError:
        emit('failure', kind='memory_limit'); sys.exit(3)
    except Exception as exc:
        emit('failure', kind='execution_error', exception_type=type(exc).__name__, message=str(exc)[:1000]); sys.exit(2)
