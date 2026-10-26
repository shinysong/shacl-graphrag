"""Read-only historical input and snapshot audit; never evaluate answers."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '_workspace/technology-selection'
OUT = BASE / 'completion-1'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def bound(root, name, digest):
    p = root / name
    if not p.resolve().is_relative_to(root.resolve()) or p.is_symlink():
        raise ValueError('Invalid input path')
    if sha(p) != digest:
        raise ValueError('Historical input mismatch: ' + str(p))
    return p


def main():
    if OUT.exists():
        raise FileExistsError('Preserve previous audit')
    freeze = json.loads((BASE / 'campaign-1/results/freeze.json').read_text())
    fixture_root = BASE / 'fixtures-1/frozen'
    bound(fixture_root, 'manifest.json', freeze['fixture_manifest_sha256'])
    fixture = json.loads((fixture_root / 'manifest.json').read_text())
    verified = [bound(fixture_root, n, h) for n, h in fixture['files'].items()]
    record = json.loads((ROOT / 'docs/experiments/records/20261021-technology-selection-maintenance-freeze.json').read_text())
    maintenance_root = BASE / 'maintenance-1/frozen'
    bound(maintenance_root, 'manifest.json', record['manifest_sha256'])
    maintenance = json.loads((maintenance_root / 'manifest.json').read_text())
    verified += [bound(maintenance_root, n, h) for n, h in maintenance['files'].items()]
    verified += [bound(maintenance_root / 'baseline', n, h) for n, h in maintenance['baseline'].items()]
    handoff = json.loads((BASE / 'handoff-1/manifest.json').read_text())
    for p in verified + [fixture_root/'manifest.json', maintenance_root/'manifest.json']:
        if sha(p) != handoff['files'][p.relative_to(ROOT).as_posix()]['sha256']:
            raise ValueError('Handoff input differs')
    saved = json.loads((BASE / 'handoff-1/verification.json').read_text())
    bound(BASE / 'handoff-1', 'technology-selection-evidence.tar.gz', saved['archive_sha256'])
    bound(BASE / 'handoff-1', 'manifest.json', saved['manifest_sha256'])
    result = {'fixture_members': len(fixture['files']), 'maintenance_input_reference_members': len(maintenance['files']),
              'maintenance_baseline_members': len(maintenance['baseline']), 'historical_manifests': 2,
              'matched_handoff_bindings': len(verified)+2, 'archive_unchanged': True,
              'claim_scope': 'Bytes match locally retained pre-execution hashes; not independently authenticated provenance or external truth',
              'new_experiments': 0, 'answers_changed': 0,
              'paper': 'docs/journal/2026-10-21-technology-selection-paper.md',
              'paper_sha256': sha(ROOT/'docs/journal/2026-10-21-technology-selection-paper.md'),
              'remaining_limits': ['Two authored workflows; no universal hop threshold', 'Human effort unmeasured',
                                   'Browser/mobile rendering not tested', 'Selected related work not exhaustive',
                                   'No claim of submission acceptance; paper draft and local evidence package']}
    OUT.mkdir()
    (OUT/'audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
