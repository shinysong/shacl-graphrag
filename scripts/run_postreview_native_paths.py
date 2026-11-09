"""Replay retained authored lookup fixtures; no model or new source calls."""
import argparse,json,hashlib
from pathlib import Path
from collections import Counter
from rdflib import Graph
from scripts.postreview_native_paths import review_native_paths
ROOT=Path('research/post-answer-review-1')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def graph_hash(text):
 g=Graph().parse(data=text,format='turtle');return hashlib.sha256('\n'.join(sorted(' '.join(n.n3() for n in t) for t in g)).encode()).hexdigest()
def run(out):
 old=ROOT/'lookup-demo-001';manifest=json.loads((old/'manifest.json').read_text())
 # Explicit frozen-source verification before executing any case.
 hashes=manifest.get('artifacts',{})
 for name in ('fixtures.json','outcomes.json'):
  if name not in hashes or sha(old/name)!=hashes[name]:raise ValueError('prior artifact hash '+name)
 fixtures=json.loads((old/'fixtures.json').read_text());prior={(r['case_id'],r['engine']):r for r in json.loads((old/'outcomes.json').read_text())}
 if len(fixtures)!=20 or len({f['case_id'] for f in fixtures})!=20 or len(prior)!=40:raise ValueError('fixture universe')
 out.mkdir(parents=True,exist_ok=False);rows=[];checks=[]
 for f in fixtures:
  pair=[]
  for engine in ('python','pyshacl'):
   row={'case_id':f['case_id'],'engine':engine}
   try:row.update(execution='completed',report=review_native_paths(f['claim'],f['sources'],engine))
   except ValueError as e:row.update(execution='input_failure',error=str(e))
   except Exception as e:row.update(execution='execution_failure',error=type(e).__name__+': '+str(e))
   prior_row=prior[(f['case_id'],engine)];same=row['execution']==prior_row['execution']
   if row['execution']=='completed' and prior_row['execution']=='completed':
    now={r['check_id']:r['status'] for r in row['report']['results']};before={r['check_id']:r['status'] for r in prior_row['report']['results'] if r['check_id']!='declared_unit'};same=same and now==before
   checks.append({'case_id':f['case_id'],'engine':engine,'check':'historical_six_rule_status_parity','pass':same});rows.append(row);pair.append(row)
  checks.append({'case_id':f['case_id'],'check':'native_engines_match','pass':pair[0]['execution']==pair[1]['execution'] and (pair[0]['execution']!='completed' or pair[0]['report']['results']==pair[1]['report']['results'])})
 counts=Counter(r['execution'] for r in rows);shape_hashes={graph_hash(r['report']['shapes_turtle']) for r in rows if r['execution']=='completed'}
 checks.append({'check':'expected_execution_denominator','pass':counts=={'completed':32,'input_failure':8}})
 checks.append({'check':'one_value_independent_shapes_graph','pass':len(shape_hashes)==1})
 dump(out/'outcomes.json',rows);dump(out/'checks.json',checks)
 summary={'source_fixture_cases':20,'engine_runs':40,'execution_counts':dict(counts),'all_checks_pass':all(c['pass'] for c in checks),'check_count':len(checks),'distinct_shapes_graphs':len(shape_hashes),'rules_per_completed_run':6,'unit_agreement_measured':False,'new_model_calls':0,'new_source_calls':0,'new_independent_questions':0,'limits':['shared source projection and availability gates','Python RDF traversal versus actual SHACL-SPARQL paths, not database engines','six-rule subset of historical lookup policy; unit agreement excluded','original authored controls reused, not LLM answers or efficacy']}
 dump(out/'summary.json',summary);dump(out/'manifest.json',{'source_fixtures':str(old/'fixtures.json'),'source_fixtures_sha256':sha(old/'fixtures.json'),'prior_outcomes_sha256':sha(old/'outcomes.json'),'source_attribution':manifest.get('source_attribution'),'code_hashes':{x:sha(Path(x)) for x in ['scripts/postreview_native_paths.py','scripts/run_postreview_native_paths.py','scripts/postreview_lookup.py','scripts/post_answer_review.py']},'hashes':{x.name:sha(x) for x in out.iterdir() if x.is_file()}})
 print(json.dumps(summary))
 if not summary['all_checks_pass']:raise SystemExit(1)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);run(p.parse_args().output)
