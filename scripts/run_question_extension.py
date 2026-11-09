"""Offline nine-type development diagnostic. No LLM calls or answer repair."""
import argparse,copy,gzip,hashlib,json
from pathlib import Path
from collections import Counter
from scripts.post_answer_review import review
from scripts.postreview_native_paths import review_native_paths
from scripts.postreview_extended import review_extended

SOURCE=Path('research/refined-hybrid-1/neo4j-source-001/frozen/source-corpus-v1.json')
SOURCE_HASH='900bb25d15bcb4dbab89076d3a1372d84762829dcd645bae7c17bc60b9693ac8'

def temporal():
 return {'kind':'temporal','claim':{'state':'selected','selected_id':'v1','latest_ids':['v2']},'evidence':{'event_date':'2025-06-30','scope':'PP6','history_complete':True,'documents':[{'id':'v1','scope':'PP6','valid_from':'2025-01-01','valid_to':'2025-07-01','release_date':'2024-12-20'},{'id':'v2','scope':'PP6','valid_from':'2025-07-01','valid_to':'2026-01-01','release_date':'2025-06-20'}]}}

def build_cases():
 raw=SOURCE.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=SOURCE_HASH:raise ValueError('source changed')
 corpus=json.loads(raw);nodes={json.loads(c['text'])['id']:json.loads(c['text']) for c in corpus['chunks'] if c['chunk_type']=='node'}
 cases=[]
 def add(q,name,parts,flags=(),unknown=(),failure=False,basis='retained source plus authored structured claim'):
  cases.append({'case_id':f'case-{len(cases)+1:03d}','question_type':q,'control':name,'basis':basis,'runtime':{'parts':copy.deepcopy(parts)},'expected':{'flag':list(flags),'unknown':list(unknown),'input_failure':failure}})
 def atomic(value=106,unit='mm',field='x_init_mm',sources=True):
  n=nodes['PP6:2'];fields={field:{'value':n['values'][field],'unit':{'x_init_mm':'mm','sample_init':'# sample'}.get(field),'locator':n['archive_path']+' | '+n['sheet']+' | '+n['field_cells'][field]}} if field in n['values'] else {}
  return {'checker':'atomic','packet':{'claims':[{'claim_id':'c','kind':'recorded','source_id':'PP6:2','field':field,'value':value,'unit':unit}],'sources':[{'source_id':'PP6:2','fields':fields}] if sources else []}}
 def lookup(anchor='PP6:2',dictionary='PP6:defect_code:4',value='Metallic inclusion',kind='defect_label',include=True):
  ss=[{'source_id':anchor,'source':nodes[anchor]}]
  if include:ss.append({'source_id':dictionary,'source':nodes[dictionary]})
  return {'checker':'native_lookup','claim':{'claim_id':'l','lookup_kind':kind,'anchor_id':anchor,'dictionary_id':dictionary,'value':value,'unit':'A' if kind=='nominal_idc' else None},'sources':ss}
 def ext(p):return {'checker':'extended','packet':p}
 def role(role='nominal',catalog='nominal',claim_text='nominal codebook current'):
  return ext({'kind':'role','claim':{'role':role,'text':claim_text},'evidence':{'declared_role':catalog},'policy_provenance':'manually declared role for welding_settings_code Idc; not NLP extraction'})
 p=atomic();add('Q1','correct',[p]);p=atomic(107);add('Q1','wrong_value',[p],['0:value_agreement']);p=atomic(sources=False);add('Q1','selected_source_missing',[p],unknown=['0:'+k for k in ['source_binding','field_binding','value_agreement','unit_agreement']])
 p=lookup();add('Q2','correct',[p]);p=lookup(value='Porosity');add('Q2','wrong_label',[p],['0:lookup_value']);p=lookup(include=False);add('Q2','dictionary_omitted',[p],unknown=['0:'+k for k in ['dictionary_key','lookup_value','workbook_hash','workbook_path','declared_header']])
 left=lookup(dictionary='PP6:welding_settings_code:1',value=450,kind='nominal_idc');right=lookup(anchor='PP6:12',dictionary='PP6:welding_settings_code:3',value=500,kind='nominal_idc')
 diff={'kind':'difference','claim':{'value':50,'unit':'A'},'evidence':{'left':{'source_id':'PP6:welding_settings_code:1','value':nodes['PP6:welding_settings_code:1']['values'][2],'unit':'A'},'right':{'source_id':'PP6:welding_settings_code:3','value':nodes['PP6:welding_settings_code:3']['values'][2],'unit':'A'}}}
 add('Q3','correct',[left,right,ext(diff)]);p=copy.deepcopy(diff);p['claim']['value']=-50;add('Q3','reversed_subtraction',[left,right,ext(p)],['2:signed_difference']);p=copy.deepcopy(diff);p['evidence']['right']=None;add('Q3','right_operand_omitted',[ext(p)],unknown=['0:signed_difference','0:difference_unit'])
 records=[]
 for sid in ['PP6:2','PP6:12']:
  n=nodes[sid];dn=nodes[n['dictionary_refs']['defect']];records.append({'id':sid,'position':n['values']['x_init_mm'],'label':dn['values'][1]})
 select={'kind':'selection','claim':{'selected_ids':['PP6:12'],'count':1},'evidence':{'universe_ids':['PP6:2','PP6:12'],'rows':records,'lower':100,'upper':250,'target_label':'Porosity'}}
 add('Q4','correct',[ext(select)]);p=copy.deepcopy(select);p['claim']={'selected_ids':['PP6:2'],'count':1};add('Q4','wrong_member_same_count',[ext(p)],['0:missing_member','0:extra_member']);p=copy.deepcopy(select);p['claim']['count']=2;add('Q4','wrong_count',[ext(p)],['0:matching_count','0:list_count_consistency']);p=copy.deepcopy(select);p['evidence']['rows'].pop();add('Q4','bounded_member_evidence_omitted',[ext(p)],unknown=['0:missing_member','0:extra_member','0:matching_count']);p=copy.deepcopy(select);p['evidence']['target_label']='not-listed';p['claim']={'selected_ids':[],'count':0};add('Q4','empty_result_with_complete_declared_scope',[ext(p)])
 add('Q5','correct_units_and_role',[atomic(),atomic(66244,'# sample','sample_init'),role()]);p=atomic(66244);add('Q5','sample_index_as_mm',[p],['0:value_agreement']);add('Q5','nominal_called_measured',[role('measured',claim_text='measured current')],['0:declared_role']);add('Q5','role_catalog_missing',[role(catalog=None)],unknown=['0:declared_role'])
 add('Q6','same_file',[lookup()]);add('Q6','same_code_name_wrong_file',[lookup(dictionary='PP7:defect_code:4')],['0:declared_reference','0:workbook_hash','0:workbook_path'])
 t=temporal();add('Q7','interior_date',[ext(t)],basis='wholly authored synthetic history');p=copy.deepcopy(t);p['claim']['selected_id']='v2';add('Q7','latest_misapplied',[ext(p)],['0:selected_binding'],basis='wholly authored synthetic history');p=copy.deepcopy(t);p['evidence']['event_date']='2025-07-01';p['claim']['selected_id']='v2';add('Q7','exact_boundary',[ext(p)],basis='wholly authored synthetic history');p=copy.deepcopy(t);p['evidence']['documents'].append({'id':'wrongscope','scope':'PP7','valid_from':'2025-01-01','valid_to':'2026-01-01','release_date':'2025-06-29'});add('Q7','wrong_scope_distractor',[ext(p)],basis='wholly authored synthetic history')
 p=copy.deepcopy(t);p['evidence']['documents'][1]['valid_from']='2025-06-01';p['claim'].update(state='ambiguous',selected_id=None);add('Q7','overlap_acknowledged',[ext(p)],basis='wholly authored synthetic history');p['claim'].update(state='selected',selected_id='v1');add('Q7','overlap_ignored',[ext(p)],['0:temporal_state'],basis='wholly authored synthetic history');p=copy.deepcopy(t);p['evidence']['history_complete']=False;p['evidence']['documents']=[];add('Q7','history_unavailable',[ext(p)],unknown=['0:'+k for k in ['temporal_state','selected_binding','missing_latest','extra_latest']],basis='wholly authored synthetic history');p=copy.deepcopy(t);p['evidence']['event_date']='2026-01-01';p['claim'].update(state='unknown',selected_id=None);add('Q7','end_boundary_no_match',[ext(p)],basis='wholly authored synthetic history');p=copy.deepcopy(t);p['evidence']['documents'][0]['release_date']='2025-06-20';p['claim']['latest_ids']=['v1','v2'];add('Q7','tied_latest_set',[ext(p)],basis='wholly authored synthetic history');p=copy.deepcopy(t);p['evidence']['event_date']='2025-02-30';add('Q7','invalid_date',[ext(p)],failure=True,basis='authored malformed synthetic history')
 add('Q8','supported_setting_missing_measurement',[left,role('measured',None)],unknown=['1:declared_role']);p=atomic(value=None,unit=None,field='review_version');add('Q8','version_field_unavailable_in_selected_record',[p],unknown=['0:field_binding','0:value_agreement','0:unit_agreement'])
 add('Q9','all_correct_draft',[lookup(),role()]);add('Q9','wrong_label_and_measured_claim',[lookup(value='Porosity'),role('measured',claim_text='actual measured current')],['0:lookup_value','1:declared_role']);add('Q9','partly_supported_draft',[lookup(include=False),role()],unknown=['0:'+k for k in ['dictionary_key','lookup_value','workbook_hash','workbook_path','declared_header']]);add('Q9','dishonest_role_projection_blindspot',[lookup(),role('nominal',claim_text='actual measured current')],basis='authored text/typed-role mismatch; passing typed checks is known unverified NLP blindspot')
 return cases,corpus['source_attribution']

