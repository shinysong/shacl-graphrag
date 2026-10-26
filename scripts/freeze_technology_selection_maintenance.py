"""Freeze authored change cases/literal references before any implementation edits."""
import hashlib
import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from check_technology_selection_python import packet

ROOT=Path(__file__).resolve().parents[1]


def expected(p):
    # Literal baseline for this small authored construction; never call an arm.
    return dict(scene_id=p['scene_id'],receipt_id='receipt',receipt='accept',
        links=dict(order_line='resolved',inspection='resolved',certificate='resolved'),
        products=[dict(id=x,revision='R1',candidate='yes' if x=='X' else 'no',
                       recheck='required' if x=='X' else 'not_required',witness=['edge'] if x=='X' else []) for x in 'EFUX'],
        impact_graph_completeness='complete',violated_checks=[],unknown_checks=[])


def xrow(e): return next(r for r in e['products'] if r['id']=='X')


def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
    cases=[]
    def add(task,name,edit=None,verdict=None,consumer=None,regression=False):
        p=packet();p['scene_id']=task+'-'+name+(('-'+consumer) if consumer else '')
        if edit:edit(p)
        e=expected(p)
        if verdict:verdict(e)
        cases.append(dict(id=p['scene_id'],task=task,consumer=consumer,regression=regression,packet=p,expected=e))
    def receipt_field(key,val): return lambda p:p['tables']['receipt'][0].update({key:val})
    def failed(e):e.update(receipt='violation',violated_checks=[dict(rule_id='certificate-dates',support=['c','r'])])
    def unknown(e):e.update(receipt='unknown',unknown_checks=[dict(rule_id='certificate-dates',support=['c','r'])]);xrow(e)['recheck']='unknown'
    add('M1','baseline',regression=True)
    add('M1','at-end',receipt_field('received_at','2026-10-01'))
    def recheck_at_end(p):
        p['tables']['receipt'][0]['received_at']='2026-10-01'
        p['question']['as_of']='2026-10-01'
    add('M1','recheck-at-end',recheck_at_end)
    add('M1','after-end',receipt_field('received_at','2026-10-02'),failed)
    add('M1','invalid-interval',lambda p:p['tables']['certificate'][0].update(expires='2025-12-31'),unknown)
    def category(value):return lambda p:next(r for r in p['tables']['product'] if r['id']=='X').update(category=value)
    add('M2','missing-category',regression=True)
    add('M2','service-spare',category('service_spare'),lambda e:xrow(e).update(recheck='not_required'))
    add('M2','other-category',category('production'))
    def dated(p):p['tables']['component_edge'][0].update(valid_from='2026-10-21',valid_to='2026-11-01')
    add('M3','at-start',dated,regression=True)
    def ended(p):dated(p);p['tables']['component_edge'][0]['valid_to']='2026-10-21';p['tables']['component_edge'][0]['valid_from']='2026-01-01'
    def no_path(e):xrow(e).update(candidate='no',recheck='not_required',witness=[])
    add('M3','at-end',ended,no_path)
    def partial(e):
        e['impact_graph_completeness']='partial'
        for r in e['products']:r.update(candidate='unknown',recheck='unknown',witness=[])
    add('M3','missing-dates',verdict=partial)
    def bad(p):dated(p);p['tables']['component_edge'][0]['valid_to']='invalid'
    add('M3','invalid-dates',bad,partial)
    def alternate(p):
        bad(p)
        edge=dict(p['tables']['component_edge'][0],id='alternate',occurrence_id='alternate',valid_from='2026-01-01',valid_to='2026-12-01')
        p['tables']['component_edge'].append(edge)
    def alt_result(e):partial(e);xrow(e).update(candidate='yes',recheck='required',witness=['alternate'])
    add('M3','alternate-path',alternate,alt_result)
    for consumer in ('A','B','C'):
        for name,q,remaining,decision in [('baseline',5,10,'accept'),('cap',8,10,'accept'),('over-cap',9,10,'violation'),('remaining',5,4,'violation'),('missing',None,10,'unknown')]:
            def edit(p,q=q,remaining=remaining):p['tables']['receipt'][0]['quantity']=q;p['tables']['order_line'][0]['remaining_quantity']=remaining
            def verdict(e,decision=decision):
                e['receipt']=decision
                if decision!='accept':e['violated_checks' if decision=='violation' else 'unknown_checks']=[dict(rule_id='quantity',support=['o','r'])]
            add('M4',name,edit,verdict,consumer,regression=name=='baseline')
    def evaluated(e,mode='pass'):
        entries=[]
        for name,occ in [('order','o'),('inspection','i'),('certificate','c')]:
            for field in ('part','revision','facility'):entries.append(dict(rule_id=name+'-'+field,support=sorted([occ,'r']),policy_version='v2',result='pass'))
        for label,support in [('inspection-receipt',['i','r']),('quantity',['o','r']),('inspection-status',['i']),('certificate-status',['c']),('certificate-dates',['c','r'])]:
            entries.append(dict(rule_id=label,support=support,policy_version='v2',result=mode if label=='quantity' else 'pass'))
        e['evaluated_checks']=sorted(entries,key=lambda c:c['rule_id'])
        if mode!='pass':
            e['receipt']='violation' if mode=='violation' else 'unknown'
            e['violated_checks' if mode=='violation' else 'unknown_checks']=[dict(rule_id='quantity',support=['o','r'])]
    add('M5','all-passed',verdict=evaluated,regression=True)
    add('M5','violation',receipt_field('quantity',11),lambda e:evaluated(e,'violation'))
    add('M5','unknown',receipt_field('quantity',None),lambda e:evaluated(e,'unknown'))
    def unresolved(e):
        e.update(receipt='unknown',links=dict(order_line='missing',inspection='resolved',certificate='resolved'),
                 unknown_checks=[dict(rule_id='link-order_line',support=['r'])],
                 evaluated_checks=[dict(rule_id='link-order_line',support=['r'],policy_version='v2',result='unknown')])
    add('M5','unresolved',lambda p:p['tables'].update(order_line=[]),unresolved)
    files={}
    for case in cases:
        for sub,data in [('runtime',dict(packet=case['packet'],consumer=case['consumer'])),('references',dict(expected=case['expected'],task=case['task'],regression=case['regression']))]:
            path=out/sub/(case['id']+'.json');path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(data,indent=2)+'\n');files[str(path.relative_to(out))]=hashlib.sha256(path.read_bytes()).hexdigest()
    sources=[ROOT/'scripts'/('technology_selection_'+n+'.py') for n in ('common','python','sqlite','rdf')]+[ROOT/'scripts/industrial_question_python.py']+list((ROOT/'research/technology-selection').glob('*'))
    baseline={}
    for p in sources:
        if not p.is_file():continue
        relative=p.relative_to(ROOT);target=out/'baseline'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);baseline[str(relative)]=hashlib.sha256(p.read_bytes()).hexdigest()
    manifest=dict(cases=[{k:c[k] for k in ('id','task','consumer','regression')} for c in cases],files=files,baseline=baseline,
        expected_initial_submissions=15,max_corrective_submissions_per_task_arm=1,
        m4_consumers='Three callers A/B/C must use one common live policy artifact per arm; copies with three hardcoded caps do not pass structural acceptance. No labor measurement.',
        m5_contract='Add evaluated_checks sorted rule_id, result pass/violation/unknown and policy_version v2 on each entry; existing canonical fields unchanged. Unresolved reference suppresses content checks.',
        scope='Authored development change tasks; literal references frozen before edits. No runtime reference access. Timed campaign stays immutable.',
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),tasks=5,initial_task_arm_submissions=15,files=len(files),baseline_files=len(baseline),patches_executed=0)))


if __name__=='__main__':main()
