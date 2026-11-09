"""Offline presence-preserving SBOM representation diagnostic; no DB or API clients."""
import argparse
import hashlib
import json
from pathlib import Path
from rdflib import Graph, Literal, Namespace, URIRef

EX = Namespace('urn:sbom-projection:')
FIELDS = ('document_hash','pointer','spec_version','dependency_field_present',
          'dependency_entry_present','scope_present','scope_value','scope_default')


def records(path):
    raw=path.read_bytes();doc=json.loads(raw);digest=hashlib.sha256(raw).hexdigest()
    schema_path=path.parent/('schema14.json' if doc['specVersion']=='1.4' else 'schema12.json')
    schema=json.loads(schema_path.read_text())
    default=schema['definitions']['component']['properties']['scope']['default']
    entries={}
    for e in doc.get('dependencies',[]):
        if e['ref'] in entries:raise ValueError('duplicate_dependency_entry')
        entries[e['ref']]=e
    nodes=[(f'/components/{i}',n) for i,n in enumerate(doc['components'])]
    if doc.get('metadata',{}).get('component',{}).get('bom-ref'):
        nodes.append(('/metadata/component',doc['metadata']['component']))
    seen=set()
    for pointer,n in nodes:
        ref=n['bom-ref']
        if ref in seen:raise ValueError('duplicate_component')
        seen.add(ref)
        yield {'id':digest+':'+ref,'ref':ref,'document_hash':digest,'pointer':pointer,
               'spec_version':doc['specVersion'],'dependency_field_present':'dependencies' in doc,
               'dependency_entry_present':ref in entries,'scope_present':'scope' in n,
               'scope_value':n.get('scope',''),'scope_default':default,
               'targets':sorted(entries.get(ref,{}).get('dependsOn',[])),
               'policy_hash':hashlib.sha256(schema_path.read_bytes()).hexdigest()}


def answers(record):
    dependency_ready={'dependency_entry_present','targets'} <= record.keys()
    scope_ready={'scope_present','scope_value','scope_default'} <= record.keys()
    return {'dependency':('projection_unknown' if not dependency_ready else 'unknown' if not record['dependency_entry_present'] else
                           'reported_nonempty' if record['targets'] else 'explicit_empty'),
            'scope':('projection_unknown' if not scope_ready else record['scope_value'] if record['scope_present'] else record['scope_default'])}


def rdf_roundtrip(record):
    g=Graph();node=URIRef('urn:sha256:'+hashlib.sha256(record['id'].encode()).hexdigest())
    for key in (*FIELDS,'id','ref','policy_hash'):g.add((node,EX[key],Literal(record[key])))
    for target in record['targets']:g.add((node,EX.target,Literal(target)))
    restored=Graph().parse(data=g.serialize(format='turtle'),format='turtle')
    out={}
    for key in (*FIELDS,'id','ref','policy_hash'):
        rows=list(restored.query('SELECT ?v WHERE { ?n ?p ?v }',initBindings={'n':node,'p':EX[key]}))
        if len(rows)!=1:raise ValueError('nonunique_projected_property')
        out[key]=rows[0][0].toPython()
    out['targets']=sorted(str(row[0]) for row in restored.query('SELECT ?v WHERE { ?n ?p ?v }',initBindings={'n':node,'p':EX.target}))
    return out


def evaluate(source,out,inventory):
    out.mkdir(parents=True,exist_ok=False);rows=[];failures=[]
    assert sum(f['nodes'] for f in inventory['files'])==inventory['planned_nodes']
    for item in inventory['files']:
        path=source/item['name']
        try:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('source_hash_mismatch')
            inputs=list(records(path))
            if len(inputs)!=item['nodes']:raise ValueError('source_node_count_mismatch')
        except Exception as exc:
            failures.append({'source':path.name,'error':type(exc).__name__+':'+str(exc)})
            continue
        for record in inputs:
            row={'source':path.name,'id':record['id'],'state':'started'}
            try:
                # Explicit property-node/edge JSON payload is not an actual Neo4j server.
                property_copy=json.loads(json.dumps(record));rdf_copy=rdf_roundtrip(record)
                row.update(state='completed',source_answer=answers(record),
                           property_answer=answers(property_copy),rdf_answer=answers(rdf_copy),
                           property_exact=property_copy==record,rdf_exact=rdf_copy==record,
                           edge_only_dependency=('reported_nonempty' if record['targets'] else 'ambiguous_empty_or_unknown'),
                           source_entry_present=record['dependency_entry_present'])
            except Exception as exc:row.update(state='failed',error=type(exc).__name__+':'+str(exc))
            rows.append(row)
            with (out/'rows.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
    summary={'planned_nodes':inventory['planned_nodes'],'emitted_nodes':len(rows),'not_emitted_nodes':inventory['planned_nodes']-len(rows),'source_failures':failures,'completed':sum(r['state']=='completed' for r in rows),
             'failed':sum(r['state']=='failed' for r in rows),
             'exact_property_roundtrips':sum(r.get('property_exact',False) for r in rows),
             'exact_rdf_roundtrips':sum(r.get('rdf_exact',False) for r in rows),
             'edge_only_ambiguous':sum(r.get('edge_only_dependency')=='ambiguous_empty_or_unknown' for r in rows),
             'limits':'Offline property-payload/RDFLib SPARQL roundtrip, not Neo4j or Neptune execution. Inspected development files; source absence is not world absence. No maintenance effort, latency or SHACL advantage measurement.'}
    (out/'evaluation.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('output',type=Path);parser.add_argument('inventory',type=Path)
    args=parser.parse_args();print(json.dumps(evaluate(args.source,args.output,json.loads(args.inventory.read_text()))))
