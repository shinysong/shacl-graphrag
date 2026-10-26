"""Posthoc frozen development acceptance, hashes before execution, no repair."""
import hashlib
import json
import sys
from pathlib import Path
from technology_selection_process import supervise
ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'_workspace/technology-selection/maintenance-1/frozen'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    submitted=Path(sys.argv[1]);out=Path(sys.argv[2])
    summarize_only = len(sys.argv)==4 and sys.argv[3]=='--summarize-only'
    if not summarize_only: out.mkdir(parents=True,exist_ok=False)
    saved = {}
    if summarize_only:
        for line in (out/'cases.jsonl').read_text().splitlines():
            row=json.loads(line);key=(row['submission'],row['case_id'])
            if key in saved:raise ValueError('duplicate saved row')
            saved[key]=row
        if len(saved)!=96:raise ValueError('incomplete saved run')
    if (out/'summary.json').exists():raise ValueError('summary exists')
    manifest=json.loads((FROZEN/'manifest.json').read_text());submissions=json.loads((submitted/'submissions.json').read_text())
    if sha(FROZEN/'manifest.json')!=submissions['baseline_manifest_sha256']:raise ValueError('changed acceptance')
    for p,h in manifest['files'].items():
        if sha(FROZEN/p)!=h:raise ValueError('changed case')
    rows=[];summary=[];artifacts={}
    for submission in submissions['submissions']:
        for p,h in submission['source_hashes'].items():
            if sha(Path(submission['root'])/p)!=h:raise ValueError('submission changed')
        if sha(submitted/(submission['id']+'.patch'))!=submission['patch_sha256']:raise ValueError('patch changed')
        selected=[c for c in manifest['cases'] if c['task']==submission['task']]
        own=[]
        for case in selected:
            reference=json.loads((FROZEN/'references'/(case['id']+'.json')).read_text())['expected']
            folder=out/(submission['id']+'--'+case['id'])
            process=saved[(submission['id'],case['id'])]['process'] if summarize_only else supervise([sys.executable,str(ROOT/'scripts/technology_selection_maintenance_worker.py'),submission['root'],submission['arm'],str(FROZEN/'runtime'/(case['id']+'.json'))],folder)
            row=dict(submission=submission['id'],case_id=case['id'],regression=case['regression'],process=process,correct=False)
            if process['status']=='completed':
                try:
                    reply=json.loads((folder/'stdout.log').read_text());row['correct']=reply['answer']==reference
                    row['actual']=reply['answer']
                    if submission['task']=='M4':
                        artifacts.setdefault(submission['id'],set()).add((reply['policy_artifact'],reply['policy_sha256']))
                except (ValueError,KeyError) as exc:row['schema_error']=str(exc)
            own.append(row);rows.append(row)
            if summarize_only:
                if row != saved[(submission['id'],case['id'])]:raise ValueError('saved outcome differs')
            else:
                with (out/'cases.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        shared_ok=submission['task']!='M4' or len(artifacts.get(submission['id'],set()))==1
        summary.append(dict(id=submission['id'],task=submission['task'],arm=submission['arm'],attempt=1,cases=len(own),correct=sum(r['correct'] for r in own),regression_cases=sum(r['regression'] for r in own),shared_artifact_ok=shared_ok,passed=all(r['correct'] for r in own) and shared_ok,changed=submission['changed'],shared_change=submission['shared_change']))
    unique={}
    for sub in submissions['submissions']:
        for change in sub['changed']:
            key=(sub['task'],change['path'],change['sha256'])
            unique.setdefault(key,dict(task=sub['task'],**change,arms=[]))['arms'].append(sub['arm'])
    result=dict(initial_submissions=len(summary),passed=sum(s['passed'] for s in summary),case_outputs=len(rows),correct_outputs=sum(r['correct'] for r in rows),submissions=summary,unique_changes=list(unique.values()),
        common_harness=dict(worker_sha256=sha(ROOT/'scripts/technology_selection_maintenance_worker.py'),scorer_sha256=sha(__file__),interpretation='Three local caller functions, not independently deployed services. Onecoordinator fixedorder; no human effort measurement. Shared test harness counted separately.'),
        preserved_first_failures=[s['id'] for s in summary if not s['passed']])
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['initial_submissions','passed','case_outputs','correct_outputs','preserved_first_failures']}))


if __name__=='__main__':main()
