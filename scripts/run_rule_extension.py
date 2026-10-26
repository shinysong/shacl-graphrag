"""Bounded offline extension experiment. Workers receive runtime data only.
Scorer references are read by coordinator after workers terminate. This is a
shared filesystem, not an OS-enforced gold-access security boundary.
"""
import hashlib
import html
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'_workspace/rule-extension-v1'
FROZEN=WORK/'frozen'
OLD=ROOT/'_workspace/technology-selection/fixtures-1/frozen'
SOURCES=['scripts/rule_extension_common.py','scripts/rule_extension_python.py','scripts/rule_extension_rdf.py','scripts/rule_extension_service.py','research/rule-extension/policy-v1.json','research/rule-extension/policy-v2.json','research/rule-extension/release-shapes-v1.ttl']


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def worker(arm):
    resource.setrlimit(resource.RLIMIT_AS,(1536*1024*1024,1536*1024*1024))
    if arm=='python':from technology_selection_python import PythonArm as Legacy
    else:from technology_selection_rdf import RDFArm as Legacy
    old={}
    def emit(obj):print(json.dumps(obj,sort_keys=True),flush=True)
    for f in sorted((OLD/'runtime').glob('*.json')):
        old[f.stem]=Legacy(json.loads(f.read_text())['packet'])
        emit(dict(type='legacy',moment='before',case=f.stem,answer=old[f.stem].query()))
    # Import extension only after saving resident legacy before outputs.
    from rule_extension_service import call
    for f in sorted((FROZEN/'runtime').glob('*.json')):
        packet=json.loads(f.read_text())
        for version in ('v1','v2'):
            for consumer in ('A','B','C'):
                emit(dict(type='new',case=f.stem,**call(arm,consumer,packet,version)))
    for case,instance in old.items():
        emit(dict(type='legacy',moment='after',case=case,answer=instance.query()))
    emit(dict(type='resource',maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def main():
    output=WORK/'attempt-1'
    if output.exists():raise SystemExit('first attempt exists; inspect and review before any new attempt')
    output.mkdir()
    frozen=json.loads((FROZEN/'manifest.json').read_text())
    hashes={str(p.relative_to(ROOT)):digest(p) for p in [ROOT/s for s in SOURCES]+[Path(__file__).resolve(),ROOT/'scripts/build_rule_extension_cases.py',ROOT/'research/rule-extension/protocol-v1.json']}
    hashes.update({str((FROZEN/k).relative_to(ROOT)):v for k,v in frozen['files'].items()})
    (output/'binding.json').write_text(json.dumps(dict(sources=hashes,legacy_baseline=frozen['baseline']),indent=2))
    observations={}; deadline=time.monotonic()+180
    for arm in ('python','rdf'):
        start=time.monotonic()
        try:
            with (output/f'{arm}.jsonl').open('w') as out,(output/f'{arm}.stderr').open('w') as err:
                result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',arm],cwd=ROOT,stdout=out,stderr=err,timeout=max(1,deadline-time.monotonic()),env=dict(os.environ,PYTHONPATH=str(ROOT/'scripts')))
            observations[arm]=dict(exit_code=result.returncode,elapsed_seconds=time.monotonic()-start)
        except subprocess.TimeoutExpired:
            observations[arm]=dict(exit_code='timeout',elapsed_seconds=time.monotonic()-start)
    failures=[]; new_rows=[]; legacy_outputs=[]; pairs=0; old_ref_assertions=0; historical_assertions=0
    by_arm={}
    for arm in ('python','rdf'):
        rows=[json.loads(s) for s in (output/f'{arm}.jsonl').read_text().splitlines()]
        by_arm[arm]=rows
        if observations[arm]['exit_code']!=0:failures.append(dict(arm=arm,error='worker failure'))
        before={}
        for row in rows:
            if row['type']=='resource':observations[arm]['maxrss_kib']=row['maxrss_kib'];continue
            if row['type']=='legacy':
                legacy_outputs.append(dict(arm=arm,**row))
                ref=json.loads((OLD/'scorer'/f"{row['case']}-expected.json").read_text())['baseline']
                old_ref_assertions+=1
                if row['answer']!=ref:failures.append(dict(arm=arm,case=row['case'],error='legacy reference mismatch',moment=row['moment']))
                old_arm='python_indexed' if arm=='python' else 'rdf_owl_shacl'
                history=ROOT/f"_workspace/technology-selection/campaign-1/results/{row['case']}-r0-{old_arm}/stdout.log"
                hist=next(x['answer'] for line in history.read_text().splitlines() if (x:=json.loads(line)).get('event')=='query' and x.get('phase')=='warmup')
                historical_assertions+=1
                if row['answer']!=hist:failures.append(dict(arm=arm,case=row['case'],error='historical baseline mismatch',moment=row['moment']))
                if row['moment']=='before':before[row['case']]=row['answer']
                else:
                    pairs+=1
                    if row['answer']!=before.get(row['case']):failures.append(dict(arm=arm,case=row['case'],error='regression'))
                continue
            ref=json.loads((FROZEN/'scorer'/f"{row['case']}.json").read_text())['expected'][row['policy_version']]
            answer=row['answer']; simplified=dict(decision=answer['decision'],violations=[x['rule_id'] for x in answer['violations']],unknown=[x['rule_id'] for x in answer['unknown']])
            record=dict(arm=arm,**row,reference_match=simplified==ref)
            packet=json.loads((FROZEN/'runtime'/f"{row['case']}.json").read_text())
            ids={r['occurrence_id'] for rs in packet['tables'].values() for r in rs}
            record['witness_ids_exist']=set(answer['evidence'])<=ids and all(set(x['support'])<=ids for k in ('violations','unknown') for x in answer[k])
            if not record['reference_match'] or not record['witness_ids_exist']:failures.append(dict(arm=arm,case=row['case'],version=row['policy_version'],consumer=row['consumer'],error='new output mismatch'))
            new_rows.append(record)
    indexed={(r['arm'],r['case'],r['policy_version'],r['consumer']):r for r in new_rows}
    parity=0; sharing=0
    for case in frozen['cases']:
        for version in ('v1','v2'):
            for consumer in ('A','B','C'):
                a=indexed.get(('python',case,version,consumer));b=indexed.get(('rdf',case,version,consumer))
                if a and b and a['answer']==b['answer']:parity+=1
                else:failures.append(dict(case=case,error='arm parity'))
            for arm in ('python','rdf'):
                group=[indexed.get((arm,case,version,c)) for c in ('A','B','C')]
                if all(group) and len({json.dumps((x['answer'],x['policy_sha256']),sort_keys=True) for x in group})==1:sharing+=1
                else:failures.append(dict(arm=arm,case=case,error='shared consumer version mismatch'))
    changed=[p for p,h in frozen['baseline'].items() if digest(ROOT/p)!=h]
    new_changed=[p for p,h in hashes.items() if digest(ROOT/p)!=h]
    if changed or new_changed:failures.append(dict(error='bound source mutated',legacy=changed,new=new_changed))
    summary=dict(study='rule-extension-1',origin='authored offline extension; no human participants',worker_observations=observations,new_decisions=len(new_rows),new_reference_matches=sum(r['reference_match'] for r in new_rows),parity_pairs=parity,shared_consumer_groups=sharing,legacy_outputs=len(legacy_outputs),before_after_pairs=pairs,legacy_reference_assertions=old_ref_assertions,historical_baseline_assertions=historical_assertions,legacy_changed_files=changed,new_changed_files=new_changed,failures=failures,
                 limits=['16 authored scenarios,2 identity/order controls; not independent domain trials','Common joins/scalar parsing/output mapping reused by both; check predicate engines differ','No raw-document extraction,actual reviewer action,GUI usability,human labor or distributed sharing measurement','Missing/duplicate document branches not exercised','Witness presence and paired equality checked; no independent completeness proof','No experimental LLM calls'],
                 production_files=[dict(path=s,lines=len((ROOT/s).read_text().splitlines()),sha256=digest(ROOT/s)) for s in SOURCES])
    (output/'new-results.json').write_text(json.dumps(new_rows,indent=2))
    (output/'legacy-results.json').write_text(json.dumps(legacy_outputs,indent=2))
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    # Read-only review surface; not an approval system or usability experiment.
    table=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ('arm','case','policy_version','consumer','reference_match'))+'<td><pre>'+html.escape(json.dumps(r['answer'],indent=2))+'</pre></td></tr>' for r in new_rows)
    page='<html><meta charset="utf-8"><title>Rule extension evidence review</title><style>body{font-family:sans-serif;max-width:1200px;margin:2rem auto}td{border:1px solid #bbb;padding:.4rem}pre{white-space:pre-wrap}</style><h1>Policy document release evidence</h1><p>Authored rule: exact document revision, Approved document, Accept review, qualified independent reviewer, start &lt;= assessment &lt; end. Read-only research evidence, no approval action.</p><h2>Policy versions</h2><pre>'+html.escape((ROOT/SOURCES[4]).read_text()+(ROOT/SOURCES[5]).read_text())+'</pre><h2>Change footprint and results</h2><pre>'+html.escape(json.dumps(summary,indent=2))+'</pre><h2>Individual outputs and evidence IDs</h2><table>'+table+'</table></html>'
    (output/'review.html').write_text(page)
    print(json.dumps(summary))
    return 1 if failures or len(new_rows)!=384 or len(legacy_outputs)!=88 else 0


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2])
    else:raise SystemExit(main())
