"""Posthoc exact frozen-reference scorer. Never imported by algorithm arms."""
import hashlib
import json
from collections import Counter
from pathlib import Path


def digest(answer):
    return hashlib.sha256(json.dumps(answer, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def score(path, process, expected):
    answers = {}; rows = []; events = []; errors = []; memory = False
    for number, line in enumerate(Path(path).read_bytes().splitlines(), 1):
        try:
            e = json.loads(line); events.append(e)
            if e.get('event') == 'failure': memory |= e.get('kind') == 'memory_limit'
            if e.get('event') != 'query': continue
            phase = e['phase']; iteration = e['iteration']
            if phase not in ('warmup','steady_1','steady_10','steady_100','post_E','post_C') or type(iteration) is not int or type(e['duration_ns']) is not int or e['duration_ns'] < 0:
                raise ValueError('invalid query event')
            if 'answer' in e:
                if digest(e['answer']) != e['digest']: raise ValueError('answer digest mismatch')
                answers[e['digest']] = e['answer']
            answer = answers[e['digest']]
            reference = expected['E' if phase == 'post_E' else 'C' if phase == 'post_C' else 'baseline']
            # Exact dictionary equality rejects missing/extra fields as well as wrong values.
            rows.append(dict(phase=phase, iteration=iteration, correct=answer == reference, duration_ns=e['duration_ns']))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append(dict(line=number, error=str(exc)[:300]))
    expected_sequence = [('warmup',0)] + [(f'steady_{n}',i) for n in (1,10,100) for i in range(n)] + [('post_E',0),('post_C',0)]
    actual_sequence = [(r['phase'],r['iteration']) for r in rows]
    if actual_sequence != expected_sequence[:len(rows)]: errors.append(dict(error='query sequence is not declared prefix'))
    complete = [e for e in events if isinstance(e,dict) and e.get('event') == 'complete']
    if process['status'] == 'completed' and (len(rows) != 114 or len(complete) != 1 or complete[0].get('queries') != 114):
        errors.append(dict(error='incomplete successful worker'))
    if process['status'] == 'timeout': status = 'timeout'
    elif process['status'] == 'artifact_limit': status = 'artifact_limit'
    elif memory: status = 'memory_limit'
    elif process['status'] != 'completed': status = 'execution_error'
    elif errors: status = 'schema_error'
    elif any(not r['correct'] for r in rows): status = 'semantic_mismatch'
    else: status = 'success'
    return dict(status=status, schema_errors=errors, queries=rows,
                wrong_queries=sum(not r['correct'] for r in rows),
                completed_phase_counts=dict(Counter(r['phase'] for r in rows)),
                missing_queries=114-len(rows), events_without_query_answers=[e for e in events if isinstance(e,dict) and e.get('event') != 'query'])
