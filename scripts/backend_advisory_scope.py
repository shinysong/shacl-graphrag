"""Declared question-family metadata replay; no current source service or answer repair."""
import json
from pathlib import Path
from rdflib import Graph
from scripts.backend_parity import canonical,digest
from scripts.backend_inference import TYPE,SC,SP
from scripts.backend_updates import input_digest
from scripts.backend_advisory import python_report,shacl_report
POLICIES={'global':{'type':'all','relation':'all'},'declared_family':{'type':'type_schema','relation':'relation_schema'},'swapped_family_control':{'type':'relation_schema','relation':'type_schema'}}


def fingerprint(state,family):
    if family=='all':return input_digest(state)
    if family=='type_schema':value={'facts':[t for t in state['facts'] if t[1]==TYPE],'schema':[t for t in state['schema'] if t[1]==SC]}
    elif family=='relation_schema':value={'facts':[t for t in state['facts'] if t[1]!=TYPE],'schema':[t for t in state['schema'] if t[1]==SP]}
    else:raise ValueError('unknown declared family')
    return digest({k:sorted(v) for k,v in value.items()})


def run(parent,shapes_path,output):
    parent=Path(parent);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    saved=[json.loads(x) for x in (parent/'results.jsonl').read_text().splitlines()]
    states=json.loads((parent/'states.json').read_text());queries=json.loads((parent/'queries.json').read_text())
    kinds={q['id']:q['kind'] for q in queries};state_by_hash={input_digest(s):s for s in states}
    plan=[{'row_index':i,'policy':p,'checker':c} for i in range(len(saved)) for p in POLICIES for c in ('python','shacl')]
    for file,value in [('plan.json',plan),('policies.json',POLICIES),('states.json',states),('queries.json',queries)]: (out/file).write_text(canonical(value)+'\n')
    (out/'runtime.py').write_bytes(Path(__file__).read_bytes());(out/'shapes.ttl').write_bytes(Path(shapes_path).read_bytes())
    # Fingerprints are published by this controlled preprocessor, not discovered by SHACL.
    inputs=[]
    try:
        for i,row in enumerate(saved):
            current=state_by_hash[row['current_input_hash']];used=state_by_hash[row['used_input_hash']]
            for policy,mapping in POLICIES.items():
                family=mapping[kinds[row['query_id']]]
                inputs.append({'row_index':i,'policy':policy,'family':family,'origin':{k:row[k] for k in ('event','arm','query_id')},'original_answer':row.get('answer'),'original_status':row['status'],'metadata':{'used_input_hash':fingerprint(used,family),'current_input_hash':fingerprint(current,family)}})
        (out/'inputs.json').write_text(canonical(inputs)+'\n')
        shapes=Graph().parse(shapes_path,format='turtle')
        with (out/'results.jsonl').open('a') as h:
            for x in inputs:
                for checker in ('python','shacl'):
                    row={**x,'checker':checker,'answer_changed':False,'decision':'advisory_only_no_veto'}
                    try:
                        if checker=='python':codes=python_report(x['metadata'])
                        else:
                            report=shacl_report(x['metadata'],shapes);codes=report['codes'];row['conforms']=report['conforms'];(out/(str(x['row_index'])+'-'+x['policy']+'-report.ttl')).write_text(report['validation_graph'])
                        row.update(status='completed',codes=codes,review_requested=bool(codes))
                    except Exception as exc:row.update(status='checker_failure',error=type(exc).__name__+': '+str(exc))
                    h.write(canonical(row)+'\n');h.flush()
    except Exception as exc:
        (out/'failure.json').write_text(canonical({'error':type(exc).__name__+': '+str(exc)})+'\n');raise

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--parent',required=True);p.add_argument('--shapes',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.parent,a.shapes,a.output)
