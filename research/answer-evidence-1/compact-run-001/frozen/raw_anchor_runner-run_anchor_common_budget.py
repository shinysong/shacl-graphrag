"""Anchor-on common-message diagnostic; no generator or scorer clients."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

# Historical resolver uses a script-local import; pin that directory explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripts.graphrag_explicit_anchor import resolve
from scripts.graphrag_anchor_candidates import inject_anchor
from scripts.graphrag_expand import expand
from scripts.graphrag_message_pack import pack_base
from scripts.graphrag_report_budget import account_report
from scripts.graphrag_shacl_binding import shacl_binding
from scripts.graphrag_check import canonical_bytes


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    m=json.loads(a.manifest.read_text());paths=m['paths']
    planned=[dict(question_id=q,arm=arm) for q in m['question_ids'] for arm in ('A1','B','C','E','D')]
    save(a.output/'planned.json',dict(rows=planned,consumed_development=True,generation_executed=False))
    if len(planned)!=120 or len(set(m['question_ids']))!=24:raise ValueError('expected24questions')
    if sys.flags.optimize:raise ValueError('assertions must remain enabled')
    for key,path in paths.items():
        if digest(path)!=m['hashes'][key]:raise ValueError('input hash mismatch:'+key)
    if m.get('anchor_enabled') is not True:raise ValueError('anchor must be enabled')
    versions={k:importlib.metadata.version(k) for k in ('tokenizers','pyshacl','rdflib')}
    if versions!={'tokenizers':'0.22.1','pyshacl':'0.40.1','rdflib':'7.6.0'}:raise ValueError('runtime version mismatch')
    save(a.output/'runtime.json',dict(versions=versions,python=sys.version,assertions_enabled=True))
    frozen=a.output/'frozen';frozen.mkdir()
    for key,path in paths.items():(frozen/(key+'-'+Path(path).name)).write_bytes(Path(path).read_bytes())
    (a.output/'manifest.json').write_bytes(a.manifest.read_bytes())
    from tokenizers import Tokenizer
    from rdflib import Graph
    tok=Tokenizer.from_file(paths['tokenizer']);tok.no_padding();tok.no_truncation()
    count=lambda s:len(tok.encode(s).ids)
    source_bytes=Path(paths['source']).read_bytes()
    source=json.loads(source_bytes)
    qs=json.loads(Path(paths['questions']).read_text())['questions']
    candidates=json.loads(Path(paths['candidates']).read_text())
    if ([q['question_id'] for q in qs]!=m['question_ids'] or [r['question_id'] for r in candidates]!=m['question_ids']):raise ValueError('question order mismatch')
    shapes=Graph().parse(paths['shapes'],format='turtle')
    rows=[];parities=[]
    with (a.output/'rows.jsonl').open('w') as log:
        def emit(qid,arm,result,upstream):
            row=dict(question_id=qid,arm=arm,result=result,upstream=upstream,generation_executed=False)
            rows.append(row);log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
        for q,cs in zip(qs,candidates):
            qid=q['question_id'];base={}
            locator_error=None
            try:
                locator=resolve(q['question'],source_bytes)
                if (locator['source_sha256']!=m['hashes']['source'] or
                    locator['question_sha256']!=hashlib.sha256(q['question'].encode('utf-8')).hexdigest()):
                    raise ValueError('locator provenance mismatch')
            except Exception as exc:
                locator_error=type(exc).__name__
                locator=dict(status='execution_error',error=locator_error)
            save(a.output/(qid+'-locator.json'),locator)
            for arm in ('A1','B'):
                orig=cs['arms'][arm]
                upstream=dict(original=orig,locator=locator)
                try:
                    if locator_error:raise ValueError('locator execution failed')
                    if 'anchor_audit' in orig:raise ValueError('reserved anchor audit field')
                    anchored=inject_anchor(orig,locator)
                    upstream['anchored']=anchored
                    result=pack_base(q['question'],anchored['ordered_candidate_ids'],source,count,anchored['upstream_status'])
                except Exception as exc:result=dict(status='execution_error',error=type(exc).__name__)
                base[arm]=result;emit(qid,arm,result,upstream)
            expansions={}
            for arm,backend in (('C','adjacency'),('E','sqlite')):
                upstream=dict(B_status=base['B']['status'],B_error=base['B'].get('error'))
                try:
                    if base['B']['status']!='ok':
                        result=dict(status='upstream_error',error='B unsuccessful')
                    else:
                        exp=expand(source,base['B']['selected_chunk_ids'],backend=backend,max_depth=1,max_candidates=32,max_evidence_bytes=64000)
                        expansions[arm]=exp;upstream['expansion']=exp
                        if exp['status']!='ok':result=dict(status='upstream_error',error='expansion unsuccessful')
                        else:
                            ids=exp['candidate_chunk_ids'];upstream['excluded_after_eight']=ids[8:]
                            result=pack_base(q['question'],ids[:8],source,count)
                except Exception as exc:result=dict(status='execution_error',error=type(exc).__name__)
                base[arm]=result;emit(qid,arm,result,upstream)
            parity=dict(question_id=qid,status_equal=base['C']['status']==base['E']['status'],
                selected_equal=base['C'].get('selected_chunks')==base['E'].get('selected_chunks'),
                candidates_equal=expansions.get('C',{}).get('candidate_chunk_ids')==expansions.get('E',{}).get('candidate_chunk_ids'),
                both_success=base['C']['status']==base['E']['status']=='ok')
            parities.append(parity)
            upstream=dict(C_status=base['C']['status'],C_error=base['C'].get('error'))
            try:
                c=base['C']
                if c['status']!='ok':result=dict(status='upstream_error',error='C unsuccessful')
                else:
                    env=dict(status='ok',selected_chunks=c['selected_chunks'],selected_chunk_ids=c['selected_chunk_ids'],evidence_sha256=c['evidence_sha256'])
                    before=canonical_bytes(env)
                    report,data,rdf,text=shacl_binding(env,shapes)
                    sub=a.output/qid;sub.mkdir()
                    save(sub/'evidence.json',env);save(sub/'report.json',report)
                    data.serialize(sub/'data.ttl',format='turtle');rdf.serialize(sub/'report.ttl',format='turtle');(sub/'report.txt').write_text(str(text))
                    upstream.update(evidence_sha256=c['evidence_sha256'],checker_parity=report['parity'],evidence_unchanged=before==canonical_bytes(env))
                    compact={k:v for k,v in report.items() if k not in ('python_results','parity')}
                    save(sub/'compact-report.json',compact)
                    checked=account_report(q['question'],c,compact,count,'ok' if report['parity'] and before==canonical_bytes(env) else 'failed')
                    if checked['C']!=c:raise ValueError('C mutation')
                    result=checked['D']
                    result['selected_chunks']=c['selected_chunks'];result['selected_chunk_ids']=c['selected_chunk_ids']
            except Exception as exc:result=dict(status='validation_execution_error',error=type(exc).__name__)
            emit(qid,'D',result,upstream)
    stable=all(digest(path)==m['hashes'][key] for key,path in paths.items())
    summary=dict(planned=120,processed=len(rows),unprocessed=120-len(rows),
        statuses={arm:dict(Counter(r['result']['status'] for r in rows if r['arm']==arm)) for arm in ('A1','B','C','D','E')},
        parity=parities,input_hashes_stable=stable,generator_ready=False,generation_executed=False,paid_calls=0)
    save(a.output/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False))
    return 0 if stable and len(rows)==120 else 1


if __name__=='__main__':raise SystemExit(main())
