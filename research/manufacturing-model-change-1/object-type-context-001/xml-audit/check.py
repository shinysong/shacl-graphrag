import audit as a,json,copy
from pathlib import Path
p=Path(__file__).parent.parent;cfg=json.loads((p/'config.json').read_text());x=json.loads((p/'observed.json').read_text());r=a.audit(cfg,x)
assert r['planned']==1200 and r['denominator_matches'] and r['source_object_universe_matches'] and all(v['status']=='scored' and v['equal'] for v in r['rows'])
y=copy.deepcopy(x);y['rows'][0]['types']=['invented'];r=a.audit(cfg,y);assert not r['rows'][0]['equal']
y=copy.deepcopy(x);y['rows'].pop();assert not a.audit(cfg,y)['denominator_matches']
y=copy.deepcopy(cfg);y['sources'][0]['main']['sha256']='0'*64;r=a.audit(y,x);assert sum(v['status']=='unscorable_source' for v in r['rows'])==600
print('1200originalXML/BFS matches; wrongtype/missingrow/badsource600unscorable controls passed')
