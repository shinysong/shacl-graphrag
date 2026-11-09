import json,hashlib
from pathlib import Path
p=Path('_workspace/manufacturing-continuation-20261107/measurement-answer')
def read(path):return json.loads(path.read_text())
freeze=read(p/'freeze.json');assert all(hashlib.sha256(Path(k).read_bytes()).hexdigest()==v for k,v in freeze['hashes'].items())
plan=read(p/'plan.json');states=read(p/'states.json');inp=read(p/'input.json');drafts={};requests={};rows=[]
for i,(s,t) in enumerate(zip(plan,states)):
 assert all(s[k]==t[k] for k in ('id','model','arm'))
 prefix=p/'responses'/f'{i:03d}';req=read(prefix.with_suffix('.request.json'));raw=read(prefix.with_suffix('.raw.txt'));result=read(prefix.with_suffix('.result.json'))
 assert req['model']==raw['model']==s['model'] and result['status']==t['state']=='completed'
 assert json.loads(raw['choices'][0]['message']['content'])==result['contract']
 body=json.loads(req['messages'][1]['content']);assert all(body[k]==inp[k] for k in ('question_id','question','evidence'))
 if s['arm']=='draft':drafts[s['model']]={'completion_status':result['status'],'finish_reason':result['finish_reason'],'parsed_response':result['contract'],'visible_text':raw['choices'][0]['message']['content']}
 else:assert body['saved_draft']==drafts[s['model']]
 if s['arm']=='shacl_review':assert body.pop('advisory_report')==read(prefix.with_suffix('.advisory.json'))
 requests[s['model'],s['arm']]=[req['messages'][0],body]
 rows.append({'index':i,**s,'verified':True})
for m in drafts:assert requests[m,'self_review']==requests[m,'shacl_review']
assert len(rows)==18
out={'runtime_frozen_hashes_match':True,'all18_positional_request_raw_contract_state_bindings':True,'six_review_pairs_exact_same_source_policy_original_draft_except_advisory':True,'rows':rows,'limits':['Checks saved artifacts, not independently authenticated provider execution','Posthoc verification never changes answers']}
Path('_workspace/manufacturing-continuation-20261107/measurement-score/binding-audit.json').write_text(json.dumps(out,indent=2)+'\n');print('18 bindings and6paired inputs verified')
