"""Offline subtarget accounting; external labels only, no runtime or model calls."""
from collections import Counter
import json
from scripts.postreview_evaluation import summarize, PHASES


def summarize_compound(plan, outputs, annotations):
    """Keep workflow execution and subtarget scoring denominators distinct.

    Each planned subtarget has a unique id and explicit selected_target_supported.
    Annotations bind the whole frozen phase payload and name one subtarget.
    No labels are inferred from a missing answer/annotation. No consensus.
    """
    base_plan=[]; expanded=[]; mapping={}; by_case={}
    for row in plan:
        cid=row['case_id']
        if cid in by_case: raise ValueError('duplicate workflow')
        targets=row['subtargets']
        if not isinstance(targets,list) or not targets: raise ValueError('nonempty subtargets required')
        seen=set()
        for target in targets:
            tid=target['subtarget_id']
            if not isinstance(tid,str) or not tid.strip() or tid in seen: raise ValueError('unique nonempty subtarget required')
            seen.add(tid)
            key=json.dumps([cid,tid],ensure_ascii=False,separators=(',',':'))
            mapping[cid,tid]=key
            expanded.append(dict(case_id=key,model=row['model'],context_id=row['context_id'],selected_target_supported=target['selected_target_supported']))
        by_case[cid]=row
        base_plan.append(dict(case_id=cid,model=row['model'],context_id=row['context_id'],selected_target_supported=False))
    # Validates exactly one phase state per original workflow and draft dependencies.
    base=summarize(base_plan,outputs,[])
    expanded_outputs=[]
    for row in outputs:
        for target in by_case[row['case_id']]['subtargets']:
            expanded_outputs.append(dict(row,case_id=mapping[row['case_id'],target['subtarget_id']]))
    expanded_annotations=[]
    for row in annotations:
        key=(row['case_id'],row['subtarget_id'])
        if key not in mapping: raise ValueError('unplanned annotation subtarget')
        copied={k:v for k,v in row.items() if k!='subtarget_id'}
        copied['case_id']=mapping[key];expanded_annotations.append(copied)
    scored=summarize(expanded,expanded_outputs,expanded_annotations)
    states={(r['case_id'],r['phase']):r['state'] for r in outputs}
    labels={(a['annotator_id'],a['case_id'],a['phase'],a['subtarget_id']):a['labels'] for a in annotations}
    aids=sorted({a['annotator_id'] for a in annotations});groups={}
    for model,b in base['groups'].items():
        ids=[c for c,r in by_case.items() if r['model']==model]
        sub=scored['groups'][model]
        groups[model]={'planned_workflows':len(ids),'workflow_execution':b['execution'],
                       'planned_subtargets':sub['planned_workflows'],'subtarget_execution_slots':sub['execution'],
                       'support_eligible_subtargets':sub['support_eligible_planned'],
                       'subtarget_annotations':sub['annotators'],'workflow_label_coverage':{}}
        for aid in aids:
            phases={}
            for phase in PHASES:
                counts=Counter()
                for cid in ids:
                    if states[cid,phase]!='succeeded': counts['unsuccessful_phase']+=1;continue
                    ls=[labels.get((aid,cid,phase,t['subtarget_id'])) for t in by_case[cid]['subtargets']]
                    if any(x is None for x in ls): counts['incompletely_annotated']+=1
                    elif any(x['target_value']=='unadjudicable' for x in ls): counts['contains_unadjudicable_target']+=1
                    elif all(x['target_value']=='matches_reference' for x in ls): counts['all_target_labels_match']+=1
                    else: counts['contains_wrong_or_withheld_target']+=1
                phases[phase]=dict(counts)
            groups[model]['workflow_label_coverage'][aid]=phases
    return {'groups':groups,'subtarget_disagreements':scored['disagreements'],
            'subtarget_identity_map':[{'encoded_id':v,'case_id':k[0],'subtarget_id':k[1]} for k,v in mapping.items()],
            'input_sha256':scored['input_sha256'],'consensus_performed':False,
            'limits':['Externally supplied annotations; no automatic semantic scoring or expert validation',
                      'All target labels match is not whole-answer correctness: unit/support/projection axes stay separate',
                      'Expanded subtarget slots share phase outputs and are not independent calls or trials',
                      'Missing annotations are unscored; failures are not withholding; no runtime gold or answer repair']}
