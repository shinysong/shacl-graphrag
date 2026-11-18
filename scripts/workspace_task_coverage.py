"""Offline authored contract probes, not model generation or quality scoring.

Creates explicit authored review decisions and scripted plans; persists every
checkpoint and failure. It never invokes a model gateway or repairs an argument.
"""
import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from apps.factory_lab import preparation as p, workspace_question
from apps.factory_lab.preparation_advisory import AdvisoryGenerator


def run(source_path, requests_path, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source_raw = Path(source_path).read_bytes()
    requests_raw = Path(requests_path).read_bytes()
    source = json.loads(source_raw)
    requests = json.loads(requests_raw)
    draft = p.create(source['files'], source['metadata'], generator=AdvisoryGenerator())
    (output/'initial-draft.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2))
    baseline_count = sum(e['kind']=='relation' for e in draft['entries'])
    class AuthoredRelationGenerator:
        name = 'authored-task-coverage-control-1'
        def suggest(self, sources):
            entries = AdvisoryGenerator().suggest(sources)
            refs = {s['name']:s for s in sources}
            entries.append({'id':'relation:authored-control','kind':'relation',
                'source':{'file':'parcel_export.csv','column':'parent_purchase','sha256':refs['parcel_export.csv']['sha256']},
                'target':{'file':'purchase_export.csv','column':'purchase_ref','sha256':refs['purchase_export.csv']['sha256']},
                'reason':'Authored diagnostic control from supplied dictionary; not automatically generated'})
            return entries
    draft = p.create(source['files'], source['metadata'], generator=AuthoredRelationGenerator())
    # Authored preparation controls; these are NOT automatic semantic approvals.
    for entry in list(draft['entries']):
        if entry['kind'] == 'mapping':
            draft = p.change(draft, entry['id'], 'approved', 'source_only', 'Authored diagnostic review',
                             'Raw exported '+entry['source']['column']+'; no eligibility inference')
        elif entry['kind'] == 'policy':
            draft = p.change(draft, entry['id'], 'approved', 'context', 'Authored diagnostic review',
                             'Document text only; applicability remains unchecked')
    relation = next(e for e in draft['entries'] if e['kind']=='relation'
                    and e['source']['file']=='parcel_export.csv'
                    and e['target']['file']=='purchase_export.csv'
                    and e['source']['column']=='parent_purchase'
                    and e['target']['column']=='purchase_ref')
    draft = p.change(draft, relation['id'], 'approved', relation['target'],
                     'Authored diagnostic review', 'Exported parcel purchase reference; exact comparison only')
    (output/'reviewed-draft.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2))
    results = []
    for request in requests['requests']:
        checkpoints = []
        packets = []
        plan = {'calls':deepcopy(request['calls']), 'unresolved':request['unresolved']}
        for item in plan['calls']:
            if item['arguments'].get('relation_id')=='@purchase_parcels':
                item['arguments']['relation_id']=relation['id']
        def call(messages):
            packets.append(deepcopy(messages))
            response = plan if len(packets)==1 else {
                'answer':'Scripted diagnostic completion; this is not a model answer.',
                'citations':[], 'unresolved':request['unresolved']}
            return {'content':json.dumps(response)}
        try:
            trace = workspace_question.ask(draft, request['question'], call,
                                           lambda t:checkpoints.append(deepcopy(t)))
            result = {'id':request['id'], 'state':'completed', 'trace':trace}
        except Exception as exc:
            result = {'id':request['id'], 'state':'failed', 'error':type(exc).__name__+': '+str(exc)}
        result.update(scripted_call_count=len(packets), packets=packets, checkpoints=checkpoints)
        results.append(result)
    manifest = {'scope':requests['scope'],'source_sha256':hashlib.sha256(source_raw).hexdigest(),
                'requests_sha256':hashlib.sha256(requests_raw).hexdigest(),
                'paid_calls':0,'initial_local_relation_count':baseline_count,
                'preparation_control':'One authored relation supplied after original local draft; not model or UI creation.', 'results':results}
    (output/'results.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps([{'id':r['id'],'state':r['state'],
                      'tools':[(e['tool'],e['state'],e.get('error')) for e in r.get('trace',{}).get('evidence',[])]}
                     for r in results]))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--sources',required=True)
    parser.add_argument('--requests',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    run(args.sources,args.requests,args.output)
