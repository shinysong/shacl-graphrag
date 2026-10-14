"""Independent reconciliation of derived fallback decisions, without policy imports."""
import argparse
import copy
import json
from collections import Counter,defaultdict
from pathlib import Path
try:
    from scripts.analyze_bounded_refresh_study import statuses,TASKS,CATALOGS,SERVICES
    from scripts.analyze_shared_semantics_study import read,sha,semantic_digest
except ModuleNotFoundError:
    from analyze_bounded_refresh_study import statuses,TASKS,CATALOGS,SERVICES
    from analyze_shared_semantics_study import read,sha,semantic_digest


def audit(run,parent,base,output):
    output.mkdir(parents=True,exist_ok=False);report=dict(status='running')
    def save():(output/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        m=read(run/'manifest.json');assert m['status']=='complete' and m['completed_rows']==m['planned_rows']==110592
        for p,h in m['input_files'].items():assert sha(parent/p)==h,p
        assert sha(base/'rows.jsonl')==m['original_rows_sha256']
        for p,h in m['source_files'].items():assert sha(run/'executed-source'/Path(p).name)==h,p
        pm=read(parent/'manifest.json');originals={r['id']:r for r in map(json.loads,(base/'rows.jsonl').open())}
        parent_rows={r['id']:r for r in map(json.loads,(parent/'rows.jsonl').open()) if r['policy']=='selective_refresh'}
        gs={g['group_id']:g for g in map(json.loads,(parent/'groups.jsonl').open()) if g['policy']=='selective_refresh'}
        totals,costs=defaultdict(Counter),defaultdict(Counter);packets={};mixed_cache={};seen=set();seen_groups=set()
        def packet(pid):
            if pid not in packets:
                v=read(parent/'runtime-packets'/(pid+'.json'));assert semantic_digest(v)==pid;packets[pid]=v
            return packets[pid]
        expected={i+'/'+c+'/'+s+'/selective_fallback' for i in originals for c in CATALOGS for s in SERVICES}
        for r in map(json.loads,(run/'rows.jsonl').open()):
            assert r['id'] in expected and r['id'] not in seen;seen.add(r['id'])
            p=parent_rows[r['parent_id']];g=gs[r['group_id']];o=originals[r['base_id']];t=r['workflow'];cat=pm['catalogs'][r['catalog']]
            assert r['parent_id']==r['base_id']+'/'+r['catalog']+'/'+r['service']+'/selective_refresh'
            assert r['id']==r['base_id']+'/'+r['catalog']+'/'+r['service']+'/selective_fallback'
            for k in ('base_id','group_id','catalog','service','workflow'):assert r[k]==p[k]
            before,after=packet(g['packet_id']),packet(g['after_packet_id'])
            gid=g['group_id']
            if gid not in mixed_cache:
                mixed=copy.deepcopy(after);selected={}
                for task in TASKS:
                    base_id='/'.join(str(g[k]) for k in ('size','seed','snapshot','fault','subject'))+'/'+task+'/'+g['arm']
                    prior=parent_rows[base_id+'/'+g['catalog']+'/'+g['service']+'/selective_refresh']
                    check=statuses(before,task,cat)
                    selected[task]=not prior['allowed'] and all(check[c]=='valid' for c in ('cross','selective','semantic'))
                    if selected[task]:mixed['actuals'][task]=before['actuals'][task];mixed['workflows'][task]=before['workflows'][task]
                mixed_cache[gid]=(mixed,selected)
            mixed,selected=mixed_cache[gid];check=statuses(mixed,t,cat)
            allowed=(not g['error'] or selected[t]) and all(check[c]=='valid' for c in ('cross','selective','semantic'))
            assert r['fallback_selected']==selected[t] and r['allowed']==bool(allowed)
            assert {k:v['status'] for k,v in r['mixed_checks'].items()}==check
            assert r['output']==mixed['actuals'][t]['output'] and r['prior_output']==p['output'] and r['prior_allowed']==p['allowed']
            first=o['actual']['output']==o['reference']['output'];last=r['output']==o['reference']['output'];known=o['reference']['output']['decision']!='unknown'
            values=dict(before_correct=first,after_correct=last,unnecessary_abstention=last and known and not allowed,correct_unknown_withheld=last and not known and not allowed,corrected_wrong_to_correct=not first and last and allowed,regression_correct_to_wrong=first and not last and allowed,reference_known=known)
            assert all(r[k]==v for k,v in values.items())
            outcome=('correct_retained' if allowed else 'correct_withheld') if last else ('wrong_allowed' if allowed else 'wrong_withheld');assert r['outcome']==outcome
            key=r['catalog']+'/'+r['service'];c=totals[key];c.update(['rows',outcome])
            for k in ('fallback_selected','unnecessary_abstention','correct_unknown_withheld','corrected_wrong_to_correct','regression_correct_to_wrong'):c[k]+=r[k]
            c['restored_correct_output']+=not p['allowed'] and allowed and last;c['newly_allowed_wrong_output']+=not p['allowed'] and allowed and not last
            if gid not in seen_groups:
                seen_groups.add(gid);c=costs[key];c['group_calls']+=1;c['inherited_fetch_attempts']+=g['fetch_attempts'];c['inherited_payload_bytes']+=g['payload_bytes'];c['inherited_service_failures']+=g['error'] is not None
        assert seen==expected and seen_groups==set(gs)
        saved=read(run/'summary.json');assert saved['totals']==dict(totals) and saved['costs']==dict(costs)
        report.update(status='complete',rows=len(seen),groups=len(gs),new_source_calls=0,scope='Independent fallback selection, mixed-check status, scores and inherited costs; parent source outputs separately audited.')
    except BaseException as exc:report.update(status='failed',error=f'{type(exc).__name__}: {exc}');raise
    finally:save()
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--parent',type=Path,required=True);p.add_argument('--base',type=Path,default=Path('runs/20261014T063154Z-shared-semantics'));p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(audit(a.run,a.parent,a.base,a.output)))
