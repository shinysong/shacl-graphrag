"""Reconcile bounded-refresh outputs, service accounting and refreshed source evidence."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

try:
    from scripts.analyze_shared_semantics_study import read, sha, reference, reconcile, semantic_digest
except ModuleNotFoundError:
    from analyze_shared_semantics_study import read, sha, reference, reconcile, semantic_digest

POLICIES = ('veto_only', 'selective_refresh', 'eager_refresh')
CATALOGS = ('documented', 'absent', 'mislabeled')
SERVICES = ('current', 'unavailable', 'stale_response')
TASKS = ('countries', 'audit', 'recommend')
METRICS = ('rows', 'wrong_allowed', 'wrong_withheld', 'correct_retained', 'correct_withheld',
           'before_correct', 'after_correct', 'unnecessary_abstention', 'correct_unknown_withheld',
           'corrected_wrong_to_correct', 'regression_correct_to_wrong', 'changed_output')


def statuses(packet, task, catalog):
    a = packet['actuals']; countries = a['countries']['output']; rec = a['recommend']['output']
    prohibited = set(packet['publisher']['restricted_countries']); cross = False
    if countries['decision'] == 'complete':
        known = set(countries['value'])
        cross = a['audit']['output']['decision'] != ('blocked' if known & prohibited else 'clear')
        if rec['decision'] == 'recommended':
            selected = [c['country'] for c in a['recommend']['evidence']['candidates'] if c['supplier'] == rec['value']]
            cross = cross or not selected or any(c not in known or c in prohibited for c in selected)
    v = packet['workflows'][task]; h = v['hashes']
    whole = h['current_source'] != h['consumed_source'] or h['published_config'] != h['installed_config'] or (v['projection_mapping'] is not None and v['projection_mapping'] != v['installed']['location_field'])
    selective = h['current_dependency'] != h['consumed_dependency'] or h['published_policy'] != h['installed_policy']
    fields = {v['installed']['location_field']}
    if v['projection_mapping'] is not None:
        fields.add(v['projection_mapping'])
    conflict = any(f in catalog and catalog[f] != 'operating_country' for f in fields)
    missing = any(f not in catalog for f in fields)
    return dict(cross='conflict' if cross else 'valid', whole='conflict' if whole else 'valid',
                selective='conflict' if selective else 'valid', semantic='conflict' if conflict else 'missing' if missing else 'valid')


def audit(run, base, output):
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', run_id=run.name)
    def save():
        (output / 'verification.json').write_text(json.dumps(report, indent=2)+'\n')
    save()
    try:
        manifest = read(run / 'manifest.json')
        assert manifest['protocol'] == 'bounded-refresh-1' and manifest['status'] == 'complete'
        assert manifest['completed_rows'] == manifest['planned_rows'] == 331776
        assert manifest['completed_group_calls'] == manifest['planned_group_calls'] == 110592
        for p, h in manifest['input_files'].items():
            assert sha(base / p) == h, p
        for p, h in manifest['source_files'].items():
            assert sha(run / 'executed-source' / Path(p).name) == h, p
        original = [json.loads(line) for line in (base / 'rows.jsonl').open()]
        reconcile(read(base / 'manifest.json'), read(base / 'planned-row-ids.json'), original)
        parents = {r['id']: r for r in original}
        expected_ids = {k+'/'+c+'/'+s+'/'+p for k in parents for c in CATALOGS for s in SERVICES for p in POLICIES}
        packets, source_cache, refs = {}, {}, {}
        def packet(identifier):
            if identifier not in packets:
                v = read(run / 'runtime-packets' / (identifier+'.json'))
                assert semantic_digest(v) == identifier
                assert set(v) == {'subject', 'publisher', 'actuals', 'workflows'}
                packets[identifier] = v
            return packets[identifier]
        def source(size, seed, snapshot):
            key = size, seed, snapshot
            if key not in source_cache:
                f = base / 'snapshots' / f'{size}-{seed}-{snapshot}'
                source_cache[key] = read(f / 'source.json'), read(f / 'intended-config.json'), (f / 'source.json').stat().st_size
            return source_cache[key]
        for r in original:
            k = r['size'], r['seed'], r['snapshot'], r['subject'], r['workflow']
            if k not in refs:
                data, config, _ = source(*k[:3]); refs[k] = reference(data, config, *k[3:])
            assert r['reference'] == refs[k]
        groups, service_detail, service_totals = {}, defaultdict(Counter), defaultdict(Counter)
        for line in (run / 'groups.jsonl').open():
            g = json.loads(line); gid = g['group_id']; assert gid not in groups
            assert gid == '/'.join(str(g[k]) for k in ('size','seed','snapshot','fault','subject','arm','catalog','service','policy'))
            before, after = packet(g['packet_id']), packet(g['after_packet_id'])
            catalog = manifest['catalogs'][g['catalog']]
            pre = {t: statuses(before,t,catalog) for t in TASKS}
            semantic_ok = all(x['semantic']=='valid' for x in pre.values())
            needs = any(x[c]!='valid' for x in pre.values() for c in ('cross','selective'))
            attempt = int(semantic_ok and (g['policy']=='eager_refresh' or (g['policy']=='selective_refresh' and needs)))
            assert g['fetch_attempts'] == attempt
            failure = bool(attempt and g['service']=='unavailable')
            assert bool(g['error']) == failure
            payload = 0
            if attempt and not failure:
                snap = 'initial' if g['service']=='stale_response' else g['snapshot']
                data, _, payload = source(g['size'],g['seed'],snap)
                for t in TASKS:
                    # Independent source decision/evidence derivation, no runtime imports.
                    assert after['actuals'][t] == reference(data,before['publisher'],g['subject'],t)
                    for h in ('current_source','current_dependency','published_config','published_policy'):
                        assert before['workflows'][t]['hashes'][h] == after['workflows'][t]['hashes'][h]
            else:
                assert before == after
            assert g['payload_bytes'] == payload
            groups[gid] = g
            for counter in (service_detail['/'.join(g[k] for k in ('policy','catalog','service','arm','fault'))], service_totals['/'.join(g[k] for k in ('policy','catalog','service'))]):
                counter['group_calls']+=1; counter['fetch_attempts']+=attempt
                counter['payload_bytes']+=payload; counter['service_failures']+=failure
        seen, detail, totals, samples, group_tasks = set(), defaultdict(Counter), defaultdict(Counter), [], defaultdict(set)
        for line in (run / 'rows.jsonl').open():
            r = json.loads(line); identifier=r['id']; assert identifier in expected_ids and identifier not in seen
            seen.add(identifier); parent=parents[r['base_id']]; g=groups[r['group_id']]; task=r['workflow']
            assert identifier == r['base_id']+'/'+r['catalog']+'/'+r['service']+'/'+r['policy']
            for k in ('size','seed','snapshot','fault','subject','arm','workflow'):
                assert r[k] == parent[k]
            for k,v in g.items():
                if k not in ('fetch_attempts','payload_bytes'): assert r[k]==v
            assert r['shared_fetch_attempts']==g['fetch_attempts'] and r['shared_payload_bytes']==g['payload_bytes']
            before,after=packet(g['packet_id']),packet(g['after_packet_id']);catalog=manifest['catalogs'][r['catalog']]
            assert before['actuals'][task]==parent['actual'] and r['before_output']==parent['actual']['output']
            assert r['output']==after['actuals'][task]['output']
            for key,p in [('before_checks',before),('after_checks',after)]:
                assert {k:v['status'] for k,v in r[key].items()}==statuses(p,task,catalog)
            state=statuses(after,task,catalog)
            allowed=not g['error'] and all(state[k]=='valid' for k in ('cross','selective','semantic'))
            assert r['allowed']==bool(allowed)
            old=parent['actual']['output']==parent['reference']['output'];new=r['output']==parent['reference']['output'];known=parent['reference']['output']['decision']!='unknown'
            outcome=('correct_retained' if allowed else 'correct_withheld') if new else ('wrong_allowed' if allowed else 'wrong_withheld')
            values=dict(before_correct=old,after_correct=new,unnecessary_abstention=new and known and not allowed,correct_unknown_withheld=new and not known and not allowed,corrected_wrong_to_correct=not old and new and allowed,regression_correct_to_wrong=old and not new and allowed,changed_output=r['output']!=r['before_output'])
            assert r['outcome']==outcome and all(r[k]==v for k,v in values.items())
            for counter in (detail['/'.join(r[k] for k in ('policy','catalog','service','arm','fault','workflow'))],totals['/'.join(r[k] for k in ('policy','catalog','service'))]):
                counter.update(['rows',outcome]);counter.update(values)
            group_tasks[r['group_id']].add(task)
            if (r['size'],r['seed'],r['arm'])==(24,17,'rdf_hybrid') and r['catalog'] in ('documented','mislabeled'):
                if (r['snapshot'],r['fault'],r['subject']) in {('cost_change','stale_projection','p4'),('supplier_move','clean','p3'),('remove_country','clean','p3'),('restrict_country','common_wrong_mapping','p4')}:
                    samples.append(dict(r,reference_output=parent['reference']['output']))
        assert seen==expected_ids and len(groups)==110592
        assert set(group_tasks)==set(groups) and all(v==set(TASKS) for v in group_tasks.values())
        saved=read(run/'summary.json');assert saved['groups']==dict(detail) and saved['service_groups']==dict(service_detail)
        report.update(status='complete',rows=len(seen),group_calls=len(groups),runtime_packets=len(packets),original_reference_rows=len(original),input_files=len(manifest['input_files']),scope='Independent refreshed source outputs/evidence, policy triggers, check statuses, scores, matrix and service accounting; no independent source-to-fingerprint implementation.')
        result=dict(run_id=run.name,totals={k:{m:v[m] for m in METRICS} for k,v in totals.items()},service_totals=dict(service_totals),groups={k:{m:v[m] for m in METRICS} for k,v in detail.items()},service_groups=dict(service_detail),verification=report)
        (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
        (output/'samples.json').write_text(json.dumps(samples,indent=2)+'\n')
    except BaseException as exc:
        report.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        raise
    finally: save()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--base',type=Path,default=Path('runs/20261014T063154Z-shared-semantics'));parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.run,args.base,args.output)))
