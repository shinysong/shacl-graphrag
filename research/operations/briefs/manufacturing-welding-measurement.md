# Bounded original welding measurement sufficiency diagnostic
Purpose: distinguish unacquired measurement source from absent facts and unverified joins. Existing consumed PP6 annotation row2 has bead1/setting1, sample66244..72493 and x106..116. Nominal setting450A. Newly acquired via strict bounded HTTP206 archive ranges: PP6 README2653bytes SHA311232a904e6b33bd7354218556563dc653a88322b92707f30484cdd0effe131 and PP6_01.hdf5 6147189bytes SHA39afbb59a225d520ecff08b928c39f0be26e0cd30022a28189d103dea0be3191. DOI10.5281/zenodo.15083865 CC-BY4. ZIP CRC verified; full12.7GB archive notdownloaded/checksummed. Acquisition/read-only inspection already done, not blinded. Preliminary12306data0/530304data1 rows; README boolean vs stored255; idx_data1 equals tablelength; coordinates differentranges. These are reviewpointers not corruption verdicts. Attributes may contain pickle text; never deserialize them.
Freeze six diagnostic outputs, every failure retains6slots. Both sources read-only, noDB/LLM/network during diagnostic. Four index-base/end-convention candidates shown together, no chosen candidate or validated defect-intervalmean. Filename/beadassociation only, calibration/coordinateframe/sourceindex convention/documentversion unverified. Conditional arithmetic not physical prescription. Raw HDF omitted from packet; reviewers must mark originalfilefacts unverified. Inspect code below; controls planned, notrun. No sourcepatch or runtimegold. Request <=250word independent review.

## diagnostic.py
```python
"""Read-only source sufficiency diagnostic; no deserialization of stored metadata."""
import json, hashlib
from pathlib import Path
import h5py
import numpy as np
IDS=['table_schema','current_channel','status_encoding','sampling_intervals','cross_table_index','annotation_alignment']
SHA='39afbb59a225d520ecff08b928c39f0be26e0cd30022a28189d103dea0be3191'

def inspect_arrays(a,b,annotation):
 if len(a)==0 or len(b)==0:raise ValueError('empty_table')
 if any(c not in a.dtype.names for c in ('process_status','timestamp','idx_data1','x')) or any(c not in b.dtype.names for c in ('current_a','timestamp')):raise ValueError('missing_field')
 if any(not np.isfinite(a[c]).all() for c in ('process_status','timestamp','idx_data1','x')) or any(not np.isfinite(b[c]).all() for c in ('current_a','timestamp')):raise ValueError('nonfinite')
 def temporal(t):
  d=np.diff(t);positive=d[d>0]
  return {'rows':len(t),'duration_seconds':float(t[-1]-t[0]),'nonpositive_intervals':int((d<=0).sum()),'median_positive_interval_seconds':float(np.median(positive)) if len(positive) else None,'effective_rows_minus_one_per_duration':float((len(t)-1)/(t[-1]-t[0])) if t[-1]>t[0] else None}
 idx=a['idx_data1'];n=len(b);x=a['x'];start=annotation['sample_init'];end=annotation['sample_end']
 if any(type(v) is not int for v in (start,end)) or not 0<=start<=end:raise ValueError('annotation_index_contract')
 candidates=[]
 for base in (0,1):
  for inclusive in (False,True):
   lo=start-base;hi=end-base+int(inclusive);valid=0<=lo<hi<=n
   candidates.append({'index_base':base,'end_inclusive':inclusive,'slice_start':lo,'slice_stop_exclusive':hi,'in_bounds':valid,'sample_count':hi-lo if valid else None,'mean_current_a_if_assumed':float(np.mean(b['current_a'][lo:hi])) if valid else None})
 values=[
  {'data0_rows':len(a),'data1_rows':len(b),'data0_fields':list(a.dtype.names),'data1_fields':list(b.dtype.names)},
  {'field':'data1/current_a','unit_source':'PP6 README: current of DC electrode [A]','finite_count':int(np.isfinite(b['current_a']).sum()),'calibration_verified':False,'not_nominal_setting':True},
  {'observed_values':np.unique(a['process_status']).tolist(),'readme_declares':'boolean','literal_zero_one_only':bool(np.isin(a['process_status'],[0,1]).all()),'interpretation':'Encoding mapping not verified; 255 is not automatically an invalid state'},
  {'data0':temporal(a['timestamp']),'data1':temporal(b['timestamp']),'readme_rates_hz':{'data0':66.7,'data1':5000},'interpretation':'Observed timestamp spacing is diagnostic; no source corruption inferred'},
  {'field':'data0/idx_data1','less_than_zero':int((idx<0).sum()),'equal_to_data1_length':int((idx==n).sum()),'greater_than_data1_length':int((idx>n).sum()),'decreases':int((np.diff(idx.astype(float))<0).sum()),'interpretation':'Undocumented index may be an exclusive boundary; equality to length is not automatically invalid'},
  {'annotation':annotation,'data0_x_range':[float(x.min()),float(x.max())],'annotation_x_interval_inside_raw_data0_range':bool(x.min()<=annotation['x_init_mm']<=annotation['x_end_mm']<=x.max()),'candidates':candidates,'selected_candidate':None,'applicable_document_version':None,'interpretation':'Filename and bead number suggest association only. Coordinate transform, index base/end convention, calibration and applicable document version remain unverified. Candidate means are conditional arithmetic, not a validated defect-interval measurement.'}
 ]
 return [{'id':i,'status':'completed','observation':v} for i,v in zip(IDS,values)]

def run(path,annotation,expected_sha=SHA):
 result={'planned':IDS,'rows':[],'scope':'One deliberately selected consumed-development PP6 bead file; source sufficiency, not QA or physical-process advice'}
 try:
  raw=Path(path).read_bytes()
  if len(raw)>7000000 or hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('source_hash_or_size')
  with h5py.File(path,'r') as f:
   for key in ('data0','data1'):
    if not isinstance(f.get(key,getlink=True),h5py.HardLink):raise ValueError('nonlocal_link')
    d=f[key]
    if not isinstance(d,h5py.Dataset) or d.ndim!=1 or d.size>1000000 or d.dtype.hasobject or d.is_virtual or d.external:raise ValueError('unsupported_dataset')
   a=f['data0'][:];b=f['data1'][:]
  result['rows']=inspect_arrays(a,b,annotation)
 except Exception as e:result['rows']=[{'id':i,'status':'failed','error':f'{type(e).__name__}: {e}'} for i in IDS]
 result['source_sha256']=expected_sha
 return result
if __name__=='__main__':
 import sys
 annotation=json.loads(Path(sys.argv[2]).read_text());result=run(sys.argv[1],annotation)
 Path(sys.argv[3]).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
 print({s:sum(r['status']==s for r in result['rows']) for s in ('completed','failed')})

```

