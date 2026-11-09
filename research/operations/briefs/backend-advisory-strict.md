# Version2 metadata boundary contract
Prior frozen17case diagnostic observed34slots,30completed4PythonTypeError(nonstring),13completepairs12codeagree; trailingLF caseSHACLconforms vsPythonmalformed. Retainv1/old168pairs336slots unchanged. NewV2: common explicit metadata dict/string-or-null input gate, no unknownkeys; nonstring rejection beforebothcheckers is NOT SHACLconformance. NewSHACLdatatype:string and min/maxLength64 plusoldpattern. ExistingPythonfullmatch unchanged. Replays168oldinputs+17authoredboundaries=185pairs370slots, notnewbenchmark. No originalanswer change/veto/repair/sourcefetch/LLM/DB. Oldreference onlyposthoccomparison; runtimeonlyinputsmetadata. Recordallfailures and rejectionseparately, no classifyrejectionasagreement. Followupdesignedaftercounterexample, consumeddevelopment. No arbitraryJSON/RDFgeneralparityclaim, samecanonicalprovenance limitations. Reviewcompletechangedsource/scorer/shapes below; shared importedchecker doesPythonre.fullmatch('[0-9a-f]{64}',value),missingNone,comparessets; SHACLmapsnonNoneLiteral,pyshacl.validate(inference=none,advanced=False),normalizedmessages. Earlierchecker source reviewed; omittedhereunverified. Main2unittestspassed; independentlyreviewdesignbefore370slotrun. Registeredchecksempty.

FILE scripts/backend_advisory_strict.py
"""Versioned metadata contract: shared input gate plus exact-length SHACL.

This diagnostic preserves v1 outputs; a rejected input is not SHACL conformance.
"""
import argparse
import json
from pathlib import Path

from rdflib import Graph
from scripts.backend_advisory import python_report, shacl_report
from scripts.backend_parity import canonical

FIELDS = {'used_input_hash', 'current_input_hash'}


def input_error(metadata):
    if not isinstance(metadata, dict):
        return 'metadata_must_be_object'
    if set(metadata) - FIELDS:
        return 'unexpected_metadata_field'
    if any(value is not None and not isinstance(value, str) for value in metadata.values()):
        return 'fingerprint_must_be_string_or_null'
    return None


