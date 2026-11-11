#!/usr/bin/env python3
"""Bounded independent worker processes; preserves planned and failed size slots."""
import argparse
import json
import os
from pathlib import Path
import random
import resource
import subprocess
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def save_plan(output,plan):
    temp=output/'plan.tmp';temp.write_text(json.dumps(plan,indent=2)+'\n');temp.replace(output/'plan.json')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--worker',choices=('unrelated','fanout'));p.add_argument('--value',type=int)
    args=p.parse_args()
    if args.worker:
        # Per-worker limits, not system-wide limits. No GPU/network/DB services.
        resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
        resource.setrlimit(resource.RLIMIT_CPU,(180,180))
        from experiments.factory_complexity.scaling import measure
        result=measure(args.output,args.worker,args.value)
        print(json.dumps({k:result[k] for k in ('axis','value','status','projected_current_triples')}));return 0
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    cells=[(a,v) for a,values in [('unrelated',(1000,10000,100000)),('fanout',(29,30,31))] for v in values]
    random.Random(20261111).shuffle(cells)
    plan=[{'axis':a,'value':v,'status':'not_attempted'} for a,v in cells]
    save_plan(output,plan)
    for slot in plan:
        dest=output/(slot['axis']+'-'+str(slot['value']))
        cmd=[sys.executable,__file__,'--worker',slot['axis'],'--value',str(slot['value']),'--output',str(dest)]
        slot.update(status='running',started_at=datetime.now(timezone.utc).isoformat())
        save_plan(output,plan)
        try:
            response=subprocess.run(cmd,cwd=ROOT,env=os.environ.copy(),capture_output=True,text=True,timeout=240)
            slot.update(status='completed' if response.returncode==0 else 'failed',exit_code=response.returncode)
            (output/(dest.name+'.stdout.txt')).write_text(response.stdout)
            (output/(dest.name+'.stderr.txt')).write_text(response.stderr)
        except subprocess.TimeoutExpired as error:
            slot.update(status='timeout',error=str(error))
            for suffix,text in (('stdout',error.stdout),('stderr',error.stderr)):
                (output/(dest.name+'.'+suffix+'.txt')).write_text(text.decode(errors='replace') if isinstance(text,bytes) else text or '')
        except OSError as error:
            slot.update(status='launch_failed',error=str(error))
        slot['finished_at']=datetime.now(timezone.utc).isoformat()
        save_plan(output,plan)
        print(json.dumps(slot),flush=True)
    # Cross-size equivalence is evaluated only when ALL unrelated-size slots completed.
    from experiments.factory_complexity.scaling import logical
    unrelated=[s for s in plan if s['axis']=='unrelated']
    equal=None
    if all(s['status']=='completed' for s in unrelated):
        rows=[logical(json.loads((output/('unrelated-'+str(s['value']))/'study_rdflib-evidence.json').read_text())) for s in unrelated]
        equal=all(row==rows[0] for row in rows)
    summary={'planned':len(plan),'completed':sum(s['status']=='completed' for s in plan),
        'unrelated_result_equal':equal,'calls':{'llm':0,'aws':0},
        'scope':'Offline in-memory software timing; no server-engine or answer-quality benchmark.'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
    return 0 if summary['completed']==len(plan) and equal is True else 1

if __name__=='__main__':raise SystemExit(main())
