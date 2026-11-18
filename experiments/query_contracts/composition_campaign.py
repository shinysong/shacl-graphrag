"""One bounded full compound-query comparison, never a selector-only substitute."""
import fcntl
import copy
import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from apps.factory_lab.store import ROOT, Store, dumps
from apps.factory_lab.llm import Gateway
from experiments.factory_complexity.tools import Views, RDFStudyTools
from .competing import CompetingTools
from .composition import (decomposition_messages, parse_decomposition, planning_packet,
                          parse_plan, checked_plan, execute_plan, report, final_messages, parse_answer)
from .model_campaign import read,write,sha,private
from .scale_campaign import settled_calls

DATA=ROOT/'research/query-contracts-1/composition-001'
CATALOG=ROOT/'research/query-contracts-1/selection-development-001/catalog.json'
VIEWS=ROOT/'research/factory-complexity-1/development-001/runtime/case-01'
LEDGER=ROOT/'_workspace/catalog-scale-20261116/study-state.sqlite'  # same unspent USD5 authorization
LOCK=ROOT/'_workspace/catalog-scale-20261116/study.launch.lock'
CAMPAIGN='query-composition-1'
CAPS={'decompose':8000,'plan':20000,'final':30000}


def schema(views):
    view,digest=views.snapshot('factory-v3')
    return {'snapshot':'factory-v3','source_sha256':digest,'as_of':view['as_of'],
            'entities':[{'id':n['id'],'kind':n['kind'],'name':n.get('name')} for n in view['nodes']],
            'notice':'Identifier registry only; relationships and qualification contents require fixed queries.'}


def prepare(work, model_file):
    work=private(work);work.mkdir(parents=True,exist_ok=False)
    cfg=read(model_file);write(work/'model.json',cfg)
    questions=read(DATA/'runtime/questions.json')
    if len(questions)!=4 or any(set(q)!={'id','question'} for q in questions):raise ValueError('Raw questions only')
    random.Random(20261116).shuffle(questions)
    write(work/'questions.json',questions)
    total=Decimal(0)
    for stage,count in [('decompose',4),('plan',8),('final',12)]:
        total+=count*2*(Decimal(CAPS[stage]+5120)*Decimal(cfg['prompt_price'])+Decimal(cfg['max_tokens'])*Decimal(cfg['completion_price'])+Decimal(cfg.get('request_price','0')))
    preview={'max_attempts':24,'max_usd':'5.00','worst_case_reservation_usd':str(total),
             'fits_cap':total<=5,'byte_caps':CAPS,'not_expected_invoice_or_tokenizer':True,
             'model':cfg['model'],'stages':'4 common decompositions,8 model DAG plans,12 final answers',
             'scope':'4 authored compound requests,3 arms; C reuses B plan, final calls independent conditional on shared trace'}
    write(work/'cost-preview.json',preview)
    write(work/'session.json',{'campaign_id':CAMPAIGN,'status':'prepared','max_attempts':24,'max_usd':'5.00','deadline':None})
    files=[DATA/'runtime/questions.json',CATALOG,*VIEWS.glob('*.json'),work/'questions.json',work/'model.json',work/'cost-preview.json',
           ROOT/'scripts/query_composition.py',ROOT/'apps/factory_lab/llm.py',ROOT/'apps/factory_lab/store.py',
           ROOT/'apps/factory_lab/graph.py',ROOT/'apps/factory_lab/rdf_graph.py',ROOT/'experiments/factory_complexity/tools.py',
           *Path(ROOT/'experiments/query_contracts').glob('*.py')]
    write(work/'execution-gate.json',{'approved':False,'files':{str(p.relative_to(ROOT)):sha(p) for p in files},
                                     'reason':'Independent reviews and checks before activation'})
    return preview


