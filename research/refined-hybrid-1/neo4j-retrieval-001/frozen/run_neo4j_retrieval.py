"""Actual Neo4j outgoing traversal from frozen selected B; no scorer inputs."""
import argparse,hashlib,json,time,resource
from pathlib import Path
from scripts.graphrag_neo4j import Neo4jSource
from scripts.graphrag_db_pack import relation_pack
from scripts.run_graphrag_relations import accounting

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('manifest','output','endpoint','namespace'):p.add_argument('--'+key,required=True)
    a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    summary={'status':'failed','planned_questions':24,'paid_calls':0};rows=[];db=None;loaded=False;started=time.monotonic()
    try:
        resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
        m=json.loads(Path(a.manifest).read_text())
        for f,h in m['hashes'].items():
            if hashlib.sha256(Path(f).read_bytes()).hexdigest()!=h:raise ValueError('hash mismatch: '+f)
        import importlib.metadata
        if importlib.metadata.version('tokenizers')!='0.22.1':raise ValueError('tokenizer runtime')
        from tokenizers import Tokenizer
        t=Tokenizer.from_file(m['tokenizer']);t.no_padding();t.no_truncation();count=lambda text:len(t.encode(text).ids)
        src=json.loads(Path(m['source']).read_text());seeds=[json.loads(x) for x in Path(m['B']).read_text().splitlines()]
        if [x['question_id'] for x in seeds]!=m['question_ids'] or len(seeds)!=24:raise ValueError('question universe mismatch')
        db=Neo4jSource(a.endpoint,a.namespace);summary['version']=db.query('CALL dbms.components() YIELD name, versions, edition RETURN name,versions,edition');db.load(src);loaded=True
        original=db.outgoing
        with (out/'queries.jsonl').open('w') as qlog,(out/'N.jsonl').open('w') as log:
            def observed(starts):
                r=original(starts);qlog.write(json.dumps({'starts':starts,'rows':r})+'\n');qlog.flush();return r
            db.outgoing=observed
            for seed in seeds:
                row={'question_id':seed['question_id'],'arm':'N','generation_executed':False,'source_sha256':m['hashes'][m['source']]}
                try:
                    if time.monotonic()-started>110:raise TimeoutError('internal limit')
                    row.update(relation_pack(src,seed,count,db=db))
                except Exception as exc:row.update(status='retrieval_error',error=f'{type(exc).__name__}: {exc}',selected_chunk_ids=[],selected_chunks=[])
                row.update(accounting(seed,row));rows.append(row);log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
        for f,h in m['hashes'].items():
            if hashlib.sha256(Path(f).read_bytes()).hexdigest()!=h:raise ValueError('input changed')
        summary['status']='completed' if all(x['status']=='ok' for x in rows) else 'partial_failure'
    except Exception as exc:summary.update(status='failed',error=f'{type(exc).__name__}: {exc}');raise
    finally:
        if loaded:
            try:db.cleanup();summary['namespace_cleanup']=True
            except Exception as exc:summary.update(namespace_cleanup=False,cleanup_error=str(exc))
        summary.update(ok=sum(x['status']=='ok' for x in rows),failed_or_unexecuted=24-sum(x['status']=='ok' for x in rows))
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
