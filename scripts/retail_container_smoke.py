"""One authored isolation smoke on a cached image; not a generated-code runner."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

BASE = Path('_workspace/retail-llm-v1/container-smoke-v1')
IMAGE = '80259ba83f86'  # Previously inventoried local ruby:3.4-bookworm image.
DOCKER = ['docker', '--host', 'unix:///var/run/docker.sock']
PROBE = r'''
import json, os, socket, tempfile, decimal
out = {"python_decimal": str(decimal.Decimal("0.1")+decimal.Decimal("0.2"))}
out["host_workspace_absent"] = not os.path.exists("/home/ubuntu/shacl-graphrag/MEMORY.md")
out["docker_socket_absent"] = not os.path.exists("/var/run/docker.sock")
out["secret_env_absent"] = not any(k.startswith(("OPENROUTER_", "AWS_", "OPENAI_")) for k in os.environ)
try:
    open("/root-write-probe", "w").write("probe")
    out["root_write_blocked"] = False
except OSError:
    out["root_write_blocked"] = True
with tempfile.TemporaryFile() as f:
    f.write(b"probe"); out["temporary_write_ok"] = True
s = socket.socket(); s.settimeout(1)
try:
    s.connect(("1.1.1.1", 443)); out["network_connect_blocked"] = False
except OSError:
    out["network_connect_blocked"] = True
finally:
    s.close()
out["uid"] = os.getuid()
print(json.dumps(out))
'''


def main():
    BASE.mkdir(parents=True, exist_ok=False)
    env = {k: os.environ[k] for k in ('PATH', 'LANG') if k in os.environ}
    runtime = BASE/'runtime'
    stdlib = Path('/usr/lib/python3.12')
    binary = Path('/usr/bin/python3.12')
    runtime.mkdir()
    shutil.copytree(stdlib, runtime/'usr/lib/python3.12',
                    ignore=shutil.ignore_patterns('__pycache__'))
    (runtime/'usr/bin').mkdir(parents=True)
    shutil.copy2(binary, runtime/'usr/bin/python3.12')
    libraries = set()
    for path in [binary, *stdlib.rglob('*.so')]:
        result = subprocess.run(['ldd', str(path)], capture_output=True, text=True,
                                timeout=10, env=env)
        if result.returncode or 'not found' in result.stdout:
            raise RuntimeError('Runtime dependency discovery failed')
        libraries.update(Path(p) for p in re.findall(r'(/[^\s()]+)', result.stdout))
    for lib in libraries:
        dest = runtime/str(lib).lstrip('/')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(lib, dest)
    loaders = [p for p in libraries if p.name.startswith('ld-linux')]
    if len(loaders) != 1:
        raise RuntimeError('Ambiguous runtime loader')
    manifest = {str(p.relative_to(runtime)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in runtime.rglob('*') if p.is_file()}
    (BASE/'runtime-hashes.json').write_text(json.dumps(manifest, indent=2))
    name = 'retail-smoke-' + uuid.uuid4().hex[:12]
    library_path = ':'.join('/runtime'+str(p) for p in sorted({p.parent for p in libraries}))
    argv = DOCKER + [
        'run', '--pull=never', '--name', name, '--rm', '--network=none',
        '--read-only', '--user=65534:65534', '--cap-drop=ALL',
        '--security-opt=no-new-privileges', '--pids-limit=32', '--memory=256m',
        '--memory-swap=256m', '--cpus=1', '--log-driver=none',
        '--tmpfs=/tmp:rw,noexec,nosuid,size=16m,mode=1777', '--workdir=/tmp',
        '--mount', f'type=bind,src={runtime.resolve()},dst=/runtime,readonly',
        '--env=PYTHONHOME=/runtime/usr', '--env=PYTHONDONTWRITEBYTECODE=1',
        '--env=PYTHONNOUSERSITE=1', '--env=LD_LIBRARY_PATH='+library_path,
        '--entrypoint=/runtime'+str(loaders[0]), IMAGE,
        '--library-path', library_path, '/runtime/usr/bin/python3.12',
        '-s', '-B', '-c', PROBE,
    ]
    observed = {'argv': argv, 'container_name': name,
                'scope': 'Authored smoke only; no generated code, dependencies install or image download'}
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=env)
        observed.update(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
        if proc.returncode == 0:
            observed['probe'] = json.loads(proc.stdout)
    except subprocess.TimeoutExpired as exc:
        observed.update(timeout=True,
                        stdout=(exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout, bytes) else exc.stdout,
                        stderr=(exc.stderr or b'').decode(errors='replace') if isinstance(exc.stderr, bytes) else exc.stderr)
    except OSError as exc:
        observed['launch_error_type'] = type(exc).__name__
    finally:
        # Persist execution evidence before cleanup, which may itself fail.
        (BASE/'observed.json').write_text(json.dumps(observed, indent=2))
        # Remove only the uniquely named container owned by this invocation.
        try:
            cleanup = subprocess.run(DOCKER+['rm', '-f', name], capture_output=True,
                                     text=True, timeout=10, env=env)
            observed['cleanup'] = {'exit_code': cleanup.returncode,
                                  'stdout': cleanup.stdout, 'stderr': cleanup.stderr}
        except (subprocess.TimeoutExpired, OSError) as exc:
            observed['cleanup'] = {'error_type': type(exc).__name__, 'unresolved': True}
        (BASE/'observed.json').write_text(json.dumps(observed, indent=2))
    print(json.dumps({k:v for k,v in observed.items() if k != 'argv'}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Preserve staging/dependency failures too; never retry or install automatically.
        if BASE.exists():
            with (BASE/'failure.json').open('x') as f:
                json.dump({'error_type': type(exc).__name__,
                           'execution_evidence_saved': (BASE/'observed.json').exists()}, f)
        raise
