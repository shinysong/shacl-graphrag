"""Three frozen generation calls; isolated execution and separate offline scoring."""
import argparse
import hashlib
import json
from pathlib import Path
from scripts.retail_arm_packets import preview
from scripts.retail_direct_pilot import digest, write_new
from scripts.retail_python_runner import execute
from scripts.retail_python_intake import inspect_python
from scripts.retail_io import parse_output

ROOT = Path('_workspace/retail-llm-v1')
BASE = ROOT/'generated-python-v1'


def prepare():
    BASE.mkdir(parents=True, exist_ok=False)
    variables = json.loads(Path('_workspace/real-retail/metadata.json').read_text())['data']['variables']
    batches = {
        'random_development': json.loads((ROOT/'selected.json').read_text())['rows'],
        'boundary_diagnostic': [{'row_id': c['row_id'], 'data': c['data']}
                                for c in json.loads((ROOT/'boundary-v1/cases.json').read_text())],
    }
    common = {}
    inputs = []
    options = [('reusable', [], 'llm_explicit_rules_python')]
    options += [('adhoc-'+k, rows, 'llm_ad_hoc_code') for k, rows in batches.items()]
    for name, rows, arm in options:
        packet = preview(rows or [{'row_id': 'template', 'data': {}}], variables)[arm]
        if name == 'reusable':
            content = json.loads(packet['messages'][1]['content'])
            content['rows'] = []
            content['normalized_rows'] = []
            packet['messages'][1]['content'] = json.dumps(content, ensure_ascii=False, sort_keys=True)
        if name.startswith('adhoc-'):
            common[name[6:]] = json.loads(packet['messages'][1]['content'])
        system = packet['messages'][0]['content'] + (
            '\nReturn only Python source, no Markdown fences. Define evaluate(packet). '
            'Python3.12 standard library only. Return the specified decisions object. '
            'No network or external files; do not print. Read packet["rows"] and, if useful, '
            'packet["normalized_rows"]. The same packet structure is supplied at execution. '
            'Missing evaluate(), exceptions, wrong outputs and omissions remain measured failures.')
        inputs.append({'model': 'openai/gpt-6-luna', 'id': 'generated-python-v1-'+name,
                       'language': 'en', 'system_prompt': system,
                       'user_prompt': packet['messages'][1]['content']})
    prior = [ROOT/'campaign-budget.json', ROOT/'boundary-v1/campaign-budget.json']
    assert sum(len(json.loads(p.read_text())['reservations']) for p in prior) == 76
    config = json.loads((ROOT/'config.json').read_text())
    external = sorted(str(p.resolve()) for p in Path('_workspace').rglob('campaign-budget.json'))
    config.update(inputs_sha256=digest(inputs), ledger_path=str((BASE/'campaign-budget.json').resolve()),
                  external_ledgers=external, max_tokens=4096,
                  predecessor_ledgers={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in prior})
    write_new(BASE/'inputs.json', inputs)
    write_new(BASE/'config.json', config)
    write_new(BASE/'packets.json', common)
    files = [BASE/'inputs.json', BASE/'config.json', BASE/'packets.json',
             ROOT/'references.json', ROOT/'boundary-v1/references.json', ROOT/'boundary-v1/cases.json',
             Path(__file__), Path('scripts/retail_python_runner.py'),
             Path('scripts/retail_python_intake.py'), Path('scripts/retail_io.py'),
             Path('scripts/score_retail_decisions.py')]
    write_new(BASE/'freeze.json', {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    print(json.dumps({'generation_calls': 3, 'reusable_artifacts': 1,
                      'adhoc_artifacts': 2, 'execution_batches_per_arm': 2}))


def evaluate():
    # References never mounted in execution; used below for scoring saved results only.
    from scripts.score_retail_decisions import score
    for path, sha in json.loads((BASE/'freeze.json').read_text()).items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha, path
    inputs = json.loads((BASE/'inputs.json').read_text())
    ledger = json.loads((BASE/'campaign-budget.json').read_text())['reservations']
    assert len(ledger) == 3 and {r['id'] for r in ledger} == {r['id'] for r in inputs}
    packets = json.loads((BASE/'packets.json').read_text())
    predictions = {}; details = []
    policies = ['customer_analysis', 'quantity_sign', 'nonnegative_price']
    for arm in ('reusable', 'adhoc'):
        predictions[arm] = {}
        for batch, packet in packets.items():
            name = 'reusable' if arm == 'reusable' else 'adhoc-'+batch
            i, r = next((i, r) for i, r in enumerate(ledger) if r['id'] == 'generated-python-v1-'+name)
            keys = [(row['row_id'], policy) for row in packet['rows'] for policy in policies]
            detail = {'arm': arm, 'batch': batch, 'generation_status': r['status']}
            pp = [{'row_id': a, 'policy': b, 'status': 'error'} for a, b in keys]
            if r['status'] == 'completed':
                raw = (BASE/'calls'/f'call-{i:04d}'/'output.ttl').read_bytes()
                parsed = inspect_python(raw)
                detail['intake'] = parsed
                if parsed['status'] == 'syntax_valid_pending_execution_review':
                    result = execute(raw, packet, BASE/'executions'/f'{arm}-{batch}')
                    detail['execution'] = result
                    if not result['container_absent']:
                        write_new(BASE/'unresolved-cleanup.json', detail)
                        raise RuntimeError('Cleanup unresolved; stop all execution')
                    if result['status'] == 'completed':
                        text = (BASE/'executions'/f'{arm}-{batch}'/'stdout.bin').read_bytes().decode('utf-8', errors='replace')
                        output = parse_output(text, keys)
                        pp = output['predictions']
                        detail['response_parse'] = output
            predictions[arm][batch] = pp
            details.append(detail)
    refs = {
        'random_development': json.loads((ROOT/'references.json').read_text()),
        'boundary_diagnostic': json.loads((ROOT/'boundary-v1/references.json').read_text()),
    }
    origins = {c['row_id']: c['origin'] for c in json.loads((ROOT/'boundary-v1/cases.json').read_text())}
    metrics = {}
    for arm, batches in predictions.items():
        metrics[arm] = {'random_development': score(refs['random_development'], batches['random_development'])}
        for origin in sorted(set(origins.values())):
            rr = [r for r in refs['boundary_diagnostic'] if origins[r['row_id']] == origin]
            pp = [r for r in batches['boundary_diagnostic'] if origins[r['row_id']] == origin]
            metrics[arm][origin] = score(rr, pp)
    result = {'metrics': metrics, 'predictions': predictions, 'details': details,
              'reported_usd': sum(r.get('reported_usd') or 0 for r in ledger),
              'reserved_usd': sum(r['upper_usd'] for r in ledger),
              'limits': ['Consumed development single-model diagnostic; no business truth',
                         'Adhoc sees batch; reusable construction sees schema/policy but no rows',
                         'One reusable artifact vs two adhoc artifacts; no construction-repeat claim',
                         'No reference repairs; all failures included', 'SHACL generation not included']}
    write_new(BASE/'result.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('metrics', 'details', 'predictions')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['prepare', 'evaluate'])
    args = p.parse_args()
    prepare() if args.action == 'prepare' else evaluate()
