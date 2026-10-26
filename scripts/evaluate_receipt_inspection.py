"""Offline authored receipt/inspection consistency demonstration; no model calls."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rule_workbench.linkage import table_digest
from rule_workbench.linkage_consistency import audit_field_consistency


def run(source, output):
    raw = source.read_bytes()
    original = json.loads(raw)
    output.mkdir(parents=True, exist_ok=False)
    variants = {'original_authored': copy.deepcopy(original), 'injected_faults': copy.deepcopy(original)}
    dirty = next(t for t in variants['injected_faults']['tables'] if t['id']=='Quality Inspection')
    # Controlled development mutations, never read by runtime evaluator as labels.
    for row in dirty['rows'][:50]: row['item_code'] = 'DECLARED-CONFLICT'
    for row in dirty['rows'][50:100]: row['item_code'] = None
    duplicates = copy.deepcopy(dirty['rows'][150:200])
    del dirty['rows'][100:150]
    dirty['rows'].extend(duplicates)
    variants['incomplete_reference'] = copy.deepcopy(variants['injected_faults'])
    next(t for t in variants['incomplete_reference']['tables'] if t['id']=='Quality Inspection')['source']['complete']=False
    expected = {
        'original_authored': {'agrees':900,'not_evaluated':100},
        'injected_faults': {'agrees':700,'violates_declared_equality':50,'missing_evidence':50,'not_evaluated':200},
        'incomplete_reference': {'not_evaluated':1000}}
    summaries = {}
    for name,p in variants.items():
        tables={t['id']:t for t in p['tables']}
        c=dict(id='receipt-inspection-item',source_table='Purchase Receipt Item',
               source_column='quality_inspection',target_table='Quality Inspection',target_column='name',
               status='confirmed',equality_status='confirmed',
               equality_pairs=[{'source_column':'item_code','target_column':'item_code'}],
               source_digest=table_digest(tables['Purchase Receipt Item']),
               target_digest=table_digest(tables['Quality Inspection']))
        r=audit_field_consistency(p,c)
        summaries[name]={'counts':r['counts'],'denominator':r['denominator'],
                         'matches_development_expectation':r['counts']==expected[name]}
        for suffix,obj in [('input',p),('report',r)]:
            (output/f'{name}-{suffix}.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    summary={'source_sha256':hashlib.sha256(raw).hexdigest(),'variants':summaries,
             'limitations':['Authored schema-inspired development data and explicit injected faults, not real company records.',
                            'Same 1000 receipts reused in variants; not 3000 independent observations.',
                            'Python exact equality only, no SHACL/RDF benefit, LLM or inspection approval claim.',
                            'Source digests and field mappings are supplied; no hidden omission detection.']}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    (output/'development-expectations.json').write_text(json.dumps(expected,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();summary=run(args.source,args.output)
    print(json.dumps(summary,indent=2))
    raise SystemExit(0 if all(v['matches_development_expectation'] for v in summary['variants'].values()) else 1)
