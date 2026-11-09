"""Offline replay plus explicitly synthetic perturbations; never calls an LLM.

Source adapter is limited to captured numeric worksheet nodes. Manual answer
projection is a fixed inspectable artifact, not an extraction algorithm. Scoring
labels are kept outside packets passed to the checker.
"""
import argparse, copy, hashlib, json
from pathlib import Path
from collections import Counter
from scripts.post_answer_review import review, validate_packet
ROOT=Path('research/post-answer-review-1')

def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def source_packet(replay):
    sources=[]
    units={'x_init_mm':'mm','x_end_mm':'mm','sample_init':'# sample','sample_end':'# sample'}
    for chunk in replay['selected_evidence']:
        node=json.loads(chunk['text'])
        if chunk['chunk_type']!='node' or not all(k in node for k in ('values','field_cells','cells')):raise ValueError('unsupported source node')
        cells={c['cell']:c for c in node['cells']}
        if len(cells)!=len(node['cells']):raise ValueError('duplicate cell')
        fields={}
        for key,value in node['values'].items():
            cell_id=node['field_cells'][key]; cell=cells[cell_id]
            if cell['formula'] is not None or type(cell['value']) is not type(value) or cell['value']!=value:raise ValueError('field-cell mismatch or formula')
            fields[key]={'value':value,'unit':units.get(key),'locator':f"{node['archive_path']} | {node['sheet']} | {cell_id}"}
        sources.append({'source_id':chunk['chunk_id'],'fields':fields})
    return sources

def cases(replay,projection):
    if projection['answer_sha256']!=hashlib.sha256(json.dumps(replay['answer'],sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest():raise ValueError('projection binding')
    base={'claims':projection['claims'],'sources':source_packet(replay)}
    result=[{'case_id':'saved_answer_manual_projection','kind':'saved replay','packet':copy.deepcopy(base),'expectations':{}}]
    # All following cases are authored software diagnostics, not observed answers.
    def add(name, mutate, expect):
        packet=copy.deepcopy(base);mutate(packet)
        result.append({'case_id':name,'kind':'synthetic mutation','packet':packet,'expectations':expect})
    add('changed_recorded_value',lambda p:p['claims'][0].update(value=999),{'c0.defect/value_agreement':'flag'})
    add('changed_declared_unit',lambda p:p['claims'][3].update(unit='cm'),{'c0.x_init_mm/unit_agreement':'flag'})
    add('selected_source_omitted',lambda p:p.update(sources=[s for s in p['sources'] if s['source_id']!='node:PP6:2']),{'c0.defect/source_binding':'unknown','c0.defect/value_agreement':'unknown'})
    add('selected_field_omitted',lambda p:p['sources'][0]['fields'].pop('defect'),{'c0.defect/field_binding':'unknown','c0.defect/value_agreement':'unknown'})
    add('citation_unbound',lambda p:p['claims'][0].update(source_id=None),{'c0.defect/source_binding':'unknown'})
    add('compound_value_unsupported',lambda p:p['claims'][0].update(value={'defect':4}),{'execution':'input_failure'})
    add('duplicate_claim_id',lambda p:p['claims'].append(copy.deepcopy(p['claims'][0])),{'execution':'input_failure'})
    add('string_instead_of_integer',lambda p:p['claims'][0].update(value='4'),{'c0.defect/value_agreement':'flag'})
    add('derived_claim_wrong_value_outside_scope',lambda p:p['claims'][7].update(value=999),{'c1/source_binding':'not_applicable','c1/value_agreement':'not_applicable'})
    def corrupt_both(p):
        p['claims'][0]['value']=999;p['sources'][0]['fields']['defect']['value']=999
    add('consistent_corrupted_source_and_claim',corrupt_both,{'c0.defect/value_agreement':'pass'})
    def wrong_record(p):
        p['claims'][0]['source_id']='node:PP6:12';p['claims'][0]['value']=p['sources'][1]['fields']['defect']['value']
    add('wrong_question_record_but_bound_value',wrong_record,{'c0.defect/value_agreement':'pass'})
    return result

def run(output):
    output.mkdir(parents=True,exist_ok=False)
    replay=json.loads((ROOT/'replay-input.json').read_text());projection=json.loads((ROOT/'manual-projection.json').read_text())
    fixtures=cases(replay,projection);dump(output/'fixtures.json',fixtures)
    rows=[]
    for case in fixtures:
        for engine in ('python','pyshacl'):
            row={'case_id':case['case_id'],'kind':case['kind'],'engine':engine,'execution':'completed'}
            try:
                validate_packet(case['packet'])
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                row.update(execution='input_failure',error_type=type(exc).__name__)
                rows.append(row)
                continue
            try:
                report=review(case['packet'],engine)
                if engine=='pyshacl':
                    for key,suffix in [('data_turtle','data'),('shapes_turtle','shapes'),('report_turtle','report')]:
                        (output/f"{case['case_id']}.{suffix}.ttl").write_text(report.pop(key))
                    (output/f"{case['case_id']}.report.txt").write_text(report.pop('report_text'))
                row['report']=report
            except Exception as exc:
                row.update(execution='execution_failure',error_type=type(exc).__name__)
            rows.append(row)
    # Offline assertions are never passed into review(), and never repair outputs.
    checks=[]
    for case in fixtures:
        pair=[r for r in rows if r['case_id']==case['case_id']]
        parity=pair[0]['execution']==pair[1]['execution'] and pair[0].get('report',{}).get('results')==pair[1].get('report',{}).get('results')
        checks.append({'case_id':case['case_id'],'engines_agree':parity})
        for row in pair:
            actual={'execution':row['execution']}
            actual.update({r['claim_id']+'/'+r['check_id']:r['status'] for r in row.get('report',{}).get('results',[])})
            checks.append({'case_id':case['case_id'],'engine':row['engine'],'expected_diagnostic_outcomes_match':all(actual.get(k)==v for k,v in {'execution':'completed',**case['expectations']}.items())})
    dump(output/'outcomes.json',rows);dump(output/'checks.json',checks)
    summary={'cases':len(fixtures),'engine_runs':len(rows),'completed':sum(r['execution']=='completed' for r in rows),'input_failures':sum(r['execution']=='input_failure' for r in rows),'execution_failures':sum(r['execution']=='execution_failure' for r in rows),'all_checks_pass':all(all(v for k,v in c.items() if k in ('engines_agree','expected_diagnostic_outcomes_match')) for c in checks),'by_case_python':{r['case_id']:dict(Counter(x['status'] for x in r.get('report',{}).get('results',[]))) for r in rows if r['engine']=='python'},'paid_calls':0,'versions':{name:__import__('importlib.metadata',fromlist=['version']).version(name) for name in ('rdflib','pyshacl')},'limitations':['manual projection, no automatic NLP','synthetic mutations are not model outcomes','shared admission gates, not independent pipeline replication','pass does not verify external truth or question relevance','no draft revision, no human-review-time measurement']}
    dump(output/'summary.json',summary)
    files=[ROOT/'replay-input.json',ROOT/'manual-projection.json',ROOT/'protocol.json',Path(__file__),Path('scripts/post_answer_review.py')]
    dump(output/'manifest.json',{'inputs':{str(f):sha(f) for f in files},'artifacts':{f.name:sha(f) for f in output.iterdir() if f.is_file()},'schema':'post-answer-demo-1'})
    print(json.dumps(summary,ensure_ascii=False))
    if not summary['all_checks_pass']:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