def prepare_format_recovery(parent, work):
    parent=private(parent);work=private(work)
    old=read(parent/'progress.json');oldsession=read(parent/'session.json')
    first=old['cases'][0]
    if old['status']!='stopped' or len(first['stages'])!=2 or first['stages'][1]['stage']!='plan' or first['stages'][1]['status']!='failed' or len(first.get('arms',{})):
        raise RuntimeError('Not the inspected two-stage format failure')
    parsed=parse_plan({'content':first['stages'][1]['public_content']},first['requirements'])
    # Reconstructed planning prompt must equal the original paid request byte-for-byte.
    views=Views(VIEWS);contracts=read(CATALOG)['catalog'];arm=first['stages'][1]['arm']
    packet=planning_packet(first['question'],first['requirements'],schema(views),contracts,arm)
    call_id=first['stages'][1]['calls'][0]['call_id'];rawrequest=parent/'calls'/(call_id+'-request.json')
    if read(rawrequest)['messages']!=packet['messages']:raise RuntimeError('Recovery would change paid input')
    preview=prepare(work,parent/'model.json')
    write(work/'questions.json',read(parent/'questions.json'))
    session=read(work/'session.json');session.update(started_at=oldsession['started_at'],deadline=oldsession['deadline'])
    write(work/'session.json',session)
    recovery={'parent_progress':str((parent/'progress.json').relative_to(ROOT)),
              'parent_progress_sha256':sha(parent/'progress.json'),
              'original_run_ids':[s['run_id'] for s in first['stages']],
              'original_attempts':2,'deadline':oldsession['deadline'],'recovered_plan':parsed,'packet':packet,
              'reason':'Manual format-envelope recovery, no source/model-content repair or new retry calls'}
    write(work/'recovery.json',recovery)
    gate=read(work/'execution-gate.json');gate['files'][str((work/'questions.json').relative_to(ROOT))]=sha(work/'questions.json')
    for q in (parent/'progress.json',rawrequest,work/'recovery.json'):
        gate['files'][str(q.relative_to(ROOT))]=sha(q)
    write(work/'execution-gate.json',gate)
    return preview


def preflight(work):
    g=read(work/'execution-gate.json');s=read(work/'session.json')
    if not g.get('approved'):raise RuntimeError('Paid gate closed')
    a=read(work/'approval.json')
    if g.get('approval_sha256')!=sha(work/'approval.json') or not a.get('human_message') or a.get('approved') is not True:
        raise RuntimeError('Approval unbound')
    for k in ('campaign_id','max_attempts','max_usd','deadline'):
        if a.get(k)!=s.get(k):raise RuntimeError('Approval scope mismatch')
    if s['campaign_id']!=CAMPAIGN or s['status']!='authorized' or s['max_attempts']!=24 or Decimal(s['max_usd'])!=5:
        raise RuntimeError('Invalid scope')
    if not read(work/'cost-preview.json')['fits_cap']:raise RuntimeError('Whole comparison does not fit')
    start=datetime.fromisoformat(s['started_at']);end=datetime.fromisoformat(s['deadline']);now=datetime.now(timezone.utc)
    if not timedelta(0)<end-start<=timedelta(hours=2) or not start<=now<end-timedelta(seconds=120):raise RuntimeError('Launch window invalid')
    for p,h in g['files'].items():
        if sha(ROOT/p)!=h:raise RuntimeError('Frozen file changed: '+p)
    if (work/'progress.json').exists():raise RuntimeError('No resume/retry')
    store=Store(LEDGER)
    if (work/'recovery.json').exists():
        recovery=read(work/'recovery.json')
        if store.budget()['attempts']!=2 or store.budget()['unresolved'] or {r['id'] for r in store.runs()}!=set(recovery['original_run_ids']) or s['deadline']!=recovery['deadline']:
            raise RuntimeError('Recovery ledger/window mismatch')
    elif store.budget()['attempts'] or store.runs():raise RuntimeError('Existing shared USD5 ledger')
    return s,g,store


