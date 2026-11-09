"""OFFLINE EVALUATION ONLY. Never import from retrieval/generator/checker."""
from pathlib import Path
import hashlib
import json
from scripts.graphrag_check import canonical_bytes
from scripts.score_graphrag_support import score

ROOT=Path('research/answer-evidence-1')
OUT=ROOT/'evaluation-targets-001'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def lines(p): return [json.loads(s) for s in Path(p).read_text().splitlines()]


def main():
    OUT.mkdir(exist_ok=False)
    result={'planned':72,'status':'failed','access':'offline evaluator only; never runtime','generation_executed':False}
    try:
        paths={'source':Path('research/graphrag-evidence-1/source-corpus-v1.json'),
               'references':Path('research/graphrag-evidence-1/development-references.json'),
               'episodes':ROOT/'answer-inputs-001/episodes.jsonl',
               'input_bindings':ROOT/'answer-inputs-001/input-hashes.json',
               'scorer':Path('scripts/score_graphrag_support.py'),
               'parser':Path('scripts/graphrag_check.py'),'builder':Path(__file__)}
        for arm in 'BCD':
            for name,file in [('scores','scores.json'),('manifest','manifest.json')]:
                paths[arm+'_'+name]=ROOT/'anchor-support-001'/arm/file
            paths[arm+'_envelopes']=ROOT/'anchor-support-001/envelopes'/(arm+'.jsonl')
        hashes={k:sha(p) for k,p in paths.items()}
        frozen=OUT/'frozen';frozen.mkdir()
        for k,p in paths.items(): (frozen/(k+'-'+p.name)).write_bytes(p.read_bytes())
        (OUT/'input-hashes.json').write_bytes(canonical_bytes({'paths':{k:str(v) for k,v in paths.items()},'hashes':hashes}))
        bindings=read(paths['input_bindings'])
        for key in ['source','questions','rows','design','schema','system','prior_manifest','parser','builder']:
            if sha(bindings['paths'][key])!=bindings['hashes'][key]:raise ValueError('prepared input binding changed')
        source=read(paths['source']);refs=read(paths['references'])
        refmap={r['question_id']:r for r in refs['references']}
        if len(refmap)!=24 or len(refs['references'])!=24:raise ValueError('reference universe')
        eps=lines(paths['episodes']);emap={(e['question_id'],e['arm']):e for e in eps}
        if len(eps)!=72 or len(emap)!=72 or set(emap)!={(q,a) for q in refmap for a in 'BCD'}:raise ValueError('episode universe')
        rows=[]
        for a in 'BCD':
            manifest=read(paths[a+'_manifest'])
            for p,h in manifest.items():
                if sha(p)!=h:raise ValueError('old support input changed')
            envs=lines(paths[a+'_envelopes']);evmap={e['question_id']:e for e in envs}
            actual=score(source,refs,envs)
            if actual!=read(paths[a+'_scores']):raise ValueError('saved score replay mismatch')
            for s in actual['results']:
                q=s['question_id'];e=emap[q,a];ref=refmap[q];env=evmap[q]
                if s['retrieval_state']!='valid_saved_evidence':raise ValueError('invalid support envelope')
                if hashlib.sha256(canonical_bytes(e['messages'])).hexdigest()!=e['message_sha256']:raise ValueError('message hash')
                body=json.loads(e['messages'][1]['content'])
                if body['evidence']!=env['selected_chunks'] or e['evidence_sha256']!=env['evidence_sha256']:raise ValueError('prepared evidence mismatch')
                present=s['evidence_state']=='present_in_supplied_bundle'
                support=bool(s['complete_support']) if present else False
                rows.append({'field_id':e['episode_id']+':primary_target','episode_id':e['episode_id'],'question_id':q,'arm':a,
                             'target_task':ref['task'],'target_record':ref['target_record'],'reference_value':ref['reference_value'],
                             'unit':ref['unit'],'interpretation':ref['interpretation'],'source_state':s['evidence_state'],
                             'selected_support':support,'support_basis':'authored frozen node-set contract, not general semantic answerability',
                             'message_sha256':e['message_sha256'],'execution_status':'not_attempted','withheld':None})
        if any(sha(p)!=hashes[k] for k,p in paths.items()):raise ValueError('inputs changed')
        (OUT/'fields.json').write_bytes(canonical_bytes(rows))
        result.update(status='ok',fields=len(rows),eligible_by_arm={a:sum(r['selected_support'] for r in rows if r['arm']==a) for a in 'BCD'},
                      source_absent=sum(r['source_state']=='absent_from_supplied_bundle' for r in rows),
                      source_present_retrieval_omission=sum(r['source_state']=='present_in_supplied_bundle' and not r['selected_support'] for r in rows),
                      limitation='One primary target per episode only; citation, qualifier, interpretation and partial-field rubrics remain separate. No normalization or semantic judging implemented.')
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
    (OUT/'summary.json').write_bytes(canonical_bytes(result));print(json.dumps(result))
    return 0 if result['status']=='ok' else 1

if __name__=='__main__':raise SystemExit(main())
