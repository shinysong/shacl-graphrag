"""One authorized final-answer pass; no tools, no retries, no gold in messages."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from apps.factory_lab.store import Store, WORK, dumps
from apps.factory_lab.llm import Gateway

INPUT=ROOT/'research/virtual-factory-llm-1/diagnostic/run-001'


def plan():
    hashes=json.loads((INPUT/'artifact-sha256.json').read_text())
    paths=sorted((INPUT/'runtime').glob('*.json'))
    if len(paths)!=36:raise RuntimeError('Expected exactly 36 frozen packets')
    rows=[]
    for p in paths:
        if hashlib.sha256(p.read_bytes()).hexdigest()!=hashes[str(p.relative_to(INPUT))]:
            raise RuntimeError('Frozen packet changed')
        value=json.loads(p.read_text())
        if set(value)!={'messages'}:raise RuntimeError('Runtime packet contract')
        if [x['role'] for x in value['messages']]!=['system','user']:raise RuntimeError('Message roles')
        rows.append((p,value['messages']))
    return rows


def execute(out, authorization):
    auth=json.loads(authorization.read_text())
    gate=json.loads((WORK/'execution-gate.json').read_text())
    relative=str(Path(__file__).resolve().relative_to(ROOT))
    if gate['files'].get(relative)!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        raise RuntimeError('Runner not bound to reviewed execution gate')
    if auth['max_attempts']!=36 or auth['existing_total_cap_usd']!='5.00':raise RuntimeError('Invalid authorization')
    session=json.loads((WORK/'session.json').read_text())
    if session['deadline']!=auth['deadline']:raise RuntimeError('Window mismatch')
    rows=plan()
    if auth['input_manifest_sha256']!=hashlib.sha256((INPUT/'artifact-sha256.json').read_bytes()).hexdigest():
        raise RuntimeError('Authorization input mismatch')
    out.mkdir(parents=True,exist_ok=False)
    store=Store();gateway=Gateway(store)
    (out/'authorization.json').write_text(dumps(auth))
    (out/'model.json').write_bytes((WORK/'model.json').read_bytes())
    (out/'budget-before.json').write_text(dumps(store.budget()))
    records=[{'packet':str(p.relative_to(INPUT)),'status':'not_attempted','reason':'pending'} for p,_ in rows]
    def save():
        (out/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
        (out/'budget-after.json').write_text(dumps(store.budget()))
    save()
    for i,((p,messages),rec) in enumerate(zip(rows,records)):
        if datetime.now(timezone.utc)>=datetime.fromisoformat(auth['deadline']):
            rec['reason']='window_expired';save();break
        # Event/call ledger shares the existing budget; batch episodes are not live UI runs.
        rid=uuid.uuid4().hex;rec.update(status='started',reason=None,trace_id=rid)
        save()
        try:
            message=gateway.call(rid,messages)
            if message.get('tool_calls') or not isinstance(message.get('content'),str) or not message['content'].strip():
                raise RuntimeError('Invalid final content')
            rec.update(status='completed',answer=message['content'])
        except Exception as e:
            rec.update(status='failed',error_type=type(e).__name__,error=str(e)[:300])
            # Unresolved/failed paid attempts retained. Stop rather than retry or spend on a broken provider.
            for pending in records[i+1:]:pending['reason']='stopped_after_failure'
            save();break
        save();print(dumps({'index':i+1,'total':len(records),'status':rec['status']}),flush=True)
    return {'completed':sum(r['status']=='completed' for r in records),
            'failed':sum(r['status']=='failed' for r in records),
            'not_attempted':sum(r['status']=='not_attempted' for r in records),
            'planned':len(records),'budget_after':store.budget()}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--authorization',type=Path,required=True)
    a=p.parse_args();print(dumps(execute(a.out,a.authorization)))
