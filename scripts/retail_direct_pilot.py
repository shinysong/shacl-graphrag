"""Prepare frozen direct-LLM pilot inputs, then score saved responses separately."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from scripts.retail_arm_packets import preview
from scripts.retail_io import parse_output

BASE=Path('_workspace/retail-llm-v1')
SOURCE=Path('_workspace/real-retail/project.json')
SOURCE_HASH='2c47251bb01fec0eb3f5c6d2469ba7da368c7d90b6a88439ddca916d0bf13344'
MODEL='openai/gpt-6-luna'

def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def write_new(path,value):
    with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2)

def paired(row,variables):
    p=preview([row],variables)['llm_direct']
    full=json.loads(p['messages'][1]['content']);raw=dict(full);raw.pop('normalized_rows')
    system=p['messages'][0]['content']+' Return only JSON, without Markdown fences.'
    return {kind:{'model':MODEL,'id':row['row_id']+'-'+kind,'language':'en','system_prompt':system,'user_prompt':json.dumps(content,ensure_ascii=False,sort_keys=True)} for kind,content in [('raw',raw),('metadata',full)]}

def prepare():
    raw=SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_HASH:raise ValueError('Source changed')
    source=json.loads(raw)['tables'][0]['rows'];assert len(source)==5000
    seed='retail-direct-development-v1'
    ids=sorted(range(2,5002),key=lambda i:(hashlib.sha256((seed+'\n'+str(i)).encode()).hexdigest(),i))[:24]
    variables=json.loads(Path('_workspace/real-retail/metadata.json').read_text())['data']['variables']
    inputs=[];selected=[]
    for pos,i in enumerate(ids):
        row={'row_id':str(i),'data':source[i-2]};selected.append(row);pair=paired(row,variables)
        inputs.extend(pair[k] for k in (('raw','metadata') if pos%2==0 else ('metadata','raw')))
    session=json.loads((BASE/'session.json').read_text())
    models=json.loads((BASE/'models.json').read_text())['data'];model=next(m for m in models if m['id']==MODEL)
    ip=float(model['pricing']['prompt'])*1e6*1.2;op=float(model['pricing']['completion'])*1e6*1.2
    externals=[]
    for path in Path('_workspace').rglob('campaign-budget.json'):
        if BASE in path.parents:continue
        data=json.loads(path.read_text())
        if not isinstance(data.get('reservations'),list) or any('at' not in r for r in data['reservations']):raise ValueError('Unaccounted ledger')
        externals.append(str(path.resolve()))
    config={'models':{MODEL:{'input_price_per_million':ip,'output_price_per_million':op,'reasoning':{'effort':'medium'},'response_aliases':[model['canonical_slug']]}},'max_calls':144,'daily_cap':500,'max_usd':5,'max_reported_usd':5,'max_tokens':2048,'timeout_seconds':120,'deadline_utc':session['deadline_utc'],'external_ledgers':sorted(externals),'inputs_sha256':digest(inputs),'ledger_path':str((BASE/'campaign-budget.json').resolve())}
    write_new(BASE/'selected.json',{'source_sha256':SOURCE_HASH,'seed':seed,'rows':selected})
    write_new(BASE/'inputs.json',inputs);write_new(BASE/'config.json',config)
    print(json.dumps({'rows':len(ids),'calls':len(inputs),'input_hash':digest(inputs),'historical_ledgers':len(externals),'model':MODEL}))

def evaluate():
    # Scorer-only imports; never passed to generator or prompts.
    from scripts.retail_reference import reference_for
    from scripts.score_retail_decisions import score
    from scripts.evaluate_retail_policies import evaluate_python
    selected=json.loads((BASE/'selected.json').read_text())['rows']
    inputs=json.loads((BASE/'inputs.json').read_text());config=json.loads((BASE/'config.json').read_text())
    if digest(inputs)!=config['inputs_sha256']:raise ValueError('Frozen input mismatch')
    ledger=json.loads((BASE/'campaign-budget.json').read_text())
    reservations={r['id']:(i,r) for i,r in enumerate(ledger['reservations'])}
    refs=[ref for row in selected for ref in reference_for(row['row_id'],row['data'],SOURCE_HASH)]
    keys=[(r['row_id'],r['policy']) for r in refs];predictions={'raw':[],'metadata':[]};details=[];pending=[]
    for inp in inputs:
        row_id,kind=inp['id'].rsplit('-',1);expected=[k for k in keys if k[0]==row_id]
        entry=reservations.get(inp['id'])
        if entry is None:pending.append(inp['id']);continue
        i,r=entry;path=BASE/'calls'/f'call-{i:04d}'
        if r['status']=='completed':
            parsed=parse_output((path/'output.ttl').read_text(),expected)
            predictions[kind].extend(parsed['predictions']);details.append({'id':inp['id'],'schema_error':parsed['schema_error'],'missing_keys':parsed['missing_keys'],'predictions':parsed['predictions']})
        else:
            predictions[kind].extend({'row_id':a,'policy':b,'status':'error'} for a,b in expected)
            details.append({'id':inp['id'],'call_failure':r['status']})
    if pending:
        print(json.dumps({'pending':len(pending),'attempted':len(reservations),'details':details}));return
    metrics={kind:score(refs,rows) for kind,rows in predictions.items()}
    py=[{'row_id':r['row_id'],'policy':ref['policy'],'status':evaluate_python(r['data'],ref['policy'])} for r in selected for ref in refs if ref['row_id']==r['row_id']]
    sh=[];wanted=set(keys)
    for path in Path('_workspace/retail-evaluation/row-compare-full-v1').glob('batch-*.json'):
        sh.extend(d for d in json.loads(path.read_text())['shacl']['decisions'] if (d['row_id'],d['policy']) in wanted)
    metrics['authored_python']=score(refs,py);metrics['reused_authored_shacl']=score(refs,sh)
    gm={(r['row_id'],r['policy']):r['status'] for r in refs};pm={a:{(r['row_id'],r['policy']):r['status'] for r in rs} for a,rs in predictions.items()}
    paired_counts=Counter()
    for k,g in gm.items():
        a,b=pm['raw'].get(k,'missing_output'),pm['metadata'].get(k,'missing_output')
        paired_counts['both_correct' if a==g and b==g else 'metadata_only_correct' if b==g else 'raw_only_correct' if a==g else 'neither_correct']+=1
    result={'scope':'Consumed development diagnostic, single model/repeat, authored-policy references not business truth','model':MODEL,'rows':24,'calls':len(reservations),'metrics':metrics,'paired_policy_counts':dict(paired_counts),'reported_usd':sum(r.get('reported_usd') or 0 for _,r in reservations.values()),'reserved_usd':sum(r['upper_usd'] for _,r in reservations.values()),'reference_support':dict(Counter(r['status'] for r in refs)),'details':details,'limitations':['Three policies per row correlated; not72independent model calls','SHACL traces reused; no new SHACL latency','Metadata treatment adds computed parsing, not RDF reasoning','No generated-code arms, human labor or heldout outcomes']}
    write_new(BASE/'result.json',result);write_new(BASE/'references.json',refs)
    print(json.dumps({k:v for k,v in result.items() if k not in ('metrics','details')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','evaluate']);args=p.parse_args()
    prepare() if args.action=='prepare' else evaluate()
