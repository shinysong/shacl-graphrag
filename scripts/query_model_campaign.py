"""Prepare closed scope or run an explicitly approved, reviewed one-launch scope."""
import argparse
import json
from experiments.query_contracts.model_campaign import prepare,run
p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('--work',required=True);a=p.parse_args()
r=prepare(a.work) if a.action=='prepare' else run(a.work)
print(json.dumps(r if a.action=='prepare' else {'status':r['status'],'budget':r['budget']},indent=2))
