"""Offline development diagnostic; source examples and authored probes stay separate."""
import hashlib
import json
from collections import Counter
from pathlib import Path

from scripts.retail_direct_pilot import SOURCE, SOURCE_HASH, paired, write_new
from scripts.retail_row_shacl import evaluate_rows
from scripts.evaluate_retail_policies import evaluate_python

BASE = Path('_workspace/retail-llm-v1/boundary-v1')


def main():
    source_bytes = SOURCE.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != SOURCE_HASH:
        raise ValueError('Source changed')
    source = json.loads(source_bytes)['tables'][0]['rows']
    cases = [
        {'source_row_id': str(i), 'data': source[i-2],
         'origin': 'selected_actual_development_source',
         'selection': 'Previously observed rare quantity-sign policy violation; purposive, not random'}
        for i in (2408, 4349)
    ]
    # These are authored scalar records, never presented as observed source faults.
    common = {'InvoiceNo': 'SYN-1', 'CustomerID': 'SYN-CUSTOMER',
              'Quantity': '1', 'UnitPrice': '1'}
    probes = [
        ('cancel_negative', {'InvoiceNo': 'cSYN-1', 'Quantity': '-1'}),
        ('cancel_positive', {'InvoiceNo': 'CSYN-1', 'Quantity': '1'}),
        ('cancel_zero', {'InvoiceNo': 'CSYN-1', 'Quantity': '0'}),
        ('ordinary_zero', {'Quantity': '0'}),
        ('ordinary_fraction', {'Quantity': '0.5'}),
        ('leading_space_invoice', {'InvoiceNo': ' CSYN-1', 'Quantity': '-1'}),
        ('missing_invoice', {'InvoiceNo': None}),
        ('invalid_quantity', {'Quantity': 'not-a-number'}),
        ('negative_price', {'UnitPrice': '-0.01'}),
        ('zero_price', {'UnitPrice': '0'}),
        ('nonfinite_price', {'UnitPrice': 'NaN'}),
        ('blank_customer', {'CustomerID': '   '}),
    ]
    cases.extend({'source_row_id': None, 'data': dict(common, **changes),
                  'origin': 'authored_boundary_probe', 'selection': name}
                 for name, changes in probes)
    for i, case in enumerate(cases):
        case['row_id'] = str(100001 + i)
    BASE.mkdir(parents=True, exist_ok=True)
    rows = [{'row_id': c['row_id'], 'data': c['data']} for c in cases]
    variables = json.loads(Path('_workspace/real-retail/metadata.json').read_text())['data']['variables']
    inputs = []
    for i, row in enumerate(rows):
        pair = paired(row, variables)
        inputs.extend(pair[k] for k in (('raw', 'metadata') if i % 2 == 0 else ('metadata', 'raw')))
    # Freeze runtime inputs first, without origin/selection labels or expected answers.
    write_new(BASE/'cases.json', cases)
    write_new(BASE/'inputs.json', inputs)
    frozen_hash = hashlib.sha256((BASE/'cases.json').read_bytes()).hexdigest()
    write_new(BASE/'manifest.json', {
        'cases_sha256': frozen_hash, 'original_source_sha256': SOURCE_HASH,
        'inputs_sha256': hashlib.sha256((BASE/'inputs.json').read_bytes()).hexdigest(),
        'scope': 'Purposive consumed-development source cases plus authored probes; not prevalence or heldout accuracy',
        'source_rows': 2, 'authored_rows': 12, 'planned_future_llm_calls': 28,
        'paid_execution_authorized_by_this_script': False,
    })
    # Scorer references are generated only after runtime packets are frozen.
    from scripts.retail_reference import reference_for
    from scripts.score_retail_decisions import score
    refs = [ref for row in rows for ref in reference_for(row['row_id'], row['data'], frozen_hash)]
    py = [{'row_id': r['row_id'], 'policy': ref['policy'],
           'status': evaluate_python(r['data'], ref['policy'])}
          for r in rows for ref in refs if ref['row_id'] == r['row_id']]
    sh = evaluate_rows(rows)
    write_new(BASE/'references.json', refs)
    write_new(BASE/'python.json', py)
    write_new(BASE/'shacl.json', sh)
    results = {}
    for origin in ('selected_actual_development_source', 'authored_boundary_probe'):
        ids = {c['row_id'] for c in cases if c['origin'] == origin}
        subset = [r for r in refs if r['row_id'] in ids]
        results[origin] = {
            'support': dict(Counter(r['status'] for r in subset)),
            'python': score(subset, [p for p in py if p['row_id'] in ids]),
            'shacl': score(subset, [p for p in sh['decisions'] if p['row_id'] in ids]),
        }
    write_new(BASE/'result.json', results)
    print(json.dumps({k: v['support'] for k, v in results.items()}))


if __name__ == '__main__':
    main()
