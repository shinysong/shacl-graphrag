"""Prepare a CLOSED two-model campaign. Approval and native review are mandatory.

One shared nonrefunded Store across both model folders. No automatic authorization,
retries, resume, price fallback, evaluator reads or final-business-answer generation.
"""
import fcntl
import hashlib
import json
import random
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from pathlib import Path
from apps.factory_lab.store import Store,ROOT,dumps
from apps.factory_lab.llm import Gateway
from experiments.factory_complexity.tools import Views,RDFStudyTools
from .competing import CompetingTools
from .core import execute,validate_plan
from .model_selection import packet,parse,plans

DATA=ROOT/'research/query-contracts-1/model-selection-001'
CATALOG=ROOT/'research/query-contracts-1/selection-development-001/catalog.json'
VIEWS=ROOT/'research/factory-complexity-1/development-001/runtime/case-01'
ID='query-model-selection-1'


def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,value):
    p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
def private(work):
    work=Path(work).resolve()
    if not work.is_relative_to(ROOT/'_workspace'):raise ValueError('Private directory required')
    return work


def prepare(work):
    work=private(work);work.mkdir(parents=True,exist_ok=False)
    requests=read(DATA/'requests.json');catalog=read(CATALOG)['catalog'];models=read(DATA/'models.json')
    if len(requests)!=6 or len(models)!=2:raise ValueError('Unexpected scope')
    slots=[];total=Decimal(0)
    for model in models:
        folder=work/model['model'].split('/')[-1];folder.mkdir();write(folder/'model.json',model)
        for index,request in enumerate(requests):
            for repeat in range(2 if index<2 else 1):
                for arm in ('full_catalog','retrieved'):
                    prepared=packet(request,catalog,arm)
                    serialized=dumps({'messages':prepared['messages'],'tools':[]}).encode()
                    if len(serialized)>60000:raise ValueError('Context cap')
                    bound=len(serialized)+4096+512*len(prepared['messages'])
                    reserve=2*(Decimal(bound)*Decimal(model['prompt_price'])+Decimal(model['max_tokens'])*Decimal(model['completion_price']))
                    total+=reserve
                    slots.append({'model':model['model'],'model_folder':folder.name,'request_id':request['id'],'repeat':repeat,'arm':arm,'request':request,'packet':prepared,'reserved_usd_bound':str(reserve),'context_bytes':len(serialized),'status':'unattempted'})
    random.Random(20261113).shuffle(slots)
    if len(slots)!=32:raise ValueError('Unexpected attempt count')
    write(work/'plan.json',slots)
    write(work/'session.json',{'campaign_id':ID,'status':'prepared_not_authorized','max_attempts':32,'max_usd':'5.00','deadline':None,'max_duration_seconds':7200})
    files=[DATA/'requests.json',DATA/'models.json',CATALOG,*VIEWS.glob('*.json'),*Path(ROOT/'experiments/query_contracts').glob('*.py'),ROOT/'experiments/factory_complexity/tools.py',ROOT/'apps/factory_lab/llm.py',ROOT/'apps/factory_lab/store.py',ROOT/'apps/factory_lab/evidence.py',ROOT/'apps/factory_lab/graph.py',ROOT/'apps/factory_lab/rdf_graph.py',work/'plan.json']
    files += [ROOT/'scripts/query_model_campaign.py'] + list(work.glob('*/model.json'))
    write(work/'execution-gate.json',{'approved':False,'reason':'New bounded human budget and independent native reviews required','files':{str(p.relative_to(ROOT)):sha(p) for p in files}})
    write(work/'cost-plan.json',{'calls':32,'derived_conditions':48,'models':models,'all_call_reservations_usd':str(total),'requested_cap_usd':'5.00','method':'Twice full UTF8 request bytes plus4096+512/message, plus2048maxoutput; not actual model tokenizer or expected invoice','will_fit_reservation_cap':total<=5,'note':'Provider-reported actual cost and input/output usage retained. All failures count. Third condition reuses retrieved selection, not independent model calls.'})
    return read(work/'cost-plan.json')


