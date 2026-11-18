"""Closed-by-default catalog-size campaign, shared nonrefunded USD5 ceiling.

prepare/offline use no credentials or API. run needs a separately hash-bound approval
for exactly this manifest. No retry/resume, no runtime evaluator, no free-form queries.
"""
import fcntl
import json
import random
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from apps.factory_lab.store import Store, ROOT, dumps
from apps.factory_lab.llm import Gateway
from experiments.factory_complexity.tools import Views, RDFStudyTools
from .competing import CompetingTools
from .catalog_scale import packet, parse, checked_choices, RecordTools, input_kind
from .model_campaign import read, write, sha, private

DATA = ROOT / 'research/query-contracts-1/catalog-scale-001'
VIEWS = ROOT / 'research/factory-complexity-1/development-001/runtime/case-01'
CAMPAIGN = 'catalog-scale-1'
STUDY_LEDGER = ROOT / '_workspace/catalog-scale-20261116/study-state.sqlite'
STUDY_LOCK = ROOT / '_workspace/catalog-scale-20261116/study.launch.lock'


def prepare(work, split='evaluation', models=None):
    if split not in ('development', 'evaluation'):
        raise ValueError('Unknown split')
    work = private(work)
    work.mkdir(parents=True, exist_ok=False)
    models = models or read(ROOT / 'research/query-contracts-1/model-selection-001/models.json')[:1]
    if not 1 <= len(models) <= 2 or len({m['model'] for m in models}) != len(models):
        raise ValueError('One or two distinct models required')
    requests = read(DATA / 'runtime' / (split + '.json'))
    slots = []
    for i, model in enumerate(models):
        folder = work / f'model-{i}'
        folder.mkdir()
        # Candidate config is frozen for preparation, not a current availability claim.
        write(folder / 'model.json', model)
        for size in (6, 24, 72):
            contracts = read(DATA / 'runtime' / f'catalog-{size}.json')
            for request in requests:
                for arm in ('full_catalog', 'retrieved'):
                    prepared = packet(request, contracts, arm)
                    serialized = dumps({'messages': prepared['messages'], 'tools': []}).encode()
                    bound = len(serialized) + 4096 + 512 * len(prepared['messages'])
                    reserve = 2 * (Decimal(bound) * Decimal(model['prompt_price']) +
                                   Decimal(model['max_tokens']) * Decimal(model['completion_price']) +
                                   Decimal(model.get('request_price', '0')))
                    slots.append({'model': model['model'], 'model_folder': folder.name,
                                  'size': size, 'arm': arm, 'split': split,
                                  'request': request, 'packet': prepared,
                                  'input_bytes': len(serialized), 'reserve_bound_usd': str(reserve),
                                  'status': 'unattempted'})
    random.Random(20261116).shuffle(slots)
    total = sum((Decimal(s['reserve_bound_usd']) for s in slots), Decimal(0))
    write(work / 'plan.json', slots)
    write(work / 'session.json', {'campaign_id': CAMPAIGN, 'status': 'prepared',
                                 'max_attempts': len(slots), 'max_usd': '5.00',
                                 'deadline': None, 'split': split})
    files = [DATA / 'runtime' / (split + '.json'), *DATA.glob('runtime/catalog-*.json'),
             *VIEWS.glob('*.json'), *work.glob('*/model.json'), work / 'plan.json',
             ROOT / 'scripts/catalog_scale.py', ROOT / 'apps/factory_lab/llm.py',
             ROOT / 'apps/factory_lab/store.py', ROOT / 'apps/factory_lab/graph.py',
             ROOT / 'apps/factory_lab/rdf_graph.py', ROOT / 'apps/factory_lab/evidence.py',
             ROOT / 'experiments/factory_complexity/tools.py',
             *Path(ROOT / 'experiments/query_contracts').glob('*.py')]
    write(work / 'execution-gate.json', {'approved': False,
          'reason': 'Exact scope authorization, independent review and current prices required',
          'files': {str(p.relative_to(ROOT)): sha(p) for p in files}})
    preview = {'attempts': len(slots), 'usd_cap': '5.00', 'reserve_bound_usd': str(total),
               'fits_cap': total <= 5, 'context_fits': all(s['input_bytes'] <= 60000 for s in slots),
               'input_tokens': None, 'actual_cost': None,
               'pricing_status': 'saved candidate rates; revalidate before any launch',
               'reserve_is_not_expected_bill': True, 'split': split,
               'runtime_gold_access': False}
    write(work / 'cost-preview.json', preview)
    gate = read(work / 'execution-gate.json')
    gate['files'][str((work / 'cost-preview.json').relative_to(ROOT))] = sha(work / 'cost-preview.json')
    write(work / 'execution-gate.json', gate)
    return preview


