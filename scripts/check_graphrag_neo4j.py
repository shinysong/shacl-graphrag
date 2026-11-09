"""Load and verify source topology on an owned temporary local Neo4j instance."""
import argparse
import hashlib
import json
from pathlib import Path
from scripts.graphrag_expand import canonical, _index
from scripts.graphrag_neo4j import Neo4jSource


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--endpoint',required=True)
    p.add_argument('--namespace',required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    summary={'status':'failed','qa_executed':False};db=None;loaded=False
    try:
        m=json.loads(a.manifest.read_text())
        for path,h in m['hashes'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise ValueError('hash mismatch: '+path)
        src=json.loads(Path(m['source']).read_text());nodes,edges,_,nc,ec=_index(src)
        if (len(nodes),len(edges))!=(328,486):raise ValueError('bounded source count mismatch')
        (a.output/'manifest.json').write_text(json.dumps(m,indent=2))
        db=Neo4jSource(a.endpoint,a.namespace)
        summary['version']=db.query('CALL dbms.components() YIELD name, versions, edition RETURN name,versions,edition')
        db.load(src);loaded=True
        saved=db.query('MATCH (n:Evidence {run:$run}) RETURN n.id AS id,n.chunk_id AS chunk_id,n.payload AS payload ORDER BY id')
        assert saved==[{'id':i,'chunk_id':nc[i],'payload':canonical(nodes[i]).decode()} for i in sorted(nodes)]
        (a.output/'nodes.json').write_text(json.dumps(saved,indent=2))
        observations=[]
        with (a.output/'outgoing.jsonl').open('w') as f:
            for nid in sorted(nodes):
                actual=db.outgoing([nid]);expected=[{'subject':e['subject'],'edge_id':i,'target':e['target'],'chunk_id':ec[i],'payload':canonical(e).decode()} for i,e in sorted(edges.items()) if e['subject']==nid]
                row={'node_id':nid,'rows':actual,'matches_source':actual==expected};observations.append(row);f.write(json.dumps(row)+'\n');f.flush()
        summary.update(status='completed',nodes=len(saved),edges=sum(len(r['rows']) for r in observations),queries=len(observations),mismatches=sum(not r['matches_source'] for r in observations))
        if summary['mismatches']:summary['status']='mismatch'
        for path,h in m['hashes'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise ValueError('input changed')
    except Exception as exc:
        summary.update(status='failed',error=f'{type(exc).__name__}: {exc}');raise
    finally:
        if db and loaded:
            try:db.cleanup();summary['namespace_cleanup']=True
            except Exception as exc:summary['namespace_cleanup']=False;summary['cleanup_error']=str(exc)
        (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))


if __name__=='__main__':main()
