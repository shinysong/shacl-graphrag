"""Source-bound human policy comparison, not automatic semantic validation."""
from copy import deepcopy
import re

from . import preparation as p, policy_inputs


def validate(record):
    if not isinstance(record, dict) or set(record) != {'binding', 'decision', 'basis', 'rationale'}:
        raise ValueError('Invalid policy comparison record')
    if not isinstance(record['binding'], str) or not re.fullmatch('[0-9a-f]{64}', record['binding']):
        raise ValueError('Invalid policy comparison binding')
    if record['decision'] not in ('agrees', 'discrepant', 'unresolved'):
        raise ValueError('Invalid policy comparison decision')
    if record['basis'] not in ('before_discount', 'after_discount', 'not_applicable', 'unresolved'):
        raise ValueError('Invalid policy calculation basis')
    if not isinstance(record['rationale'], str) or not 1 <= len(record['rationale'].strip()) <= 3500:
        raise ValueError('Record the compared values, scope and unresolved differences')


def context(draft, entry_id):
    entry = next((e for e in draft['entries'] if e['id'] == entry_id), None)
    _, contracts = p.adapter_config(draft['adapter'])
    if entry is None or entry['kind'] != 'policy' or entry['target'] not in contracts:
        raise ValueError('Select a policy with a supported interpretation')
    inputs = policy_inputs.describe(draft, contracts)[entry['target']]
    # Until task-specific dependencies are defined, bind every mapping decision.
    # IDs, references and calculation inputs can change applicability even when
    # the policy's displayed thresholds stay identical.
    mappings = [{k: deepcopy(e.get(k)) for k in ('id','source','target','status')}
                for e in draft['entries'] if e['kind']=='mapping']
    inputs['scope_mappings'] = mappings
    # Bind all source bytes and metadata conservatively. An additional policy
    # may change applicability even when the original paragraph is unchanged.
    bound = {'adapter': draft['adapter'], 'metadata': draft['metadata'],
             'sources': {s['name']: s['sha256'] for s in draft['sources']},
             'policy': {k: entry.get(k) for k in ('id', 'source', 'target', 'status', 'interpretation', 'temporal')},
             'inputs': inputs}
    return entry, inputs, p.digest(bound)


def status(draft, entry_id):
    entry, inputs, binding = context(draft, entry_id)
    record = entry.get('agreement')
    if record is None:
        state = 'unreviewed'
    else:
        validate(record)
        state = record['decision'] if record['binding'] == binding else 'stale'
    return {'state': state, 'binding': binding, 'record': deepcopy(record), 'inputs': inputs}


def review(draft, entry_id, binding, decision, basis, rationale):
    entry, inputs, current = context(draft, entry_id)
    if binding != current:
        raise ValueError('Policy comparison inputs changed; reopen the comparison')
    record = {'binding': current, 'decision': decision, 'basis': basis, 'rationale': rationale}
    validate(record)
    if decision == 'agrees':
        if entry['status'] != 'approved' or any(f['state'] != 'available' for f in inputs['fields']):
            raise ValueError('Approve the policy and its required field mappings before confirming agreement')
        if entry['target'] in ('shipping', 'coupon') and basis != 'before_discount':
            raise ValueError('The fixed calculation requires an explicit before-discount basis')
        if basis == 'unresolved':
            raise ValueError('Resolve the calculation basis before confirming agreement')
    history = p._validated_history(draft)
    result = deepcopy(draft)
    updated = next(e for e in result['entries'] if e['id'] == entry_id)
    if updated.get('agreement') != record:
        history.append(p._history_record(updated, 'change'))
    updated['agreement'] = record
    p._set_history(result, history)
    return result


def require_confirmed(draft):
    """Decision-only workspace guard; raw lookup and historical replay stay usable."""
    if draft['adapter'] != p.ADAPTER:
        return
    _, contracts = p.adapter_config(draft['adapter'])
    for entry in draft['entries']:
        if entry['kind'] != 'policy' or entry['status'] != 'approved' or entry['target'] not in contracts:
            continue
        current = status(draft, entry['id'])
        if current['state'] != 'agrees':
            raise ValueError('Review policy and table agreement before decision execution: '
                             + entry['id'] + ' (' + current['state'] + ')')
        record = current['record']
        if entry['target'] in ('shipping', 'coupon') and record['basis'] != 'before_discount':
            raise ValueError('Review before-discount calculation basis before decision execution')
        if record['basis'] == 'unresolved' or any(f['state'] != 'available' for f in current['inputs']['fields']):
            raise ValueError('Resolve policy calculation inputs before decision execution')
