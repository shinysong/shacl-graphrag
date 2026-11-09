"""Bounded offline replay; freezes inputs before writing answers, keeps all slots."""
import argparse
import hashlib
import json
from pathlib import Path
from scripts.manufacturing_answer_adapter import adapt

BACKENDS={'sqlite_python','rdflib_offline','neo4j_cypher','neptune_sparql'}
QUESTIONS={f'Q{i}' for i in range(1,10)}


def run(source,policy_path,out,expected_source_hash,expected_policy_hash):
    out.mkdir(parents=True,exist_ok=False)
    manifest={'expected_source_hash':expected_source_hash,'expected_policy_hash':expected_policy_hash,
              'planned':36,'mode':'offline replay of historical backend bindings; no DB calls'}
    try:
        raw=source.read_bytes();policy_bytes=policy_path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_source_hash:raise ValueError('source_hash_mismatch')
        if hashlib.sha256(policy_bytes).hexdigest()!=expected_policy_hash:raise ValueError('policy_hash_mismatch')
        rows=[json.loads(x) for x in raw.decode().splitlines()]
        rows=[r for r in rows if r['case_id'] in QUESTIONS]
        keys=[(r['backend'],r['case_id']) for r in rows]
        if len(keys)!=36 or set(keys)!={(b,q) for b in BACKENDS for q in QUESTIONS}:raise ValueError('slot_universe_mismatch')
        policy=json.loads(policy_bytes)
    except Exception as exc:
        manifest.update(status='input_failure',completed=0,not_executed=36,error=type(exc).__name__+':'+str(exc))
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        return manifest
    (out/'inputs.json').write_text(json.dumps({'rows':rows,'policy':policy},indent=2)+'\n')
    outputs=[]
    for saved in rows:
        try:result=adapt(saved,policy)
        except Exception as exc:result={'backend':saved['backend'],'question_id':saved['case_id'],'status':'adapter_failure','error':type(exc).__name__+':'+str(exc)}
        outputs.append(result)
        with (out/'results.jsonl').open('a') as stream:stream.write(json.dumps(result,ensure_ascii=False)+'\n')
    counts={s:sum(r['status']==s for r in outputs) for s in sorted({r['status'] for r in outputs})}
    manifest.update(status='replay_complete',emitted=len(outputs),not_executed=36-len(outputs),counts=counts,
                    limits='Same hand-authored adapter/policy; not new LLM answers or live backend comparison. No external-truth assessment.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('source','policy','out'):parser.add_argument(name,type=Path)
    parser.add_argument('source_hash');parser.add_argument('policy_hash')
    args=parser.parse_args();print(json.dumps(run(args.source,args.policy,args.out,args.source_hash,args.policy_hash)))
