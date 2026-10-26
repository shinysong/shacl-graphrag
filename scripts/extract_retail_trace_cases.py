"""Posthoc illustrations from saved development outcomes; no re-execution."""
import hashlib
import json
from pathlib import Path
from rdflib import Graph, SH, URIRef

BASE=Path('_workspace/retail-evaluation/row-compare-full-v1')
OUT=Path('_workspace/retail-evaluation/trace-cases-v1.json')
SOURCE=Path('_workspace/real-retail/project.json')
EXPECTED='2c47251bb01fec0eb3f5c6d2469ba7da368c7d90b6a88439ddca916d0bf13344'

def main():
    raw=SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('Source hash mismatch')
    rows=json.loads(raw)['tables'][0]['rows'];cases=[];seen_customer=False;seen_control=False
    for file in sorted(BASE.glob('batch-*.json'),key=lambda p:int(p.stem.split('-')[1])):
        batch_raw=file.read_bytes();batch=json.loads(batch_raw)
        py={(d['row_id'],d['policy']):d['status'] for d in batch['python']}
        for d in batch['shacl']['decisions']:
            take=d['policy']=='quantity_sign' and d['status']=='violation'
            if d['policy']=='customer_analysis' and d['status']=='violation' and not seen_customer:
                take=True;seen_customer=True
            if d['policy']=='quantity_sign' and d['status']=='pass' and not seen_control:
                take=True;seen_control=True
            if not take:continue
            trace=batch['shacl']['traces'][d['policy']]
            report=Graph().parse(data=trace['report_turtle'],format='turtle')
            node=URIRef('urn:retail:row:'+d['row_id']);witness=[]
            for result in report.subjects(SH.focusNode,node):
                witness.append({str(p):str(o) for p,o in report.predicate_objects(result)})
            if d['status']=='violation' and not witness:raise ValueError('Missing saved violation witness')
            cases.append({'row_id':d['row_id'],'policy':d['policy'],'source_cells':rows[int(d['row_id'])-2],
                'python_status':py[(d['row_id'],d['policy'])],'shacl_status':d['status'],
                'saved_report_witnesses':witness,'shape_turtle':trace['shape_turtle'],
                'batch_file':str(file),'batch_sha256':hashlib.sha256(batch_raw).hexdigest()})
    payload={'scope':'Posthoc outcome-selected illustrations, not a new evaluation or representative sample',
        'selection':'All quantity violations, first customer-presence violation, first quantity pass in saved batch order',
        'source_sha256':EXPECTED,'policy_origin':'Research-authored; violations do not establish retailer data errors or transaction illegitimacy',
        'source_attribution':'UCI Online Retail, Daqing Chen (2015), DOI10.24432/C5BW33, CC BY4.0',
        'cases':cases,'new_validation_runs':0,'paid_calls':0}
    with OUT.open('x') as f:json.dump(payload,f,indent=2)
    print(json.dumps([{'row_id':c['row_id'],'policy':c['policy'],'cells':c['source_cells'],'status':c['shacl_status']} for c in cases]))

if __name__=='__main__':main()
