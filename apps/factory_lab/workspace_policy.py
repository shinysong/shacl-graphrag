"""Human applicability selection for the fixed workspace policy adapter.

This does not compile text or infer which document is authoritative. Legacy
research preparation semantics are preserved outside the workspace boundary.
"""
from . import preparation as p, policy_dates


def groups(draft):
    _,contracts=p.adapter_config(draft['adapter'])
    result=[]
    for target,contract in contracts.items():
        entries=[e for e in draft['entries'] if e['kind']=='policy' and e['target']==target]
        if len(entries)<2:continue
        result.append({'target':target,'meaning':contract['meaning'],'entries':entries,
                       'multiple_approved':sum(e['status']=='approved' for e in entries)>1})
    return result


def require_unambiguous(draft):
    for entry in draft['entries']:
        if entry['kind']=='policy' and entry['status']=='approved' and entry['target'] not in ('context','unsupported',''):
            dates=policy_dates.candidates(entry['source']['text'])
            if dates and 'temporal' not in entry:
                raise ValueError('Review policy date roles before decision execution')
            if 'temporal' in entry:
                policy_dates.validate(entry['temporal'],entry['source']['text'])
                policy_dates.require_applicable(entry['temporal'],draft['metadata']['as_of'])
    unresolved=[g['target'] for g in groups(draft) if g['multiple_approved']]
    if unresolved:
        raise ValueError('Select the applicable policy source before decision execution: '+', '.join(unresolved))


def resolve(draft, target, selected_id, rationale):
    if not isinstance(rationale,str) or not 1<=len(rationale.strip())<=3500:
        raise ValueError('Record the applicability and exclusion rationale (1..3500 characters)')
    group=next((g for g in groups(draft) if g['target']==target),None)
    if group is None or selected_id not in {e['id'] for e in group['entries']}:
        raise ValueError('Select one of the policy source candidates')
    # One complete source interpretation for this fixed adapter. Complementary
    # clauses requiring composition must remain unresolved, not silently merged.
    result=draft
    for entry in group['entries']:
        selected=entry['id']==selected_id
        result=p.change(result,entry['id'],'approved' if selected else 'excluded',target,
                        note=('Applicable source selected: ' if selected else 'Excluded in favor of '+selected_id+': ')+rationale,
                        interpretation=rationale if selected else entry['interpretation'],temporal=entry.get('temporal'))
    return result


def require_ready(draft):
    from . import policy_agreement
    require_unambiguous(draft)
    policy_agreement.require_confirmed(draft)
