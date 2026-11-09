import runtime as r
import json,copy
from pathlib import Path
p={'types':{('o','B'),('x','B')},'edges':{('B','A')},'closure':{('B','A')},'allclasses':{'A','B'}}
for arm in r.ARMS:assert r.memberships(p,arm,{'o'})=={'o':['A','B']}
cfg=json.loads(Path(__file__).with_name('config.json').read_text());cfg=copy.deepcopy(cfg)
for s in cfg['sources']:s['main']['path']='/missing'
x=r.run(cfg);assert x['planned']==len(x['rows'])==1200 and all(q['status']=='source_failed' for q in x['rows'])
print('all-type set originalobjectfilter andfull1200failure controls passed')
