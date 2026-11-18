"""Offline full-adapter admissibility of saved proposals, without repair or scoring.

Successful replay means a pending draft can be built, not that its meaning,
relations, policy interpretation, or citations are correct. No gateway is used.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from apps.factory_lab import preparation
from apps.factory_lab.preparation_model import ModelProposalGenerator


class ReplayMismatch(ValueError):
    pass


def replay(packet_dir, attempts_path):
    root = Path(packet_dir)
    manifest = json.loads((root/'manifest.json').read_bytes())
    source_raw = (root/'input.json').read_bytes()
    if hashlib.sha256(source_raw).hexdigest() != manifest['input_sha256']:
        raise ReplayMismatch('Source input digest mismatch')
    # Replay the frozen implementation, not a silently changed parser/prompt.
    for name, digest in manifest['implementation_sha256'].items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ReplayMismatch('Frozen implementation differs')
    cases = json.loads(source_raw)['cases']
    captures = {r['id']: r for r in manifest['records']}
    ids = [c['id'] for c in cases]
    if len(set(ids)) != len(ids) or len(captures) != len(manifest['records']) or set(ids) != set(captures):
        raise ReplayMismatch('Duplicate or mismatched case set')
    frozen = {}
    for cid in ids:
        if not isinstance(cid,str) or not cid.isascii() or not cid.replace('_','').isalnum():
            raise ReplayMismatch('Invalid case identifier')
        record = captures[cid]
        if record['state'] != 'captured_before_response':
            raise ReplayMismatch('Uncaptured packet')
        raw = (root/(cid+'-messages.json')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record['messages_sha256']:
            raise ReplayMismatch('Packet digest mismatch')
        frozen[cid] = raw
    attempts_raw = Path(attempts_path).read_bytes()
    attempts = json.loads(attempts_raw)['attempts']
    seen = set()
    for a in attempts:
        if a['case_id'] not in captures or not isinstance(a['attempt_id'],str) or not a['attempt_id'] or a['attempt_id'] in seen:
            raise ReplayMismatch('Invalid attempt binding')
        if a['status'] not in ('response','failed') or a.get('packet_sha256') != captures[a['case_id']]['messages_sha256']:
            raise ReplayMismatch('Attempt packet/status mismatch')
        seen.add(a['attempt_id'])
    results = []
    for case in cases:
        selected = [a for a in attempts if a['case_id'] == case['id']]
        if not selected:
            results.append({'case_id':case['id'],'state':'not_attempted'})
        for attempt in selected:
            row = {'case_id':case['id'],'attempt_id':attempt['attempt_id']}
            if attempt['status'] == 'failed':
                results.append(row | {'state':'execution_failed'})
                continue
            callbacks = []
            def saved(messages):
                raw = json.dumps(messages,ensure_ascii=False).encode()
                if raw != frozen[case['id']] or callbacks:
                    raise ReplayMismatch('Regenerated message differs or repeated callback')
                callbacks.append(True)
                return deepcopy(attempt['message'])
            try:
                draft = preparation.create(case['files'],
                    {'snapshot_id':case['id'],'as_of':'2026-11-17','currency':'KRW'},
                    generator=ModelProposalGenerator(saved,'saved-response-replay'))
            except ReplayMismatch:
                raise
            except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
                if not callbacks:
                    raise ReplayMismatch('Failure before saved response validation') from exc
                row.update(state='proposal_rejected',error_type=type(exc).__name__)
            else:
                if len(callbacks) != 1:
                    raise ReplayMismatch('Saved response was not consumed')
                row.update(state='pending_draft_created',draft=draft)
            results.append(row)
    return {'scope':'Full adapter admissibility only; no semantic truth, citation entailment, approval or quality score.',
            'input_sha256':manifest['input_sha256'],
            'attempts_sha256':hashlib.sha256(attempts_raw).hexdigest(),
            'planned_cases':len(cases),'recorded_attempts':len(attempts),
            'states':dict(Counter(r['state'] for r in results)), 'results':results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packets');parser.add_argument('attempts');parser.add_argument('output')
    args = parser.parse_args()
    result = replay(args.packets,args.attempts)
    with Path(args.output).open('x') as stream: json.dump(result,stream,ensure_ascii=False,indent=2)