def run(parents, shapes_path, output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = []
    for parent in parents:
        for item in json.loads((parent / 'inputs.json').read_text()):
            inputs.append({**item, 'id': parent.name + '/' + item['id'], 'parent_run': parent.name, 'parent_id': item['id']})
    plan = [{'id': item['id'], 'checker': checker} for item in inputs for checker in ('python', 'shacl')]
    (output / 'inputs.json').write_text(canonical(inputs) + '\n')
    (output / 'plan.json').write_text(canonical(plan) + '\n')
    (output / 'runtime.py').write_bytes(Path(__file__).read_bytes())
    (output / 'advisory-runtime.py').write_bytes(Path('scripts/backend_advisory.py').read_bytes())
    (output / 'shapes.ttl').write_bytes(shapes_path.read_bytes())
    shapes = Graph().parse(shapes_path, format='turtle')
    with (output / 'results.jsonl').open('a') as handle:
        for index, item in enumerate(inputs):
            error = input_error(item['metadata'])
            for checker in ('python', 'shacl'):
                row = {'id': item['id'], 'checker': checker, 'parent_run': item['parent_run'], 'parent_id': item['parent_id'], 'answer_changed': False}
                if 'original_answer' in item:
                    row['original_answer'] = item['original_answer']
                    row['original_status'] = item['original_status']
                if error:
                    row.update(status='input_rejected', error=error, decision='invalid_input_not_conformance')
                else:
                    try:
                        if checker == 'python':
                            codes = python_report(item['metadata'])
                        else:
                            report = shacl_report(item['metadata'], shapes)
                            codes = report['codes']
                            row['conforms'] = report['conforms']
                            (output / f'{index}-report.ttl').write_text(report['validation_graph'])
                        row.update(status='completed', codes=codes, review_requested=bool(codes), decision='advisory_only_no_veto')
                    except Exception as exc:
                        row.update(status='checker_failure', error=f'{type(exc).__name__}: {exc}')
                handle.write(canonical(row) + '\n')
                handle.flush()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, action='append', required=True)
    parser.add_argument('--shapes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.parent, args.shapes, args.output)

FILE tests/test_backend_advisory_strict.py
import unittest
from scripts.backend_advisory_strict import input_error


class StrictEnvelopeTests(unittest.TestCase):
    def test_input_boundary_rejects_nonstring_and_unknown_fields(self):
        for value in (True, 123, ['a'], {'value': 'a'}):
            self.assertEqual(input_error({'used_input_hash': value}), 'fingerprint_must_be_string_or_null')
        self.assertEqual(input_error({'answer': 'not-checker-input'}), 'unexpected_metadata_field')
        self.assertEqual(input_error(['a']), 'metadata_must_be_object')

    def test_missing_and_malformed_strings_reach_semantic_checker(self):
        for metadata in ({}, {'used_input_hash': None}, {'used_input_hash': ''}, {'current_input_hash': 'a'*64+'\n'}):
            self.assertIsNone(input_error(metadata))

FILE research/backend-reasoning-review-1/advisory-contracts-002/shapes.ttl
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix ex: <urn:shacl-study:advisory:> .
ex:ResultShape a sh:NodeShape ; sh:targetClass ex:Result ;
 sh:property ex:UsedRequired, ex:CurrentRequired, ex:UsedFormat, ex:CurrentFormat, ex:VersionAgreement .
ex:UsedRequired sh:path ex:usedHash ; sh:minCount 1 ; sh:message "missing_used_fingerprint" .
ex:CurrentRequired sh:path ex:currentHash ; sh:minCount 1 ; sh:message "missing_current_fingerprint" .
ex:UsedFormat sh:path ex:usedHash ; sh:datatype xsd:string ; sh:minLength 64 ; sh:maxLength 64 ; sh:pattern "^[0-9a-f]{64}$" ; sh:message "malformed_used_fingerprint" .
ex:CurrentFormat sh:path ex:currentHash ; sh:datatype xsd:string ; sh:minLength 64 ; sh:maxLength 64 ; sh:pattern "^[0-9a-f]{64}$" ; sh:message "malformed_current_fingerprint" .
ex:VersionAgreement sh:path ex:usedHash ; sh:equals ex:currentHash ; sh:message "fingerprint_disagreement_review_scope" .

FILE research/backend-reasoning-review-1/evaluation/score_strict.py
"""Posthoc version comparison on consumed authored inputs, never runtime repair."""
import json, sys
from pathlib import Path
from scripts.check_backend_evidence import coverage
out=Path(sys.argv[1]); inputs=json.loads((out/'inputs.json').read_text());plan=json.loads((out/'plan.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()];coverage(plan,rows,('id','checker'))
lookup={(r['id'],r['checker']):r for r in rows};old=Path('research/backend-reasoning-review-1/advisory-replay-001');oldrows=[json.loads(x) for x in (old/'results.jsonl').read_text().splitlines()];oldlookup={(r['id'],r['policy']):r for r in oldrows}
pairs=[];unchanged=0
for x in inputs:
 a,b=[lookup[(x['id'],c)] for c in ('python','shacl')];both=a['status']==b['status']=='completed';reject=a['status']==b['status']=='input_rejected' and a['error']==b['error'];agree=both and a['codes']==b['codes'];pairs.append({'id':x['id'],'completed_pair':both,'code_agreement':agree,'shared_rejection':reject})
 for r in (a,b):
  assert r['answer_changed'] is False
  if 'original_answer' in x:assert r['original_answer']==x['original_answer'] and r['original_status']==x['original_status']
 if x['parent_run']=='advisory-replay-001':
  unchanged+=all(r['status']=='completed' and r['codes']==oldlookup[(x['parent_id'],r['checker'])]['codes'] for r in (a,b))
result={'planned':len(plan),'observed':len(rows),'completed':sum(r['status']=='completed' for r in rows),'input_rejected':sum(r['status']=='input_rejected' for r in rows),'checker_failures':sum(r['status']=='checker_failure' for r in rows),'pairs':len(pairs),'completed_pairs':sum(p['completed_pair'] for p in pairs),'agreeing_completed_pairs':sum(p['code_agreement'] for p in pairs),'shared_rejected_pairs':sum(p['shared_rejection'] for p in pairs),'unchanged_old_pairs':unchanged,'checks':pairs,'scope':'Post-observation contract revision on consumed inputs, no general arbitraryinput parity or QA efficacy; shared input rejections not SHACL conformance.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
assert all(p['code_agreement'] or p['shared_rejection'] for p in pairs)