def preflight(work):
    work=private(work);session=read(work/'session.json');gate=read(work/'execution-gate.json')
    if not gate.get('approved'):raise RuntimeError('Independent paid gate closed')
    approval=read(work/'approval.json')
    if gate.get('approval_sha256')!=sha(work/'approval.json'):raise RuntimeError('Unbound approval')
    if session.get('campaign_id')!=ID or session.get('status')!='authorized' or session.get('max_attempts')!=32 or Decimal(session.get('max_usd','0'))!=5:raise RuntimeError('Invalid scope')
    for key in ('campaign_id','max_attempts','max_usd','deadline'):
        if approval.get(key)!=session.get(key):raise RuntimeError('Approval scope mismatch')
    if approval.get('approved') is not True or not approval.get('human_message'):raise RuntimeError('Explicit budget approval missing')
    start=datetime.fromisoformat(session['started_at']);end=datetime.fromisoformat(session['deadline']);now=datetime.now(timezone.utc)
    if not start<=now<end-timedelta(seconds=120) or not timedelta(0)<end-start<=timedelta(hours=2):raise RuntimeError('Launch window invalid')
    for path,expected in gate['files'].items():
        if sha(ROOT/path)!=expected:raise RuntimeError('Frozen input changed: '+path)
    if (work/'progress.json').exists():raise RuntimeError('No automatic resume')
    store=Store(work/'state.sqlite')
    if store.budget()['attempts'] or store.runs():raise RuntimeError('Existing ledger')
    return session,gate,store


def run(work):
    work=private(work)
    with (work/'.launch.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Duplicate campaign launch') from None
        session,gate,store=preflight(work);slots=read(work/'plan.json')
        progress={'status':'running','slots':slots};write(work/'progress.json',progress)
        current=None
        try:
            tools=CompetingTools(RDFStudyTools(Views(VIEWS)))
            gateways={}
            for slot in slots:
                if datetime.now(timezone.utc)+timedelta(seconds=120)>=datetime.fromisoformat(session['deadline']):raise RuntimeError('Launch cutoff')
                folder=work/slot['model_folder']
                if folder.name not in gateways:
                    write(folder/'session.json',session)
                    localgate=dict(gate,files=dict(gate['files']))
                    localgate['files'][str((folder/'session.json').relative_to(ROOT))]=sha(folder/'session.json')
                    write(folder/'execution-gate.json',localgate)
                    gateways[folder.name]=Gateway(store,work_dir=folder)
                current=slot;slot['status']='started';write(work/'progress.json',progress)
                rid=store.create({'request':slot['request_id'],'model':slot['model'],'arm':slot['arm'],'repeat':slot['repeat']});slot['run_id']=rid
                message=gateways[folder.name].call(rid,slot['packet']['messages'])
                slot['message']={'content':message.get('content')} # never export hidden reasoning
                choices=parse(slot['request'],slot['packet'],message);slot['decisions']=choices
                proposed=plans(slot['request'],choices);slot['plans']=proposed;slot['executions']={}
                for condition in ('raw','checked') if slot['arm']=='retrieved' else ('raw',):
                    try:
                        validate_plan(proposed[condition]);out=execute(proposed[condition],tools,max_calls=12)
                        out['plan_origin']='model_selection_on_supplied_decomposition'
                        slot['executions'][condition]={'status':'executed','result':out}
                    except Exception as exc:slot['executions'][condition]={'status':'invalid_or_failed','error':str(exc)}
                slot['status']='completed';store.status(rid,'completed');write(work/'progress.json',progress);current=None
            progress['status']='completed'
        except Exception as exc:
            progress['status']='stopped';progress['error']=str(exc)
            if current is not None:current['status']='failed';current['error']=str(exc)
        finally:
            progress['budget']=store.budget();write(work/'progress.json',progress)
            gate['approved']=False;gate['reason']='Campaign terminated; no automatic retry/resume';write(work/'execution-gate.json',gate)
            for folder in work.iterdir():
                if folder.is_dir() and (folder/'execution-gate.json').exists():
                    local=read(folder/'execution-gate.json');local['approved']=False;write(folder/'execution-gate.json',local)
        return progress