def run(work):
    work=private(work);LOCK.parent.mkdir(parents=True,exist_ok=True)
    with LOCK.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        session,gate,store=preflight(work)
        progress={'status':'running','cases':[dict(q,status='unattempted',stages=[],arms={}) for q in read(work/'questions.json')]}
        if (work/'recovery.json').exists():
            recovery=read(work/'recovery.json');parent=read(ROOT/recovery['parent_progress'])
            progress=copy.deepcopy(parent);progress.update(status='running',original_failure=recovery)
            progress.pop('error',None);progress.pop('budget',None)
            first=progress['cases'][0];first['status']='unattempted'
            oldstage=first['stages'][1];oldstage.update(original_status='failed',status='reused_format_normalized')
            first['arms'][oldstage['arm']]={'packet':recovery['packet'],'raw_plan':recovery['recovered_plan']}
        write(work/'progress.json',progress);current=None;stage_record=None
        try:
            views=Views(VIEWS);tools=CompetingTools(RDFStudyTools(views));shared_schema=schema(views)
            contracts=read(CATALOG)['catalog'];gateway=Gateway(store,work_dir=work)
            def call(case,stage,arm,messages):
                nonlocal stage_record
                if datetime.now(timezone.utc)+timedelta(seconds=120)>=datetime.fromisoformat(session['deadline']):raise RuntimeError('Launch cutoff')
                n=len(dumps({'messages':messages,'tools':[]}).encode())
                if n>CAPS[stage]:raise RuntimeError('Predeclared '+stage+' byte cap exceeded')
                rid=store.create({'case':case['id'],'stage':stage,'arm':arm})
                store.status(rid,'running')
                stage_record={'stage':stage,'arm':arm,'run_id':rid,'input_bytes':n,'status':'started'}
                case['stages'].append(stage_record);write(work/'progress.json',progress)
                message=gateway.call(rid,messages)
                stage_record['public_content']=message.get('content')
                stage_record['calls']=settled_calls(store,rid)
                # Parsing is done immediately by the caller; malformed model output is retained.
                return message
            def finish():
                nonlocal stage_record
                stage_record['status']='completed';store.status(stage_record['run_id'],'completed');stage_record=None
                write(work/'progress.json',progress)
            for case in progress['cases']:
                current=case;case['status']='running';write(work/'progress.json',progress)
                if 'requirements' not in case:
                    message=call(case,'decompose','shared',decomposition_messages(case['question'],shared_schema))
                    requirements=parse_decomposition(message);case['requirements']=requirements;finish()
                else:requirements=case['requirements']
                arm_order=['full','retrieved'];random.Random(20261116+int(case['id'][-1])).shuffle(arm_order)
                for arm in arm_order:
                    if arm in case['arms'] and 'raw_plan' in case['arms'][arm]:continue
                    packet=planning_packet(case['question'],requirements,shared_schema,contracts,arm)
                    message=call(case,'plan',arm,packet['messages']);plan=parse_plan(message,requirements)
                    case['arms'][arm]={'packet':packet,'raw_plan':plan};finish()
                b=case['arms']['retrieved'];c_plan,rejected=checked_plan(b['raw_plan'],b['packet']['visible_tools'])
                case['arms']['checked']={'packet':b['packet'],'raw_plan':b['raw_plan'],'plan':c_plan,'rejections':rejected}
                for arm,entry in case['arms'].items():
                    plan=entry.get('plan',entry['raw_plan']);entry['execution']=execute_plan(plan,tools,entry['packet']['visible_tools'])
                    if arm=='checked':entry['review']=report(plan,entry['execution'],entry['rejections'])
                # All plans/executions frozen before finalization; no final answer feeds another arm.
                final_order=['full','retrieved','checked'];random.Random(20261117+int(case['id'][-1])).shuffle(final_order)
                for arm in final_order:
                    entry=case['arms'][arm];plan=entry.get('plan',entry['raw_plan'])
                    messages=final_messages(case['question'],requirements,plan,entry['execution'],entry['packet']['catalog'],shared_schema,entry.get('review'))
                    message=call(case,'final',arm,messages)
                    entry['answer']=parse_answer(message,requirements,entry['execution']);finish()
                case['status']='completed';write(work/'progress.json',progress);current=None
            progress['status']='completed'
        except Exception as exc:
            progress.update(status='stopped',error=str(exc))
            if current is not None:current['status']='failed'
            if stage_record is not None:
                stage_record.update(status='failed',error=str(exc));store.status(stage_record['run_id'],'failed')
                stage_record['calls']=settled_calls(store,stage_record['run_id'])
        finally:
            progress['budget']=store.budget();write(work/'progress.json',progress)
            gate.update(approved=False,reason='Terminated; no automatic retry/resume');write(work/'execution-gate.json',gate)
            session['status']=progress['status'];write(work/'session.json',session)
        return progress
