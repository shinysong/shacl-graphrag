"""Audit saved development annotations, never run a generator or score truth.

Supports the authored cases/results/*-draft.json diagnostic format. Comparisons
bind saved annotations to their declared expectations and observed draft values;
this does not validate the expectations or independently reproduce generation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(values, label):
    require(len(values) == len(set(values)), 'Duplicate ' + label)


def audit(root):
    root = Path(root)
    raw = (root / 'cases.json').read_bytes()
    cases = json.loads(raw)['cases']
    saved = json.loads((root / 'results.json').read_text())
    require(hashlib.sha256(raw).hexdigest() == saved['case_file_sha256'], 'Case hash mismatch')
    ids = [c['id'] for c in cases]
    unique(ids, 'case ID')
    require(all(re.fullmatch(r'[a-zA-Z0-9_-]+', x) for x in ids), 'Unsafe case ID')
    require(ids == [r['id'] for r in saved['results']], 'Result coverage/order mismatch')
    rows = []
    for case, result in zip(cases, saved['results']):
        cid = case['id']
        files = case['files']
        unique([f['name'] for f in files], 'source name')
        hashes = {f['name']: hashlib.sha256(f['content'].encode()).hexdigest() for f in files}
        require(result['files_sha256'] == hashes, cid + ': source hashes mismatch')
        if 'failure' in result:
            failure = result['failure']
            require(case.get('expected_format_error') is True and failure.get('expected_format_error') is True
                    and failure.get('type') == 'ValueError' and bool(failure.get('message')),
                    cid + ': unexpected or malformed saved failure')
            require(not (root / (cid + '-draft.json')).exists(), cid + ': failure also has draft')
            rows.append({'id': cid, 'state': 'recorded_format_failure'})
            continue
        require(not case.get('expected_format_error'), cid + ': missing expected failure')
        draft = json.loads((root / (cid + '-draft.json')).read_text())
        entries = draft['entries']
        unique([e['id'] for e in entries], 'entry ID')
        require(all(e['status'] == 'pending' for e in entries), cid + ': reviewed draft in initial diagnostic')
        sources = draft['sources']
        unique([s['name'] for s in sources], 'draft source name')
        require({s['name']: s['content'] for s in sources} == {f['name']: f['content'] for f in files},
                cid + ': draft source content mismatch')
        require({s['name']: s['sha256'] for s in sources} == hashes, cid + ': draft hashes mismatch')
        mappings = {e['id'][4:]: e for e in entries if e['kind'] == 'mapping'}
        require(all(e['id'].startswith('map:') for e in entries if e['kind'] == 'mapping'), 'Invalid mapping ID')
        checks = result['mapping_checks']
        fields = [c['field'] for c in checks]
        unique(fields, 'annotated mapping field')
        expected = case.get('mapping_expectations', {})
        require(set(fields) == set(expected), cid + ': annotation coverage mismatch')
        for check in checks:
            field = check['field']
            require(field in mappings, cid + ': annotated mapping absent')
            entry = mappings[field]
            require(check['expected'] == expected[field], cid + ': changed mapping expectation')
            require(check['actual'] == entry['target'], cid + ': changed mapping outcome')
            require(type(check['matches']) is bool and check['matches'] == (expected[field] == entry['target']),
                    cid + ': mapping match flag mismatch')
            require(check['candidates'] == entry['extraction']['candidates'] and
                    check['table_candidate'] == entry['extraction']['table_candidate'], cid + ': candidate mismatch')
        policies = [e for e in entries if e['kind'] == 'policy']
        expectations = case.get('policy_expectations', [])
        require(len(result['policy_checks']) == len(expectations) <= len(policies), cid + ': policy coverage mismatch')
        for check, expected, entry in zip(result['policy_checks'], expectations, policies):
            actual = {'target': entry['target'], 'basis': entry['extraction']['basis'],
                      'question_required': bool(entry['extraction']['questions'])}
            require(check['expected'] == expected and check['actual'] == actual, cid + ': policy tuple mismatch')
            require(type(check['matches']) is bool and check['matches'] == (expected == actual), cid + ': policy flag mismatch')
            require(check['questions'] == entry['extraction']['questions'], cid + ': policy questions mismatch')
        relations = [e for e in entries if e['kind'] == 'relation']
        counts = [e['extraction'].get('related_policy_count', 0) for e in policies]
        require(result['relations'] == relations, cid + ': relation result mismatch')
        require(result['comparison_counts'] == counts, cid + ': comparison result mismatch')
        require(result['all_unapproved'] is True, cid + ': approval summary mismatch')
        require(not case.get('relation_expected') or bool(relations), cid + ': expected candidate absent')
        require(not case.get('comparison_expected') or any(counts), cid + ': expected comparison absent')
        rows.append({'id': cid, 'state': 'consistent_saved_annotations', 'mapping_entries': len(mappings),
                     'annotated_mappings': len(fields), 'unscored_mappings': sorted(set(mappings) - set(fields)),
                     'policy_entries': len(policies), 'annotated_policy_tuples': len(expectations)})
    return {'audit_version': 2, 'scope': 'Saved annotation consistency only; not semantic accuracy or execution reproduction',
            'cases': rows, 'limitations': ['Expectations are authored, not independently certified truth',
                'Source extraction, policy slot completeness and original execution are not verified',
                'Unscored entries remain unscored; consumed development is not heldout evaluation']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory), ensure_ascii=False, indent=2))
