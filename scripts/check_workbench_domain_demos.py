"""Offline connector and SHACL checks against separately authored fixture labels."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rule_workbench.connectors import read_file
from rule_workbench.core import run_checks
from rule_workbench.exports import export_bundle,export_json,import_json


def signature(results):
    return {(r['rule_id'],r['row']):r['status'] for r in results}


def check_domain(directory,output):
    project=json.loads((directory/'confirmed-project.json').read_text())
    expected=json.loads((directory/'expectations.json').read_text())
    expected=expected['results'] if isinstance(expected,dict) else expected
    oracle=signature(expected)
    runs=[]
    for format_name in ['json','csv','xlsx','sqlite']:
        p=copy.deepcopy(project)
        if format_name!='json':
            paths=sorted(directory.glob('*.csv')) if format_name=='csv' else [directory/('data.'+format_name)]
            loaded=[t for path in paths for t in read_file(path.name,path.read_bytes())]
            # Explicit fixture mapping, not automatic entity/schema discovery.
            by_name={t['source'].get('sheet') or t['source'].get('table') or Path(t['source']['file']).stem:t for t in loaded}
            assert len(by_name)==len(project['tables']), (format_name,'table count')
            for table in p['tables']:
                imported=by_name[table['id']]
                assert imported['columns']==table['columns']
                assert len(imported['rows'])==len(table['rows'])
                table['rows']=imported['rows'];table['source']=imported['source']
        started=time.perf_counter();result=run_checks(p);elapsed=time.perf_counter()-started
        observed=signature(result['results'])
        differences=[{'rule_id':key[0],'row':key[1],'expected':oracle.get(key),'observed':observed.get(key)} for key in sorted(set(oracle)|set(observed),key=str) if oracle.get(key)!=observed.get(key)]
        restored=run_checks(import_json(export_json(p,True)))
        roundtrip_equal=signature(restored['results'])==observed
        dest=output/format_name;dest.mkdir(parents=True)
        (dest/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        (dest/'bundle.zip').write_bytes(export_bundle(p,result,True))
        runs.append({'format':format_name,'counts':result['counts'],'result_entries':len(result['results']),'differences':differences,'roundtrip_equal':roundtrip_equal,'seconds':elapsed})
    report={'domain':directory.name,'tables':{t['id']:len(t['rows']) for t in project['tables']},'expected_entries':len(oracle),'runs':runs,'all_match':all(not r['differences'] and r['roundtrip_equal'] for r in runs),'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    reports=[]
    for domain in ['manufacturing','healthcare','finance','ecommerce']:
        destination=args.output/domain;destination.mkdir()
        report=check_domain(args.data/domain,destination);reports.append(report)
        print(domain,report['all_match'],report['runs'][0]['counts'],flush=True)
    (args.output/'summary.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))
    return 0 if all(r['all_match'] for r in reports) else 1
if __name__=='__main__':raise SystemExit(main())
