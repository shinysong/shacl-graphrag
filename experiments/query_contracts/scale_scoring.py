"""Posthoc only. Must never be imported by campaign or packet construction."""
from collections import Counter
from decimal import Decimal


def score(progress, rubric):
    groups = {}
    spending = {}
    rows = []
    for slot in progress['slots']:
        key = (slot['model'], slot['size'], slot['arm'])
        counts = groups.setdefault(key, Counter(planned_requests=0, completed_requests=0,
                      failed_requests=0, unattempted_requests=0, planned_tasks=0,
                      scored_tasks=0, correct_tool=0, correct_null=0, wrong_tool=0,
                      unnecessary_null=0, supported_tasks=0, candidate_hit=0,
                      model_error_with_candidate=0, unsupported_tool_selected=0,
                      checked_wrong_allowed=0, checked_correct_blocked=0,
                      checked_wrong_blocked=0, checked_rejections=0,
                      input_bytes=0, prompt_tokens=0, completion_tokens=0,
                      usage_measured_calls=0, scored_supported_candidate_present=0))
        costs = spending.setdefault(key, {'reported': Decimal(0), 'known': 0})
        counts['planned_requests'] += 1
        counts['planned_tasks'] += len(slot['request']['tasks'])
        counts['input_bytes'] += slot['input_bytes']
        status = slot['status']
        counts['completed_requests'] += status == 'completed'
        counts['failed_requests'] += status in ('failed', 'started')
        counts['unattempted_requests'] += status == 'unattempted'
        for call in slot.get('calls', []):
            usage = call.get('usage', {})
            if call.get('cost') is not None:
                costs['reported'] += Decimal(str(call['cost']))
                costs['known'] += 1
            if isinstance(usage.get('prompt_tokens'), int) and isinstance(usage.get('completion_tokens'), int):
                counts['prompt_tokens'] += usage['prompt_tokens']
                counts['completion_tokens'] += usage['completion_tokens']
                counts['usage_measured_calls'] += 1
        # Candidate inclusion is observable even when a paid request fails/unattempted.
        expected = rubric['accepted_tools'][slot['request']['id']]
        for task in slot['request']['tasks']:
            valid = expected[task['id']]
            if valid:
                counts['supported_tasks'] += 1
                counts['candidate_hit'] += bool(set(valid).intersection(slot['packet']['presented_tools'][task['id']]))
        if status != 'completed':
            continue
        checks = {d['id']: d for d in slot.get('checked_decisions', [])}
        for d in slot['decisions']:
            valid = expected[d['id']]
            hit = bool(set(valid).intersection(slot['packet']['presented_tools'][d['id']]))
            chosen = d['tool']
            category = ('correct_tool' if chosen in valid else 'wrong_tool') if chosen is not None else ('unnecessary_null' if valid else 'correct_null')
            counts[category] += 1
            counts['scored_tasks'] += 1
            wrong = category in ('wrong_tool', 'unnecessary_null')
            counts['scored_supported_candidate_present'] += bool(valid) and hit
            counts['model_error_with_candidate'] += bool(valid) and hit and wrong
            counts['unsupported_tool_selected'] += not valid and chosen is not None
            check = checks.get(d['id'])
            if check:
                rejected = check['rejection'] is not None
                counts['checked_rejections'] += rejected
                counts['checked_correct_blocked'] += rejected and category == 'correct_tool'
                counts['checked_wrong_blocked'] += rejected and category == 'wrong_tool'
                counts['checked_wrong_allowed'] += not rejected and category == 'wrong_tool'
            rows.append({'model': key[0], 'size': key[1], 'arm': key[2],
                         'request': slot['request']['id'], 'task': d['id'],
                         'selected': chosen, 'accepted': valid, 'candidate_present': hit,
                         'category': category, 'check': check})
    return {'scope': 'Authored service-selection diagnostic; no final answer accuracy',
            'status': progress['status'], 'budget': progress.get('budget'),
            'groups': [dict(model=k[0], size=k[1], arm=k[2], **v,
                            unscored_tasks=v['planned_tasks']-v['scored_tasks'],
                            reported_usd=str(spending[k]['reported']) if spending[k]['known'] else None,
                            cost_measured_calls=spending[k]['known']) for k, v in groups.items()],
            'rows': rows,
            'interpretation': 'candidate_hit/supported_tasks; model errors conditional on candidate; bytes are not tokens; zero usage_measured_calls means tokens unmeasured, not zero use'}
