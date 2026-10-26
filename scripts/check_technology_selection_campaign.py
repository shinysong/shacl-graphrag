"""Failure-path and scorer controls; no performance fixtures executed."""
import json
import sys
from pathlib import Path
from technology_selection_process import supervise
from technology_selection_score import score, digest


def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    resistant=supervise([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready",flush=True); time.sleep(20)'],out/'kill',wall_seconds=.3,grace_seconds=.05)
    assert resistant['status']=='timeout' and resistant['returncode']==-9 and resistant['termination_confirmed']
    child=supervise([sys.executable,'-c','import os,time; pid=os.fork(); time.sleep(20) if pid==0 else None'],out/'descendant',wall_seconds=.3,grace_seconds=.05)
    assert child['status']=='timeout' and child['termination_confirmed'] and child['elapsed_ns']<2_000_000_000
    code='import resource,json,sys; resource.setrlimit(resource.RLIMIT_AS,(64*1024*1024,64*1024*1024))\ntry: x=bytearray(128*1024*1024)\nexcept MemoryError: print(json.dumps(dict(event="failure",kind="memory_limit")),flush=True); sys.exit(3)'
    memory=supervise([sys.executable,'-c',code],out/'memory')
    assert score(out/'memory/stdout.log',memory,{})['status']=='memory_limit'
    answer={'literal':'expected'}; refs={k:answer for k in ('baseline','E','C')}
    sequence=[('warmup',0)]+[(f'steady_{n}',i) for n in (1,10,100) for i in range(n)]+[('post_E',0),('post_C',0)]
    events=[dict(event='query',phase=p,iteration=i,duration_ns=1,digest=digest(answer),answer=answer) for p,i in sequence]
    events.append(dict(event='complete',queries=114))
    path=out/'events.jsonl'
    def save(): path.write_text(''.join(json.dumps(e)+'\n' for e in events))
    save(); assert score(path,{'status':'completed'},refs)['status']=='success'
    events[10]['answer']={'literal':'wrong'};events[10]['digest']=digest(events[10]['answer']);save()
    assert score(path,{'status':'completed'},refs)['wrong_queries']==1
    events[10]['digest']='corrupt';save();assert score(path,{'status':'completed'},refs)['status']=='schema_error'
    events=events[:3];save();partial=score(path,{'status':'timeout'},refs)
    assert partial['status']=='timeout' and partial['missing_queries']==111
    print('7 controls passed: forced kill, descendant pipe, explicit memory failure, exact scoring, wrong answer, corrupt digest, partial timeout;0performancefixture executions')


if __name__=='__main__':main()