def run_part(part,engine):
 if part['checker']=='atomic':return review(part['packet'],engine)
 if part['checker']=='native_lookup':return review_native_paths(part['claim'],part['sources'],engine)
 if part['checker']=='extended':return review_extended(part['packet'],engine)
 raise ValueError('checker')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);args=ap.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
 cases,attribution=build_cases();results=[];checks=[]
 # Evaluator expectations and scenario labels are separate from runtime inputs.
 (out/'runtime-inputs.jsonl').write_text(''.join(json.dumps({'case_id':c['case_id'],'runtime':c['runtime']},ensure_ascii=False)+'\n' for c in cases))
 (out/'evaluation-cases.json').write_text(json.dumps([{k:v for k,v in c.items() if k!='runtime'} for c in cases],ensure_ascii=False,indent=2)+'\n')
 for case in cases:
  pair=[]
  for engine in ('python','pyshacl'):
   row={'case_id':case['case_id'],'question_type':case['question_type'],'engine':engine,'reports':[]}
   try:
    for part in case['runtime']['parts']:row['reports'].append(run_part(copy.deepcopy(part),engine))
    row['status']='completed';flat={f"{i}:{r['check_id']}":r['status'] for i,report in enumerate(row['reports']) for r in report['results']};row['normalized']=flat
    flags=sorted(k for k,v in flat.items() if v=='flag');unknown=sorted(k for k,v in flat.items() if v=='unknown')
    ok=not case['expected']['input_failure'] and flags==sorted(case['expected']['flag']) and unknown==sorted(case['expected']['unknown'])
   except (ValueError,KeyError,TypeError) as e:
    row.update(status='input_failure',error=type(e).__name__+': '+str(e));ok=case['expected']['input_failure']
   except Exception as e:
    row.update(status='execution_failure',error=type(e).__name__+': '+str(e));ok=False
   checks.append({'case_id':case['case_id'],'engine':engine,'expected_outcome_matched':ok});results.append(row);pair.append(row)
  checks.append({'case_id':case['case_id'],'engine_parity':pair[0]['status']==pair[1]['status'] and pair[0].get('normalized')==pair[1].get('normalized')})
 with (out/'raw-reports.jsonl.gz').open('wb') as file:
  with gzip.GzipFile(fileobj=file,mode='wb',mtime=0) as stream:
   for row in results:stream.write((json.dumps(row,ensure_ascii=False)+'\n').encode())
 (out/'outcomes.json').write_text(json.dumps([{k:v for k,v in r.items() if k!='reports'} for r in results],ensure_ascii=False,indent=2)+'\n')
 passed=sum(x.get('expected_outcome_matched',x.get('engine_parity')) for x in checks)
 summary={'authored_cases':len(cases),'cases_by_question_type':dict(Counter(c['question_type'] for c in cases)),'planned_engine_runs':len(cases)*2,'execution_counts':dict(Counter(r['status'] for r in results)),'checks_passed':passed,'checks_total':len(checks),'new_model_calls':0,'actual_model_outputs_evaluated':0,'source_attribution':attribution,'limits':['consumed-development source plus authored claims, not natural question benchmark','synthetic version history separate from real source','shared projection and completeness declarations','Q8 checks missing declared evidence, not global absence or automatic review prose','Q9 authored-draft checks, not model revision efficacy; dishonest role projection may pass','no codebook/aggregate/temporal rule inferred automatically']}
 (out/'checks.json').write_text(json.dumps(checks,indent=2)+'\n');(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 (out/'manifest.json').write_text(json.dumps({'source_sha256':SOURCE_HASH,'artifacts':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()},'code_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path('scripts/postreview_extended.py')]}},indent=2)+'\n')
 print(json.dumps(summary,ensure_ascii=False));return 0 if passed==len(checks) else 1
if __name__=='__main__':raise SystemExit(main())