## check.py
```python
import numpy as np,tempfile
from pathlib import Path
import diagnostic as d
A=np.zeros(4,dtype=[('process_status','f8'),('timestamp','f8'),('idx_data1','i8'),('x','f8')]);B=np.zeros(10,dtype=[('current_a','f8'),('timestamp','f8')]);A['timestamp']=[0,1,2,3];A['idx_data1']=[0,3,8,10];A['x']=[500,510,520,530];A['process_status']=[0,255,255,0];B['timestamp']=np.arange(10)/5;B['current_a']=np.arange(10)
annotation={'sample_init':2,'sample_end':5,'x_init_mm':10,'x_end_mm':20}
r=d.inspect_arrays(A,B,annotation);assert len(r)==6 and [x['id'] for x in r]==d.IDS
assert r[2]['observation']['literal_zero_one_only'] is False
assert r[4]['observation']['equal_to_data1_length']==1 and r[4]['observation']['greater_than_data1_length']==0
v=r[5]['observation'];assert v['selected_candidate'] is None and not v['annotation_x_interval_inside_raw_data0_range'];assert [x['sample_count'] for x in v['candidates']]==[3,4,3,4];assert [x['mean_current_a_if_assumed'] for x in v['candidates']]==[3,3.5,2,2.5]
for bad in [dict(annotation,sample_init=-1),dict(annotation,sample_end=1)]:
 try:d.inspect_arrays(A,B,bad)
 except ValueError:pass
 else:raise AssertionError('invalid index accepted')
a=A.copy();a['x'][0]=float('nan')
try:d.inspect_arrays(a,B,annotation)
except ValueError:pass
else:raise AssertionError('nonfinite accepted')
with tempfile.TemporaryDirectory() as td:
 for path in [Path(td)/'missing.h5',Path(td)/'bad.h5']:
  if path.name=='bad.h5':path.write_bytes(b'invalid')
  r=d.run(path,annotation);assert len(r['rows'])==6 and all(x['status']=='failed' for x in r['rows'])
print('baseline, encoding/boundary, four candidate arithmetic, invalid index, nonfinite, missing and hash controls passed')

```
