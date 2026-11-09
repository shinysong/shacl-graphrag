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
