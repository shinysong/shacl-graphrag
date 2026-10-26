"""Exact joins/scalar parsing and output mapping shared by two rule engines.
No status equality, self-review or period comparison is computed here.
The RDF arm materializes joined operands, not a raw document RDF database.
"""
from datetime import date
from copy import deepcopy


def text(v):
    return isinstance(v, str) and bool(v.strip())


def day(v):
    try:
        return date.fromisoformat(v).toordinal() if type(v) is str and len(v) == 10 else None
    except ValueError:
        return None


def prepare(packet, policy):
    p = deepcopy(packet)
    if set(p['tables']) != {'document', 'review', 'qualification'}:
        raise ValueError('unexpected table set')
    rows = [r for records in p['tables'].values() for r in records]
    ids = [r['occurrence_id'] for r in rows]
    if len(rows) > 64 or len(ids) != len(set(ids)) or not all(text(i) for i in ids):
        raise ValueError('invalid bounded input')
    checks = []
    def add(rule_id, kind, values, used):
        checks.append(dict(rule_id=rule_id, kind=kind, values=values,
                           support=sorted({r['occurrence_id'] for r in used})))
    q, t = p['question'], p['tables']
    docs = [r for r in t['document'] if (r.get('id'), r.get('revision')) == (q['document_id'], q['revision'])]
    add('document-link', 'equal', [1, 1] if len(docs) == 1 else None, docs)
    if len(docs) == 1:
        d = docs[0]
        status = d.get('status')
        add('document-status', 'equal', [status, policy['document_status']] if status in ('Draft','Approved') else None, [d])
        reviews = [r for r in t['review'] if (r.get('document_id'), r.get('revision')) == (d['id'],d['revision'])]
        add('review-link', 'equal', [1,1] if len(reviews) == 1 else None, [d,*reviews])
        if len(reviews) == 1:
            r = reviews[0]
            value = r.get('decision')
            add('review-decision', 'equal', [value,policy['review_decision']] if value in ('Accept','Reject') else None, [r])
            a, b = d.get('author'), r.get('reviewer')
            add('self-review', 'different', [a,b] if text(a) and text(b) else None, [d,r])
            quals = [x for x in t['qualification'] if text(b) and x.get('person') == b and x.get('role') == policy['required_role']]
            add('qualification-link','equal',[1,1] if len(quals) == 1 else None,[r,*quals])
            if len(quals) == 1:
                c = quals[0]
                vals = [day(c.get('start')),day(q.get('assessment_date')),day(c.get('end'))]
                add('qualification-dates','interval',vals if all(x is not None for x in vals) else None,[r,c])
    return checks


def assemble(checks, failed, unknown):
    by_id = {x['rule_id']: x for x in checks}
    if not (set(failed) | set(unknown)) <= by_id.keys() or set(failed) & set(unknown):
        raise ValueError('invalid engine diagnostics')
    def details(ids):
        return [dict(rule_id=i,support=by_id[i]['support']) for i in sorted(ids)]
    return dict(decision='blocked' if failed else 'unknown' if unknown else 'eligible',
                violations=details(failed), unknown=details(unknown),
                evidence=sorted({i for c in checks for i in c['support']}))
