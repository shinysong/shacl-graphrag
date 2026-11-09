import hashlib,json,sys
from pathlib import Path
ROOT=Path('research/manufacturing-model-change-1')
def build(base,out,live_run=None):
 source=Path(base).read_text()
 if 'id="hierarchy-demo"' in source:raise ValueError('already_extended')
 cfg=json.loads((ROOT/'subtype-offline-001/config.json').read_text())
 for item in cfg['sources']:
  if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['projection_sha256']:raise ValueError('projection_hash_mismatch')
 nodes=[json.loads(Path(s['path']).read_text())['nodes'] for s in cfg['sources']]
 rows=[json.loads(l) for l in (ROOT/'subtype-offline-001/rows.jsonl').read_text().splitlines()]
 identity=lambda r:(r['source_index'],r['kind'],r['target'],r['arm'])
 expected={(q['source_index'],q['kind'],q['target'],arm) for q in cfg['questions'] for arm in ('asserted','python_transitive','owlrl_transitive')}
 if len(rows)!=744 or len({identity(r) for r in rows})!=744 or {identity(r) for r in rows}!=expected:raise ValueError('offline_denominator')
 if live_run:
  p=Path(live_run);live_rows=[json.loads(l) for l in (p/'rows.jsonl').read_text().splitlines()];plan=json.loads((p/'plan.json').read_text())
  identity=lambda r:(r['source_index'],r['kind'],r['target'],r['arm'])
  if len(live_rows)!=992 or len({identity(r) for r in live_rows})!=992 or {identity(r) for r in live_rows}!={identity(r) for r in plan}:raise ValueError('live_denominator')
  rows+=live_rows
 d={'sources':cfg['sources'],'nodes':[{k:{'class':n['class'],'browse':n['browse']} for k,n in ns.items()} for ns in nodes],'rows':rows,'witnesses':[r for r in json.loads((ROOT/'witness-001/offline-witnesses.json').read_text())['reports'] if r['arm']=='owlrl_transitive'],'cases':json.loads((ROOT/'advisory-metadata-001/fixtures.json').read_text()),'advisory':[json.loads(l) for l in (ROOT/'advisory-metadata-001/rows.jsonl').read_text().splitlines()],'live_run':str(live_run) if live_run else None}
 change=json.loads((ROOT/'query-footprint-001/results.json').read_text())
 if len(change['rows'])!=124 or len({(r['kind'],r['target']) for r in change['rows']})!=124:raise ValueError('change_denominator')
 d['change']=change
 data=json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
 fragment=Path(__file__).with_name('fragment.html').read_text().replace('__HD_DATA__',data)
 if source.count('</body>')!=1:raise ValueError('body_contract')
 Path(out).parent.mkdir(parents=True,exist_ok=True)
 Path(out).write_text(source.replace('</body>',fragment+'\n</body>'))
 print({'rows':len(rows),'witnesses':len(d['witnesses']),'cases':len(d['cases']),'live_run':d['live_run']})
if __name__=='__main__':build(sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None)
