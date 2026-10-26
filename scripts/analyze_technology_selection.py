"""Descriptive paired-case analysis of immutable measurements; no executions."""
import csv
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('python_indexed','sqlite_recursive','rdf_owl_shacl')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source=ROOT/'_workspace/technology-selection/campaign-1/results'
    record=json.loads((ROOT/'docs/experiments/records/20261021-technology-selection-campaign.json').read_text())
    if sha(source/'results.jsonl') != record['results_sha256']: raise ValueError('results changed')
    freeze=json.loads((source/'freeze.json').read_text())
    cases={c['case_id']:c for c in json.loads((ROOT/'research/technology-selection/cases-v1.json').read_text())}
    rows=[json.loads(line) for line in (source/'results.jsonl').read_text().splitlines()]
    planned={r['attempt_id']:r for r in freeze['runs']}
    if len({r['attempt_id'] for r in rows})!=len(rows): raise ValueError('duplicate attempts')
    metrics=[]; counts=Counter(); grouped=defaultdict(list)
    for row in rows:
        if row['attempt_id'] not in planned: raise ValueError('unplanned attempt')
        if any(row[k]!=planned[row['attempt_id']][k] for k in ('case_id','arm','repeat')): raise ValueError('identity mismatch')
        counts[row['status']]+=1
        if row['status']!='success': continue  # all failure denominators retained; no cost mixing
        scored=row['score']; queries=scored['queries']; events=scored['events_without_query_answers']
        if len(queries)!=114 or any(not q['correct'] for q in queries): raise ValueError('invalid success')
        def event(name):
            found=[e for e in events if e['event']==name]
            if len(found)!=1: raise ValueError('ambiguous event '+name)
            return found[0]
        prep=event('prepare'); inp=event('input'); warm=[q['duration_ns'] for q in queries if q['phase']=='warmup']
        if len(warm)!=1: raise ValueError('warmup count')
        m=dict(attempt_id=row['attempt_id'],case_id=row['case_id'],arm=row['arm'],repeat=row['repeat'],
               input_ms=inp['duration_ns']/1e6,prepare_ms=prep['duration_ns']/1e6,
               normalization_ms=prep['normalization_ns']/1e6,arm_setup_ms=prep['setup_ns']/1e6,
               imports_ms=event('imports')['duration_ns']/1e6,warmup_ms=warm[0]/1e6,
               reset_ms=event('reset')['duration_ns']/1e6,
               whole_worker_ms=row['process']['elapsed_ns']/1e6,
               whole_worker_peak_mib=event('complete')['ru_maxrss_kib']/1024)
        for n in (1,10,100):
            q=[q['duration_ns'] for q in queries if q['phase']==f'steady_{n}']
            if len(q)!=n: raise ValueError('batch count')
            m[f'query_{n}_mean_ms']=sum(q)/n/1e6
            m[f'query_{n}_sum_ms']=sum(q)/1e6
            # Sum of observed components, not a separately executed cold deployment.
            m[f'components_{n}_ms']=(inp['duration_ns']+prep['duration_ns']+warm[0]+sum(q))/1e6
        for label in ('E','C'):
            u=[e for e in events if e['event']=='update' and e['phase']==label]
            q=[q for q in queries if q['phase']=='post_'+label]
            if len(u)!=1 or len(q)!=1: raise ValueError('update count')
            m[f'update_{label}_ms']=u[0]['duration_ns']/1e6
            m[f'post_{label}_ms']=q[0]['duration_ns']/1e6
            m[f'update_query_{label}_ms']=(u[0]['duration_ns']+q[0]['duration_ns'])/1e6
        metrics.append(m);grouped[(m['case_id'],m['arm'])].append(m)
    counts['not_recorded']=len(planned)-len(rows)
    cells=[]; index={}
    numeric=[k for k in metrics[0] if k.endswith(('_ms','_mib'))]
    for (case,arm), samples in sorted(grouped.items()):
        cell=dict(**cases[case],arm=arm,repeats=len(samples))
        for key in numeric:
            vals=[r[key] for r in samples]
            cell[key]=dict(median=statistics.median(vals),min=min(vals),max=max(vals))
        cells.append(cell);index[(case,arm)]=cell
    paired=[]
    for case in sorted(cases):
        if any((case,a) not in index or index[(case,a)]['repeats']!=3 for a in ARMS):continue
        row=dict(case_id=case)
        for metric in numeric:
            values={a:index[(case,a)][metric]['median'] for a in ARMS}
            row[metric]=dict(medians=values,minimum_arm=min(values,key=values.get),
                             sqlite_over_python=values['sqlite_recursive']/values['python_indexed'],
                             rdf_over_python=values['rdf_owl_shacl']/values['python_indexed'])
        paired.append(row)
    summary={}
    for metric in numeric:
        summary[metric]=dict(paired_cases=len(paired),minimum_counts=dict(Counter(p[metric]['minimum_arm'] for p in paired)),
            sqlite_over_python_range=[min(p[metric]['sqlite_over_python'] for p in paired),max(p[metric]['sqlite_over_python'] for p in paired)],
            rdf_over_python_range=[min(p[metric]['rdf_over_python'] for p in paired),max(p[metric]['rdf_over_python'] for p in paired)])
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    result=dict(source_results_sha256=sha(source/'results.jsonl'),analysis_sha256=sha(__file__),
                denominator=dict(planned=len(planned),recorded=len(rows),statuses=dict(counts),successful_cells=len(cells),paired_cases=len(paired)),
                definitions=dict(components='input+prepare+warmup+observed batch query sum; excludes imports, serialization/IPC and earlier batches; arithmetic decomposition, not separate cold deployment run',
                                 query='per-worker batch mean; three technical repeat median/min/max within case',
                                 memory='whole worker ru_maxrss includes imports/all phases; not heap and not peak subtraction',
                                 minimum='minimum observed case median, not statistical significance or universal winner',
                                 updates='actual full rebuild in all arms; RDF fresh closure even certificate-only; no optimized incrementality claim'),
                cells=cells,paired=paired,summary=summary)
    (out/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
    with (out/'per-attempt.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(metrics[0]));writer.writeheader();writer.writerows(metrics)
    with (out/'case-medians.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=['case_id','edges','depth','width','seed','arm','repeats']+numeric);writer.writeheader()
        for cell in cells:writer.writerow({**{k:cell[k] for k in ['case_id','edges','depth','width','seed','arm','repeats']},**{k:cell[k]['median'] for k in numeric}})
    print(json.dumps(dict(denominator=result['denominator'],selected={k:summary[k] for k in ['prepare_ms','query_100_mean_ms','components_100_ms','update_query_E_ms','update_query_C_ms','whole_worker_peak_mib']}),indent=2))


if __name__=='__main__':main()
