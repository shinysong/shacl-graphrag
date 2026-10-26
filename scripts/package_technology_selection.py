"""Create a local evidence snapshot; no measurement execution or publication."""
import hashlib
import io
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '_workspace/technology-selection'
OUT = BASE / 'handoff-1'
MAX_BYTES = 64 * 1024 * 1024
DIRECTORIES = ('fixtures-1/frozen', 'campaign-1', 'analysis-1', 'maintenance-1',
               'maintenance-2', 'maintenance-summary-1', 'paper-1', 'figures-1',
               'embed-1', 'embed-2', 'related-1')
EXCLUDED_PARTS = {'__pycache__', '.git', '.venv', '.env', 'MEMORY.md', 'AGENTS.md'}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    if OUT.exists():
        raise FileExistsError('Preserve existing handoff')
    freeze = json.loads((BASE / 'campaign-1/results/freeze.json').read_text())
    # Preserve the exact measured sources, not a silently updated implementation.
    for name, digest in freeze['bindings'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('Measured source changed: ' + name)
    analysis_record = json.loads((ROOT / 'docs/experiments/records/20261021-technology-selection-analysis.json').read_text())
    for name, digest in analysis_record['bindings'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('Analysis changed: ' + name)
    campaign_record = json.loads((ROOT / 'docs/experiments/records/20261021-technology-selection-campaign.json').read_text())
    if sha(BASE / 'campaign-1/results/results.jsonl') != campaign_record['results_sha256']:
        raise ValueError('Raw results changed')
    analysis = json.loads((BASE / 'analysis-1/output/analysis.json').read_text())
    maintenance_record = json.loads((ROOT / 'docs/experiments/records/20261021-technology-selection-maintenance.json').read_text())
    if sha(ROOT / maintenance_record['summary']) != maintenance_record['summary_sha256']:
        raise ValueError('Maintenance summary changed')
    assert analysis['denominator']['recorded'] == 198
    assert analysis['denominator']['statuses']['success'] == 198
    assert len(analysis['cells']) == 66 and len(analysis['paired']) == 22
    assert maintenance_record['observed']['correct_outputs'] == 96
    assert maintenance_record['observed']['initial_submissions'] == 15
    assert maintenance_record['observed']['original_check_exit'] == 1
    assert maintenance_record['observed']['summary_recovery_exit'] == 0
    assert maintenance_record['observed']['new_workers_in_recovery'] == 0
    paths = set()
    for name in DIRECTORIES:
        paths.update(p for p in (BASE / name).rglob('*') if p.is_file())
    for name in ('research/technology-selection', 'docs/assets/technology-selection'):
        paths.update(p for p in (ROOT / name).rglob('*') if p.is_file())
    paths.update((ROOT / 'scripts').glob('*technology_selection*.py'))
    paths.update((ROOT / 'docs/experiments/records').glob('20261021-technology-selection-*.json'))
    paths.update(ROOT / name for name in ('scripts/industrial_question_python.py', 'pyproject.toml', 'uv.lock',
                 'docs/journal/2026-10-21-technology-selection-paper.md',
                 'docs/lessons-learned/2026-10-21-summary-recovery.md'))
    paths = sorted(p for p in paths if not EXCLUDED_PARTS.intersection(p.relative_to(ROOT).parts))
    payload = {}
    for p in paths:
        if p.is_symlink() or not p.resolve().is_relative_to(ROOT):
            raise ValueError('Unsupported link: ' + str(p))
        if p.suffix.lower() in {'.pem', '.key'} or p.name.startswith('.env'):
            raise ValueError('Forbidden file')
        payload[p.relative_to(ROOT).as_posix()] = p.read_bytes()
    if sum(map(len, payload.values())) > MAX_BYTES:
        raise ValueError('Snapshot exceeds 64 MiB')
    audit = {
        'claims': [
            {'claim': '198 successful attempts / 66 cells / 22 paired cases', 'evidence': 'analysis-1/output/analysis.json', 'status': 'verified aggregates and source hashes'},
            {'claim': '15 first submissions / 96 matched maintenance outputs', 'evidence': 'docs/experiments/records/20261021-technology-selection-maintenance.json', 'status': 'verified recorded counts and summary hash'},
            {'claim': 'Original reporting failure preserved', 'evidence': 'maintenance record original_check_exit=1 / recovery_exit=0', 'status': 'record retained, no rerun'},
        ],
        'limits': ['Not a new correctness experiment; no gold repair', 'No human maintenance labor measurement',
                   'Authored two-task evidence, not industrial external truth',
                   'Local snapshot only; no upload or publication',
                   'Original runners retain fixed deadlines and no-overwrite guards; this is not a one-command fresh campaign',
                   'Python/dependency binaries are not bundled; uv.lock and host metadata are retained',
                   'Native review job trees and unrelated studies are not included; review IDs remain in records'],
        'files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in payload.items()},
    }
    OUT.mkdir()
    (OUT / 'manifest.json').write_text(json.dumps(audit, indent=2) + '\n')
    archive = OUT / 'technology-selection-evidence.tar.gz'
    with tarfile.open(archive, 'w:gz') as tf:
        for name, data in payload.items():
            info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o644
            tf.addfile(info, io.BytesIO(data))
    # Re-read each member without extracting or executing any bundled file.
    with tarfile.open(archive, 'r:gz') as tf:
        members = tf.getmembers()
        assert len(members) == len(payload)
        for member in members:
            assert member.isfile() and member.name in payload
            assert hashlib.sha256(tf.extractfile(member).read()).hexdigest() == audit['files'][member.name]['sha256']
    result = {'files': len(payload), 'uncompressed_bytes': sum(map(len, payload.values())),
              'archive_bytes': archive.stat().st_size, 'archive_sha256': sha(archive),
              'manifest_sha256': sha(OUT / 'manifest.json'), 'verified_members': len(payload), 'new_experiments': 0}
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
