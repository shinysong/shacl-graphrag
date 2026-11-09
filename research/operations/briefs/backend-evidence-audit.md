# Offline archived evidence audit
Review new offline audit and copied scorers, not live DB experiments. Prior reviewed completed runs: parity40slots(36complete4unsupported), inference224, updates160, import20, followup10, advisory336, scopedadvisory960; offlinepreflights20/128/64 also preserved. Original unexpected n10s URN KEEP export differences and stale ablations are intended retained outcomes. New runner never imports runtime DB/LLM clients; recomputes saved evaluations in temporary copies, verifies full slot coverage and unchanged 809-artifact manifest before/after. Original scorers copied byte-identical; evaluator-only references are consumed manually authored development contracts, never runtime repair. Audit passed10runs; 3new regression tests passed. Localmanifest is self-recorded, not authenticated remoteexecution proof or external truth. Cleanup receipts attest saved scoped-empty results, not current AWS account state. External stop separately explicitly confirmed stopped, owned temporaryn10sremoved. Existing inferencecleanup test clock fixed beforecutoff to avoid time-dependent test failure; runtime unchanged. No new paidcalls/DB/restarts/push. Review ONLY this packet; imported function bodies/large stored files omitted and unverified. Direct tests/checks reported separately; job has no registered checks.

