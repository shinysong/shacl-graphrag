"""Posthoc label agreement for frozen document controls; never a runtime checker.

Consumes saved provider-message dictionaries, not generated or repaired answers.
Whole proposal-schema validity and citation entailment are not measured here.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def score(packet_dir, rubric_path, attempts_path, *, allow_json_envelope=False):
    root = Path(packet_dir)
    rubric_raw = Path(rubric_path).read_bytes()
    attempts_raw = Path(attempts_path).read_bytes()
    rubric = json.loads(rubric_raw)['cases']
    attempts = json.loads(attempts_raw)['attempts']
    expected = {c['id']: c for c in rubric}
    if len(expected) != len(rubric):
        raise ValueError('Duplicate rubric case')
    seen = set()
    for a in attempts:
        if a['case_id'] not in expected or not isinstance(a['attempt_id'], str) or not a['attempt_id'] or a['attempt_id'] in seen:
            raise ValueError('Unknown case or duplicate/invalid attempt ID')
        if a['status'] not in ('response', 'failed'):
            raise ValueError('Explicit response or failed status required')
        seen.add(a['attempt_id'])
    captures = {r['id']: r for r in json.loads((root/'manifest.json').read_text())['records']}
    rows = []
    hashes = {}
    for case_id, case in expected.items():
        # Case IDs originate in the separately reviewed local rubric, not responses.
        if not case_id.isascii() or not case_id.replace('_', '').isalnum():
            raise ValueError('Unsafe rubric case ID')
        capture = captures.get(case_id)
        if not capture or capture['state'] != 'captured_before_response':
            raise ValueError('Rubric requires a captured packet')
        raw = (root/(case_id+'-messages.json')).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != capture['messages_sha256']:
            raise ValueError('Packet hash mismatch')
        hashes[case_id] = digest
        packet = json.loads(json.loads(raw)[1]['content'])
        relations = {e['id']: e for e in packet['existing_relations']}
        evidence_ids = {e['id'] for e in packet['entries']}
        pair = set(case['assessment_of_pair'])
        candidates = [e for e in relations.values() if
                      {e[k]['file']+':'+e[k]['column'] for k in ('source', 'target')} == pair]
        if not candidates or case['expected'] not in ('supported', 'contradicted', 'uncertain'):
            raise ValueError('Missing candidate or invalid expectation')
        selected = [a for a in attempts if a['case_id'] == case_id]
        if not selected:
            rows.append({'case_id':case_id, 'state':'not_attempted', 'directions':[]})
        for attempt in selected:
            result = {'case_id':case_id, 'attempt_id':attempt['attempt_id'], 'directions':[]}
            if attempt['status'] == 'failed':
                result.update(state='execution_failed', error=attempt.get('error'))
                rows.append(result)
                continue
            try:
                if allow_json_envelope:
                    from apps.factory_lab.preparation_model import decode_proposal
                    response, envelope = decode_proposal(attempt['message']['content'])
                    result['response_format'] = envelope
                else:
                    response = json.loads(attempt['message']['content'])
                values = response.get('relation_assessments', [])
                if not isinstance(values, list):
                    raise ValueError('Assessments must be a list')
                indexed = {}
                for v in values:
                    key = v['id']
                    if key not in relations or key in indexed or v['assessment'] not in ('supported', 'contradicted', 'uncertain'):
                        raise ValueError('Invalid/duplicate assessment')
                    evidence = v.get('evidence', [])
                    if not isinstance(evidence, list) or any(not isinstance(x, str) or x not in evidence_ids for x in evidence):
                        raise ValueError('Unknown evidence pointer')
                    if v['assessment'] != 'uncertain' and not evidence:
                        raise ValueError('Missing evidence pointer')
                    indexed[key] = v
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                result.update(state='assessment_invalid', error=str(exc))
            else:
                result['state'] = 'assessment_scored'
                for e in candidates:
                    value = indexed.get(e['id'])
                    actual = value['assessment'] if value else None
                    result['directions'].append({'id':e['id'], 'source':e['source'], 'target':e['target'],
                        'expected':case['expected'], 'actual':actual,
                        'outcome':'unassessed' if value is None else 'agrees' if actual == case['expected'] else 'disagrees',
                        'evidence_ids':value.get('evidence', []) if value else []})
            rows.append(result)
    return {'scope':'Authored development pair-label agreement, directions retained separately. Not direction correctness, citation entailment, full response validity, truth, approval or model quality evidence by itself.',
            'rubric_sha256':hashlib.sha256(rubric_raw).hexdigest(),
            'attempts_sha256':hashlib.sha256(attempts_raw).hexdigest(), 'packet_sha256':hashes,
            'response_policy':'single-json-envelope-v1' if allow_json_envelope else 'strict-json',
            'planned_cases':len(rubric), 'recorded_attempts':len(attempts),
            'case_attempt_states':dict(Counter(r['state'] for r in rows)),
            'direction_outcomes':dict(Counter(d['outcome'] for r in rows for d in r['directions'])),
            'results':rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packets'); parser.add_argument('rubric'); parser.add_argument('attempts')
    parser.add_argument('output')
    parser.add_argument('--allow-json-envelope',action='store_true',help='Explicit changed-parser diagnostic; never rewrite original strict results')
    args = parser.parse_args()
    report = score(args.packets, args.rubric, args.attempts, allow_json_envelope=args.allow_json_envelope)
    with Path(args.output).open('x') as out:
        json.dump(report, out, ensure_ascii=False, indent=2)
