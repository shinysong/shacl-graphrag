"""Source-integrity census over retained development records, not QA accuracy."""
import argparse,collections,gzip,hashlib,json
from pathlib import Path
from scripts.postreview_lookup import POLICIES,cell_value
from scripts.postreview_native_paths import review_native_paths
SOURCE=Path('research/refined-hybrid-1/neo4j-source-001/frozen/source-corpus-v1.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def run(out):
 source_hash=sha(SOURCE)
 if source_hash!='900bb25d15bcb4dbab89076d3a1372d84762829dcd645bae7c17bc60b9693ac8':raise ValueError('frozen source hash changed')
 corpus=json.loads(SOURCE.read_text());nodes={n['node_id']:n for n in corpus['nodes']}
 if len(nodes)!=len(corpus['nodes']):raise ValueError('duplicate source ID')
 anchors=[n for n in corpus['nodes'] if n['node_type']=='annotation']
 if len(anchors)!=243 or len(nodes)!=328:raise ValueError('frozen inventory changed')
 out.mkdir(parents=True,exist_ok=False);rows=[];pairs=[];all_statuses=collections.Counter();shapes={};effective={}
 with (out/'raw-traces.jsonl.gz').open('wb') as rawfile,gzip.GzipFile(fileobj=rawfile,mode='wb',mtime=0) as raw:
  for anchor in anchors:
   for kind,policy in POLICIES.items():
    aid=anchor['node_id'];ref=anchor['source'].get('dictionary_refs',{}).get(policy['selector']);target=nodes.get(ref);case_id=aid+'/'+kind;pair=[]
    sources=[{'source_id':aid,'source':anchor['source']}]
    if target is not None and ref!=aid:sources.append({'source_id':ref,'source':target['source']})
    value=None
    if target is not None and target['source'].get('excel_row'):
     value=cell_value(target['source'],policy['column']+str(target['source']['excel_row']))
    claim={'claim_id':'source-derived/'+case_id,'lookup_kind':kind,'anchor_id':aid,'dictionary_id':ref,'value':value,'unit':policy['unit']}
    for engine in ('python','pyshacl'):
     row={'case_id':case_id,'anchor_id':aid,'lookup_kind':kind,'engine':engine,'target_id':ref,'target_in_retained_bundle':target is not None,'candidate_value_available':value is not None,'claim_value_provenance':'copied from source cell, not LLM output'}
     report=None
     try:
      if not isinstance(ref,str) or not ref:row.update(execution='not_attempted_no_declared_reference',results=[])
      else:
       report=review_native_paths(claim,sources,engine);row.update(execution='completed',results=report['results'],raw_shacl_conforms=report['raw_shacl_conforms'])
       # Exact serialized shapes can differ only by prefix order; preserve every variant.
       for field,store in [('shapes_turtle',shapes),('effective_shapes_turtle',effective)]:
        if report[field] is not None:
         key=hashlib.sha256(report[field].encode()).hexdigest();store[key]=report[field];row[field+'_sha256']=key
       all_statuses.update((engine,r['check_id'],r['status']) for r in report['results'])
     except ValueError as e:row.update(execution='input_failure',error=str(e),results=[])
     except Exception as e:row.update(execution='execution_failure',error=type(e).__name__+': '+str(e),results=[])
     raw.write((json.dumps({'row':row,'claim':claim,'sources':sources,'report':report},ensure_ascii=False)+'\n').encode());rows.append(row);pair.append(row)
    pairs.append({'case_id':case_id,'same_execution':pair[0]['execution']==pair[1]['execution'],'same_checks':pair[0]['results']==pair[1]['results']})
 counts=collections.Counter(r['execution'] for r in rows)
 expected=[a['node_id']+'/'+kind for a in anchors for kind in POLICIES]
 checks={'full_universe':len(expected)==486 and len(rows)==972 and len({(r['case_id'],r['engine']) for r in rows})==972,'all_pairs_retained':len(pairs)==486,'all_pair_states_match':all(p['same_execution'] and p['same_checks'] for p in pairs),'no_unexpected_failures':not counts['input_failure'] and not counts['execution_failure'],'corpus_hash_unchanged':sha(SOURCE)==source_hash}
 summary={'inventory':{'nodes':328,'annotation_rows':243,'dictionary_rows':85},'candidate_links':486,'engine_attempt_slots':972,'execution_counts':dict(counts),'status_counts':[{'engine':e,'check_id':c,'status':s,'count':n} for (e,c,s),n in sorted(all_statuses.items())],'unavailable_target_links':sum(not r['target_in_retained_bundle'] for r in rows if r['engine']=='python'),'missing_value_links':sum(not r['candidate_value_available'] for r in rows if r['engine']=='python'),'all_checks_pass':all(checks.values()),'new_paid_calls':0,'new_sources':0,'limits':['consumed development source census, not fresh QA/benchmark','claim values copied from source; value agreement tautological when available','same-policy six-rule subset only; no unit agreement','missing retained target does not prove global source absence','shared projection and missing gates; no independent semantic interpretation','ValueError classification limited to inspected corpus and runner, not general failure taxonomy']}
 dump(out/'rows.json',rows);dump(out/'pairs.json',pairs);dump(out/'checks.json',checks);dump(out/'summary.json',summary)
 for key,text in shapes.items():(out/f'input-shapes-{key}.ttl').write_text(text)
 for key,text in effective.items():(out/f'effective-shapes-{key}.ttl').write_text(text)
 dump(out/'manifest.json',{'source':str(SOURCE),'source_sha256':source_hash,'source_attribution':corpus['source_attribution'],'code_hashes':{x:sha(Path(x)) for x in ['scripts/audit_postreview_source_paths.py','scripts/postreview_native_paths.py','scripts/postreview_lookup.py','scripts/post_answer_review.py']},'artifacts':{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
 print(json.dumps({k:v for k,v in summary.items() if k!='status_counts'}))
 if not summary['all_checks_pass']:raise SystemExit(1)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output)
