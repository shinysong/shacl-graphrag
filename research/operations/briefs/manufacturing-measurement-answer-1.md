# Additional frozen review packet

## check.py
```python
import copy,json,tempfile,sys,hashlib
from pathlib import Path
from unittest.mock import patch
import runner,checker
A={'nominal_idc_a':999,'recorded_current_channel':False,'verified_defect_interval_mean_a':456.7,'applicable_document_version':'invented','review_pointers':[],'citations':[],'basis':'deliberately unsupported fixture'}
for align in (False,True):
 for version in (False,True):
  r,_,_=checker.report(A,{'alignment_known':align,'version_known':version});wanted=[]
  if not align:wanted.append('unsupported_interval_claim')
  if not version:wanted.append('unsupported_version_claim')
  assert r['flags']==wanted
assert checker.structural(A)
assert checker.report(None,{'alignment_known':False,'version_known':False})[0]['status']=='unknown'
B=copy.deepcopy(A);B['verified_defect_interval_mean_a']=None;B['applicable_document_version']=None
assert checker.report(B,{'alignment_known':False,'version_known':False})[0]['flags']==[] # Nominal999 deliberately outside checker scope.
providers=json.loads((runner.ROOT/'providers.json').read_text());inp=json.loads((runner.ROOT/'input.json').read_text())
class Response:
 def __init__(self,request,index,mode):
  self.status_code=500 if mode=='http_failure' and index==0 else 200
  text='broken JSON' if mode=='format_failure' and index==0 else json.dumps(A)
  provider=next(p for p in providers if p['model']==request['model'])
  self.raw=json.dumps({'model':provider['model'],'provider':provider['provider'],'usage':{'cost':0.001,'prompt_tokens':100,'completion_tokens':100},'choices':[{'finish_reason':'stop','message':{'content':text}}]}).encode()
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def iter_bytes(self):yield self.raw
class Client:
 mode='';requests=[]
 def __init__(self,*args,**kwargs):pass
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def stream(self,method,url,headers,json):
  assert url=='https://openrouter.ai/api/v1/chat/completions' and method=='POST';i=len(self.requests);self.requests.append(json);return Response(json,i,self.mode)
for mode in ('completed_wrong','format_failure','http_failure'):
 with tempfile.TemporaryDirectory() as td:
  p=Path(td);ledger={'attempt_cap':180,'authorized_usd':15,'attempts':162,'status':'phase_complete','reservations':[{'slot_id':f'old{i}','state':'resolved','status':'completed','reported_usd':'0','reserved_usd':'0'} for i in range(162)]}
  (p/'campaign-budget.json').write_text(json.dumps(ledger));(p/'providers.json').write_text(json.dumps(providers));(p/'input.json').write_text(json.dumps(inp));freeze={'hashes':{}};(p/'freeze.json').write_text(json.dumps(freeze));(p/'launch-gate.json').write_text(json.dumps({'decision':'ready','freeze_sha256':hashlib.sha256(runner.base.canonical(freeze)).hexdigest()}))
  Client.mode=mode;Client.requests=[]
  with patch.object(runner,'ROOT',p),patch.object(runner,'LEDGER',p/'campaign-budget.json'),patch('httpx.Client',Client),patch('dotenv.dotenv_values',lambda _: {'OPENROUTER_API_KEY':'mock-only'}):
   runner.run();states=json.loads((p/'states.json').read_text());l=json.loads((p/'campaign-budget.json').read_text());assert len(states)==18
   if mode=='http_failure':assert len(Client.requests)==1 and l['attempts']==163 and l['reservations'][-1]['state']=='unresolved' and sum(s['state']=='not_attempted' for s in states)==17
   else:
    assert len(Client.requests)==18 and l['attempts']==180
    if mode=='completed_wrong':assert all(s['state']=='completed' for s in states)
    else:assert states[0]['state']=='output_failure' and sum(s['state']=='completed' for s in states)==17
    assert json.loads((p/'responses/017.result.json').read_text())['contract']['nominal_idc_a']==999
    try:runner.run()
    except (ValueError,FileExistsError):pass
    else:raise AssertionError('repeat launch allowed')
    assert len(Client.requests)==18
print('checker parity four contexts + null/invalid scope; mocked18 wrong outputs retained, format failure18slots, unresolvedHTTP1call17unattempted, repeat launch rejected; zero network')

```

