# Posthoc advisory metadata review
UserwantsSHACLfinalreviewratherthancompulsoryveto. Sixauthoreddiagnostics, two unchangedselectedsourcewitnessmetadata cases andfourcontrolledmetadatainterventions. Common suppliedsourcehashes/counts/booleans;notnatural-languageextraction ornewindependentknowledge. SameinputPythonandpySHACL; advisoryonly,noanswerchange/veto/extra source lookup. Priorwitness/XMLsourceverification separateandnot suppliedhere. Selectedsupportnottruth;emptyanswerdoesnotproveabsence. Fullscopeflagsunloadedcontextasneedsreview,notknownwronganswer. StrictsharedIOchecks precedebothcomparators. Controlsplannednotrun.
```python
"""Advisory-only posthoc review over common evidence metadata, no repair."""
import json,re
from pathlib import Path
from rdflib import Graph,Namespace,RDF,Literal
from pyshacl import validate
E=Namespace('urn:manufacturing-review:');SH=Namespace('http://www.w3.org/ns/shacl#')
SHAPES='''@prefix e: <urn:manufacturing-review:> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
e:Snapshot a sh:NodeShape; sh:targetClass e:Review;
 sh:property [sh:path e:selected_hash; sh:equals e:required_hash; sh:message "snapshot_mismatch"] .
e:Support a sh:NodeShape; sh:targetClass e:Review;
 sh:property [sh:path e:unsupported_count; sh:maxInclusive 0; sh:message "unsupported_returned_value"] .
e:Execution a sh:NodeShape; sh:targetClass e:Review;
 sh:property [sh:path e:execution_status; sh:hasValue "completed"; sh:message "execution_unavailable"] .
e:Context a sh:NodeShape; sh:targetClass e:Review; sh:message "full_context_unverified";
 sh:or ( [sh:property [sh:path e:requires_full_context; sh:hasValue false]]
         [sh:property [sh:path e:unloaded_count; sh:maxInclusive 0]] ) .
'''
FIELDS={'selected_hash','required_hash','unsupported_count','returned_count','unloaded_count','execution_status','requires_full_context'}
def checked(row):
 if set(row)!=FIELDS:raise ValueError('field_contract')
 for k in ('selected_hash','required_hash'):
  if not isinstance(row[k],str) or not re.fullmatch('[a-f0-9]{64}',row[k]):raise ValueError('hash_contract')
 for k in ('unsupported_count','returned_count','unloaded_count'):
  if type(row[k]) is not int or row[k]<0:raise ValueError('count_contract')
 if row['unsupported_count']>row['returned_count']:raise ValueError('support_count_contract')
 if type(row['requires_full_context']) is not bool or row['execution_status'] not in ('completed','query_failed','unsupported_selected_adapter'):raise ValueError('state_contract')
 return row

def python_flags(row):
 r=checked(row);flags=[]
 if r['selected_hash']!=r['required_hash']:flags.append('snapshot_mismatch')
 if r['unsupported_count']:flags.append('unsupported_returned_value')
 if r['execution_status']!='completed':flags.append('execution_unavailable')
 if r['requires_full_context'] and r['unloaded_count']:flags.append('full_context_unverified')
 return sorted(flags)

def shacl_flags(row):
 r=checked(row);g=Graph();g.add((E.packet,RDF.type,E.Review))
 for k,v in r.items():g.add((E.packet,E[k],Literal(v)))
 shapes=Graph().parse(data=SHAPES,format='turtle');ok,report,_=validate(g,shacl_graph=shapes,inference='none',advanced=False)
 flags=sorted({str(m) for result in report.subjects(RDF.type,SH.ValidationResult) for m in report.objects(result,SH.resultMessage)})
 if ok!= (not flags):raise ValueError('unexpected_empty_report')
 return flags,g.serialize(format='turtle'),report.serialize(format='turtle')

def run(fixtures,out):
 cases=json.loads(Path(fixtures).read_text());out=Path(out);out.mkdir(parents=True,exist_ok=False);results=[]
 (out/'shapes.ttl').write_text(SHAPES)
 for i,case in enumerate(cases):
  row={'id':case['id'],'basis':case['basis'],'advisory_only':True,'answer_changed':False}
  try:
   p=python_flags(case['metadata']);s,data,report=shacl_flags(case['metadata']);row.update(status='completed',python=p,shacl=s,equal=p==s)
   (out/f'{i}-data.ttl').write_text(data);(out/f'{i}-report.ttl').write_text(report)
  except Exception as e:row.update(status='input_or_checker_failed',error=type(e).__name__+': '+str(e))
  results.append(row)
  with (out/'rows.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 summary={'planned':len(cases),'emitted':len(results),'completed':sum(r['status']=='completed' for r in results),'equal':sum(r.get('equal',False) for r in results),'limits':['Authored diagnostic metadata interventions, not observed model mistakes','Common counts/provenance preprocessor, not SHACL-specific information gain','Advisory only; no veto, repair, extra source lookup or LLM effect measured','A conforming packet can still contain false facts if evidence cannot contradict them']}
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');return summary
if __name__=='__main__':
 import sys
 print(run(sys.argv[1],sys.argv[2]))

```
## Controls
```python
import policy
base={'selected_hash':'a'*64,'required_hash':'a'*64,'unsupported_count':0,'returned_count':7,'unloaded_count':25,'execution_status':'completed','requires_full_context':False}
for change,expected in [({},[]),({'selected_hash':'b'*64},['snapshot_mismatch']),({'requires_full_context':True},['full_context_unverified']),({'unsupported_count':1},['unsupported_returned_value']),({'execution_status':'query_failed'},['execution_unavailable']),({'returned_count':0},[])]:
 r={**base,**change};assert policy.python_flags(r)==policy.shacl_flags(r)[0]==expected
for change in ({'unsupported_count':True},{'selected_hash':'invalid'},{'unsupported_count':8}):
 for f in (policy.python_flags,policy.shacl_flags):
  try:f({**base,**change})
  except ValueError:pass
  else:raise AssertionError('invalid_input_accepted')
print('six metadata policies and three shared malformed-input controls pass; advisory only')

```
## Frozen fixtures
```json
[
  {
    "id": "selected_supported",
    "basis": "Unmodified selected-source witness metadata; not external truth",
    "metadata": {
      "selected_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "required_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "unsupported_count": 0,
      "returned_count": 7,
      "unloaded_count": 19,
      "execution_status": "completed",
      "requires_full_context": false
    }
  },
  {
    "id": "full_scope_request",
    "basis": "Authored request scope change with same selected evidence",
    "metadata": {
      "selected_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "required_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "unsupported_count": 0,
      "returned_count": 7,
      "unloaded_count": 19,
      "execution_status": "completed",
      "requires_full_context": true
    }
  },
  {
    "id": "wrong_snapshot",
    "basis": "Authored provenance mismatch, not observed engine error",
    "metadata": {
      "selected_hash": "849b29895d096867856642c777b1f6b1c9854c9932354b10a45089d3af7f6e74",
      "required_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "unsupported_count": 0,
      "returned_count": 7,
      "unloaded_count": 19,
      "execution_status": "completed",
      "requires_full_context": false
    }
  },
  {
    "id": "unsupported_value",
    "basis": "Authored unsupported-value count control, not observed model output",
    "metadata": {
      "selected_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "required_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "unsupported_count": 1,
      "returned_count": 8,
      "unloaded_count": 19,
      "execution_status": "completed",
      "requires_full_context": false
    }
  },
  {
    "id": "empty_selected",
    "basis": "Unmodified empty selected-source answer metadata, no absence claim",
    "metadata": {
      "selected_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "required_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "unsupported_count": 0,
      "returned_count": 0,
      "unloaded_count": 19,
      "execution_status": "completed",
      "requires_full_context": false
    }
  },
  {
    "id": "failed_execution",
    "basis": "Authored execution-failure control, not actual engine failure",
    "metadata": {
      "selected_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "required_hash": "ada2158cf4b307e571a243d5944422496cc80e93d33831ae92c4162505e3b2c0",
      "unsupported_count": 0,
      "returned_count": 0,
      "unloaded_count": 19,
      "execution_status": "query_failed",
      "requires_full_context": false
    }
  }
]

```
