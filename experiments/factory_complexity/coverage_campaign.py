"""One-launch four-case declaration follow-up; old campaign is never reopened."""
import fcntl
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
import threading
from apps.factory_lab.agent import Runner
from apps.factory_lab.llm import Gateway
from apps.factory_lab.store import ROOT, Store
from .campaign import read, write, hash_file
from .tools import Views, RDFStudyTools, CATALOG, NOTICE

COVERAGE_NOTICE=NOTICE.replace('The qualification reviewer checks retrieved replacement candidates only, not impact-list completeness or version changes.', 'The qualification reviewer checks explicitly declared order/machine pairs and replacement-query pairs using selected evidence only; it does not check impact-list completeness or version changes.')
ID='factory-coverage-live-1'
CASES=('case-04','case-05','case-11','case-12')

def prepare(work, readiness, model, human_message):
    work=Path(work).resolve()
    if not work.is_relative_to(ROOT/'_workspace'):raise ValueError('Private work required')
    if not human_message.strip():raise ValueError('Execution instruction required')
    available=read(readiness)
    config=read(model)
    endpoints=available['data']['data']['endpoints']
    matches=[e for e in endpoints if e.get('tag')==config['provider']]
    if available['model']!=config['model'] or len(matches)!=1:raise ValueError('Model/provider mismatch')
    e=matches[0]
    if any(Decimal(e['pricing'][k])!=Decimal(config[k+'_price']) for k in ('prompt','completion')):raise ValueError('Price changed')
    if not {'tools','tool_choice','temperature','max_tokens','seed'}.issubset(e['supported_parameters']):raise ValueError('Parameter support changed')
    now=datetime.now(timezone.utc);deadline=(now+timedelta(hours=1)).isoformat()
    config['checked_at']=available['checked_at']
    work.mkdir(parents=True,exist_ok=False)
    plan=[]
    orders=[('self','python','shacl'),('python','shacl','self'),('shacl','self','python'),('self','shacl','python')]
    for cid,order in zip(CASES,orders):
        path=ROOT/'research/factory-complexity-1/development-001/runtime'/cid
        Views(path)
        plan.append({'case_id':cid,'runtime':str(path.relative_to(ROOT)),'review_order':list(order),'status':'not_attempted'})
    write(work/'plan.json',plan)
    write(work/'model.json',config)
    write(work/'session.json',{'campaign_id':ID,'started_at':now.isoformat(),'deadline':deadline,'max_usd':'2.00','max_attempts':36,
        'scope':'Four previously zero-target consumed development cases, new draft and three review branches, model declarations only, no retries'})
    write(work/'approval.json',{'execution_requested':True,'human_message':human_message,'recorded_at':now.isoformat(),
        'operator_limits':{'max_attempts':36,'max_usd':'2.00','deadline':deadline},
        'authorization_note':'Latest explicit actual-LLM execution instruction; ceilings are conservative operator limits, not verbatim numeric human approval. Prior campaign remains closed.'})
    write(work/'readiness.json',available)
    files=list((ROOT/'apps/factory_lab').glob('*.py'))+[ROOT/'experiments/factory_complexity'/n for n in ('coverage_campaign.py','campaign.py','tools.py')]
    files += [ROOT/'research/virtual-factory-llm-1/policy.json']
    files += [work/n for n in ('plan.json','model.json','session.json','approval.json','readiness.json')]
    files += [p for slot in plan for p in (ROOT/slot['runtime']).glob('*.json')]
    write(work/'execution-gate.json',{'approved':False,'files':{str(p.relative_to(ROOT)):hash_file(p) for p in files}})
    return read(work/'session.json')

def preflight(work):
    work=Path(work).resolve()
    if not work.is_relative_to(ROOT/'_workspace'):raise ValueError('Private work required')
    s=read(work/'session.json');a=read(work/'approval.json');g=read(work/'execution-gate.json');plan=read(work/'plan.json')
    if s['campaign_id']!=ID or s['max_attempts']!=36 or Decimal(s['max_usd'])!=2:raise ValueError('Scope mismatch')
    if not a.get('execution_requested') or not a.get('human_message') or a['operator_limits']!={k:s[k] for k in ('deadline','max_attempts','max_usd')}:raise ValueError('Instruction/limits mismatch')
    if [p['case_id'] for p in plan]!=list(CASES):raise ValueError('Case denominator changed')
    if not g.get('approved'):raise RuntimeError('Independent review gate closed')
    for n,h in g['files'].items():
        if hash_file(ROOT/n)!=h:raise RuntimeError('Frozen file changed: '+n)
    if datetime.now(timezone.utc)+timedelta(seconds=120)>=datetime.fromisoformat(s['deadline']):raise RuntimeError('Launch cutoff')
    if (work/'progress.json').exists() or (work/'paid-stop.json').exists():raise RuntimeError('Prior launch/stop; no automatic retry')
    store=Store(work/'state.sqlite')
    if store.budget()['attempts'] or store.runs():raise RuntimeError('Existing ledger; no reset')
    return s,plan,store

def run(work):
    work=Path(work).resolve()
    if not work.is_relative_to(ROOT/'_workspace'):raise ValueError('Private work required')
    with (work/'.launch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        s,plan,store=preflight(work);write(work/'progress.json',plan)
        result={'planned_cases':4,'planned_drafts':4,'planned_finals':12,'status':'running'}
        class BoundedGateway(Gateway):
            def call(self,*args,**kw):
                if datetime.now(timezone.utc)+timedelta(seconds=120)>=datetime.fromisoformat(s['deadline']):raise RuntimeError('Response/cleanup cutoff')
                return super().call(*args,**kw)
        try:
            for slot in plan:
                if store.budget()['unresolved'] or (work/'paid-stop.json').exists():break
                views=Views(ROOT/slot['runtime'])
                runner=Runner(store,RDFStudyTools(views),lambda st:BoundedGateway(st,work_dir=work),
                    snapshot_resolver=views.snapshot,tool_catalog=CATALOG,source_notice=COVERAGE_NOTICE,
                    review_order=slot['review_order'],coverage_review=True)
                config={'question':views.manifest['question'],'snapshot':'factory-v3','review':'compare','planning':False}
                rid=store.create(config);slot.update(run_id=rid,status='running');write(work/'progress.json',plan)
                runner.cancel_flags[rid]=threading.Event();runner.lock.acquire();runner.execute(rid,config)
                slot['status']=store.get(rid)['status'];write(work/'progress.json',plan)
                write(work/(slot['case_id']+'-events.json'),store.events(rid))
                if slot['status']!='completed':break
            result['status']='completed_scope' if all(p['status']=='completed' for p in plan) else 'partial_stopped'
        finally:
            result.update(budget=store.budget(),slots=plan)
            write(work/'result.json',result)
            g=read(work/'execution-gate.json');g.update(approved=False,reason='Launch ended; no automatic reopening');write(work/'execution-gate.json',g)
        return result
