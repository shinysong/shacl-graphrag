Posthocconsistencydiagnostic,all4rowsalreadyinspected; notnewtruth orheldout.18candidates144endpointcomparisons. No winnerdeclaredverified. OriginalHDFandworkbookomittedunverified; summaryreadandoriginalworkbookhashchecked. Review<=250words.

## check.py
```
import diagnostic as d
assert d.quantize(3.5,'nearest_half_up')==4 and d.quantize(3.5,'floor')==3 and d.quantize(3.5,'ceil')==4
r=d.run('/missing');assert len(r['rows'])==144 and all(x['status']=='failed' for x in r['rows']) and r['selected_verified_mapping'] is None
assert len(d.CANDIDATES)==18 and len(set(d.CANDIDATES))==18
print('rounding and144failure denominator,18candidate universe controls passed')

```

## diagnostic.py
```
import json,hashlib,math,itertools
from pathlib import Path
WORKBOOK=Path('_workspace/actionable-source-audit/source/ZENODO_Penelope/PP6/2. ndt_data/defects_xlocation.xlsx')
SHA='7674d7522b4fcd40b9da4ec3f8b3843373614f39ecd6a70ab6a366d4010751d3'
DIAG=Path('research/manufacturing-measurement-1/diagnostic-001/diagnostic.json')
CANDIDATES=list(itertools.product(('declared5000','N/duration','(N-1)/duration'),('floor','nearest_half_up','ceil'),(0,1)))
def quantize(x,mode):return math.floor(x) if mode=='floor' else math.ceil(x) if mode=='ceil' else math.floor(x+0.5)
def run(workbook=WORKBOOK,diagnosis=DIAG):
 plan=[{'candidate':f'{rate}|{mode}|{offset}','rate':rate,'rounding':mode,'offset':offset,'excel_row':row,'endpoint':endpoint} for rate,mode,offset in CANDIDATES for row in (2,3,4,5) for endpoint in ('init','end')]
 try:
  import openpyxl
  if hashlib.sha256(Path(workbook).read_bytes()).hexdigest()!=SHA:raise ValueError('workbook_hash')
  data=json.loads(Path(diagnosis).read_text());obs={r['id']:r['observation'] for r in data['rows'] if r['status']=='completed'}
  h=obs['sampling_intervals']['data1'];n=h['rows'];duration=h['duration_seconds']
  if not isinstance(n,int) or n<=1 or not math.isfinite(duration) or duration<=0:raise ValueError('timestamp_summary')
  rates={'declared5000':5000,'N/duration':n/duration,'(N-1)/duration':(n-1)/duration}
  w=openpyxl.load_workbook(workbook,read_only=True,data_only=True);settings=list(w['welding_settings_code'].values);assert settings[1][7]=='ts (cm/min)' and settings[2][0]==1 and settings[2][7]==48
  allrows=list(w['PP6'].values);chosen={i:r for i,r in enumerate(allrows,1) if len(r)>=7 and r[2]==1};w.close()
  if set(chosen)!={2,3,4,5} or any(r[1]!=1 for r in chosen.values()):raise ValueError('bead_selection')
  output=[]
  for s in plan:
   r=chosen[s['excel_row']];ix=3 if s['endpoint']=='init' else 4;position=r[ix];stored=r[ix+2]
   if not isinstance(position,(int,float)) or not math.isfinite(position) or position<0 or type(stored)!=int:raise ValueError('endpoint_schema')
   unrounded=position/8*rates[s['rate']];pred=quantize(unrounded,s['rounding'])+s['offset'];output.append({**s,'status':'completed','position_mm':position,'stored_sample':stored,'predicted_sample':pred,'unrounded':unrounded,'residual':pred-stored,'exact':pred==stored})
  summaries=[{'candidate':f'{a}|{b}|{c}','endpoints':8,'exact':sum(r['exact'] for r in output if r['candidate']==f'{a}|{b}|{c}'),'max_abs_residual':max(abs(r['residual']) for r in output if r['candidate']==f'{a}|{b}|{c}')} for a,b,c in CANDIDATES]
  return {'planned':144,'rows':output,'candidates':summaries,'selected_verified_mapping':None,'source_workbook_sha256':SHA,'summary_sha256':hashlib.sha256(Path(diagnosis).read_bytes()).hexdigest(),'limitations':['Posthoc consumed4rows; family motivated by observed row2','Timestamp summary reused, not independently reparsed HDF in this phase','No proof of file association, physical coordinate mapping, calibration or endpoint inclusion','No change to prior paid answers']}
 except Exception as e:return {'planned':144,'rows':[{**s,'status':'failed','error':f'{type(e).__name__}: {e}'} for s in plan],'candidates':[],'selected_verified_mapping':None}
if __name__=='__main__':
 import sys
 Path(sys.argv[1]).write_text(json.dumps(run(),indent=2)+'\n')

```

## protocol.json
```
{
 "id":"manufacturing-alignment-001",
 "design":"Posthoc source-consistency diagnostic, not held-out inference or verified alignment",
 "prior_inspection":"PP6 row2 and all four bead1 rows inspected before this freeze; row2 approximately matches x/speed*(N-1)/duration with flooring",
 "source":"Original PP6 workbook bead1 rows, original archived data1 timestamp summary, nominal setting1 speed48cm/min",
 "candidate_family":{"rate":["declared5000","N/duration","(N-1)/duration"],"rounding":["floor","nearest_half_up","ceil"],"offset":[0,1]},
 "query":"Each candidate predicts both stored sample indices from position_mm/(48*10/60) * rate; compare all four rows/eight endpoints",
 "planned_candidate_endpoint_rows":144,
 "failure_policy":"On source hash/schema/selection error emit144failed slots; no partial denominator replacement",
 "interpretation":"Keep all18 candidate summaries, no selecting a verified mapping; arithmetic agreement cannot establish actual trajectory, calibration, slice endpoint semantics or author implementation. Nominal travel speed is read as source metadata, not an operating prescription.",
 "no_retroactive_change":"Do not change measurement-answer-001 frozen inputs, null judgments or original answers"
}

```

## freeze.json
```
{
  "research/manufacturing-measurement-1/alignment-001/check.py": "b31f6c7e76ac968f0bc9f4e3ce896d17d05a24c755b8e71385bd83dfd3dc4e73",
  "research/manufacturing-measurement-1/alignment-001/diagnostic.py": "02ef4bfce5ba634da155075847983e497a8bb66fa2dd3059cff842e6d38fb3a1",
  "research/manufacturing-measurement-1/alignment-001/protocol.json": "6404e8d3067c32eb0a82f19b6d41f6860d8b42f9c10fe95eb94a02c2737e69fa"
}

```
