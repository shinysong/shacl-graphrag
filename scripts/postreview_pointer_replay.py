"""Strict pointer/value diagnostic on saved outputs; not semantic citation scoring.

No fuzzy locator repair, question interpretation, evaluation gold or new source
lookup. A mismatch may be a metadata assertion or ambiguous locator, not an error
in the answer. Units and natural-language coverage remain unverified.
"""
import argparse,hashlib,json,re
from pathlib import Path
from collections import Counter
from scripts.post_answer_review import review,token
from scripts.graphrag_check import canonical_bytes
from scripts.run_post_answer_demo import dump,sha
INPUTS=Path('research/answer-evidence-1/answer-inputs-001/episodes.jsonl')
ANSWERS=Path('research/answer-evidence-1/final-answers-001/outcomes.jsonl')


def resolve(node,locator):
    """Return (resolved scalar, supported syntax) without interpreting prose."""
    if not isinstance(locator,str):return None,False
    match=re.fullmatch(r'(values|dictionary_refs|field_cells)\.([A-Za-z_][A-Za-z_0-9]*)',locator)
    if match:
        container=node.get(match[1]);key=match[2]
        if not isinstance(container,dict) or key not in container:return None,False
        value=container[key]
        if match[1]=='values':
            address=node.get('field_cells',{}).get(key)
            cells=[c for c in node.get('cells',[]) if c.get('cell')==address]
            if len(cells)!=1 or cells[0].get('formula') is not None:return None,False
            if token(cells[0]['value'])!=token(value):raise ValueError('source field/cell inconsistency')
        token(value);return value,True
    match=re.fullmatch(r'values\[(\d+)\]',locator)
    if match:
        values=node.get('values');i=int(match[1]);cells=node.get('cells',[])
        if not isinstance(values,list) or i>=len(values) or i>=len(cells):return None,False
        if cells[i].get('formula') is not None:return None,False
        if token(values[i])!=token(cells[i]['value']):raise ValueError('source values/cells inconsistency')
        token(values[i]);return values[i],True
    match=re.fullmatch(r'cells\[(\d+)\]\.(cell|value)',locator)
    if match:
        cells=node.get('cells',[]);i=int(match[1]);key=match[2]
        if i>=len(cells) or key not in cells[i]:return None,False
        if key=='value' and cells[i].get('formula') is not None:return None,False
        token(cells[i][key]);return cells[i][key],True
    match=re.fullmatch(r'(?:cells\.)?([A-Z]+[1-9][0-9]*)',locator)
    if match:
        cells=[c for c in node.get('cells',[]) if c.get('cell')==match[1]]
        if len(cells)!=1 or cells[0].get('formula') is not None:return None,False
        token(cells[0]['value']);return cells[0]['value'],True
    return None,False


def packet_for(answer,evidence):
    nodes={}
    for chunk in evidence:
        if chunk['chunk_id'] in nodes:raise ValueError('duplicate chunk')
        node=json.loads(chunk['text'])
        if not isinstance(node,dict):raise ValueError('source JSON object')
        nodes[chunk['chunk_id']]=node
    claims=[];source_fields={sid:{} for sid in nodes};mapping=[]
    for i,claim in enumerate(answer['claims']):
        citations=claim['citations'] or [{'chunk_id':None,'locator':None}]
        for k,citation in enumerate(citations):
            sid=citation['chunk_id'];locator=citation['locator'];node=nodes.get(sid)
            value,supported=resolve(node,locator) if node is not None else (None,False)
            field=f'pointer/{i}/{k}' if supported else None;cid=f'claim/{i}/citation/{k}'
            if supported:source_fields[sid][field]={'value':value,'unit':None,'locator':locator}
            claims.append({'claim_id':cid,'kind':claim['kind'],'source_id':sid,'field':field,'value':claim['value'],'unit':claim['unit']})
            mapping.append({'check_claim_id':cid,'original_claim_index':i,'original_citation_index':k if claim['citations'] else None,'locator':locator,'pointer_resolved':supported,'claim_text':claim['text'],'claimed_value':claim['value'],'selected_pointer_value':value})
    return {'claims':claims,'sources':[{'source_id':sid,'fields':fields} for sid,fields in source_fields.items()]},mapping


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    input_rows=list(map(json.loads,INPUTS.read_text().splitlines()))
    inputs={r['episode_id']:r for r in input_rows}
    answers=list(map(json.loads,ANSWERS.read_text().splitlines()))
    if len(input_rows)!=72 or len(inputs)!=72 or len(answers)!=72 or len({r['episode_id'] for r in answers})!=72 or set(inputs)!={r['episode_id'] for r in answers}:raise ValueError('full episode manifest')
    rows=[]
    for answer in answers:
        eid=answer['episode_id'];entry=inputs[eid]
        if hashlib.sha256(canonical_bytes(entry['messages'])).hexdigest()!=entry['message_sha256'] or entry['message_sha256']!=answer['message_sha256']:raise ValueError('saved input binding')
        row={'episode_id':eid,'original_status':answer['status'],'replay_status':'not_attempted_original_failure'}
        if answer['status']!='completed':rows.append(row);continue
        try:
            evidence=json.loads(entry['messages'][1]['content'])['evidence']
            packet,mapping=packet_for(answer['answer'],evidence)
            from scripts.post_answer_review import validate_packet
            validate_packet(packet)
        except (ValueError,TypeError,KeyError,AttributeError,IndexError) as exc:
            row.update(replay_status='input_failure',error_type=type(exc).__name__);rows.append(row);continue
        row.update(replay_status='completed',original_claim_items=len(answer['answer']['claims']),mapping=mapping,engines=[])
        for engine in ('python','pyshacl'):
            result={'engine':engine,'execution':'completed'}
            try:result['report']=review(packet,engine)
            except Exception as exc:result.update(execution='execution_failure',error_type=type(exc).__name__);row['replay_status']='execution_failure'
            row['engines'].append(result)
        a,b=row['engines'];row['engines_agree']=a['execution']==b['execution'] and a.get('report',{}).get('results')==b.get('report',{}).get('results')
        rows.append(row)
    dump(out/'outcomes.json',rows)
    summary={'episodes':len(rows),'episode_statuses':dict(Counter(r['replay_status'] for r in rows)),'claim_items_in_processed_answers':sum(r.get('original_claim_items',0) for r in rows),'empty_claim_answers':sum(r.get('original_claim_items')==0 for r in rows),'pointer_entries':sum(len(r.get('mapping',[])) for r in rows),'resolved_pointer_entries':sum(m['pointer_resolved'] for r in rows for m in r.get('mapping',[])),'python_value_statuses':dict(Counter(c['status'] for r in rows for e in r.get('engines',[]) if e['engine']=='python' for c in e.get('report',{}).get('results',[]) if c['check_id']=='value_agreement')),'completed_engine_parity':all(r.get('engines_agree') for r in rows if r['replay_status']=='completed'),'paid_calls':0,'limits':['posthoc consumed development outputs','strict pointer/value contract is not semantic citation accuracy','flags require review of claim intent and metadata assertions','no units, question applicability, text coverage or revision efficacy measured','paired engine results share resolver; not independent semantic replication']}
    dump(out/'summary.json',summary)
    dump(out/'manifest.json',{'inputs':{str(p):sha(p) for p in [INPUTS,ANSWERS,Path(__file__),Path('scripts/post_answer_review.py')]},'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
    print(json.dumps(summary))
    if not summary['completed_engine_parity'] or any(r['replay_status'] in ('input_failure','execution_failure') for r in rows):raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
