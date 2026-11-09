"""Posthoc review comparison; supplied classifications are evaluation-only."""
import argparse
import json
from pathlib import Path


def evaluate(folder, evaluator, out):
    config=json.loads((folder/'config.json').read_text())
    expected={q['id']:q['expected_classification'] for q in json.loads(evaluator.read_text())}
    inputs={q['id']:json.loads(q['messages'][1]['content']) for q in config['inputs']}
    rows=[]
    for index,slot in enumerate(config['slots']):
        qid,arm,model=slot['question_id'].split('|')
        if model!=slot['model']:raise ValueError('model_binding')
        draft=inputs[slot['question_id']]['saved_draft']
        before_correct=(draft['completion_status']=='completed' and draft['parsed_response']['classification']==expected[qid])
        row={**slot,'case':qid,'arm':arm,'state':'not_completed','correct':False,'draft_correct':before_correct,
             'draft_status':draft['completion_status']}
        path=folder/'responses'/f'{index:03d}.result.json'
        if path.exists():
            result=json.loads(path.read_text());row['state']=result['status'];row['answer']=result.get('contract')
            row['correct']=result['status']=='completed' and result['contract']['classification']==expected[qid]
        rows.append(row)
    counts={a:{'planned':sum(r['arm']==a for r in rows),'completed':sum(r['arm']==a and r['state']=='completed' for r in rows),
               'correct':sum(r['arm']==a and r['correct'] for r in rows),
               'correct_draft_harmed':sum(r['arm']==a and r['draft_correct'] and not r['correct'] for r in rows),
               'wrong_valid_draft_corrected':sum(r['arm']==a and r['draft_status']=='completed' and not r['draft_correct'] and r['correct'] for r in rows),
               'failed_draft_to_correct':sum(r['arm']==a and r['draft_status']!='completed' and r['correct'] for r in rows)} for a in ('self_review','shacl_review')}
    pairs=[]
    for qid in ('P01','P02','P03'):
        for p in config['providers']:
            rr={r['arm']:r for r in rows if r['case']==qid and r['model']==p['model']}
            pairs.append({'case':qid,'model':p['model'],'self_correct':rr['self_review']['correct'],'shacl_correct':rr['shacl_review']['correct']})
    out.write_text(json.dumps({'planned':len(rows),'arm_counts':counts,'pairs':pairs,'rows':rows,
        'limits':'Posthoc three-case development subset selected after P03 errors. Both conditions receive same source and normative policy, share original draft, common additional2048outputcap. No independent draft replicas, explanationtruth, externaltruth or maintenanceeffort measurement.'},ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('evaluator',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args();evaluate(a.folder,a.evaluator,a.out)
