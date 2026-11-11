"""Prepare a closed paid gate; execute only a separately approved frozen scope."""
import copy
import fcntl
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import itertools
import json
from pathlib import Path
import random
import threading

from apps.factory_lab.agent import Runner
from apps.factory_lab.llm import Gateway
from apps.factory_lab.store import ROOT,Store
from apps.factory_lab.evidence import canonical
from .tools import Views,RDFStudyTools,CATALOG,NOTICE

DEADLINE='2026-11-11T17:32:41+00:00'
CAMPAIGN='factory-complexity-1'


def write(path,value):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(path)


def read(path):return json.loads(Path(path).read_text())

def hash_file(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(work,runtime,model,readiness):
    work=Path(work).resolve();runtime=Path(runtime).resolve()
    if not work.is_relative_to(ROOT/'_workspace') or not runtime.is_relative_to(ROOT):raise ValueError('Invalid campaign paths')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(DEADLINE):raise RuntimeError('Research deadline expired')
    config=read(model);available=read(readiness)
    endpoints=available.get('data',{}).get('data',{}).get('endpoints',[])
    matches=[e for e in endpoints if e.get('tag')==config['provider']]
    if available.get('model')!=config['model'] or len(matches)!=1:raise ValueError('Provider readiness mismatch')
    endpoint=matches[0]
    for key in ('prompt','completion'):
        if Decimal(endpoint['pricing'][key])!=Decimal(config[key+'_price']):raise ValueError('Price changed')
    if not {'tools','tool_choice','temperature','max_tokens','seed'}.issubset(endpoint['supported_parameters']):raise ValueError('Required model parameter missing')
    config['checked_at']=available['checked_at']
    config.update(max_tokens=2048,temperature=0,reasoning_effort='low')
    paths=sorted(runtime.glob('case-*'))
    if len(paths)!=12:raise ValueError('Expected twelve runtime cases')
    for path in paths:Views(path)  # Validate runtime only; never read evaluator labels.
    work.mkdir(parents=True,exist_ok=False)
    random.Random(20261111).shuffle(paths)
    permutations=list(itertools.permutations(('self','python','shacl')))
    plan=[{'case_id':p.name,'runtime':str(p.relative_to(ROOT)),'review_order':list(permutations[i%6]),
           'status':'not_attempted','max_calls':9,'planning':False} for i,p in enumerate(paths)]
    write(work/'plan.json',plan)
    write(work/'session.json',{'campaign_id':CAMPAIGN,'started_at':datetime.now(timezone.utc).isoformat(),
        'deadline':DEADLINE,'max_usd':'5.00','max_attempts':108,'status':'prepared_not_authorized',
        'prior_campaign':'_workspace/factory-lab-20261109; untouched separate ledger; prior authorization closed'})
    write(work/'model.json',config)
    files=list((ROOT/'apps/factory_lab').glob('*.py'))+list((ROOT/'experiments/factory_complexity').glob('*.py'))
    # Evaluator code is deliberately NOT a runtime input or gate-read file.
    files=[p for p in files if p.name not in ('evaluator.py','fixtures.py','scaling.py')]
    files += [ROOT/'scripts/factory_complexity_campaign.py',ROOT/'research/virtual-factory-llm-1/policy.json',
              work/'session.json',work/'model.json',work/'plan.json']
    files += [p for directory in paths for p in sorted(directory.glob('*.json'))]
    write(work/'execution-gate.json',{'approved':False,'reason':'Awaiting explicit new paid scope plus independent execution reviews',
        'files':{str(p.relative_to(ROOT)):hash_file(p) for p in files}})
    write(work/'readiness.json',available)
    return {'work':str(work),'cases':12,'planned_finals':36,'max_calls':108,'max_usd':'5.00','gate_open':False,
            'deadline':DEADLINE,'note':'Hard nonrefunded reservation cap may leave unattempted cases; not a quote or guarantee all cases fit.'}


def preflight(work):
    work=Path(work).resolve()
    if not work.is_relative_to(ROOT/'_workspace'):raise ValueError('Private campaign directory required')
    session=read(work/'session.json');approval=read(work/'approval.json');gate=read(work/'execution-gate.json')
    if session.get('campaign_id')!=CAMPAIGN or session['deadline']!=DEADLINE:raise RuntimeError('Campaign/deadline mismatch')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(DEADLINE):raise RuntimeError('Research deadline expired')
    if session['max_attempts']!=108 or Decimal(session['max_usd'])!=Decimal('5'):raise RuntimeError('Frozen scope mismatch')
    if approval.get('approved') is not True or approval.get('campaign_id')!=CAMPAIGN or approval.get('deadline')!=DEADLINE or approval.get('max_attempts')!=108 or Decimal(str(approval.get('max_usd','0')))!=Decimal('5') or not approval.get('human_message'):
        raise RuntimeError('Explicit new paid scope missing')
    if gate.get('approved') is not True or gate.get('approval_sha256')!=hash_file(work/'approval.json'):
        raise RuntimeError('Independent execution gate closed or unbound approval')
    for name,expected in gate['files'].items():
        if hash_file(ROOT/name)!=expected:raise RuntimeError('Frozen input changed: '+name)
    if (work/'progress.json').exists():raise RuntimeError('Prior launch exists; no automatic resume')
    store=Store(work/'state.sqlite')
    if store.budget()['attempts'] or store.runs():raise RuntimeError('Existing campaign ledger; no reset/replay')
    return session,read(work/'plan.json'),store


def run(work):
    work=Path(work).resolve()
    if not work.is_relative_to(ROOT/'_workspace'):raise ValueError('Private campaign directory required')
    with (work/'.launch.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Campaign launch already active') from None
        return _run_locked(work)


def _run_locked(work):
    work=Path(work).resolve();session,plan,store=preflight(work)
    progress=copy.deepcopy(plan);write(work/'progress.json',progress)
    result={'planned_cases':12,'planned_finals':36,'status':'running','new_campaign':str(work.relative_to(ROOT))}
    try:
        for slot in progress:
            if datetime.now(timezone.utc)>=datetime.fromisoformat(DEADLINE):
                result['stop_reason']='deadline';break
            if (work/'paid-stop.json').exists():result['stop_reason']='paid_stop';break
            if not read(work/'execution-gate.json').get('approved'):result['stop_reason']='gate_closed';break
            budget=store.budget()
            if budget['unresolved'] or budget['attempts']>=108 or Decimal(budget['reserved_nonrefunded_usd'])>=Decimal('5'):
                result['stop_reason']='budget_or_unresolved';break
            views=Views(ROOT/slot['runtime']);graph=RDFStudyTools(views)
            runner=Runner(store,graph,lambda s:Gateway(s,work_dir=work),snapshot_resolver=views.snapshot,
                          tool_catalog=CATALOG,source_notice=NOTICE,review_order=slot['review_order'])
            config={'question':views.manifest['question'],'snapshot':'factory-v3','review':'compare','planning':False}
            rid=store.create(config);slot.update(status='running',run_id=rid);write(work/'progress.json',progress)
            runner.cancel_flags[rid]=threading.Event();runner.lock.acquire();runner.execute(rid,config)
            saved=store.get(rid);slot['status']=saved['status'];write(work/'progress.json',progress)
            write(work/(slot['case_id']+'-events.json'),store.events(rid))
            if slot['status']!='completed':result['stop_reason']='episode_failed_no_retry';break
        result['status']='completed_scope' if all(s['status']=='completed' for s in progress) else 'partial_stopped'
    except BaseException as error:
        result.update(status='interrupted_or_failed',error_type=type(error).__name__)
        raise
    finally:
        result['budget']=store.budget();result['completed_cases']=sum(s['status']=='completed' for s in progress)
        result['not_attempted_cases']=sum(s['status']=='not_attempted' for s in progress)
        result['failed_cases']=sum(s['status']=='failed' for s in progress)
        result['unresolved_running_cases']=sum(s['status']=='running' for s in progress)
        events=[e for slot in progress if slot.get('run_id') for e in store.events(slot['run_id'])]
        result['drafts_generated']=sum(e['kind']=='draft' for e in events)
        result['finals_generated']=sum(e['kind']=='branch_final' for e in events)
        write(work/'result.json',result)
        gate=read(work/'execution-gate.json');gate.update(approved=False,reason='Launch ended; no automatic reopening')
        write(work/'execution-gate.json',gate)
    return result
