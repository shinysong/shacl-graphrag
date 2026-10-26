"""Single-worker frozen campaign; no retries, APIs, or runtime oracle access."""
import fcntl
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from technology_selection_process import supervise
from technology_selection_score import score

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT/'_workspace/technology-selection/fixtures-1/frozen'
DEADLINE = datetime.fromisoformat('2026-10-21T20:36:57.705000+00:00')
MAX_BYTES = 512*1024*1024
RESERVE = 16*1024*1024


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    start = time.monotonic()
    stop = min(start+2700, start+max(0,(DEADLINE-datetime.now(timezone.utc)).total_seconds()))
    lock = (ROOT/'_workspace/technology-selection/campaign.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=False)
    files = list((ROOT/'scripts').glob('technology_selection_*.py')) + [Path(__file__),ROOT/'scripts/industrial_question_python.py',ROOT/'uv.lock'] + list((ROOT/'research/technology-selection').glob('*'))
    bindings = {str(p.relative_to(ROOT)):sha(p) for p in files if p.is_file()}
    manifest = json.loads((FIXTURES/'manifest.json').read_text())
    bindings.update(manifest.get('bindings', {}))
    def verify():
        for path, value in bindings.items():
            if sha(ROOT/path) != value: raise ValueError('source binding changed: '+path)
        for path, value in manifest['files'].items():
            if sha(FIXTURES/path) != value: raise ValueError('fixture changed: '+path)
    verify()
    runs = json.loads((ROOT/'research/technology-selection/runs-v1.json').read_text())
    freeze = dict(started_at=datetime.now(timezone.utc).isoformat(), deadline=DEADLINE.isoformat(), max_seconds=2700,max_bytes=MAX_BYTES,bindings=bindings,fixture_manifest_sha256=sha(FIXTURES/'manifest.json'),runs=runs,platform=sys.version,cpu_count=os.cpu_count())
    payload = json.dumps(freeze,indent=2).encode()
    if len(payload)>RESERVE//2: raise ValueError('metadata reserve exceeded')
    (output/'freeze.json').write_bytes(payload)
    used = len(payload); results = []
    for run in runs:
        row = dict(run)
        if time.monotonic()+13 > stop or used+RESERVE >= MAX_BYTES:
            row.update(status='not_run',reason='campaign time/deadline/artifact ceiling')
        else:
            verify()  # Before each paid-free algorithm launch; no mutation to frozen source.
            directory = output/run['attempt_id']
            result = supervise([sys.executable,str(ROOT/'scripts/technology_selection_worker.py'),run['arm'],str(FIXTURES/'runtime'/ (run['case_id']+'.json'))],directory,
                               byte_limit=min(4*1024*1024,MAX_BYTES-used-RESERVE),absolute_deadline=stop)
            used += result['bytes']; row['process'] = result
            if result['status']=='not_run': row.update(status='not_run',reason=result['reason'])
            else:
                expected=json.loads((FIXTURES/'scorer'/(run['case_id']+'-expected.json')).read_text())
                row['score']=score(directory/'stdout.log',result,expected); row['status']=row['score']['status']
        line=(json.dumps(row,separators=(',', ':'))+'\n').encode()
        if len(line)>65536 or used+len(line)>MAX_BYTES: raise RuntimeError('reserved metadata exceeded')
        with (output/'results.jsonl').open('ab') as f: f.write(line); f.flush(); os.fsync(f.fileno())
        used+=len(line); results.append(row['status'])
        print(json.dumps(dict(attempt=run['attempt_id'],status=row['status'],completed=len(results))),flush=True)
    final=dict(slots=len(results),counts={s:results.count(s) for s in sorted(set(results))},elapsed_seconds=time.monotonic()-start,bytes_before_summary=used)
    data=json.dumps(final,indent=2).encode()
    if used+len(data)>MAX_BYTES: raise RuntimeError('summary quota')
    (output/'summary.json').write_bytes(data)
    print(json.dumps(final),flush=True)


if __name__=='__main__': main()
