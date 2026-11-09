# Published manufacturing ticket identity review
Existing mainworkbook case retained. Auxiliary manufacturingdocument collection Fujitsu pinnedHF4244add75777abb16ddebe1b061c99ce5338c771,CCBY4.0,pinnedREADME. CSV100records13cols from172049bytes. Operationalauthenticity/syntheticstatusunknown; do notclaim genuine industrialincidents. Names andlocationfields only, no physicalinstructions/causalrecommendations. Sourceinspectionobserved oneequipmentnamemultiplelocations; maybemovedsameasset orhomonymousassets, notknownbadmerge. Three groupingpolicies on same100rows: Equipment,Location+Equipment,Location+Equipment+Device. Shared advisorymax1reportedlocation pergroup andmin1location perrecord, independent Pythonlen vs actualpySHACL. Locationgroupingpassesbyconstruction; zeroflagsnotaccuracyimprovement. Full3plannedpolicydenominator and failuresretained. IDs/provenance preserved. No actualDB/LLM calls; no goldrepair or automaticassetidentity resolution. Returnhumanreviewpointer only. Fourdirectsoftwarecheckspass; source omitted unverified byreview.


Revision: strict UTF8/CSV, header uniqueness and row widths; acquisition/parse failures retain all three policy rows; audit/artifact failures distinguished. Six additional malformed-input retention checks.

```python
"""Published ticket identity review; grouping policy is not physical asset identity."""
import csv,json,hashlib,io
from pathlib import Path
from urllib.parse import quote
from collections import defaultdict
from rdflib import Graph,URIRef,Literal,Namespace,RDF
from pyshacl import validate

N=Namespace('urn:manufacturing-identity-review:')
SH=Namespace('http://www.w3.org/ns/shacl#')
POLICIES={'name_only':['Equipment'],'location_equipment':['Location','Equipment'],
          'location_equipment_device':['Location','Equipment','Device']}


def audit(rows, fields):
    if len({r['Incident_ID'] for r in rows})!=len(rows):raise ValueError('duplicate_incident_id')
    if any(not r['Incident_ID'].strip() for r in rows):raise ValueError('empty_incident_id')
    groups=defaultdict(list)
    for row in rows:
        if not all(k in row and isinstance(row[k],str) for k in {'Incident_ID','Location','Equipment','Device'}):raise ValueError('missing_required_field')
        groups[tuple(row[k] for k in fields)].append(row)
    data=Graph();shapes=Graph();expected=set();mapping={};group_rows=[]
    record_shape=N.RecordShape;group_shape=N.GroupShape
    for shape,klass,prop,path,count_pred in [(record_shape,N.Record,N.RecordLocation,N.location,SH.minCount),(group_shape,N.Group,N.GroupLocation,N.location,SH.maxCount)]:
        shapes.add((shape,RDF.type,SH.NodeShape));shapes.add((shape,SH.targetClass,klass));shapes.add((shape,SH.property,prop));shapes.add((prop,SH.path,path));shapes.add((prop,count_pred,Literal(1)))
    for key,members in sorted(groups.items()):
        encoded=json.dumps(key,ensure_ascii=False,separators=(',',':'));gid=hashlib.sha256(encoded.encode()).hexdigest();g=N['group:'+gid];mapping[str(g)]=('group',gid)
        data.add((g,RDF.type,N.Group));locations=sorted({r['Location'] for r in members if r['Location'].strip()})
        for location in locations:data.add((g,N.location,Literal(location)))
        if len(locations)>1:expected.add(('group',gid,'multiple_reported_locations'))
        for row in members:
            record=N['record:'+quote(row['Incident_ID'],safe='')];mapping[str(record)]=('record',row['Incident_ID'])
            data.add((record,RDF.type,N.Record));data.add((g,N.member,record))
            if row['Location'].strip():data.add((record,N.location,Literal(row['Location'])))
            else:expected.add(('record',row['Incident_ID'],'missing_location'))
        group_rows.append({'group_id':gid,'key':list(key),'incident_ids':[r['Incident_ID'] for r in members],
                           'reported_locations':locations,'review_needed':len(locations)>1,
                           'interpretation':'Review pointer only; does not assert same/different physical asset'})
    conform,report,_=validate(data,shacl_graph=shapes,inference='none',advanced=False)
    measured=set()
    for result in report.subjects(RDF.type,SH.ValidationResult):
        focus=str(report.value(result,SH.focusNode));shape=report.value(result,SH.sourceShape)
        category='missing_location' if shape==N.RecordLocation else 'multiple_reported_locations' if shape==N.GroupLocation else None
        if category is None:raise ValueError('unexpected_shape')
        measured.add((*mapping[focus],category))
    return {'groups':group_rows,'python_findings':[list(x) for x in sorted(expected)],'shacl_findings':[list(x) for x in sorted(measured)],
            'findings_equal':expected==measured,'shacl_conforms':bool(conform),'input_records':len(rows),
            'limits':['Policy authored after source inspection; exploratory','Grouping keys are declared reporting scopes, not verified asset identities','Location grouping conforms by construction, not accuracy improvement','No physical prescriptions or automatic record repair']},data,shapes,report


def run(source,output):
    out=Path(output);out.mkdir(exist_ok=False,parents=True)
    manifest={'source':str(source),'planned_policies':list(POLICIES),'rows':None}
    results=[];phase='acquisition'
    try:
        raw=Path(source).read_bytes();manifest['sha256']=hashlib.sha256(raw).hexdigest()
        phase='csv_parse'
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
        headers=reader.fieldnames
        if not headers or len(headers)!=len(set(headers)) or any(not h.strip() for h in headers):raise ValueError('invalid_headers')
        if not {'Incident_ID','Location','Equipment','Device'}.issubset(headers):raise ValueError('missing_required_headers')
        rows=list(reader)
        if any(None in row or any(v is None for v in row.values()) for row in rows):raise ValueError('row_width_mismatch')
        manifest['rows']=len(rows)
    except Exception as exc:
        results=[{'policy':name,'status':'input_error','phase':phase,'error':type(exc).__name__+':'+str(exc)} for name in POLICIES]
    if not results:
        for name,fields in POLICIES.items():
            phase='audit'
            try:
                result,data,shapes,report=audit(rows,fields);result.update(policy=name,status='completed')
                phase='artifact_write'
                data.serialize(out/(name+'-data.ttl'),format='turtle');shapes.serialize(out/(name+'-shapes.ttl'),format='turtle');report.serialize(out/(name+'-report.ttl'),format='turtle')
            except Exception as exc:result={'policy':name,'status':'execution_error','phase':phase,'error':type(exc).__name__+':'+str(exc)}
            results.append(result)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False)+'\n')
    return results

if __name__=='__main__':
    import sys
    run(sys.argv[1],sys.argv[2])

```

