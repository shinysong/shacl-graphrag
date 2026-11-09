"""Captured-source software fixtures, not LLM answers or fresh evaluation."""
import argparse, copy, json
from collections import Counter
from pathlib import Path
from scripts.postreview_lookup import compile_trace, review_lookup, POLICIES
from scripts.run_post_answer_demo import dump, sha
ROOT=Path('research/post-answer-review-1')
INPUT=ROOT/'question-candidates-001/candidate-runtime.jsonl'

def fixtures():
    result=[]
    for episode in map(json.loads,INPUT.read_text().splitlines()):
        eid=episode['episode_id']
        if 'lookup-complete_selected' not in eid:continue
        kind='defect_label' if 'defect_lookup' in eid else 'nominal_idc'
        sources=episode['selected_evidence'];anchor,target=sources
        policy=POLICIES[kind];address=policy['column']+str(target['source']['excel_row'])
        value=next(c['value'] for c in target['source']['cells'] if c['cell']==address)
        claim={'claim_id':'authored-lookup','lookup_kind':kind,'anchor_id':anchor['source_id'],'dictionary_id':target['source_id'],'value':value,'unit':policy['unit']}
        def add(name,c,s,expectations):
            result.append({'case_id':eid+'/'+name,'origin':'coordinator-authored source-derived software fixture, not LLM answer','claim':copy.deepcopy(c),'sources':copy.deepcopy(s),'expectations':expectations})
        add('matching',claim,sources,{'all_pass':True})
        add('target_omitted',claim,sources[:1],{'lookup_value':'unknown','dictionary_key':'unknown','declared_reference':'pass'})
        changed=copy.deepcopy(claim);changed['value']='deliberately changed value'
        add('value_changed',changed,sources,{'lookup_value':'flag'})
        both=copy.deepcopy(sources)
        next(c for c in both[1]['source']['cells'] if c['cell']==address)['value']=changed['value']
        add('source_and_claim_changed',changed,both,{'all_pass':True})
        malformed=copy.deepcopy(sources);malformed[1]['source']['header_rows']={}
        add('malformed_header',claim,malformed,{'execution':'input_failure'})
    if len(result)!=20:raise ValueError('expected four bindings times five controls')
    return result

def run(output):
    output.mkdir(parents=True,exist_ok=False)
    cases=fixtures();dump(output/'fixtures.json',cases);rows=[]
    for case in cases:
        for engine in ('python','pyshacl'):
            row={'case_id':case['case_id'],'engine':engine,'execution':'completed'}
            try:compile_trace(case['claim'],case['sources'])
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                row.update(execution='input_failure',error_type=type(exc).__name__)
                rows.append(row);continue
            try:row['report']=review_lookup(case['claim'],case['sources'],engine)
            except Exception as exc:row.update(execution='execution_failure',error_type=type(exc).__name__)
            rows.append(row)
    checks=[]
    for case in cases:
        pair=[r for r in rows if r['case_id']==case['case_id']]
        checks.append({'case_id':case['case_id'],'engines_agree':pair[0]['execution']==pair[1]['execution'] and pair[0].get('report',{}).get('results')==pair[1].get('report',{}).get('results')})
        for row in pair:
            actual={r['check_id']:r['status'] for r in row.get('report',{}).get('results',[])}
            actual['all_pass']=bool(actual) and all(v=='pass' for v in actual.values())
            actual['execution']=row['execution']
            expected={'execution':'completed',**case['expectations']}
            checks.append({'case_id':case['case_id'],'engine':row['engine'],'expected_match':all(actual.get(k)==v for k,v in expected.items())})
    dump(output/'outcomes.json',rows);dump(output/'checks.json',checks)
    summary={'software_cases':len(cases),'engine_runs':len(rows),'execution_counts':dict(Counter(r['execution'] for r in rows)),'all_checks_pass':all(c.get('engines_agree',c.get('expected_match')) for c in checks),'paid_calls':0,'claims_are_model_outputs':False,'compiler_shared':True,'limits':['supplied provenance strings compared, not original workbook authenticity','manually declared templates and source-derived fixtures','no question interpretation, external truth or physical applicability','no revision, efficacy or human review time measured']}
    dump(output/'summary.json',summary)
    inputs=[INPUT,ROOT/'question-candidates-001/manifest.json',Path(__file__),Path('scripts/postreview_lookup.py'),Path('scripts/post_answer_review.py')]
    dump(output/'manifest.json',{'inputs':{str(p):sha(p) for p in inputs},'artifacts':{p.name:sha(p) for p in output.iterdir() if p.is_file()},'source_attribution':json.loads((ROOT/'question-candidates-001/manifest.json').read_text())['source_attribution']})
    print(json.dumps(summary))
    if not summary['all_checks_pass']:raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