def preflight(work):
    gate = read(work / 'execution-gate.json')
    if not gate.get('approved'):
        raise RuntimeError('Paid gate closed')
    session = read(work / 'session.json')
    approval = read(work / 'approval.json')
    scope = ('campaign_id', 'max_attempts', 'max_usd', 'deadline', 'split')
    if any(approval.get(k) != session.get(k) for k in scope) or not approval.get('human_message') or approval.get('approved') is not True:
        raise RuntimeError('Approval mismatch')
    if gate.get('approval_sha256') != sha(work / 'approval.json'):
        raise RuntimeError('Approval hash mismatch')
    if session['campaign_id'] != CAMPAIGN or session['status'] != 'authorized' or not 0 < Decimal(session['max_usd']) <= 5:
        raise RuntimeError('Invalid campaign scope')
    if session['max_attempts'] != len(read(work / 'plan.json')) or not 1 <= session['max_attempts'] <= 100:
        raise RuntimeError('Attempt scope mismatch')
    preview = read(work / 'cost-preview.json')
    if not preview['fits_cap'] or not preview['context_fits']:
        raise RuntimeError('Predeclared complete scope does not fit; do not truncate arms')
    start = datetime.fromisoformat(session['started_at'])
    end = datetime.fromisoformat(session['deadline'])
    if not timedelta(0) < end - start <= timedelta(hours=2) or not start <= datetime.now(timezone.utc) < end-timedelta(seconds=120):
        raise RuntimeError('Launch window invalid')
    for p, expected in gate['files'].items():
        if sha(ROOT / p) != expected:
            raise RuntimeError('Frozen runtime changed: ' + p)
    if (work / 'progress.json').exists():
        raise RuntimeError('No resume or retry')
    store = Store(STUDY_LEDGER)
    if store.budget()['attempts'] or store.runs():
        raise RuntimeError('Existing ledger')
    return session, gate, store


def execute_choices(request, decisions, contracts, original, records):
    """Identical per-task execution/error policy in A/B/C; no whole-plan advantage."""
    by_tool = {c['tool']: c for c in contracts}
    executions = []
    for task, decision in zip(request['tasks'], decisions):
        choice = decision['tool']
        item = {'id': task['id'], 'tool': choice, 'status': 'unselected'}
        executions.append(item)
        if choice is None:
            continue
        try:
            contract = by_tool[choice]
            binding = task['binding']
            if set(binding) != {'literal', 'kind'} or binding['kind'] != input_kind(contract):
                raise ValueError('incompatible_input_kind')
            if 'implementation' in contract:
                result = records.run(contract, binding)
            else:
                argument = next(iter(contract['input']))
                result = original.run('factory-v3', choice, {argument: binding['literal']})
            item.update(status='executed', result=result)
        except Exception as exc:
            item.update(status='failed', error=str(exc))
    return executions


def settled_calls(store, run_id):
    """Canonical ledger includes known billing on failed/truncated responses.

Failure event payloads intentionally lack usage in the shared gateway; event-only
aggregation would silently drop billed failures from per-condition measurements.
"""
    with store.db() as connection:
        rows = connection.execute('SELECT id,reserved,status,details FROM calls WHERE run_id=? ORDER BY at,id', (run_id,)).fetchall()
    return [dict(json.loads(row['details']), call_id=row['id'],
                 reserved_nonrefunded_usd=row['reserved'], status=row['status']) for row in rows]


def run(work):
    work = private(work)
    STUDY_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with STUDY_LOCK.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        session, gate, store = preflight(work)
        progress = {'status': 'running', 'slots': read(work / 'plan.json')}
        write(work / 'progress.json', progress)  # before graph setup
        records = None
        current = None
        try:
            views = Views(VIEWS)
            original = CompetingTools(RDFStudyTools(views))
            records = RecordTools(views.snapshot('factory-v3')[0])
            gateways = {}
            for slot in progress['slots']:
                if datetime.now(timezone.utc) + timedelta(seconds=120) >= datetime.fromisoformat(session['deadline']):
                    raise RuntimeError('Launch cutoff')
                current = slot
                slot['status'] = 'started'
                rid = store.create({k: slot[k] for k in ('model', 'size', 'arm', 'split')})
                slot['run_id'] = rid
                store.status(rid, 'running')
                write(work / 'progress.json', progress)
                folder = work / slot['model_folder']
                if folder.name not in gateways:
                    write(folder / 'session.json', session)
                    local = json.loads(json.dumps(gate))
                    local['files'][str((folder / 'session.json').relative_to(ROOT))] = sha(folder / 'session.json')
                    write(folder / 'execution-gate.json', local)
                    gateways[folder.name] = Gateway(store, work_dir=folder)
                started = time.monotonic()
                message = gateways[folder.name].call(rid, slot['packet']['messages'])
                slot['call_seconds'] = time.monotonic() - started
                slot['public_content'] = message.get('content')
                decisions = parse(slot['request'], slot['packet'], message)
                slot['decisions'] = decisions
                contracts = read(DATA / 'runtime' / f'catalog-{slot["size"]}.json')
                slot['raw_execution'] = execute_choices(slot['request'], decisions, contracts, original, records)
                if slot['arm'] == 'retrieved':
                    slot['checked_decisions'] = checked_choices(slot['request'], decisions, contracts)
                    slot['checked_execution'] = execute_choices(slot['request'], slot['checked_decisions'], contracts, original, records)
                # Provider-reported values retained separately from offline byte counts and reservations.
                slot['calls'] = settled_calls(store, rid)
                slot['status'] = 'completed'
                store.status(rid, 'completed')
                write(work / 'progress.json', progress)
                current = None
            progress['status'] = 'completed'
        except Exception as exc:
            progress.update(status='stopped', error=str(exc))
            if current is not None:
                current.update(status='failed', error=str(exc))
                if current.get('run_id'):
                    store.status(current['run_id'], 'failed')
                    current['calls'] = settled_calls(store, current['run_id'])
        finally:
            if records is not None:
                records.close()
            progress['budget'] = store.budget()
            write(work / 'progress.json', progress)
            for p in [work / 'execution-gate.json', *work.glob('*/execution-gate.json')]:
                g = read(p)
                g.update(approved=False, reason='Scope terminated; no retry/resume')
                write(p, g)
            session['status'] = progress['status']
            write(work / 'session.json', session)
        return progress
