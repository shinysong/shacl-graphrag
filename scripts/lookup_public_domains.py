"""Produce unreviewed candidates for explicitly supplied public domain names."""
import argparse,json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rule_workbench.domain_candidates import find_domain_candidates

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--requests',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    with a.source.open('rb') as f:raw=f.read(100000)
    with a.requests.open('rb') as f:request_bytes=f.read(1000001)
    if len(request_bytes)>1000000:raise ValueError('Requests exceed 1MB.')
    report=find_domain_candidates(raw,json.loads(request_bytes))
    with a.output.open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps(report['counts']))
