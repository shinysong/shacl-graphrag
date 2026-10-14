"""Independent matrix/score reconciliation of veto-only replay; never repairs answers."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

try:
    from scripts.analyze_shared_semantics_study import read, sha, reference, reconcile, semantic_digest
except ModuleNotFoundError:
    from analyze_shared_semantics_study import read, sha, reference, reconcile, semantic_digest

POLICIES = {'none': (), 'cross_only': ('cross',), 'version_only': ('whole',),
            'semantic_only': ('semantic',), 'all_checks': ('cross', 'whole', 'semantic'),
            'selective_checks': ('cross', 'selective', 'semantic')}
CATALOGS = ('documented', 'absent', 'mislabeled')
METRICS = ('rows', 'wrong_allowed', 'wrong_withheld', 'correct_retained', 'correct_withheld',
           'unnecessary_abstention', 'correct_unknown_withheld')


def audit(run, base, output):
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'run_id': run.name, 'checked_rows': 0}
    def save():
        (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    save()
    try:
        manifest = read(run / 'manifest.json')
        if manifest['status'] != 'complete' or manifest['completed_rows'] != 221184 or manifest['planned_rows'] != 221184:
            raise ValueError('Incomplete replay manifest')
        for path, expected in manifest['input_files'].items():
            if sha(base / path) != expected:
                raise ValueError('Changed input: ' + path)
        for path, expected in manifest['source_files'].items():
            if sha(run / 'executed-source' / Path(path).name) != expected:
                raise ValueError('Changed archived source: ' + path)
        original = [json.loads(line) for line in (base / 'rows.jsonl').read_text().splitlines()]
        reconcile(read(base / 'manifest.json'), read(base / 'planned-row-ids.json'), original)
        originals = {r['id']: r for r in original}
        expected_ids = {identifier + '/' + catalog + '/' + policy for identifier in originals
                        for catalog in CATALOGS for policy in POLICIES}
        refs, seen, detailed, totals, samples = {}, set(), defaultdict(Counter), defaultdict(Counter), []
        packets = {}
        for row in original:
            key = row['size'], row['seed'], row['snapshot'], row['subject'], row['workflow']
            if key not in refs:
                folder = base / 'snapshots' / f'{key[0]}-{key[1]}-{key[2]}'
                refs[key] = reference(read(folder / 'source.json'), read(folder / 'intended-config.json'), key[3], key[4])
            if row['reference'] != refs[key]:
                raise ValueError('Independent source reference mismatch')
        for line in (run / 'rows.jsonl').open():
            row = json.loads(line)
            identifier = row['id']
            if identifier in seen or identifier not in expected_ids:
                raise ValueError('Duplicate or undeclared row')
            seen.add(identifier)
            if identifier != row['base_id'] + '/' + row['catalog'] + '/' + row['guard']:
                raise ValueError('Identity binding mismatch')
            parent = originals[row['base_id']]
            if row['packet_id'] not in packets:
                packet = read(run / 'runtime-packets' / (row['packet_id'] + '.json'))
                if semantic_digest(packet) != row['packet_id'] or set(packet) != {'actuals', 'publisher', 'workflows'}:
                    raise ValueError('Runtime packet digest or boundary mismatch')
                packets[row['packet_id']] = packet
            packet = packets[row['packet_id']]
            if packet['actuals'][row['workflow']] != parent['actual']:
                raise ValueError('Runtime packet actual mismatch')
            if row['catalog_hash'] != semantic_digest(manifest['catalogs'][row['catalog']]):
                raise ValueError('Catalog digest mismatch')
            if any(row[k] != parent[k] for k in ('arm', 'fault', 'workflow')) or row['output'] != parent['actual']['output']:
                raise ValueError('Parent binding mismatch')
            checks = row['checks']
            if set(checks) != {'cross', 'whole', 'selective', 'semantic'}:
                raise ValueError('Missing check')
            reasons = {k: checks[k]['reasons'] for k in POLICIES[row['guard']] if checks[k]['status'] != 'valid'}
            allowed = not reasons
            if row['allowed'] != allowed or row['veto_reasons'] != reasons:
                raise ValueError('Policy aggregation mismatch')
            correct = parent['actual']['output'] == parent['reference']['output']
            known = parent['reference']['output']['decision'] != 'unknown'
            outcome = ('correct_retained' if allowed else 'correct_withheld') if correct else ('wrong_allowed' if allowed else 'wrong_withheld')
            unnecessary = correct and known and not allowed
            unknown = correct and not known and not allowed
            if (row['outcome'], row['unnecessary_abstention'], row['correct_unknown_withheld'], row['reference_known']) != (outcome, unnecessary, unknown, known):
                raise ValueError('Independent score mismatch')
            detail_key = '/'.join(row[k] for k in ('guard', 'catalog', 'arm', 'fault', 'workflow'))
            for counts in (detailed[detail_key], totals[row['guard'] + '/' + row['catalog']]):
                counts.update(['rows', outcome])
                counts['unnecessary_abstention'] += unnecessary
                counts['correct_unknown_withheld'] += unknown
            if (parent['size'], parent['seed']) == (24, 17) and row['guard'] in ('all_checks', 'selective_checks'):
                cases = {('cost_change', 'stale_projection', 'p4'),
                         ('supplier_move', 'stale_projection', 'p3'),
                         ('restrict_country', 'common_wrong_mapping', 'p4'),
                         ('allow_backup', 'stale_config_copy', 'p0')}
                if (parent['snapshot'], parent['fault'], parent['subject']) in cases and row['arm'] in ('local_json', 'rdf_hybrid'):
                    samples.append(dict(**row, question_context={k: parent[k] for k in ('snapshot', 'subject')},
                                        actual=parent['actual'], reference=parent['reference']))
        if seen != expected_ids:
            raise ValueError('Missing replay rows')
        saved = read(run / 'summary.json')
        if saved['rows'] != len(seen) or saved['groups'] != dict(detailed):
            raise ValueError('Summary disagrees with rows')
        normalized = {k: {metric: v[metric] for metric in METRICS} for k, v in totals.items()}
        report.update(status='complete', checked_rows=len(seen), original_rows=len(original),
                      independent_reference_rows=len(original), input_files=len(manifest['input_files']),
                      limitation='Reconciles identities, scores, policy aggregation and hashes; not an independent implementation of each primitive guard.')
        public = dict(run_id=run.name, original_run_id=base.name, totals=normalized,
                      groups={k: {m: v[m] for m in METRICS} for k, v in detailed.items()}, verification=report)
        (output / 'summary.json').write_text(json.dumps(public, indent=2) + '\n')
        (output / 'samples.json').write_text(json.dumps(samples, indent=2) + '\n')
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        save()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--base', type=Path, default=Path('runs/20261014T063154Z-shared-semantics'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.run, args.base, args.output)))
