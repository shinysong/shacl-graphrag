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
