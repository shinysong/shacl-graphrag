"""Expand intake failures to declared keys; never generate successful decisions."""
from scripts.retail_python_intake import inspect_python
from scripts.retail_turtle_intake import inspect_turtle

FAILURES={'generation_empty_or_truncated','artifact_parse_error','artifact_unsupported_or_isolation_rejected'}

def intake_for_keys(raw,kind,keys,attempt_id):
    if not isinstance(attempt_id,str) or not attempt_id.strip():raise ValueError('Attempt ID required')
    if kind not in ('python','turtle'):raise ValueError('Unsupported artifact kind')
    normalized=[];seen=set()
    for key in keys:
        if not isinstance(key,(tuple,list)) or len(key)!=2 or any(not isinstance(v,str) or not v.strip() for v in key):
            raise ValueError('Expected nonblank row_id/policy pairs')
        pair=tuple(key)
        if pair in seen:raise ValueError('Duplicate evaluation key')
        seen.add(pair);normalized.append(pair)
    if not normalized:raise ValueError('At least one declared key required')
    intake=(inspect_python if kind=='python' else inspect_turtle)(raw)
    failed=intake['status'] in FAILURES
    return {'attempt_id':attempt_id,'artifact_kind':kind,'intake':intake,
            'declared_keys':[list(k) for k in normalized],
            'ready_for_scoring':failed,
            'state':'terminal_intake_failure' if failed else 'pending_execution',
            'failure_stage':intake['status'] if failed else None,
            'predictions':[{'row_id':r,'policy':p,'status':'error'} for r,p in normalized] if failed else [],
            'note':'error is a scoring bucket; failure_stage distinguishes pre-execution failure from actual runtime failure. Pending artifacts must not be scored as completed runs.'}
