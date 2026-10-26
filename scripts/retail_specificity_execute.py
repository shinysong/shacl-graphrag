"""Audit frozen specificity inputs; execute unchanged artifacts and score saved outputs."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from scripts.retail_specificity_inputs import ROOT, BASE
from scripts.retail_direct_pilot import write_new
from scripts.retail_python_runner import execute
from scripts.retail_python_intake import inspect_python
from scripts.retail_io import parse_output

MAP = {'task_1': 'customer_analysis', 'task_2': 'quantity_sign', 'task_3': 'nonnegative_price'}


def verify(path):
    for name, sha in json.loads(path.read_text()).items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == sha, name


def audit():
    from scripts.nl2shacl_multimodel import Runner
    verify(BASE/'freeze.json')
    old = json.loads((ROOT/'generated-python-v1/freeze.json').read_text())
    source = ROOT/'generated-python-v1/packets.json'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == old[str(source)]
    config = json.loads((BASE/'config.json').read_text())
    inputs = json.loads((BASE/'inputs.json').read_text())
    assert not (BASE/'campaign-budget.json').exists()
    current_ledgers = {str(p.resolve()) for p in Path('_workspace').rglob('campaign-budget.json')}
    assert current_ledgers == set(config['external_ledgers'])
    prior = []
    for name, sha in config['predecessor_ledgers'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == sha
        prior.extend(json.loads(Path(name).read_text())['reservations'])
    assert len(prior) == 80 and all(r['status'] == 'completed' and r['reported_usd'] is not None for r in prior)
    consumed = {(r['model'], r['id'], r['language']) for r in prior}
    assert len(consumed) == 80 and not consumed.intersection((r['model'], r['id'], r['language']) for r in inputs)
    runner = Runner(config, inputs, BASE/'calls', None)
    upper = sum(Decimal(str(runner.request(row)[1])) for row in inputs)
    reserved = sum(Decimal(str(r['upper_usd'])) for r in prior)
    reported = sum(Decimal(str(r['reported_usd'])) for r in prior)
    now = datetime.now(timezone.utc)
    daily = sum(datetime.fromisoformat(r['at'].replace('Z','+00:00')).date() == now.date()
                for name in current_ledgers for r in json.loads(Path(name).read_text())['reservations'])
    assert now < datetime.fromisoformat(config['deadline_utc'])
    assert daily + 2 <= config['daily_cap'] and len(prior)+2 <= config['max_calls']
    assert reserved+upper <= Decimal(str(config['max_usd'])) and reported+upper <= Decimal(str(config['max_reported_usd']))
    paths = [Path(__file__), Path('scripts/retail_python_runner.py'), Path('scripts/retail_python_intake.py'),
             Path('scripts/retail_io.py'), Path('scripts/score_retail_decisions.py'),
             Path('scripts/nl2shacl_multimodel.py'), ROOT/'references.json', ROOT/'boundary-v1/references.json',
             ROOT/'boundary-v1/cases.json', ROOT/'container-smoke-v1/runtime-hashes.json', ROOT/'container-smoke-v1/observed.json']
    write_new(BASE/'execution-freeze.json', {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    out = {'prior_calls':80,'planned_calls':2,'historical_daily_calls':daily,'prior_reported_usd':str(reported),
           'prior_reserved_usd':str(reserved),'new_upper_usd':str(upper),'external_ledgers':len(current_ledgers)}
    write_new(BASE/'audit.json', out)
    print(json.dumps(out))


def generation_plan(inputs, ledger):
    planned = {r['id'] for r in inputs}
    assert len(planned) == len(inputs)
    assert len({r['id'] for r in ledger}) == len(ledger)
    assert {r['id'] for r in ledger} <= planned
    return {r['id']: next(((i, x) for i, x in enumerate(ledger) if x['id'] == r['id']),
                         (None, {'status': 'not_attempted'})) for r in inputs}


def cost_summary(ledger):
    unresolved = sum(r.get('reported_usd') is None for r in ledger)
    known = sum((Decimal(str(r['reported_usd'])) for r in ledger if r.get('reported_usd') is not None), Decimal(0))
    return {'reported_usd': float(known) if not unresolved else None,
            'known_reported_usd': str(known), 'unresolved_cost_count': unresolved,
            'reserved_usd': float(sum((Decimal(str(r['upper_usd'])) for r in ledger), Decimal(0)))}


def may_execute(status, now, deadline):
    return status == 'completed' and now < deadline


def evaluate():
    from scripts.score_retail_decisions import score
    verify(BASE/'freeze.json'); verify(BASE/'execution-freeze.json')
    deadline = datetime.fromisoformat(json.loads((BASE/'config.json').read_text())['deadline_utc'])
    ledger = json.loads((BASE/'campaign-budget.json').read_text())['reservations'] if (BASE/'campaign-budget.json').exists() else []
    inputs = json.loads((BASE/'inputs.json').read_text())
    plan = generation_plan(inputs, ledger)
    packets = json.loads((BASE/'packets.json').read_text())
    predictions = {}; details = []
    for arm in ('underspecified', 'explicit'):
        i,r = plan['policy-specificity-v1-'+arm]
        predictions[arm] = {}
        for batch, packet in packets.items():
            keys = [(row['row_id'], p) for row in packet['rows'] for p in MAP]
            pp = [{'row_id': a, 'policy': b, 'status': 'error'} for a,b in keys]
            detail = {'arm':arm,'batch':batch,'generation_status':r['status']}
            detail['execution_eligible'] = may_execute(r['status'], datetime.now(timezone.utc), deadline)
            if r['status'] == 'completed' and not detail['execution_eligible']:
                detail['execution_not_started'] = 'deadline'
            if detail['execution_eligible']:
                raw = (BASE/'calls'/f'call-{i:04d}'/'output.ttl').read_bytes()
                parsed = inspect_python(raw); detail['intake'] = parsed
                if parsed['status'] == 'syntax_valid_pending_execution_review':
                    dest = BASE/'executions'/f'{arm}-{batch}'
                    result = execute(raw, packet, dest); detail['execution'] = result
                    if not result['container_absent']:
                        write_new(BASE/'unresolved-cleanup.json',detail)
                        raise RuntimeError('Unresolved cleanup')
                    if result['status'] == 'completed':
                        output = parse_output((dest/'stdout.bin').read_bytes().decode('utf-8',errors='replace'),keys)
                        detail['response_parse'] = output; pp = output['predictions']
            # Task-name translation only, after unmodified raw decisions were saved; never change status.
            predictions[arm][batch] = [dict(p,policy=MAP[p['policy']]) for p in pp]
            details.append(detail)
    refs = {'random_development':json.loads((ROOT/'references.json').read_text()),
            'boundary_diagnostic':json.loads((ROOT/'boundary-v1/references.json').read_text())}
    origins = {c['row_id']:c['origin'] for c in json.loads((ROOT/'boundary-v1/cases.json').read_text())}
    metrics = {}
    for arm, batches in predictions.items():
        metrics[arm] = {'random_development':score(refs['random_development'],batches['random_development'])}
        for origin in sorted(set(origins.values())):
            metrics[arm][origin] = score([r for r in refs['boundary_diagnostic'] if origins[r['row_id']] == origin],
                                        [p for p in batches['boundary_diagnostic'] if origins[p['row_id']] == origin])
    result = {'metrics':metrics,'predictions':predictions,'details':details,
              **cost_summary(ledger),
              'limitations':['Contract agreement not external business accuracy',
                             'One artifact per arm: treatment difference not separable from generation variation',
                             'Same source semantics and parsing in both arms; explicit operational definitions only treatment',
                             'Consumed development72, selected actual6, authored36 decisions kept separate',
                             'Prior reusable failure unchanged; no matched historical or RDF superiority claim']}
    write_new(BASE/'result.json',result)
    write_new(Path('docs/experiments/records/20261020-retail-policy-specificity.json'),result)
    print(json.dumps({'metrics':metrics,'reported_usd':result['reported_usd'],'reserved_usd':result['reserved_usd'],'unresolved_cost_count':result['unresolved_cost_count']}))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['audit','evaluate']);a=p.parse_args()
    audit() if a.action == 'audit' else evaluate()
