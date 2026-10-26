"""Reviewed successor configuration and offline scoring for frozen boundary inputs."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from scripts.retail_direct_pilot import digest, write_new
from scripts.retail_io import parse_output

ROOT = Path('_workspace/retail-llm-v1')
BASE = ROOT/'boundary-v1'


def checked_inputs():
    manifest = json.loads((BASE/'manifest.json').read_text())
    for name in ('cases', 'inputs'):
        if hashlib.sha256((BASE/f'{name}.json').read_bytes()).hexdigest() != manifest[name+'_sha256']:
            raise ValueError('Frozen artifact changed: '+name)
    cases = json.loads((BASE/'cases.json').read_text())
    inputs = json.loads((BASE/'inputs.json').read_text())
    for inp in inputs:
        row_id, kind = inp['id'].rsplit('-', 1)
        case = next(c for c in cases if c['row_id'] == row_id)
        packet = json.loads(inp['user_prompt'])
        if packet['rows'] != [{'row_id': row_id, 'data': case['data']}]:
            raise ValueError('Prompt/case mismatch')
    return cases, inputs


def prepare():
    cases, inputs = checked_inputs()
    old = ROOT/'campaign-budget.json'
    old_data = json.loads(old.read_text())
    assert len(old_data['reservations']) == 48
    assert all(r['status'] == 'completed' and r['reported_usd'] is not None
               for r in old_data['reservations'])
    # Detect actual-source duplicates even though this diagnostic has opaque IDs.
    consumed_source = {r['row_id'] for r in json.loads((ROOT/'selected.json').read_text())['rows']}
    assert not consumed_source.intersection(c['source_row_id'] for c in cases if c['source_row_id'])
    config = json.loads((ROOT/'config.json').read_text())
    externals = []
    for path in Path('_workspace').rglob('campaign-budget.json'):
        if path.resolve() == (BASE/'campaign-budget.json').resolve():
            continue
        data = json.loads(path.read_text())
        assert isinstance(data['reservations'], list) and all('at' in r for r in data['reservations'])
        externals.append(str(path.resolve()))
    config.update(inputs_sha256=digest(inputs),
                  ledger_path=str((BASE/'campaign-budget.json').resolve()),
                  external_ledgers=sorted(externals),
                  predecessor_ledgers={str(old.resolve()): hashlib.sha256(old.read_bytes()).hexdigest()})
    # Existing max144/$5 covers predecessor48 plus successor28, not a fresh budget.
    write_new(BASE/'config.json', config)
    paths = [BASE/'cases.json', BASE/'inputs.json', BASE/'references.json',
             BASE/'config.json', Path(__file__), Path('scripts/score_retail_decisions.py'),
             Path('scripts/retail_io.py')]
    write_new(BASE/'launch-freeze.json', {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    print(json.dumps({'planned_calls': len(inputs), 'predecessor_calls': 48,
                      'combined_cap': config['max_calls'], 'combined_usd_cap': config['max_usd']}))


def evaluate():
    from scripts.score_retail_decisions import score
    for name, sha in json.loads((BASE/'launch-freeze.json').read_text()).items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == sha, name
    cases, inputs = checked_inputs()
    refs = json.loads((BASE/'references.json').read_text())
    ledger = json.loads((BASE/'campaign-budget.json').read_text())['reservations']
    entries = {r['id']: (i, r) for i, r in enumerate(ledger)}
    missing = [r['id'] for r in inputs if r['id'] not in entries]
    if missing:
        print(json.dumps({'planned': len(inputs), 'attempted': len(ledger), 'pending': missing}))
        return
    predictions = {'raw': [], 'metadata': []}
    details = []
    for inp in inputs:
        row_id, kind = inp['id'].rsplit('-', 1)
        keys = [(r['row_id'], r['policy']) for r in refs if r['row_id'] == row_id]
        i, reservation = entries[inp['id']]
        if reservation['status'] == 'completed':
            parsed = parse_output((BASE/'calls'/f'call-{i:04d}'/'output.ttl').read_text(), keys)
            predictions[kind].extend(parsed['predictions'])
            details.append({'id': inp['id'], 'schema_error': parsed['schema_error'], 'missing_keys': parsed['missing_keys']})
        else:
            predictions[kind].extend({'row_id': a, 'policy': b, 'status': 'error'} for a, b in keys)
            details.append({'id': inp['id'], 'failure': reservation['status']})
    split = {}
    for origin in sorted({c['origin'] for c in cases}):
        ids = {c['row_id'] for c in cases if c['origin'] == origin}
        rr = [r for r in refs if r['row_id'] in ids]
        split[origin] = {kind: score(rr, [r for r in pp if r['row_id'] in ids])
                         for kind, pp in predictions.items()}
    old = json.loads((ROOT/'campaign-budget.json').read_text())['reservations']
    result = {'split_metrics': split, 'predictions': predictions, 'details': details,
              'planned_calls': 28, 'attempted_calls': len(ledger),
              'attempt_status': dict(Counter(r['status'] for r in ledger)),
              'reported_usd': sum(r.get('reported_usd') or 0 for r in ledger),
              'reserved_usd': sum(r['upper_usd'] for r in ledger),
              'campaign_calls': len(old)+len(ledger),
              'campaign_reported_usd': sum(r.get('reported_usd') or 0 for r in old+ledger),
              'campaign_reserved_usd': sum(r['upper_usd'] for r in old+ledger),
              'limits': ['Purposive actual development cases and authored probes reported separately',
                         'No business truth, prevalence, heldout or RDF advantage claim',
                         'One model/repeat; three correlated decisions per row',
                         'Reference labels never supplied to generation; no repairs']}
    write_new(BASE/'llm-result.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('predictions','details','split_metrics')}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['prepare', 'evaluate'])
    a = p.parse_args()
    prepare() if a.action == 'prepare' else evaluate()
