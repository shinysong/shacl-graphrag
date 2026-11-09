# Source presence preservation diagnostic (planned, not executed)

Purpose: identify the exact operational metadata Neo4j/LPG and Neptune/RDF must retain to preserve already-declared CycloneDX meanings. This is an adapter correctness question, not an inference-engine performance comparison.

Use five pinned original SBOM documents and all679nodes including roots. Preserve source SHA256, per-document bom-ref namespace, pointer, specVersion, component scope presence/raw value, top-level dependency-field presence, per-node dependency-entry presence, and edge targets. Freeze policy(schema) hash separately. Dependencies absent in raw source are unknown; missing projection while source field advertised present must remain projection loss, not source absence. Missing component scope may use pinned consumer default, with raw absence retained for provenance; no customer-installation inference.

Compare (1) shared source reader; (2) property-node/edge payload roundtrip; (3) RDF serialization/SPARQL roundtrip. These are OFFLINE representation adapters, not actualDB runs. Actual backend parity requires a new bounded live phase and independent reviewed queries. Edge-only ablation drops entry-presence metadata; report unanswerability/collisions, do not silently assign empty to missing. Include authored paired input controls differing only in empty-entry vs absent-entry, omitted-scope vs explicitrequired, and sourceabsence vs deliberately lost projection; label these synthetic controls separately from real-file observations.

Denominator all679nodes times two tasks, failures retained individually. Exact source/presence tuple roundtrip and decision classification are separate outcomes; byte-identical RDF serialization not required. No LLM calls. Compare only document semantics, no freshheldout, ontology automaticgeneration, maintenance labor, real deployment safety or graphDB superiority claims. Do not start Neptune solely to repeat offline facts; live phase should specifically test adapter/query path equivalence and provenance retention.

Implementation (complete new diagnostic):
```python
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
    needed={'dependency_entry_present','scope_present','scope_value','scope_default'}
    if not needed <= record.keys():return {'dependency':'projection_unknown','scope':'projection_unknown'}
    return {'dependency':('unknown' if not record['dependency_entry_present'] else
                           'reported_nonempty' if record['targets'] else 'explicit_empty'),
            'scope':record['scope_value'] if record['scope_present'] else record['scope_default']}


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


def evaluate(source,out):
    out.mkdir(parents=True,exist_ok=False);rows=[];failures=[]
    for path in sorted(source.glob('SBOM__*.json')):
        try:inputs=list(records(path))
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
    summary={'planned_nodes':len(rows),'source_failures':failures,'completed':sum(r['state']=='completed' for r in rows),
             'failed':sum(r['state']=='failed' for r in rows),
             'exact_property_roundtrips':sum(r.get('property_exact',False) for r in rows),
             'exact_rdf_roundtrips':sum(r.get('rdf_exact',False) for r in rows),
             'edge_only_ambiguous':sum(r.get('edge_only_dependency')=='ambiguous_empty_or_unknown' for r in rows),
             'limits':'Offline property-payload/RDFLib SPARQL roundtrip, not Neo4j or Neptune execution. Inspected development files; source absence is not world absence. No maintenance effort, latency or SHACL advantage measurement.'}
    (out/'evaluation.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();print(json.dumps(evaluate(args.source,args.output)))

```
Tests:
```python
from scripts.sbom_projection import answers, rdf_roundtrip


def record():
    return dict(id='doc:ref',ref='ref',document_hash='a'*64,pointer='/components/0',
                spec_version='1.4',dependency_field_present=True,dependency_entry_present=True,
                scope_present=False,scope_value='',scope_default='required',targets=[],policy_hash='b'*64)


def test_presence_collisions_and_provenance():
    a=record();b={**a,'dependency_entry_present':False}
    assert a['targets']==b['targets']
    assert answers(a)['dependency']=='explicit_empty'
    assert answers(b)['dependency']=='unknown'
    c={**a,'scope_present':True,'scope_value':'required'}
    assert answers(a)['scope']==answers(c)['scope']=='required'
    assert rdf_roundtrip(a)==a and rdf_roundtrip(b)==b and rdf_roundtrip(c)==c
    assert rdf_roundtrip(a)!=rdf_roundtrip(c)


def test_projection_loss_is_not_source_absence():
    a=record();del a['dependency_entry_present']
    assert answers(a)['dependency']=='projection_unknown'
    assert answers(record())['dependency']=='explicit_empty'

```
Direct2tests passed. Sourcebytes not included; plannedexpected679nodes known inventory, fail if sourcefailures oractualcount mismatch; do not infer expectedcount from onlysuccessfulfiles. No liveDB execution. Existing paidledger unchanged.
