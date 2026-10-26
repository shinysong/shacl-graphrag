"""One fixed consumed-development comparison, never a held-out accuracy benchmark."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from time import perf_counter
from scripts.evaluate_retail_policies import evaluate_python, POLICIES
from scripts.retail_row_shacl import evaluate_rows

PROJECT=Path('_workspace/real-retail/project.json')
EXPECTED='2c47251bb01fec0eb3f5c6d2469ba7da368c7d90b6a88439ddca916d0bf13344'
OUT=Path('_workspace/retail-evaluation/row-compare-v1')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--full-development',action='store_true')
    args=parser.parse_args()
    limit=5000 if args.full_development else 500
    out=Path('_workspace/retail-evaluation/row-compare-full-v1') if args.full_development else OUT
    raw=PROJECT.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('Development source changed')
    source=json.loads(raw)['tables'][0]['rows']
    if len(source)!=5000:raise ValueError('Expected consumed development project')
    rows=[{'row_id':str(i+2),'data':r} for i,r in enumerate(source[:limit])]
    out.mkdir(exist_ok=False)
    (out/'selection.json').write_text(json.dumps({'project_sha256':EXPECTED,'selection':f'first{limit} ordered consumed development rows, no outcome filtering; overlaps prior500 if full','rows':limit,'batch_size':100,'paid_calls':0},indent=2))
    all_py=[];all_sh=[];times=[]
    for start in range(0,len(rows),100):
        batch=rows[start:start+100]
        t=perf_counter()
        py=[{'row_id':r['row_id'],'policy':p,'status':evaluate_python(r['data'],p)} for r in batch for p in POLICIES]
        pt=perf_counter()-t
        t=perf_counter();sh=evaluate_rows(batch);st=perf_counter()-t
        record={'start':start,'python_seconds':pt,'shacl_wrapper_seconds':st,'python':py,'shacl':sh}
        (out/f'batch-{start//100}.json').write_text(json.dumps(record,indent=2))
        all_py.extend(py);all_sh.extend(sh['decisions']);times.append({'python_seconds':pt,'shacl_wrapper_seconds':st})
    pmap={(d['row_id'],d['policy']):d['status'] for d in all_py}
    smap={(d['row_id'],d['policy']):d['status'] for d in all_sh}
    mismatch=[{'row_id':k[0],'policy':k[1],'python':pmap.get(k),'shacl':smap.get(k)} for k in sorted(pmap.keys()|smap.keys()) if pmap.get(k)!=smap.get(k)]
    summary={'rows':len(rows),'decisions_per_arm':len(all_py),'mismatches':mismatch,'counts':{arm:{p:dict(Counter(d['status'] for d in ds if d['policy']==p)) for p in POLICIES} for arm,ds in [('python',all_py),('shacl',all_sh)]},'timings':times,'limitations':['One ordered consumed development prefix, not representative or heldout','Authored policy agreement, not external business truth','Python direct cells; SHACL time includes mapping, shapes, validation and in-memory trace serialization','One run, fixed Python-before-SHACL order; no engine-performance or maintenance-labor inference','SHACL unknown handling uses shared preprocessing outside validator','No LLM or generated artifacts']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))

if __name__=='__main__':main()
