"""Freeze invoice-disjoint evaluation inputs without computing policy labels."""
import hashlib
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from openpyxl import load_workbook

SEED = 'retail-review-1/invoice-holdout/v1'
COUNT = 32

def key(value):
    if value is None or str(value).strip() == '':
        return None
    return str(value)  # No case/whitespace/cancellation-prefix merging.

def select_invoices(invoices, development, count=COUNT):
    eligible = set(invoices) - set(development) - {None}
    return sorted(eligible, key=lambda v: (hashlib.sha256((SEED+'\0'+v).encode()).hexdigest(),v))[:count]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    root=Path('_workspace/real-retail');out=Path('_workspace/retail-evaluation/frozen-v1')
    if out.exists():
        raise FileExistsError('Never overwrite a frozen or failed split; inspect first.')
    out.mkdir()
    source=root/'original.xlsx';pin=json.loads((root/'acquisition-report.json').read_text())
    assert digest(source)==pin['files']['original.xlsx']['sha256']
    wb=load_workbook(source,read_only=True,data_only=True);sheet=wb.worksheets[0];it=sheet.iter_rows(values_only=True)
    header=list(next(it));assert header[0]=='InvoiceNo'
    invoices=Counter();dev=set();total=0;missing=0
    for row in it:
        total+=1;k=key(row[0])
        if total<=5000:dev.add(k)
        if k is None:missing+=1
        else:invoices[k]+=1
    wb.close()
    selected=select_invoices(invoices,dev);assert len(selected)==COUNT;assert not set(selected)&dev
    manifest={'source_sha256':digest(source),'source_sheet':sheet.title,'seed':SEED,'selection':'32 lowest seeded SHA256 invoice identifiers among all nonblank invoices absent from first5000 development rows; entire invoice groups retained', 'development_prefix_rows':5000,'development_invoice_count':len(dev-{None}), 'scanned_rows':total,'missing_invoice_rows':missing,'unique_invoices':len(invoices),'eligible_invoices':len(set(invoices)-dev),'selected_invoices':selected,'expected_selected_rows':sum(invoices[k] for k in selected),'limitations':['Invoice-disjoint only; products/customers/time may overlap.','Not population-weighted row sampling; no rare-error stratification.','No policy labels or outcome-driven selection; untouched input bundle.','XLSX dates normalized to ISO; source bytes preserved; source API advertised row count independently checked here.']}
    wb=load_workbook(source,read_only=True,data_only=True);it=wb.worksheets[0].iter_rows(values_only=True);assert list(next(it))==header
    actual=Counter();chosen=set(selected)
    with (out/'inputs.jsonl').open('w') as f:
        for worksheet_row,row in enumerate(it,start=2):
            k=key(row[0])
            if k not in chosen:continue
            assert worksheet_row>5001
            values={c:(v.isoformat() if isinstance(v,(datetime,date)) else v) for c,v in zip(header,row)}
            f.write(json.dumps({'worksheet_row':worksheet_row,'invoice':k,'data':values},ensure_ascii=False,allow_nan=False)+'\n');actual[k]+=1
    wb.close()
    assert dict(actual)=={k:invoices[k] for k in selected}
    manifest.update(actual_selected_rows=sum(actual.values()),inputs_sha256=digest(out/'inputs.jsonl'))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['scanned_rows','unique_invoices','eligible_invoices','actual_selected_rows','development_invoice_count']}))

if __name__=='__main__':main()
