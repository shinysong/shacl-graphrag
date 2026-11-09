"""Offline selected-C binding SHACL/Python comparison, preserving exact envelopes."""
import argparse,json,hashlib,importlib.metadata,shutil
from pathlib import Path
from collections import Counter
from rdflib import Graph
from scripts.graphrag_shacl_binding import shacl_binding
from scripts.graphrag_check import canonical_bytes

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    summary={'status':'failed','planned':24,'generation_executed':False};rows=[]
    try:
        m=json.loads(Path(a.manifest).read_text())
        for path,h in m['hashes'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise ValueError('hash mismatch')
        for package,version in m['runtime'].items():
            if importlib.metadata.version(package)!=version:raise ValueError('runtime mismatch')
        envelopes=[json.loads(x) for x in Path(m['input']).read_text().splitlines()]
        if len(envelopes)!=24 or len({e['question_id'] for e in envelopes})!=24:raise ValueError('question universe')
        shapes=Graph().parse(m['shapes']);f=out/'frozen';f.mkdir()
        for path in m['hashes']:shutil.copyfile(path,f/Path(path).name)
        shutil.copyfile(a.manifest,out/'manifest.json')
        for e in envelopes:
            row={'question_id':e['question_id'],'status':'error','evidence':e}
            try:
                result,g,report,text=shacl_binding(e,shapes);row.update(status='ok',report=result)
                stem=out/e['question_id'];g.serialize(str(stem)+'.data.ttl',format='turtle');report.serialize(str(stem)+'.report.ttl',format='turtle');Path(str(stem)+'.report.txt').write_text(text)
            except Exception as exc:row['error']=f'{type(exc).__name__}: {exc}'
            rows.append(row)
            (out/'results.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        for path,h in m['hashes'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise ValueError('input changed')
        summary.update(status='completed',ok=sum(r['status']=='ok' for r in rows),parity_rows=sum(r.get('report',{}).get('parity',False) for r in rows),binding_statuses=dict(Counter(x['status'] for r in rows for x in r.get('report',{}).get('results',[]))))
        if summary['ok']!=24 or summary['parity_rows']!=24:summary['status']='partial_failure'
    finally:
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