```python
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('identity',Path(__file__).with_name('runtime.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def row(i,location):return {'Incident_ID':i,'Location':location,'Equipment':'same name','Device':'motor'}
rows=[row('one','A'),row('two','B')]
for fields,count in [(['Equipment'],1),(['Location','Equipment'],0)]:
 r,*_=m.audit(rows,fields);assert r['findings_equal'] and len(r['python_findings'])==count
r,*_=m.audit([row('one','A'),row('two','')],['Equipment']);assert r['findings_equal'] and r['python_findings']==[['record','two','missing_location']]
try:m.audit([row('one','A'),row('one','B')],['Equipment'])
except ValueError:pass
else:raise AssertionError('duplicate accepted')
print('four software checks passed; no observed source run')

import tempfile,json
with tempfile.TemporaryDirectory() as tmp:
 base=Path(tmp)
 for i,body in enumerate([b'\xff', b'Incident_ID,Location,Equipment,Device,Device\na,A,x,y,z\n', b'Incident_ID,Location,Equipment,Device\na,A,x,y,extra\n', b'Incident_ID,Location,Equipment,Device\na,A,x\n', b'Incident_ID,Location,Equipment,Device\n"unterminated']):
  source=base/str(i);source.write_bytes(body)
  result=m.run(source,base/(str(i)+'out'))
  assert len(result)==3 and all(r['status']=='input_error' and r['phase']=='csv_parse' for r in result)
  assert json.loads((base/(str(i)+'out')/'results.json').read_text())==result
 result=m.run(base/'absent',base/'missingout')
 assert len(result)==3 and all(r['phase']=='acquisition' for r in result)
print('six additional failure retention checks passed')

```
