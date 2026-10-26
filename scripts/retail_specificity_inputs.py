"""Freeze policy-specificity construction inputs; no model or artifact execution."""
import hashlib
import json
from pathlib import Path
from scripts.retail_direct_pilot import digest, write_new

ROOT = Path('_workspace/retail-llm-v1')
BASE = ROOT/'policy-specificity-v1'
TASKS = {'task_1': 'Assess customer-analysis readiness',
         'task_2': 'Assess consistency of invoice cancellation with quantity',
         'task_3': 'Assess acceptability of recorded unit price'}
SYSTEM = ('Return only Python source, no Markdown fences. Define evaluate(packet) using '
          'Python3.12 standard library only. No network or external files; do not print. '
          'Return {"decisions":[{"row_id":"...","policy":"task_1|task_2|task_3",'
          '"status":"pass|violation|unknown"}]}, one decision per row and task. '
          'Implement your interpretation; use unknown where supplied information cannot '
          'support a decision. Wrong outputs, omissions and exceptions remain outcomes.')


def build():
    old = json.loads((ROOT/'generated-python-v1/packets.json').read_text())
    # Positive selection: never forward original policies, mapping, instruction or semantics.
    packets = {}
    for batch, original in old.items():
        packets[batch] = {
            'rows': [{'row_id': r['row_id'], 'data': r['data']} for r in original['rows']],
            'normalized_rows': [
                {'row_id': r['row_id'], 'fields': {
                    k: {key: val for key, val in field.items()
                        if key in ('datatype', 'raw', 'source_key_present', 'state', 'value')}
                    for k, field in r['fields'].items()}}
                for r in original['normalized_rows']],
        }
    variables = json.loads(Path('_workspace/real-retail/metadata.json').read_text())['data']['variables']
    # Official source descriptions remain common, including cancellation prefix semantics.
    # Dataset-level missing_values declarations are not normative row-level requirements.
    variables = [{k: v[k] for k in ('name', 'type', 'description', 'units')} for v in variables]
    interface = json.loads(Path('research/retail-evaluation/executable-input-interface-v1.json').read_text())['python_packet']
    interface = {k: v for k, v in interface.items() if k != 'shacl_mapping'}
    interface['normalized_rows'] = [{'row_id': '<same opaque string>', 'fields': {
        '<column>': {'state': 'valid|missing|invalid', 'source_key_present': '<boolean>',
                     'raw': '<original scalar>', 'datatype': '<type>', 'value': '<parsed value when valid>'}}}]
    interface['output']['decisions'][0]['policy'] = 'task_1|task_2|task_3'
    common = {'tasks': TASKS, 'variables': variables, 'interface': interface,
              'parsing_metadata': 'Optional normalized_rows contains parsing states, not policy decisions. '
              'Quantity/UnitPrice use finite decimal parsing; other fields retain string values. '
              'Blank means absent, null or whitespace-only scalar. Invalid numeric strings and booleans are invalid. '
              'No currency or separator cleanup. You may use raw rows or parsed fields.',
              'runtime_keys': ['rows', 'normalized_rows']}
    semantics = json.loads(Path('research/retail-evaluation/evaluation-contract.json').read_text())['common_semantics']
    explicit = {'blank': semantics['blank'], 'number': semantics['number'],
                'cancellation': semantics['cancellation'],
                'task_1': semantics['customer_analysis'], 'task_2': semantics['quantity_sign'],
                'task_3': semantics['nonnegative_price']}
    inputs = []
    for condition in ('underspecified', 'explicit'):
        content = dict(common)
        if condition == 'explicit':
            content['operational_policy'] = explicit
        inputs.append({'model': 'openai/gpt-6-luna', 'id': 'policy-specificity-v1-'+condition,
                       'language': 'en', 'system_prompt': SYSTEM,
                       'user_prompt': json.dumps(content, ensure_ascii=False, sort_keys=True)})
    # The sole serialized user-prompt difference is the operational policy object.
    a, b = [json.loads(i['user_prompt']) for i in inputs]
    del b['operational_policy']
    assert a == b and inputs[0]['system_prompt'] == inputs[1]['system_prompt']
    assert [len(p['rows']) for p in packets.values()] == [14, 24] or sorted(len(p['rows']) for p in packets.values()) == [14, 24]
    inventory = {
        'construction': {'tasks': 'Authored broad purposes with opaque task IDs; no threshold-bearing IDs',
                         'variables': 'Pinned official UCI names/types/descriptions/units; not operational policies',
                         'interface': 'Explicit nested row.data and response schema; no examples or outcomes',
                         'parsing_metadata': 'Common syntactic parsing definitions; no normative eligibility or decisions',
                         'operational_policy': 'Explicit condition only: frozen authored common_semantics'},
        'runtime': {'rows': 'Original saved development row_id/data only',
                    'normalized_rows': 'Saved parsing fields only; no URI, rule, eligibility, scorer or result'},
        'excluded': ['policies', 'common_semantics', 'field_mapping', 'instruction', 'reference labels', 'previous artifacts'],
        'task_to_scorer_policy_not_sent_to_model': {'task_1': 'customer_analysis', 'task_2': 'quantity_sign', 'task_3': 'nonnegative_price'},
        'limitations': ['Source definitions include C cancellation semantics and declared Integer Quantity in both arms',
                       'Operational policy may intentionally differ from source type metadata; not external truth',
                       'One artifact per condition; no independent replication or causal significance',
                       'No execution approved by this freeze alone']}
    return inputs, packets, inventory


def main():
    inputs, packets, inventory = build()
    prior = [ROOT/'campaign-budget.json', ROOT/'boundary-v1/campaign-budget.json',
             ROOT/'generated-python-v1/campaign-budget.json', ROOT/'generated-shacl-v1/campaign-budget.json']
    assert sum(len(json.loads(p.read_text())['reservations']) for p in prior) == 80
    BASE.mkdir(exist_ok=False)
    config = json.loads((ROOT/'config.json').read_text())
    config.update(inputs_sha256=digest(inputs), max_tokens=4096,
                  ledger_path=str((BASE/'campaign-budget.json').resolve()),
                  external_ledgers=sorted(str(p.resolve()) for p in Path('_workspace').rglob('campaign-budget.json')),
                  predecessor_ledgers={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in prior})
    for name, obj in [('inputs', inputs), ('packets', packets), ('inventory', inventory), ('config', config)]:
        write_new(BASE/(name+'.json'), obj)
    paths = [Path(__file__), Path('research/retail-evaluation/policy-specificity-protocol-v1.json'),
             Path('research/retail-evaluation/executable-input-interface-v1.json'),
             Path('research/retail-evaluation/evaluation-contract.json'),
             ROOT/'generated-python-v1/packets.json', Path('_workspace/real-retail/metadata.json')]
    paths += list(BASE.glob('*.json'))
    write_new(BASE/'freeze.json', {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    print(json.dumps({'planned_calls': len(inputs), 'runtime_batch_rows': {k: len(v['rows']) for k,v in packets.items()},
                      'paid_calls': 0, 'status': 'frozen for fresh exact-packet and execution review'}))


if __name__ == '__main__':
    main()
