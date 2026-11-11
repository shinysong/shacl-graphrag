#!/usr/bin/env python3
"""Explicit preparation/run commands; preparation never authorizes paid calls."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from experiments.factory_complexity.campaign import prepare,run

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('prepare','run'));p.add_argument('--work',required=True)
    p.add_argument('--runtime');p.add_argument('--model');p.add_argument('--readiness')
    args=p.parse_args()
    if args.action=='prepare':
        if not all((args.runtime,args.model,args.readiness)):p.error('prepare requires runtime, model, readiness')
        result=prepare(args.work,args.runtime,args.model,args.readiness)
    else:result=run(args.work)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
