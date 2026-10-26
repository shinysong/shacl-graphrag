"""Build authored procurement projections grounded in pinned ERPNext schemas.

No ERP server, real company records, LLM calls or automated mapping approval.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rule_workbench.core import new_project
from rule_workbench.linkage import audit_relationship, table_digest
from scripts.industrial_source_snapshot import validate_snapshot


def build(sources, output):
    manifest, payloads = validate_snapshot(sources)
    required = {
        'item.json': ['item_code', 'item_name', 'stock_uom'],
        'purchase_order_item.json': ['item_code', 'qty', 'uom'],
        'purchase_receipt_item.json': ['item_code', 'qty', 'quality_inspection'],
        'quality_inspection.json': ['item_code', 'status'],
    }
    for filename, fields in required.items():
        schema = json.loads(payloads[filename])
        if not set(fields) <= {f['fieldname'] for f in schema['fields']}:
            raise ValueError('Pinned schema fields missing: ' + filename)
    output.mkdir(parents=True, exist_ok=False)
    p = new_project('ERP schema-inspired linkage development fixture')
    items = [{'item_code': f'P{i:03}', 'item_name': f'Part {i}', 'stock_uom': 'Nos'} for i in range(300)]
    items.append({'item_code': 'P000', 'item_name': 'Conflicting master row', 'stock_uom': 'Box'})
    order, receipts, inspections, aliases, expected = [], [], [], [], []
    for i in range(1000):
        code = f'P{1 + i % 299:03}'
        mode = i % 10
        if mode == 0:
            value, status = f'LEGACY-{i}', 'candidate_only'
            aliases.append({'source_value': value, 'target_value': code,
                            'evidence': f'authored-legacy-crosswalk.csv:{len(aliases)+2}'})
        elif mode == 1:
            value, status = None, 'missing_key'
        elif mode == 2:
            value, status = f'EXTERNAL-{i}', 'unmatched_in_snapshot'
        elif mode == 3:
            value, status = 'P000', 'ambiguous'
        else:
            value, status = code, 'linked'
        order.append({'item_code': value, 'qty': 10, 'uom': 'Nos'})
        receipts.append({'item_code': code, 'qty': 10, 'quality_inspection': f'QI-{i}' if i < 900 else None})
        if i < 900:
            inspections.append({'item_code': code, 'status': 'Accepted', 'name': f'QI-{i}'})
        expected.append({'source_row': i+1, 'status': status})
    for name, rows in [('Item', items), ('Purchase Order Item', order),
                       ('Purchase Receipt Item', receipts), ('Quality Inspection', inspections)]:
        p['tables'].append({'id': name, 'name': name, 'columns': list(rows[0]), 'rows': rows,
                            'source': {'kind': 'authored_schema_projection', 'complete': True,
                                       'schema_commit': manifest['commit']}})
        with (output / (name.lower().replace(' ', '-')+'.csv')).open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    # This is a supplied development mapping, not model inference or end-user review.
    c = {'id': 'purchase-item', 'source_table': 'Purchase Order Item', 'source_column': 'item_code',
         'target_table': 'Item', 'target_column': 'item_code', 'status': 'confirmed',
         'source_digest': table_digest(p['tables'][1]), 'target_digest': table_digest(p['tables'][0])}
    reports = {}
    reports['complete_snapshot'] = audit_relationship(p, c, aliases)
    partial = copy.deepcopy(p)
    partial['tables'][0]['source']['complete'] = False
    cp = {**c, 'target_digest': table_digest(partial['tables'][0])}
    reports['undeclared_completeness'] = audit_relationship(partial, cp, aliases)
    reports['unreviewed_mapping'] = audit_relationship(p, {**c, 'status': 'draft'}, aliases)
    observed = [{'source_row': r['source_row'], 'status': r['status']}
                for r in reports['complete_snapshot']['results']]
    summary = {'source_kind': 'Authored records, schema-inspired; NOT operational ERP data.',
               'schema_commit': manifest['commit'], 'tables': {t['id']: len(t['rows']) for t in p['tables']},
               'audited_relationship': c['id'], 'audited_source_rows': 1000,
               'other_relationships': 'Receipt and inspection projections prepared, NOT audited in this first slice.',
               'counts': {k: v['counts'] for k, v in reports.items()},
               'matches_authored_development_labels': observed == expected,
               'limitations': ['No LLM, fuzzy matching, business rule execution, or ontology comparison.',
                               'Declared target completeness is supplied, not independently verified.',
                               'Same rows replayed under three policies; not 3,000 independent examples.',
                               'Aliases are authored operational suggestions, never auto-confirmed.']}
    for name, obj in [('project', p), ('contract', c), ('aliases', aliases),
                      ('expectations', expected), ('reports', reports), ('summary', summary),
                      ('source-manifest', manifest)]:
        (output / (name+'.json')).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')
    with (output/'authored-legacy-crosswalk.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['source_value','target_value','evidence']);writer.writeheader();writer.writerows(aliases)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    summary = build(args.sources, args.output)
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary['matches_authored_development_labels'] else 1)
