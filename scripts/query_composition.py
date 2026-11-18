"""Raw compound request -> model decomposition/DAG -> fixed queries -> final answer."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiments.query_contracts.composition_campaign import prepare,prepare_format_recovery,run
p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','recover-prepare','run']);p.add_argument('--work',required=True);p.add_argument('--model-file');p.add_argument('--parent')
a=p.parse_args()
if a.command=='prepare' and not a.model_file:p.error('--model-file required')
if a.command=='recover-prepare' and not a.parent:p.error('--parent required')
result=prepare(a.work,a.model_file) if a.command=='prepare' else (prepare_format_recovery(a.parent,a.work) if a.command=='recover-prepare' else run(a.work))
print(json.dumps(result,ensure_ascii=False,indent=2))
