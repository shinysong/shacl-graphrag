"""Offline accounting of frozen outputs and externally supplied annotations.

No model client, automatic semantic scoring, reference repair, or consensus.
Annotator IDs are operator supplied, not authenticated human identities.
"""
from collections import Counter
import hashlib
import json

PHASES = ('draft', 'self_review', 'report')
STATES = ('succeeded', 'failed', 'not_attempted')
AXES = {
    'target_value': ('matches_reference', 'differs_or_offtarget', 'withheld', 'unadjudicable'),
    'unit': ('matches_reference', 'wrong', 'missing', 'not_applicable', 'unadjudicable'),
    'selected_evidence_support': ('supported', 'unsupported', 'ambiguous', 'no_assertion'),
    'nominal_or_measured_scope': ('nominal_correct', 'incorrectly_measured', 'unspecified', 'not_applicable', 'unadjudicable'),
    'citation_intent': ('content', 'location_metadata', 'mixed', 'unclear', 'missing'),
    'citation_applicability': ('supports_intended_proposition', 'does_not_support', 'ambiguous', 'missing'),
    'projection': ('faithful', 'omitted_proposition', 'wrong_binding', 'wrong_kind', 'compound_scalar', 'unadjudicable'),
    'review_pointer': ('relevant_and_valid', 'irrelevant', 'misleading', 'unadjudicable', 'not_applicable'),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def transition(before, after):
    """Target transition only; do not collapse independent support/unit axes."""
    b, a = before['target_value'], after['target_value']
    if 'unadjudicable' in (b, a):
        return 'unadjudicable'
    if b == a:
        return 'unchanged_target_label'
    names = {'matches_reference': 'matching', 'differs_or_offtarget': 'wrong', 'withheld': 'withheld'}
    return names[b] + '_to_' + names[a]


def summarize(plan, outputs, annotations):
    """Validate full planned denominator and summarize each annotator separately.

    plan: case_id/model/context_id/selected_target_supported. Evidence sufficiency
    is an evaluator input, never inferred from the model's self-reported status.
    outputs: exactly one state per case/phase; succeeded payload is frozen JSON.
    annotations: all eight rubric axes plus exact payload hash and rationale.
    Missing annotation remains unscored; no implicit label or consensus.
    """
    cases = {}
    for row in plan:
        cid = row['case_id']
        if not isinstance(cid, str) or not cid or cid in cases:
            raise ValueError('nonempty unique case_id required')
        if type(row['selected_target_supported']) is not bool:
            raise ValueError('evidence eligibility must be explicit boolean')
        for key in ('model', 'context_id'):
            if not isinstance(row[key], str) or not row[key]:
                raise ValueError('nonempty model/context_id required')
        cases[cid] = row
    traces = {}
    for row in outputs:
        key = (row['case_id'], row['phase'])
        if key in traces or key[0] not in cases or key[1] not in PHASES:
            raise ValueError('duplicate or unplanned output')
        state = row['state']
        if state not in STATES:
            raise ValueError('unknown execution state')
        if state == 'succeeded':
            if 'payload' not in row:
                raise ValueError('successful output requires payload')
            digest(row['payload'])
        elif 'payload' in row or not isinstance(row.get('reason'), str) or not row['reason'].strip():
            raise ValueError('failure/not-attempted requires reason and no success payload')
        traces[key] = row
    if set(traces) != {(cid, phase) for cid in cases for phase in PHASES}:
        raise ValueError('every planned phase must have explicit state')
    for cid in cases:
        if traces[cid, 'draft']['state'] != 'succeeded':
            if any(traces[cid, p]['state'] != 'not_attempted' for p in PHASES[1:]):
                raise ValueError('dependent revision without successful draft')
    labels = {}
    annotators = set()
    for row in annotations:
        aid = row['annotator_id']
        key = (row['case_id'], row['phase'])
        if not isinstance(aid, str) or not aid.strip() or key not in traces:
            raise ValueError('invalid annotator or unplanned annotation')
        bound = (aid,) + key
        if bound in labels or traces[key]['state'] != 'succeeded':
            raise ValueError('duplicate annotation or annotation on unsuccessful output')
        if row['payload_sha256'] != digest(traces[key]['payload']):
            raise ValueError('annotation is not bound to frozen payload')
        if set(row['labels']) != set(AXES):
            raise ValueError('all and only rubric axes required')
        if any(value not in AXES[axis] for axis, value in row['labels'].items()):
            raise ValueError('invalid rubric label')
        if not isinstance(row.get('rationale'), str) or not row['rationale'].strip():
            raise ValueError('explicit adjudication rationale required')
        # A rationale is audit material, not evidence of judgement correctness.
        labels[bound] = row['labels']
        annotators.add(aid)
    groups = {}
    for model in sorted({x['model'] for x in cases.values()}):
        ids = [cid for cid, row in cases.items() if row['model'] == model]
        eligible = [cid for cid in ids if cases[cid]['selected_target_supported']]
        group = {'planned_workflows': len(ids), 'support_eligible_planned': len(eligible),
                 'execution': {}, 'annotators': {}}
        for phase in PHASES:
            count = Counter(traces[cid, phase]['state'] for cid in ids)
            group['execution'][phase] = {state: count[state] for state in STATES}
        for aid in sorted(annotators):
            ar = {'phases': {}, 'transitions': {}}
            for phase in PHASES:
                scored = [cid for cid in ids if (aid, cid, phase) in labels]
                eligible_scored = [cid for cid in scored if cid in eligible]
                ar['phases'][phase] = {
                    'scored': len(scored),
                    'successful_unscored': sum(traces[cid, phase]['state'] == 'succeeded' for cid in ids) - len(scored),
                    'support_eligible_scored': len(eligible_scored),
                    'unnecessary_withholding': sum(labels[aid, cid, phase]['target_value'] == 'withheld' for cid in eligible_scored),
                    'axes': {axis: dict(Counter(labels[aid, cid, phase][axis] for cid in scored)) for axis in AXES},
                }
            for phase in PHASES[1:]:
                pairs = [cid for cid in ids if (aid, cid, 'draft') in labels and (aid, cid, phase) in labels]
                ar['transitions'][phase] = {
                    'planned_pairs': len(ids), 'scored_pairs': len(pairs),
                    'not_scored_pairs': len(ids) - len(pairs),
                    'target': dict(Counter(transition(labels[aid, cid, 'draft'], labels[aid, cid, phase]) for cid in pairs)),
                    'axis_pairs': {axis: dict(Counter(labels[aid, cid, 'draft'][axis] + ' -> ' + labels[aid, cid, phase][axis] for cid in pairs)) for axis in AXES},
                }
            group['annotators'][aid] = ar
        groups[model] = group
    disagreements = []
    for cid, phase in traces:
        present = {aid: labels[aid, cid, phase] for aid in sorted(annotators) if (aid, cid, phase) in labels}
        if len(present) < 2:
            continue
        differing = [axis for axis in AXES if len({x[axis] for x in present.values()}) > 1]
        if differing:
            disagreements.append({'case_id': cid, 'phase': phase, 'axes': differing, 'labels': present})
    return {'input_sha256': digest({'plan': plan, 'outputs': outputs, 'annotations': annotations}),
            'groups': groups, 'disagreements': disagreements, 'consensus_performed': False,
            'limits': ['externally supplied labels, no automatic semantic scoring or human identity verification',
                       'source agreement is not external truth', 'no confidence intervals or model ranking',
                       'planned failures retained separately from withholding', 'no runtime or repair use']}
