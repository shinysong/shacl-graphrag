"""Bounded actual selected-B C/E retrieval; no references or generation."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import resource
import shutil
import time
from scripts.graphrag_expand import canonical
from scripts.graphrag_relation_pack import relation_pack


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def accounting(seed, row):
    selected=set(row.get('selected_chunk_ids', []))
    eligible=row.get('eligible_chunk_ids', [])
    return dict(displaced_seed_ids=[x for x in seed.get('selected_chunk_ids', []) if x not in selected],
                first8_excluded_ids=[x for x in row.get('candidate_chunk_ids', []) if x not in eligible]
                if eligible else [],
                candidate_selection_reached=bool(eligible))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();rows=[];summary={'status':'started','planned_pairs':24,'planned_arm_rows':48,'new_model_calls':0}
    try:
        resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
        manifest=json.loads(args.manifest.read_text());paths=manifest['paths']
        for p,h in manifest['hashes'].items():
            if sha(p)!=h:raise ValueError('hash mismatch: '+p)
        if importlib.metadata.version('tokenizers')!='0.22.1':raise ValueError('tokenizer runtime mismatch')
        from tokenizers import Tokenizer
        tokenizer=Tokenizer.from_file(paths['tokenizer']);tokenizer.no_padding();tokenizer.no_truncation()
        count=lambda text:len(tokenizer.encode(text).ids)
        source=json.loads(Path(paths['source']).read_text())
        seeds=[json.loads(x) for x in Path(paths['B']).read_text().splitlines()]
        ids=manifest['question_ids']
        if len(ids)!=24 or len(set(ids))!=24 or [r['question_id'] for r in seeds]!=ids:raise ValueError('question universe mismatch')
        fanout=Counter(e['subject'] for e in source['edges'])
        observed={'nodes':len(source['nodes']),'edges':len(source['edges']),'chunks':len(source['chunks']),'max_outgoing':max(fanout.values(),default=0),'source_bytes':Path(paths['source']).stat().st_size}
        if observed!=manifest['source_inventory']:raise ValueError('source inventory mismatch')
        frozen=args.output/'frozen';frozen.mkdir()
        for name,p in paths.items():
            if name!='tokenizer':shutil.copyfile(p,frozen/Path(p).name)
        for p in manifest['hashes']:
            if p.startswith('scripts/') or p.endswith('.md'):shutil.copyfile(p,frozen/Path(p).name)
        shutil.copyfile(args.manifest,args.output/'manifest.json')
        handles={arm:(args.output/f'{arm}.jsonl').open('w') for arm in ('C','E')}
        parity=[]
        try:
            for seed in seeds:
                pair=[]
                for arm,backend in [('C','adjacency'),('E','sqlite')]:
                    row={'question_id':seed['question_id'],'arm':arm,'generation_executed':False,'source_sha256':manifest['hashes'][paths['source']]}
                    try:
                        if time.monotonic()-started>110:raise TimeoutError('internal elapsed limit')
                        row.update(relation_pack(source,seed,count,backend))
                    except Exception as exc:
                        row.update(status='retrieval_error',error=f'{type(exc).__name__}: {exc}',selected_chunk_ids=[],selected_chunks=[])
                    row.update(accounting(seed,row));rows.append(row);pair.append(row)
                    handles[arm].write(json.dumps(row,ensure_ascii=False)+'\n');handles[arm].flush()
                left={k:v for k,v in pair[0].items() if k not in ('arm','backend')}
                right={k:v for k,v in pair[1].items() if k not in ('arm','backend')}
                parity.append({'question_id':seed['question_id'],'exact_except_backend':left==right,'both_ok':all(r['status']=='ok' for r in pair)})
        finally:
            for h in handles.values():h.close()
        (args.output/'parity.json').write_text(json.dumps(parity,indent=2))
        for p,h in manifest['hashes'].items():
            if sha(p)!=h:raise ValueError('input changed during run: '+p)
        summary.update(status='completed',inventory=observed,parity_pairs=sum(p['exact_except_backend'] for p in parity))
    except Exception as exc:
        summary.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        summary.update(actual_arm_rows=len(rows),ok=sum(r['status']=='ok' for r in rows),failed_or_unexecuted=48-sum(r['status']=='ok' for r in rows),elapsed_seconds=time.monotonic()-started,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if summary['status']=='completed' and (summary['failed_or_unexecuted'] or summary['parity_pairs']!=24):summary['status']='partial_failure'
        (args.output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))

if __name__=='__main__':main()
