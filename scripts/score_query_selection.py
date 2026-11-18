"""Posthoc evaluator. Never imported by selection or query execution."""
import argparse
import hashlib
import json
from pathlib import Path


def score(record, rubric):
    accepted=rubric['accepted_tools']; summaries={}
    for arm in ('top1','typed_top3'):
        # Count intentions once; backend duplicates are parity checks, not extra trials.
        slots=[s for s in record['slots'] if s['arm']==arm and s['backend']=='sqlite']
        counts={'obligations':sum(len(v) for v in accepted.values()),'correct_selection':0,
                'wrong_selection':0,'unnecessary_unselected':0,'correct_unselected':0,
                'unscored_failure':0,'invalid_plans':0,'retained_errors':[]}
        seen=set()
        for slot in slots:
            expected=accepted[slot['request_id']]
            if slot['status']!='recorded':continue
            result=slot['result']; counts['invalid_plans']+=not result['selection']['structurally_valid']
            for decision in result['selection']['decisions']:
                key=(slot['request_id'],decision['id']);seen.add(key)
                choice=decision['selected_tool']; valid=expected[decision['id']]
                category=('correct_selection' if choice in valid else 'wrong_selection') if choice else ('unnecessary_unselected' if valid else 'correct_unselected')
                counts[category]+=1
                if category in ('wrong_selection','unnecessary_unselected'):
                    counts['retained_errors'].append({'request':key[0],'task':key[1],'selected':choice,'accepted':valid})
        counts['unscored_failure']=counts['obligations']-len(seen);summaries[arm]=counts
    parity=[]
    for arm in ('top1','typed_top3'):
        for request in accepted:
            slots=[s for s in record['slots'] if s['arm']==arm and s['request_id']==request]
            a,b=slots
            ra=a.get('result',{});rb=b.get('result',{})
            ea=ra.get('execution');eb=rb.get('execution')
            parity.append({'request':request,'arm':arm,'selection_equal':ra.get('selection')==rb.get('selection'),
                'executed_both':ea is not None and eb is not None,
                'outputs_equal':ea['outputs']==eb['outputs'] if ea is not None and eb is not None else None})
    return {'scope':'authored development; selection labels not final answer accuracy',
            'summaries':summaries,'backend_parity':parity,'answer_quality':'unmeasured'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--results',required=True);p.add_argument('--rubric',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    dest=Path(a.output)
    if dest.exists():raise ValueError('Output already exists')
    result=score(json.loads(Path(a.results).read_text()),json.loads(Path(a.rubric).read_text()))
    result['sha256']={s:hashlib.sha256(Path(s).read_bytes()).hexdigest() for s in (a.results,a.rubric)}
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
