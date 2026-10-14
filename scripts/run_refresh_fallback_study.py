"""Derived fallback replay: preserve prevalidated answers after an unusable refresh.

Uses recorded selective-refresh responses; no new source calls. Inherited cost
is counterfactual policy cost, not another set of performed fetches.
"""
import argparse
import copy
import json
import os
import signal
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

try:
    from scripts import run_semantic_guard_study as guard
    from scripts import run_bounded_refresh_study as refresh
except ModuleNotFoundError:
    import run_semantic_guard_study as guard
    import run_bounded_refresh_study as refresh

ROOT = Path(__file__).resolve().parents[1]
TASKS = refresh.TASKS


def preserve_valid(packet, refreshed, prior_allowed, service_failed, catalog):
    """Select only from existing outputs. No reference or correctness flags."""
    before = {t: guard.checks(packet,t,catalog) for t in TASKS}
    mixed = copy.deepcopy(refreshed)
    selected = {}
    for task in TASKS:
        valid_before = all(before[task][c]['status']=='valid' for c in refresh.SELECTED)
        selected[task] = not prior_allowed[task] and valid_before
        if selected[task]:
            mixed['actuals'][task] = copy.deepcopy(packet['actuals'][task])
            mixed['workflows'][task] = copy.deepcopy(packet['workflows'][task])
    checks = {t: guard.checks(mixed,t,catalog) for t in TASKS}
    allowed = {t: (not service_failed or selected[t]) and
               all(checks[t][c]['status']=='valid' for c in refresh.SELECTED) for t in TASKS}
    return dict(packet=mixed, checks=checks, allowed=allowed, fallback_selected=selected)


def runtime_policy(packet, catalog, fetch):
    """Callable policy for future live adapter; still at most one bundle read."""
    result = refresh.runtime_policy(packet,catalog,'selective_refresh',fetch)
    fallback = preserve_valid(packet,result['refreshed_packet'],result['allowed'],bool(result['error']),catalog)
    return dict(result, actuals=fallback['packet']['actuals'], allowed=fallback['allowed'],
                refreshed_packet=fallback['packet'], after_checks=fallback['checks'],
                fallback_selected=fallback['fallback_selected'],
                changed_outputs={t:packet['actuals'][t]['output']!=fallback['packet']['actuals'][t]['output'] for t in TASKS})


