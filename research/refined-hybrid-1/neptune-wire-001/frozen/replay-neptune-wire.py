import hashlib,json,shutil
from pathlib import Path
from urllib.parse import parse_qs
from scripts.graphrag_neptune_codec import outgoing_request,outgoing_response,QUERY
paths=['research/refined-hybrid-1/neo4j-retrieval-001/queries.jsonl','scripts/graphrag_neptune_codec.py','tests/test_graphrag_neptune_codec.py',__file__]
hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
out=Path('research/refined-hybrid-1/neptune-wire-001');out.mkdir(exist_ok=False)
summary={'status':'failed','planned':24,'neptune_calls':0,'fixture_origin':'actual saved Neo4j rows rewrapped as simulated Neptune results; not Neptune responses'};rows=[]
try:
 records=[json.loads(x) for x in Path(paths[0]).read_text().splitlines()]
 if len(records)!=24:raise ValueError('unexpected query count')
 (out/'frozen').mkdir()
 for p in paths:shutil.copyfile(p,out/'frozen'/Path(p).name)
 (out/'manifest.json').write_text(json.dumps({'hashes':hashes,'scope':'offline wire contract only','official_sources_checked':'2026-11-02','sources':['https://docs.aws.amazon.com/neptune/latest/userguide/access-graph-opencypher-queries.html','https://docs.aws.amazon.com/neptune/latest/userguide/opencypher-parameterized-queries.html']},indent=2))
 for i,r in enumerate(records):
  item={'index':i,'status':'error'}
  try:
   req=outgoing_request('neptune-future-namespace',r['starts'])
   params=parse_qs(req['body'].decode());assert params['query']==[QUERY]
   assert json.loads(params['parameters'][0])=={'run':'neptune-future-namespace','starts':sorted(set(r['starts']))}
   raw=json.dumps({'results':r['rows']},ensure_ascii=False,separators=(',',':')).encode()
   parsed=outgoing_response(200,raw,r['starts']);assert parsed==r['rows']
   (out/f'{i:02}.request.form').write_bytes(req['body'])
   (out/f'{i:02}.simulated-response.json').write_bytes(raw)
   item.update(status='ok',row_count=len(parsed),request_sha256=hashlib.sha256(req['body']).hexdigest(),simulated_response_sha256=hashlib.sha256(raw).hexdigest())
  except Exception as exc:item['error']=f'{type(exc).__name__}: {exc}'
  rows.append(item)
  (out/'results.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
 for p,h in hashes.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
 summary.update(status='completed' if all(x['status']=='ok' for x in rows) else 'partial_failure',ok=sum(x['status']=='ok' for x in rows),row_occurrences=sum(x.get('row_count',0) for x in rows))
except Exception as exc:
 summary['error']=f'{type(exc).__name__}: {exc}';raise
finally:
 summary.update(processed=len(rows),unprocessed=24-len(rows))
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
