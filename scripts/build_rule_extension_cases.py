"""Write authored fixtures and explicit expectations; never execute either arm."""
import copy
import hashlib
import json
import random
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'_workspace/rule-extension-v1/frozen'
NAMES = ['eligible','draft-document','rejected-review','self-approval','expired-qualification','future-qualification','missing-review','duplicate-review','missing-qualification','duplicate-qualification','invalid-date','missing-author','unknown-document-status','wrong-document-revision','blocked-plus-unknown','expiry-boundary']
# Authored before first engine execution. Each tuple = violations, unknown IDs.
EXPECT = [
 ([],[]),(['document-status'],[]),(['review-decision'],[]),(['self-review'],[]),
 (['qualification-dates'],[]),(['qualification-dates'],[]),([],['review-link']),([],['review-link']),
 ([],['qualification-link']),([],['qualification-link']),([],['qualification-dates']),([],['self-review']),
 ([],['document-status']),([],['document-link']),(['document-status'],['review-link']),(['qualification-dates'],[])]

def main():
    if OUT.exists():
        raise SystemExit('refuse overwrite frozen fixtures')
    (OUT/'runtime').mkdir(parents=True); (OUT/'scorer').mkdir()
    cases=[]
    for seed in (11,23):
        prefix=f's{seed}-'
        for i,name in enumerate(NAMES):
            d=dict(occurrence_id=prefix+'d',id=prefix+'policy',revision='r1',author=prefix+'alice',status='Approved')
            r=dict(occurrence_id=prefix+'r',document_id=d['id'],revision='r1',reviewer=prefix+'bob',decision='Accept')
            quals=[dict(occurrence_id=prefix+k,person=r['reviewer'],role=role,start='2026-01-01',end='2027-01-01') for k,role in [('q','PolicyReviewer'),('c','ComplianceReviewer')]]
            reviews=[r]
            if i==0: quals[1]['end']='2026-10-22'
            if i in (1,14):d['status']='Draft'
            if i==2:r['decision']='Reject'
            if i==3:
                r['reviewer']=d['author']
                for q in quals:q['person']=d['author']
            if i==4:
                for q in quals:q['end']='2026-10-21'
            if i==5:
                for q in quals:q['start']='2026-10-23'
            if i in (6,14):reviews=[]
            if i==7:reviews.append(dict(r,occurrence_id=prefix+'r-duplicate'))
            if i==8:quals=quals[1:]
            if i==9:quals.append(dict(quals[0],occurrence_id=prefix+'q-duplicate'))
            if i==10:
                for q in quals:q['end']='not-a-date'
            if i==11:del d['author']
            if i==12:d['status']='Mysterious'
            if i==13:d['revision']='r2'
            if i==15:
                for q in quals:q['end']='2026-10-22'
            packet=dict(question=dict(document_id=d['id'],revision='r1',assessment_date='2026-10-22'),tables=dict(document=[d],review=reviews,qualification=quals))
            for rows in packet['tables'].values():random.Random(seed).shuffle(rows)
            case=f'c{i:02}s{seed}';cases.append(case)
            (OUT/'runtime'/f'{case}.json').write_text(json.dumps(packet,sort_keys=True))
            expected={}
            for v in ('v1','v2'):
                bad,unknown=copy.deepcopy(EXPECT[i])
                if v=='v2' and i==0:bad=['qualification-dates']
                if v=='v2' and i in (8,9):bad,unknown=[],[]
                expected[v]=dict(decision='blocked' if bad else 'unknown' if unknown else 'eligible',violations=bad,unknown=unknown)
            (OUT/'scorer'/f'{case}.json').write_text(json.dumps(dict(scenario=name,expected=expected),sort_keys=True))
    old=[ROOT/'scripts'/f'technology_selection_{s}.py' for s in ('python','rdf','common')]
    old+=list((ROOT/'research/technology-selection').glob('*v1.*'))
    old+= [ROOT/'scripts/industrial_question_python.py']
    manifest=dict(cases=cases,scenarios=16,seed_controls=[11,23],unexercised=['missing-document','duplicate-document','multiple review authors','new predicate beyond supported kinds'],
                  baseline={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in old},
                  files={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*.json')})
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True))
    print(OUT)

if __name__=='__main__':main()