## build_inputs.py
```python
import json,hashlib
from pathlib import Path
p=Path(__file__).resolve().parent;diagnostic=json.loads(Path('research/manufacturing-measurement-1/diagnostic-001/diagnostic.json').read_text());obs={x['id']:x['observation'] for x in diagnostic['rows']}
source=json.loads(Path('research/backend-reasoning-review-1/design-001/source-subset.json').read_text());nominal=next(n['source'] for n in source['nodes'] if n['node_id']=='PP6:welding_settings_code:1')
evidence=[{'id':'S1','role':'archived annotation row','record':obs['annotation_alignment']['annotation']},{'id':'S2','role':'nominal settings codebook','record':nominal},{'id':'S3','role':'archived README channel description','archive_path':'ZENODO_Penelope/PP6/README.txt','sha256':'311232a904e6b33bd7354218556563dc653a88322b92707f30484cdd0effe131','description':'current_a: current of the DC electrode [A]; data1 described as 5 kHz'},{'id':'S4','role':'read-only file inspection, not calibrated physical truth','archive_path':'ZENODO_Penelope/PP6/1. process_data/PP6_01/PP6_01.hdf5','sha256':diagnostic['source_sha256'],'data1_rows':obs['table_schema']['data1_rows'],'fields':obs['table_schema']['data1_fields'],'raw_data0_x_range':obs['annotation_alignment']['data0_x_range']},{'id':'S5','role':'conditional arithmetic under authored assumptions, not a validated defect interval','candidate_slices':obs['annotation_alignment']['candidates'],'selected_candidate':None},{'id':'S6','role':'scope of this study, not a claim of global absence','unverified':['annotation sample numbers address this HDF5 file and data1 table','index base and end inclusion','coordinate origin/transform','calibration','applicable review-document version'],'file_bead_association':'Filename and annotation bead number suggest association; not independently validated'}]
system='''Answer the supplied manufacturing evidence question in Korean using only the supplied evidence. No external lookup or physical operating advice. Return exactly one JSON object, no Markdown, with these exact fields:
nominal_idc_a: number or null;
recorded_current_channel: boolean (whether a recorded current channel is present in the supplied file evidence, not whether calibration/alignment is verified);
verified_defect_interval_mean_a: number or null (only a verified association to this annotation interval qualifies; conditional arithmetic is not such verification);
applicable_document_version: nonempty string or null (the applicable review-document version, not a dataset DOI/release);
review_pointers: array of short strings explaining concrete unresolved checks;
citations: array of objects {"claim": string, "source_id": string}, pointing to supplied S1..S6 IDs;
basis: short explanation, at most150words.
Preserve answerable nominal and channel facts while separating unresolved claims. The operational policy is supplied, not learned: a verified-interval claim requires known annotation/file/table/alignment conventions; a document-version claim requires known document applicability. No such verification may be inferred solely from a number being in bounds or near a nominal value. An advisory report, if present, checks only its stated scope and is neither external truth nor a compulsory veto. No gold answer is supplied. Keep unsupported statements as unknown; do not erase supported facts just because another claim is unresolved.'''
question='PP6 작업표 2행에 대해 명목 Idc, 기록된 전류 채널의 존재, 이 결함 구간에 대응한다고 검증된 실제 평균 전류, 적용 검토 문서 버전을 각각 판단해 주세요. 무엇을 근거로 말할 수 있고 어느 연결 규약을 사람이 추가 확인해야 하나요?'
data={'question_id':'W-M01','question':question,'evidence':evidence,'system':system,'checker_context':{'alignment_known':False,'version_known':False},'review_instruction':'Review the saved draft independently using exactly the same question, evidence and operational policy. Correct it if necessary, preserve it if justified. Some runs include a two-constraint advisory report. Return the same JSON schema. Do not claim additional source verification.'}
(p/'input.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print('input bytes',len((p/'input.json').read_bytes()))

```
