"""Bounded single local algorithm process; never an LLM/API worker."""
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path


def supervise(command, output, *, wall_seconds=12.0, grace_seconds=0.5,
              byte_limit=4*1024*1024, absolute_deadline=None):
    """Store bounded raw streams. Failed-process sampled VmHWM is a lower bound.

    absolute_deadline is monotonic time; reserve grace before starting. Caller
    owns campaign quota/accounting. Refuse an existing directory: no retries.
    """
    start = time.monotonic()
    if absolute_deadline is not None and start + wall_seconds + grace_seconds + 0.25 > absolute_deadline:
        return dict(status='not_run', reason='insufficient deadline reserve', bytes=0)
    if wall_seconds <= 0 or grace_seconds < 0 or byte_limit < 1:
        raise ValueError('invalid limits')
    directory = Path(output); directory.mkdir(parents=True, exist_ok=False)
    files = {name: (directory / (name+'.log')).open('wb') for name in ('stdout', 'stderr')}
    selector = selectors.DefaultSelector()
    process = None; count = 0; highwater = 0; reason = None; killed_at = None
    first_output_ns = None
    start_ns = time.perf_counter_ns()
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        for name, stream in [('stdout', process.stdout), ('stderr', process.stderr)]:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        expiry = start + wall_seconds
        def terminate(sig):
            try: os.killpg(process.pid, sig)
            except ProcessLookupError: pass
        while selector.get_map() or process.poll() is None:
            now = time.monotonic()
            try:
                for line in Path(f'/proc/{process.pid}/status').read_text().splitlines():
                    if line.startswith('VmHWM:'):
                        highwater = max(highwater, int(line.split()[1]))
            except (FileNotFoundError, ProcessLookupError):
                pass
            if reason is None and now >= expiry:
                reason = 'timeout'; killed_at = now; terminate(signal.SIGTERM)
            if killed_at is not None and now >= killed_at + grace_seconds:
                terminate(signal.SIGKILL)
                # Bound drain even if a descendant inherited a pipe.
                if now >= killed_at + grace_seconds + 0.15:
                    break
            for key, _ in selector.select(0.02):
                try: data = os.read(key.fileobj.fileno(), 65536)
                except BlockingIOError: continue
                if not data:
                    selector.unregister(key.fileobj); key.fileobj.close(); continue
                if first_output_ns is None: first_output_ns = time.perf_counter_ns()-start_ns
                available = byte_limit-count
                if available > 0:
                    saved = data[:available]; files[key.data].write(saved); files[key.data].flush(); count += len(saved)
                if len(data) > available and reason is None:
                    reason = 'artifact_limit'; killed_at = time.monotonic(); terminate(signal.SIGTERM)
        if process.poll() is None:
            terminate(signal.SIGKILL)
        try: process.wait(timeout=0.1)
        except subprocess.TimeoutExpired:
            reason = reason or 'termination_unconfirmed'
        return dict(status=reason or ('completed' if process.returncode == 0 else 'process_error'),
                    returncode=process.returncode, bytes=count, elapsed_ns=time.perf_counter_ns()-start_ns,
                    first_output_ns=first_output_ns, sampled_vmhwm_kib_lower_bound=highwater,
                    termination_confirmed=process.poll() is not None)
    finally:
        if process is not None and process.poll() is None:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        for key in list(selector.get_map().values()): key.fileobj.close()
        selector.close()
        for stream in files.values(): stream.close()
