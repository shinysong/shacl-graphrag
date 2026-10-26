"""Bounded local-container execution; no host execution of artifact source."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import time
import uuid

SMOKE = Path('_workspace/retail-llm-v1/container-smoke-v1')
OUTPUT_LIMIT = 65536
WALL_SECONDS = 10
BOOTSTRAP = '''import json, runpy
packet = json.load(open("/task/packet.json"))
namespace = runpy.run_path("/task/artifact.py")
result = namespace["evaluate"](packet)
print(json.dumps(result, allow_nan=False))
'''


def execute(source, packet, output, *, shacl_dependencies=False):
    if not isinstance(source, bytes) or len(source) > 65536:
        raise ValueError('Artifact byte limit')
    source.decode('utf-8', errors='strict')
    packet_bytes = json.dumps(packet, ensure_ascii=False, allow_nan=False).encode()
    if len(packet_bytes) > 1048576:
        raise ValueError('Packet byte limit')
    runtime = SMOKE/'runtime'
    for name, sha in json.loads((SMOKE/'runtime-hashes.json').read_text()).items():
        path = runtime/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError('Runtime changed')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    task = output/'task'
    task.mkdir()
    (task/'artifact.py').write_bytes(source)
    (task/'packet.json').write_bytes(packet_bytes)
    (task/'runner.py').write_text(BOOTSTRAP)
    # Input files are public experimental inputs only, never scorer files.
    for p in task.iterdir():
        p.chmod(0o444)
    task.chmod(0o555)
    name = 'retail-exec-' + uuid.uuid4().hex[:12]
    observed_smoke = json.loads((SMOKE/'observed.json').read_text())
    argv = observed_smoke['argv'][:]
    argv[argv.index('--name')+1] = name
    image_pos = argv.index('80259ba83f86')
    argv[image_pos:image_pos] = ['--mount', f'type=bind,src={task.resolve()},dst=/task,readonly']
    if shacl_dependencies:
        deps = Path('_workspace/retail-llm-v1/shacl-runtime-v1/site')
        manifest = json.loads((deps.parent/'hashes.json').read_text())
        actual = {str(p.relative_to(deps)) for p in deps.rglob('*') if p.is_file()}
        if actual != set(manifest):
            raise ValueError('Dependency file set changed')
        for rel, sha in manifest.items():
            path = deps/rel
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise ValueError('Dependency bytes changed')
        image_pos = argv.index('80259ba83f86')
        argv[image_pos:image_pos] = [
            '--mount', f'type=bind,src={deps.resolve()},dst=/deps,readonly',
            '--env=PYTHONPATH=/deps']
    assert argv[-2] == '-c'
    argv[-2:] = ['/task/runner.py']
    env = {k: os.environ[k] for k in ('PATH', 'LANG') if k in os.environ}
    docker = ['docker', '--host', 'unix:///var/run/docker.sock']
    result = {'container_name': name, 'artifact_sha256': hashlib.sha256(source).hexdigest(),
              'packet_sha256': hashlib.sha256(packet_bytes).hexdigest(),
              'wall_limit_seconds': WALL_SECONDS, 'combined_output_limit': OUTPUT_LIMIT,
              'status': 'launch_error', 'argv': argv}
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    process = None
    started = time.monotonic()
    selector = selectors.DefaultSelector()
    try:
        process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        for stream, label in ((process.stdout, 'stdout'), (process.stderr, 'stderr')):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        result['status'] = 'running'
        while selector.get_map():
            if time.monotonic()-started >= WALL_SECONDS:
                result['status'] = 'timeout'
                break
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fd, 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                remaining = OUTPUT_LIMIT-sum(len(v) for v in streams.values())
                streams[key.data].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    result['status'] = 'output_limit'
                    break
            if result['status'] == 'output_limit':
                break
        if result['status'] == 'running':
            remaining_time = max(0.01, WALL_SECONDS-(time.monotonic()-started))
            try:
                code = process.wait(timeout=remaining_time)
                result.update(exit_code=code, status='completed' if code == 0 else 'execution_error')
            except subprocess.TimeoutExpired:
                result['status'] = 'timeout'
    except OSError as exc:
        result['error_type'] = type(exc).__name__
    finally:
        result['execution_elapsed_seconds'] = time.monotonic()-started
        if process is not None and process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired) as exc:
                result['cli_stop_error'] = type(exc).__name__
        selector.close()
        result['evidence_errors'] = []
        for label, data in streams.items():
            try:
                (output/(label+'.bin')).write_bytes(data)
            except OSError as exc:
                result['evidence_errors'].append({'file': label+'.bin', 'type': type(exc).__name__})
        try:
            (output/'execution.json').write_text(json.dumps(result, indent=2))
        except OSError as exc:
            result['evidence_errors'].append({'file': 'execution.json', 'type': type(exc).__name__})
        try:
            clean = subprocess.run(docker+['rm', '-f', name], capture_output=True,
                                   text=True, timeout=10, env=env)
            result['cleanup'] = {'exit_code': clean.returncode, 'stderr': clean.stderr}
            check = subprocess.run(docker+['container', 'inspect', '--format', '{{.Id}}', name],
                                   capture_output=True, text=True, timeout=10, env=env)
            result['container_absent'] = check.returncode != 0 and 'No such container' in check.stderr
        except (OSError, subprocess.TimeoutExpired) as exc:
            result['cleanup'] = {'unresolved': True, 'error_type': type(exc).__name__}
            result['container_absent'] = False
        if result['evidence_errors']:
            result['execution_status_before_evidence_error'] = result['status']
            result['status'] = 'evidence_error'
        try:
            (output/'execution.json').write_text(json.dumps(result, indent=2))
        except OSError as exc:
            result['evidence_errors'].append({'file': 'execution.json', 'type': type(exc).__name__})
            result['status'] = 'evidence_error'
        if process is not None:
            process.stdout.close()
            process.stderr.close()
    return result


def authored_checks():
    base = Path('_workspace/retail-llm-v1/runner-checks-v1')
    probes = {
        'success': (b'def evaluate(packet):\n return {"decisions": []}\n', 'completed'),
        'exception': (b'def evaluate(packet):\n raise ValueError("authored failure")\n', 'execution_error'),
        'timeout': (b'def evaluate(packet):\n while True: pass\n', 'timeout'),
        'stdout_flood': (b'def evaluate(packet):\n while True: print("x"*8192, flush=True)\n', 'output_limit'),
    }
    summary = {}
    for label, (source, expected) in probes.items():
        result = execute(source, {}, base/label)
        summary[label] = {'expected': expected, 'observed': result['status'],
                          'container_absent': result['container_absent'],
                          'captured_bytes': sum((base/label/(s+'.bin')).stat().st_size
                                                for s in ('stdout', 'stderr'))}
        # Stop if cleanup is unresolved; no additional containers until inspected.
        if not result['container_absent']:
            break
    (base/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    assert len(summary) == len(probes)
    assert all(r['observed'] == r['expected'] and r['container_absent']
               and r['captured_bytes'] <= OUTPUT_LIMIT for r in summary.values())


if __name__ == '__main__':
    authored_checks()
