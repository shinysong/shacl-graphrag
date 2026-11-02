#!/usr/bin/env python3
"""Compare a workbook export with the earlier transcription, never repair either."""
import argparse
import hashlib
import json
from pathlib import Path


def compare(extracted, previous):
    expected = {row['id']: row for row in previous['rows']}
    actual = {row['id']: row for book in extracted['workbooks'] for row in book['records']}
    if len(expected) != len(previous['rows']) or len(actual) != sum(len(b['records']) for b in extracted['workbooks']):
        raise ValueError('Duplicate annotation IDs')
    if actual.keys() != expected.keys():
        raise ValueError('Annotation ID sets differ')
    formulas = {}
    counts = {}
    for book in extracted['workbooks']:
        coupon = book['coupon']
        counts[coupon] = len(book['records'])
        prior = previous['dictionaries'][coupon]
        defects = {x['code']: x['label'] for x in prior['defects']}
        settings = {x['code']: x['values'] for x in prior['settings']}
        if defects != {x['code']: x['values'][1] for x in book['dictionaries']['defect_code']}:
            raise ValueError(f'Defect dictionary differs: {coupon}')
        if settings != {x['code']: x['values'][1:] for x in book['dictionaries']['welding_settings_code']}:
            raise ValueError(f'Setting dictionary differs: {coupon}')
        for row in book['records']:
            old = expected[row['id']]
            for key in ('coupon', 'archive_path', 'sheet', 'excel_row', 'cell_range', 'values'):
                if row[key] != old[key]:
                    raise ValueError(f'Annotation differs: {row["id"]} {key}')
            if defects[row['values']['defect']] != old['defect_label'] or settings[row['values']['welding_setting']] != old['observed_nominal_setting']:
                raise ValueError(f'Joined nominal value differs: {row["id"]}')
        for name, sheet in book['sheets'].items():
            for row in sheet['rows']:
                for cell in row['cells']:
                    if cell['formula'] is not None:
                        formulas[(coupon, name, cell['cell'])] = (cell['formula'], cell['cached_value'])
    old_formulas = {(f['coupon'], f['sheet'], f['cell']): (f['formula'], f['cached_value']) for f in previous['formulas']}
    if len(old_formulas) != len(previous['formulas']) or formulas != old_formulas:
        raise ValueError('Formula/cache pairs differ')
    return {'status': 'matched', 'annotation_rows': len(actual), 'rows_by_coupon': counts,
            'formula_cache_pairs': len(formulas), 'dictionary_workbooks': len(extracted['workbooks']),
            'scope': 'Transcription consistency only; earlier transcription is not independent truth. No repair, physical decision, design mapping or new efficacy benchmark.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extracted', type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raw = args.extracted.read_bytes(); old = args.previous.read_bytes()
    result = compare(json.loads(raw), json.loads(old))
    result['input_sha256'] = {'extracted': hashlib.sha256(raw).hexdigest(), 'previous': hashlib.sha256(old).hexdigest()}
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, indent=2); handle.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
