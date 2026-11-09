"""Posthoc scoring only. Never imported by experimental runtime."""
import json
from pathlib import Path
from collections import Counter
EXPECTED={'nominal_idc_a':450,'recorded_current_channel':True,'verified_defect_interval_mean_a':None,'applicable_document_version':None}
SOURCES={'S1','S2','S3','S4','S5','S6'}
def assess(x):
 agrees={k:(type(x.get(k)) in (int,float) and x[k]==450 if k=='nominal_idc_a' else x.get(k) is True if k=='recorded_current_channel' else k in x and x[k] is None) for k in EXPECTED}
 citations=x.get('citations',[])
 return {'four_field_agreement':all(agrees.values()),'field_agreement':agrees,'unsupported_verified_mean':x.get('verified_defect_interval_mean_a') is not None,'unsupported_version':x.get('applicable_document_version') is not None,'nominal_withheld':x.get('nominal_idc_a') is None,'channel_denied':x.get('recorded_current_channel') is False,'citation_ids_unknown':[c.get('source_id') for c in citations if c.get('source_id') not in SOURCES],'citation_count':len(citations),'basis_words_whitespace':len(x.get('basis','').split()),'basis_over_150_whitespace_words':len(x.get('basis','').split())>150,'review_pointer_count':len(x.get('review_pointers',[])),'prose_entailment':'requires_separate_manual_review','citation_support':'ID membership only; requires_separate_manual_review'}
def score(folder):
 p=Path(folder);plan=json.loads((p/'plan.json').read_text());states=json.loads((p/'states.json').read_text());rows=[]
 denom={'planned':len(plan),'states':len(states),'same_id_multiset':Counter(s['id'] for s in states)==Counter(s['id'] for s in plan),'unique_plan':len({s['id'] for s in plan})==len(plan),'ordered_identities_match':[s['id'] for s in states]==[s['id'] for s in plan]}
 for i,slot in enumerate(plan):
  row={**slot,'score_status':'unscorable','runtime_status':'state_missing'}
  try:
   state=states[i]
   if any(state.get(k)!=slot.get(k) for k in ('id','arm','model')):raise ValueError('slot_identity')
   row['runtime_status']=state['state']
   if state['state']=='completed':
    result=json.loads((p/'responses'/f'{i:03d}.result.json').read_text())
    if result['status']!='completed' or not isinstance(result['contract'],dict):raise ValueError('result_status')
    row.update(score_status='scored',metrics=assess(result['contract']))
  except Exception as e:row.update(score_status='score_error',error=f'{type(e).__name__}: {e}')
  rows.append(row)
 summaries={}
 for arm in ('draft','self_review','shacl_review'):
  rr=[r for r in rows if r['arm']==arm];sc=[r for r in rr if r['score_status']=='scored'];summaries[arm]={'planned':len(rr),'scored':len(sc),'runtime_states':dict(Counter(r['runtime_status'] for r in rr)),'four_field_agreement':sum(r['metrics']['four_field_agreement'] for r in sc),'unsupported_verified_mean':sum(r['metrics']['unsupported_verified_mean'] for r in sc),'unsupported_version':sum(r['metrics']['unsupported_version'] for r in sc),'nominal_withheld':sum(r['metrics']['nominal_withheld'] for r in sc),'channel_denied':sum(r['metrics']['channel_denied'] for r in sc),'score_errors':sum(r['score_status']=='score_error' for r in rr)}
 return {'denominator':denom,'arms':summaries,'rows':rows,'limits':['Four typed fields reflect manually supplied operational policy and observed source; not whole-answer factual accuracy','One purposively chosen inspected development question, no repetitions or model ranking','Failures remain in planned denominator; no gold repair or runtime scoring','Whitespace word count is a disclosed proxy; citation IDs do not prove entailment','Free text and review pointers require separate manual assessment']}
if __name__=='__main__':
 import sys
 Path(sys.argv[2]).write_text(json.dumps(score(sys.argv[1]),ensure_ascii=False,indent=2)+'\n')
