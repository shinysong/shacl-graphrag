"""Build a self-contained presentation of saved backend results (posthoc only)."""
import hashlib
import json
from pathlib import Path

BASE = Path('research/backend-reasoning-review-1')
TARGET = Path('docs/experiments/seminar/backend-review.html')
TEMPLATE = Path('research/backend-reasoning-review-1/presentation-template.html')


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def build():
    source = BASE / 'updates-live-001'
    rows = read_rows(source / 'results.jsonl')
    evaluation = json.loads((source / 'evaluation.json').read_text())
    ref = {(x['event'], x['arm'], x['query_id']): x['matches_current_reference'] for x in evaluation['checks']}
    reports = read_rows(BASE / 'advisory-scope-001/results.jsonl') + read_rows(BASE / 'advisory-query-scope-001/results.jsonl')
    lookup = {(r['row_index'], r['policy'], r['checker']): r for r in reports}
    cards = []
    for i, row in enumerate(rows):
        paired = {}
        for policy in ('global', 'declared_family', 'swapped_family_control', 'declared_query', 'swapped_query_control'):
            a, b = [lookup[(i, policy, c)] for c in ('python', 'shacl')]
            if a['status'] != 'completed' or b['status'] != 'completed' or a['codes'] != b['codes']:
                raise ValueError('Presentation requires explicit handling of checker failures/disagreement')
            fields = ('review_requested', 'family', 'metadata', 'origin', 'original_answer', 'original_status', 'answer_changed')
            if any(a[field] != b[field] for field in fields):
                raise ValueError('Displayed report fields or original output disagree')
            if a['original_answer'] != row['answer'] or a['original_status'] != row['status'] or a['answer_changed']:
                raise ValueError('Report is not bound to its original output')
            if a['origin'] != {k: row[k] for k in ('event', 'arm', 'query_id')}:
                raise ValueError('Report origin disagrees with saved output')
            paired[policy] = {'review': a['review_requested'], 'codes': a['codes'], 'family': a['family'], 'metadata': a['metadata']}
        cards.append({k: row[k] for k in ('event', 'arm', 'query_id', 'answer', 'status')} | {
            'matches_declared_reference': ref[(row['event'], row['arm'], row['query_id'])], 'reports': paired})
    plan = json.loads((source / 'plan.json').read_text())
    key = lambda x: (x['event'], x['arm'], x['query_id'])
    if (len(cards) != len(plan) or len({key(x) for x in cards}) != len(cards)
            or {key(x) for x in cards} != {key(x) for x in plan}):
        raise ValueError('Incomplete or duplicate presentation coverage')
    inputs = [source / 'results.jsonl', source / 'evaluation.json', BASE / 'advisory-scope-001/results.jsonl', BASE / 'advisory-query-scope-001/results.jsonl']
    payload = {'cards': cards, 'events': list(dict.fromkeys(r['event'] for r in rows)),
               'queries': list(dict.fromkeys(r['query_id'] for r in rows)),
               'source_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    template = TEMPLATE.read_text()
    if template.count('__SAVED_EVIDENCE__') != 1:
        raise ValueError('Expected one saved-evidence placeholder')
    TARGET.write_text(template.replace('__SAVED_EVIDENCE__', encoded))
    print(json.dumps({'path': str(TARGET), 'saved_outputs': len(cards), 'report_pairs': len(cards)*5, 'sha256': hashlib.sha256(TARGET.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    build()