FILE scripts/check_backend_evidence.py
#!/usr/bin/env python3
"""Recompute archived development scores offline; never launch a database/model.

Run from the repository root. Hashes detect changes against a local snapshot;
they do not authenticate remote execution or establish external factual truth.
"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile

BASE = Path('research/backend-reasoning-review-1')
RUNS = {
    'offline-001': ('bindings', ('backend', 'case_id')),
    'live-001': ('bindings', ('backend', 'case_id')),
    'inference-offline-001': ('inference', ('variant', 'arm', 'query_id')),
    'inference-live-001': ('inference', ('variant', 'arm', 'query_id')),
    'updates-offline-001': ('updates', ('event', 'arm', 'query_id')),
    'updates-live-001': ('updates', ('event', 'arm', 'query_id')),
    'rdf-import-live-001': ('import', ('case', 'operation')),
    'import-followup-live-001': ('import', ('case', 'operation')),
    'advisory-replay-001': ('advisory', ('id', 'policy')),
    'advisory-scope-001': ('scope', ('row_index', 'policy', 'checker')),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def coverage(plan, rows, fields):
    key = lambda row: tuple(row[field] for field in fields)
    planned, observed = [key(x) for x in plan], [key(x) for x in rows]
    if len(set(planned)) != len(planned):
        raise ValueError('duplicate planned slot')
    if len(set(observed)) != len(observed):
        raise ValueError('duplicate observed slot')
    if set(planned) != set(observed):
        raise ValueError('missing or unplanned observed slot')
    return len(planned)


def verify_manifest(root, entries):
    for relative, expected in entries.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f'missing/out-of-root artifact: {relative}')
        if sha(path) != expected:
            raise ValueError(f'changed artifact: {relative}')


def verify_cleanup(path):
    receipts = json.loads(path.read_text())
    for row in receipts:
        if row.get('status', 'completed') != 'completed':
            raise ValueError(f'failed cleanup in {path}')
        receipt = row.get('receipt', row)
        if receipt is None:  # SQLite/RDFLib have no remote cleanup receipt.
            if row.get('backend') not in ('sqlite_python', 'rdflib_offline'):
                raise ValueError(f'unexpected null cleanup in {path}')
        elif receipt.get('remaining') not in (0, False):
            raise ValueError(f'nonempty or missing cleanup count in {path}')
    return len(receipts)


def replay(name, scorer, fields, scratch):
    original = BASE / name
    plan = json.loads((original / 'plan.json').read_text())
    rows = [json.loads(line) for line in (original / 'results.jsonl').read_text().splitlines()]
    count = coverage(plan, rows, fields)
    copy = scratch / name
    copy.mkdir()
    for filename in ('plan.json', 'results.jsonl', 'inputs.json', 'cases.json'):
        if (original / filename).exists():
            shutil.copyfile(original / filename, copy / filename)
    old_argv = sys.argv
    try:
        sys.argv = [f'score_{scorer}.py', str(copy)]
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            runpy.run_path(str(BASE / 'evaluation' / f'score_{scorer}.py'), run_name='__main__')
        (copy / 'scorer.log').write_text(captured.getvalue())
    finally:
        sys.argv = old_argv
    if json.loads((copy / 'evaluation.json').read_text()) != json.loads((original / 'evaluation.json').read_text()):
        raise ValueError(f'archived evaluation differs: {name}')
    cleanup_count = verify_cleanup(original / 'cleanup.json') if (original / 'cleanup.json').exists() else 0
    if (original / 'final-cleanup.json').exists():
        final = json.loads((original / 'final-cleanup.json').read_text())
        if final != {'constraints': [], 'nodes': [{'count': 0}]}:
            raise ValueError(f'nonempty final cleanup: {name}')
    return {'run': name, 'planned': count, 'observed': len(rows), 'evaluation_reproduced': True,
            'cleanup_receipts_checked': cleanup_count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory under ignored _workspace')
    args = parser.parse_args()
    root = Path.cwd().resolve()
    output = args.output.resolve()
    if not output.is_relative_to(root / '_workspace') or output.exists():
        parser.error('output must be a new directory under _workspace')
    output.mkdir(parents=True)
    manifest_path = BASE / 'evaluation' / 'artifact-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    result = {'status': 'failed', 'network_calls': 0, 'scope': 'Saved development artifacts only; no QA efficacy or remote execution authentication.', 'runs': []}
    try:
        verify_manifest(root, manifest['sha256'])
        with tempfile.TemporaryDirectory(prefix='replay-', dir=output) as temporary:
            for name, (scorer, fields) in RUNS.items():
                result['runs'].append(replay(name, scorer, fields, Path(temporary)))
        # Ensure scorers did not mutate any original archived artifact.
        verify_manifest(root, manifest['sha256'])
        result.update(status='passed', manifest_sha256=sha(manifest_path), hashed_artifacts=len(manifest['sha256']))
    except Exception as error:
        result['error'] = f'{type(error).__name__}: {error}'
    (output / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

FILE tests/test_backend_evidence.py
import json
from pathlib import Path
import tempfile
import unittest

from scripts.check_backend_evidence import coverage, sha, verify_cleanup, verify_manifest


class EvidenceTests(unittest.TestCase):
    def test_missing_duplicate_and_unplanned_slots_rejected(self):
        plan = [{'id': 1}, {'id': 2}]
        self.assertEqual(coverage(plan, list(reversed(plan)), ('id',)), 2)
        for rows in (plan[:1], [plan[0], plan[0]], [plan[0], {'id': 3}]):
            with self.assertRaises(ValueError):
                coverage(plan, rows, ('id',))
        with self.assertRaises(ValueError):
            coverage([plan[0], plan[0]], plan, ('id',))

    def test_mutated_answer_and_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / 'answers.json'
            artifact.write_text('{"answer": [1]}')
            manifest = {'answers.json': sha(artifact)}
            verify_manifest(root, manifest)
            artifact.write_text('{"answer": [2]}')
            with self.assertRaises(ValueError):
                verify_manifest(root, manifest)
            artifact.unlink()
            with self.assertRaises(ValueError):
                verify_manifest(root, manifest)

    def test_failed_nonempty_and_missing_cleanup_counts_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'cleanup.json'
            path.write_text(json.dumps([{'receipt': {'remaining': False}}]))
            self.assertEqual(verify_cleanup(path), 1)
            for row in ({'receipt': {'remaining': 1}}, {'receipt': {}}, {'status': 'failed', 'receipt': {'remaining': 0}}):
                path.write_text(json.dumps([row]))
                with self.assertRaises(ValueError):
                    verify_cleanup(path)

FILE research/backend-reasoning-review-1/evaluation/score_advisory.py
import json,sys
from pathlib import Path
out=Path(sys.argv[1]);inputs=json.loads((out/'inputs.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()];plan=json.loads((out/'plan.json').read_text())
key=lambda r:(r['id'],r['policy']);assert len({key(r) for r in rows})==len(rows);assert {key(r) for r in rows}<={key(r) for r in plan}
lookup={key(r):r for r in rows};evaluation=json.loads(Path('research/backend-reasoning-review-1/updates-live-001/evaluation.json').read_text());reference={(x['event'],x['arm'],x['query_id']):x['matches_current_reference'] for x in evaluation['checks']}
summary={};checks=[]
for x in inputs:
    truth=reference[tuple(x['origin'][k] for k in ('event','arm','query_id'))]
    pair=[lookup.get((x['id'],p)) for p in ('python','shacl')]
    same=all(r and r['status']=='completed' for r in pair) and pair[0]['codes']==pair[1]['codes']
    checks.append({'id':x['id'],'cohort':x['cohort'],'policy_agreement':same,'source_query_set_matches_reference':truth})
    for policy,row in zip(('python','shacl'),pair):
        s=summary.setdefault(x['cohort']+'/'+policy,{'planned':0,'completed':0,'reports_requesting_review':0,'query_set_mismatch_with_review':0,'matching_query_set_with_review':0,'query_set_mismatch_without_review':0})
        s['planned']+=1
        if row and row['status']=='completed':
            s['completed']+=1;s['reports_requesting_review']+=row['review_requested']
            s['query_set_mismatch_with_review']+=not truth and row['review_requested']
            s['matching_query_set_with_review']+=truth and row['review_requested']
            s['query_set_mismatch_without_review']+=not truth and not row['review_requested']
            assert row['original_answer']==x['original_answer'] and row['answer_changed'] is False
result={'planned_checker_slots':len(plan),'observed_checker_slots':len(rows),'unobserved':len(plan)-len(rows),'policy_pairs':len(inputs),'agreeing_pairs':sum(x['policy_agreement'] for x in checks),'summary':summary,'checks':checks,'interpretation':'Offline replay, same metadata policy, no new answers or model calls. Version warning is not factual-error finding. Query-set matches use consumed authored reference; not external truth. Matching outputs flagged are review burden, not actual abstention because no veto. Authored metadata controls separate.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
assert len(rows)==len(plan) and all(x['policy_agreement'] for x in checks)

Bindings/import scorers omitted (previous reviews), unverified here.

FILE research/backend-reasoning-review-1/evaluation/score_inference.py
import json,sys,hashlib
from pathlib import Path
run=Path(sys.argv[1]);refpath=Path('research/backend-reasoning-review-1/inference-contracts-001/evaluator-only.json');ref=json.loads(refpath.read_text())['expected'];rows=[json.loads(x) for x in (run/'results.jsonl').read_text().splitlines()];plan=json.loads((run/'plan.json').read_text());key=lambda r:(r['variant'],r['arm'],r['query_id']);assert len({key(r) for r in rows})==len(rows);assert {key(r) for r in rows}<={key(r) for r in plan}
checks=[]
for r in rows:
 expected=ref[r['variant']][r['query_id']];match=r['status']=='completed' and r.get('answer')==expected
 checks.append({'variant':r['variant'],'arm':r['arm'],'query_id':r['query_id'],'status':r['status'],'matches_current_reference':match})
summary={arm:{'observed':sum(r['arm']==arm for r in rows),'completed':sum(r['arm']==arm and r['status']=='completed' for r in rows),'matching_current_reference':sum(c['arm']==arm and c['matches_current_reference'] for c in checks)} for arm in sorted({r['arm'] for r in plan})}
result={'planned':len(plan),'observed':len(rows),'unobserved':len(plan)-len(rows),'by_arm':summary,'checks':checks,'reference_sha256':hashlib.sha256(refpath.read_bytes()).hexdigest(),'interpretation':'Current authored schema query membership; asserted ablation and stale snapshot intentionally can differ. Not external truth, human maintenance benefit or general OWL equivalence.'}
(run/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
assert len(rows)==len(plan)
assert all(c['matches_current_reference'] for c in checks if c['arm'] not in ('asserted','stale_base_rdfs'))

FILE research/backend-reasoning-review-1/evaluation/score_scope.py
import json,sys
from pathlib import Path
out=Path(sys.argv[1]);plan=json.loads((out/'plan.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()];inputs=json.loads((out/'inputs.json').read_text());expected={(x['row_index'],x['policy']):x for x in inputs}
key=lambda r:(r['row_index'],r['policy'],r['checker']);assert len({key(r) for r in rows})==len(rows);assert {key(r) for r in rows}<={key(r) for r in plan}
parent=Path('research/backend-reasoning-review-1/updates-live-001');ev=json.loads((parent/'evaluation.json').read_text());ref={(x['event'],x['arm'],x['query_id']):x['matches_current_reference'] for x in ev['checks']}
lookup={key(r):r for r in rows};summary={};pairs=[]
for p in plan:
    row=lookup.get(key(p));s=summary.setdefault(p['policy']+'/'+p['checker'],{'planned':0,'completed':0,'review_flags':0,'mismatch_with_review':0,'matching_with_review':0,'mismatch_without_review':0});s['planned']+=1
    if row and row['status']=='completed':
        x=expected[(p['row_index'],p['policy'])];assert row['original_answer']==x['original_answer'] and not row['answer_changed']
        matches=ref[tuple(row['origin'][k] for k in ('event','arm','query_id'))];flag=row['review_requested']
        s['completed']+=1;s['review_flags']+=flag;s['mismatch_with_review']+=not matches and flag;s['matching_with_review']+=matches and flag;s['mismatch_without_review']+=not matches and not flag
for i,p in expected:
    a,b=[lookup.get((i,p,c)) for c in ('python','shacl')];pairs.append(bool(a and b and a['status']==b['status']=='completed' and a['codes']==b['codes']))
result={'planned_checker_slots':len(plan),'observed':len(rows),'pairs':len(pairs),'agreeing_pairs':sum(pairs),'summary':summary,'interpretation':'Derived replay on same160controlledbackendoutputs. Typedfamilymapping supplied, not learnedNLunderstanding. Metadataonly/noLLM/veto/repair. Correctflags quantify proxyreviewburden, not actual labor orabstention.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert len(rows)==len(plan) and all(pairs)

FILE research/backend-reasoning-review-1/evaluation/score_updates.py
import json,sys,hashlib
from pathlib import Path
out=Path(sys.argv[1]);reference=Path('research/backend-reasoning-review-1/inference-contracts-001/evaluator-only.json')
ref=json.loads(reference.read_text())['expected']
mapping={'initial':'two_supports','delete_primary':'remove_primary','delete_alternate':'remove_both_annotation_supports','restore_paths':'two_supports','delete_fact':'remove_source_edge','restore_fact':'two_supports','delete_schema':'missing_schema','restore_schema':'two_supports'}
plan=json.loads((out/'plan.json').read_text());rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()] if (out/'results.jsonl').exists() else []
key=lambda r:(r['event'],r['arm'],r['query_id'])
assert len({key(x) for x in plan})==len(plan)
assert len({key(x) for x in rows})==len(rows)
assert {key(x) for x in rows}<={key(x) for x in plan}
checks=[];byarm={}
for p in plan:
    found=[r for r in rows if key(r)==key(p)]
    row=found[0] if found else {**p,'status':'not_observed'}
    expected=ref[mapping[p['event']]][p['query_id']]
    matched=row['status']=='completed' and row['answer']==expected
    checks.append({**p,'status':row['status'],'matches_current_reference':matched})
    counts=byarm.setdefault(p['arm'],{'planned':0,'completed':0,'matching_current_reference':0})
    counts['planned']+=1;counts['completed']+=row['status']=='completed';counts['matching_current_reference']+=matched
result={'planned':len(plan),'observed':len(rows),'unobserved':len(plan)-len(rows),'by_arm':byarm,'checks':checks,'reference_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),'event_mapping':mapping,'interpretation':'Repeated quiescent authoredchanges on consumed development source IDs, not independent samples, benchmark, LLM answers or fullOWL reasoner comparison.'}
(out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
assert all(c['completed']==c['planned'] for c in byarm.values())
assert all(c['matching_current_reference']==c['planned'] for a,c in byarm.items() if a not in ('stale_offline','neptune_stale'))
