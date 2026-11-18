"""Offline authored proposal diagnostics; no gateway or runtime gold access.

Exact declared expectations measure fixture agreement, not external truth.
Unannotated proposals and policy interpretation remain unscored.
"""
import argparse
import hashlib
import json
from pathlib import Path
from apps.factory_lab import preparation
from apps.factory_lab.preparation_advisory import AdvisoryGenerator


def run(cases_path, output):
    raw = Path(cases_path).read_bytes()
    cases = json.loads(raw)['cases']
    ids = [c['id'] for c in cases]
    if len(ids) != len(set(ids)) or any(not x.replace('_', '').isalnum() for x in ids):
        raise ValueError('Case IDs must be unique safe names')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for case in cases:
        record = {'id': case['id'], 'source_hashes': {
            f['name']: hashlib.sha256(f['content'].encode()).hexdigest() for f in case['files']}}
        try:
            # Only sources and snapshot metadata reach the actual generator.
            draft = preparation.create(case['files'], {
                'snapshot_id': case['id'], 'as_of': '2026-11-17', 'currency': 'KRW'},
                generator=AdvisoryGenerator())
        except Exception as exc:
            record.update(state='generation_failed', failure_type=type(exc).__name__, failure=str(exc))
        else:
            (output / (case['id'] + '-draft.json')).write_text(json.dumps(draft, ensure_ascii=False, indent=2))
            expected = case['expectations']
            mappings = {e['id'][4:]: e['target'] for e in draft['entries'] if e['kind'] == 'mapping'}
            pairs = {frozenset(e[k]['file'] + ':' + e[k]['column'] for k in ('source', 'target'))
                     for e in draft['entries'] if e['kind'] == 'relation'}
            checks = [{'kind': 'mapping', 'subject': key, 'expected': value,
                       'actual': mappings.get(key), 'matches': mappings.get(key) == value}
                      for key, value in expected['mappings'].items()]
            for name, present in [('required_relations', True), ('forbidden_relations', False)]:
                checks.extend({'kind': name, 'subject': pair, 'expected_present': present,
                               'actual_present': frozenset(pair) in pairs,
                               'matches': (frozenset(pair) in pairs) == present}
                              for pair in expected[name])
            record.update(state='generated', checks=checks,
                          all_pending=all(e['status'] == 'pending' for e in draft['entries']),
                          unscored_mapping_fields=sorted(set(mappings) - set(expected['mappings'])),
                          unscored_policy_count=sum(e['kind'] == 'policy' for e in draft['entries']),
                          observed_relation_pairs=sorted(sorted(pair) for pair in pairs))
        results.append(record)
    report = {'scope': 'Authored development fixture agreement only; not semantic accuracy, heldout evaluation or LLM quality',
              'case_file_sha256': hashlib.sha256(raw).hexdigest(), 'generator': AdvisoryGenerator.name,
              'attempted_cases': len(cases), 'failed_cases': sum(r['state'] == 'generation_failed' for r in results),
              'results': results}
    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cases')
    parser.add_argument('output')
    args = parser.parse_args()
    print(json.dumps(run(args.cases, args.output), ensure_ascii=False, indent=2))
