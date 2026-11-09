import copy,json
from pathlib import Path
import runtime as r
# No real source execution: small invented controls and full predeclared failure universe.
a={'models':[{'required':[{'ModelUri':'http://opcfoundation.org/UA/IA/','Version':'1','PublicationDate':'x'}]}],'nodes':{'a':{}}};b={'models':[{'attributes':{'ModelUri':'http://opcfoundation.org/UA/IA/','Version':'1','PublicationDate':'x'}}],'nodes':{'b':{}}}
assert set(r.combine(a,b)['nodes'])=={'a','b'} and set(a['nodes'])=={'a'}
c=copy.deepcopy(b);c['models'][0]['attributes']['PublicationDate']='y'
try:r.combine(a,c)
except ValueError as e:assert str(e)=='selected_exact_metadata_binding'
else:raise AssertionError('mismatch accepted')
c=copy.deepcopy(b);c['nodes']={'a':{}}
try:r.combine(a,c)
except ValueError as e:assert str(e)=='duplicate_definition_outside_contract'
else:raise AssertionError('duplicate accepted')
cfg=json.loads(Path(__file__).with_name('config.json').read_text());cfg=copy.deepcopy(cfg)
for s in cfg['sources']:s['main']['path']='/missing'
x=r.run(cfg);assert len(x['rows'])==x['planned']==992 and all(s['status']=='source_failed' for s in x['rows'])
print('merge/preserve original/exactmetadata/duplicate/full992missing-source controls passed')
