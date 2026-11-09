import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('identity',Path(__file__).with_name('runtime.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def row(i,location):return {'Incident_ID':i,'Location':location,'Equipment':'same name','Device':'motor'}
rows=[row('one','A'),row('two','B')]
for fields,count in [(['Equipment'],1),(['Location','Equipment'],0)]:
 r,*_=m.audit(rows,fields);assert r['findings_equal'] and len(r['python_findings'])==count
r,*_=m.audit([row('one','A'),row('two','')],['Equipment']);assert r['findings_equal'] and r['python_findings']==[['record','two','missing_location']]
try:m.audit([row('one','A'),row('one','B')],['Equipment'])
except ValueError:pass
else:raise AssertionError('duplicate accepted')
print('four software checks passed; no observed source run')

import tempfile,json
with tempfile.TemporaryDirectory() as tmp:
 base=Path(tmp)
 for i,body in enumerate([b'\xff', b'Incident_ID,Location,Equipment,Device,Device\na,A,x,y,z\n', b'Incident_ID,Location,Equipment,Device\na,A,x,y,extra\n', b'Incident_ID,Location,Equipment,Device\na,A,x\n', b'Incident_ID,Location,Equipment,Device\n"unterminated']):
  source=base/str(i);source.write_bytes(body)
  result=m.run(source,base/(str(i)+'out'))
  assert len(result)==3 and all(r['status']=='input_error' and r['phase']=='csv_parse' for r in result)
  assert json.loads((base/(str(i)+'out')/'results.json').read_text())==result
 result=m.run(base/'absent',base/'missingout')
 assert len(result)==3 and all(r['phase']=='acquisition' for r in result)
print('six additional failure retention checks passed')