def replay(parent, base, output):
    output.mkdir(parents=True,exist_ok=False)
    manifest=dict(protocol='refresh-fallback-1',status='running',parent_run=parent.name,
                  planned_rows=110592,completed_rows=0,started=datetime.now(UTC).isoformat(),
                  new_source_calls=0,cost_scope='Inherited selective-refresh trace cost; no extra performed calls.')
    guard.save(output/'manifest.json',manifest)
    totals, costs, samples = defaultdict(Counter), defaultdict(Counter), []
    handlers={}
    def interrupted(signum,frame): raise KeyboardInterrupt(f'Signal {signum}')
    for sig in (signal.SIGINT,signal.SIGTERM): handlers[sig]=signal.signal(sig,interrupted)
    try:
        pm=guard.read(parent/'manifest.json');assert pm['protocol']=='bounded-refresh-1' and pm['status']=='complete'
        assert pm['completed_rows']==331776 and pm['completed_group_calls']==110592
        manifest['input_files']={str(p.relative_to(parent)):guard.sha(p) for p in sorted(parent.rglob('*')) if p.is_file()}
        manifest['original_rows_sha256']=guard.sha(base/'rows.jsonl')
        originals={r['id']:r for r in map(json.loads,(base/'rows.jsonl').open())}
        archive=output/'executed-source';archive.mkdir();manifest['source_files']={}
        for p in [Path(__file__),ROOT/'scripts/run_semantic_guard_study.py',ROOT/'scripts/run_bounded_refresh_study.py',ROOT/'tests/test_refresh_fallback_study.py',ROOT/'scripts/analyze_refresh_fallback_study.py',ROOT/'scripts/analyze_bounded_refresh_study.py',ROOT/'uv.lock']:
            (archive/p.name).write_bytes(p.read_bytes());manifest['source_files'][str(p.relative_to(ROOT))]=guard.sha(p)
        packets={}
        def packet(pid):
            if pid not in packets:
                value=guard.read(parent/'runtime-packets'/(pid+'.json'));assert guard.digest(value)==pid;packets[pid]=value
            return packets[pid]
        group_rows=defaultdict(dict)
        for r in map(json.loads,(parent/'rows.jsonl').open()):
            if r['policy']=='selective_refresh':
                assert r['workflow'] not in group_rows[r['group_id']]
                group_rows[r['group_id']][r['workflow']]=r
        groups=[g for g in map(json.loads,(parent/'groups.jsonl').open()) if g['policy']=='selective_refresh']
        assert len(groups)==len(group_rows)==36864 and len({g['group_id'] for g in groups})==len(groups)
        expected={k+'/'+c+'/'+s+'/selective_fallback' for k in originals for c in guard.CATALOGS for s in refresh.SERVICES}
        assert len(expected)==110592
        seen=set();guard.save(output/'manifest.json',manifest)
        with (output/'rows.jsonl').open('x') as handle:
            for g in groups:
                rows=group_rows[g['group_id']];assert set(rows)==set(TASKS)
                before,after=packet(g['packet_id']),packet(g['after_packet_id'])
                result=preserve_valid(before,after,{t:rows[t]['allowed'] for t in TASKS},bool(g['error']),guard.CATALOGS[g['catalog']])
                key=g['catalog']+'/'+g['service']
                costs[key]['group_calls']+=1;costs[key]['inherited_fetch_attempts']+=g['fetch_attempts']
                costs[key]['inherited_payload_bytes']+=g['payload_bytes'];costs[key]['inherited_service_failures']+=g['error'] is not None
                for task,r in rows.items():
                    identifier=r['base_id']+'/'+key+'/selective_fallback';assert identifier in expected and identifier not in seen;seen.add(identifier)
                    original=originals[r['base_id']];actual=result['packet']['actuals'][task]
                    v=dict(id=identifier,parent_id=r['id'],base_id=r['base_id'],group_id=g['group_id'],catalog=g['catalog'],service=g['service'],workflow=task,
                           output=actual['output'],allowed=result['allowed'][task],fallback_selected=result['fallback_selected'][task],
                           mixed_checks=result['checks'][task],prior_allowed=r['allowed'],prior_output=r['output'],
                           **refresh.evaluate(original['actual'],actual,original['reference'],result['allowed'][task]))
                    handle.write(json.dumps(v,sort_keys=True)+'\n');manifest['completed_rows']+=1
                    count=totals[key];count.update(['rows',v['outcome']])
                    for name in ('fallback_selected','unnecessary_abstention','correct_unknown_withheld','corrected_wrong_to_correct','regression_correct_to_wrong'):count[name]+=v[name]
                    count['restored_correct_output']+=not r['allowed'] and v['allowed'] and v['after_correct']
                    count['newly_allowed_wrong_output']+=not r['allowed'] and v['allowed'] and not v['after_correct']
                    if g['size']==24 and g['seed']==17 and g['arm']=='rdf_hybrid' and g['subject']=='p4' and g['snapshot']=='cost_change' and g['fault']=='stale_projection':
                        samples.append(dict(v,reference_output=original['reference']['output'],before_output=original['actual']['output']))
                if manifest['completed_rows']%384==0:handle.flush();os.fsync(handle.fileno());guard.save(output/'manifest.json',manifest)
            handle.flush();os.fsync(handle.fileno())
        assert seen==expected;manifest['status']='complete'
        guard.save(output/'samples.json',samples)
    except BaseException as exc:
        manifest.update(status='partial',error=f'{type(exc).__name__}: {exc}');raise
    finally:
        manifest['finished']=datetime.now(UTC).isoformat();guard.save(output/'manifest.json',manifest)
        guard.save(output/'summary.json',dict(rows=manifest['completed_rows'],totals=dict(totals),costs=dict(costs)))
        for sig,handler in handlers.items():signal.signal(sig,handler)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--parent',type=Path,required=True)
    parser.add_argument('--base',type=Path,default=ROOT/'runs/20261014T063154Z-shared-semantics');parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();print(json.dumps(replay(a.parent,a.base,a.output)))
