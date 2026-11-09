"""Offline inventory and aggregation of explicit coordinator judgments; never generates answers."""
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT=Path('_workspace/answer-campaign-20261103')
INPUT=Path('research/answer-evidence-1/answer-inputs-001/episodes.jsonl')
TARGETS=Path('research/answer-evidence-1/evaluation-targets-001/fields.json')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    planned=[json.loads(s) for s in INPUT.read_text().splitlines()]
    freeze=json.loads((ROOT/'freeze.json').read_text())
    for name,h in freeze['hashes'].items():
        if sha(Path(name))!=h:raise ValueError('generation freeze changed')
    binding=json.loads((TARGETS.parent/'input-hashes.json').read_text())
    for key,name in binding['paths'].items():
        if sha(Path(name))!=binding['hashes'][key]:raise ValueError('target provenance changed')
    if sha(TARGETS) != '47f4837af102673af708d9b468a831b9a1968699afe83aec63cbff3ab312dfa2':raise ValueError('target fields changed')
    target_rows=json.loads(TARGETS.read_text())
    targets={r['episode_id']:r for r in target_rows}
    if len(targets)!=len(target_rows):raise ValueError('duplicate targets')
    questions={r['question_id'] for r in planned}
    keys=[(r['question_id'],r['arm']) for r in planned]
    if len(questions)!=24 or len(set(keys))!=72 or set(keys)!={(q,a) for q in questions for a in 'BCD'}:raise ValueError('question arm universe')
    if [r['episode_id'] for r in planned]!=freeze['episode_order']:raise ValueError('frozen order')
    for r in planned:
        t=targets[r['episode_id']]
        if any(r[k]!=t[k] for k in ['question_id','arm','message_sha256']):raise ValueError('target identity')
    annotations=json.loads((ROOT/'adjudications.json').read_text())
    by={r['episode_id']:r for r in annotations}
    ids={r['episode_id'] for r in planned}
    if len(planned)!=72 or len(ids)!=72 or set(targets)!=ids or len(by)!=len(annotations):raise ValueError('universe/duplicate')
    ledger=json.loads((ROOT/'campaign-budget.json').read_text())
    attempts={r['episode_id']:r for r in ledger['attempts']}
    if len(attempts)!=len(ledger['attempts']) or not set(attempts)<=ids:raise ValueError('ledger universe')
    rows=[];completed=set()
    for p in planned:
        eid=p['episode_id'];t=targets[eid];a=attempts.get(eid)
        rpath=ROOT/'responses'/(eid+'.result.json')
        rawpath=ROOT/'responses'/(eid+'.raw.txt')
        result=json.loads(rpath.read_text()) if rpath.exists() else None
        if a and a['state']=='resolved' and result is None:raise ValueError('missing resolved result')
        status=result['status'] if result else ('not_attempted' if a is None else 'unresolved_attempt')
        row=dict(episode_id=eid,question_id=p['question_id'],arm=p['arm'],status=status,
                 source_state=t['source_state'],selected_support=t['selected_support'],task=t['target_task'],
                 target_outcome='not_evaluable',unnecessary_withholding=None,
                 unsupported_assertion=None,review_pointer='not_evaluable',claim_support=[],citation_ids=[],
                 note='No semantically adjudicated schema-valid response')
        if result:
            if not a or a['state']!='resolved' or Decimal(a['reported_usd'])!=Decimal(result['reported_usd']):raise ValueError('cost/result binding')
            request=json.loads((ROOT/'responses'/(eid+'.request.json')).read_text())
            expected=dict(freeze['payload_settings'],messages=p['messages'])
            if request!=expected:raise ValueError('request identity/settings')
            if a['status']!=result['status']:raise ValueError('ledger result status')
            raw=json.loads(rawpath.read_text())
            if raw.get('model')!=freeze['model'] or raw.get('provider')!='OpenAI':raise ValueError('raw model/provider')
            if Decimal(str(raw['usage']['cost']))!=Decimal(result['reported_usd']):raise ValueError('raw cost')
            if status=='completed':
                if json.loads(raw['choices'][0]['message']['content'])!=result['answer']:raise ValueError('raw answer binding')
                completed.add(eid);j=by[eid]
                if j['result_sha256']!=sha(rpath):raise ValueError('adjudication result binding')
                if j['target_outcome'] not in ['correct','wrong','withheld','not_evaluable']:raise ValueError('target label')
                if j['unsupported_assertion'] not in [True,False,None]:raise ValueError('certainty label')
                if j['review_pointer'] not in ['relevant','irrelevant','none','not_evaluable']:raise ValueError('review label')
                claims=result['answer']['claims']
                if len(j['claim_support'])!=len(claims) or any(c not in ['supported','unsupported','unknown'] for c in j['claim_support']):raise ValueError('claims denominator')
                row.update({k:j[k] for k in ['target_outcome','unsupported_assertion','review_pointer','claim_support','note']})
                if t['selected_support'] and j['target_outcome']!='not_evaluable':row['unnecessary_withholding']=j['target_outcome']=='withheld'
                row['citation_ids']=[c['chunk_id'] in p['selected_chunk_ids'] for cl in claims for c in cl['citations']]
                row['result_sha256']=sha(rpath)
        rows.append(row)
    if set(by)!=completed:raise ValueError('adjudication full completed universe')
    arms={}
    for arm in 'BCD':
        sub=[r for r in rows if r['arm']==arm];eligible=[r for r in sub if r['selected_support']]
        yes=sum(r['unnecessary_withholding'] is True for r in eligible);evaluated=sum(r['unnecessary_withholding'] is not None for r in eligible)
        arms[arm]=dict(planned=len(sub),execution=dict(Counter(r['status'] for r in sub)),target=dict(Counter(r['target_outcome'] for r in sub)),
            source_states={state:dict(Counter(r['target_outcome'] for r in sub if r['source_state']==state)) for state in sorted({r['source_state'] for r in sub})},
            eligible=len(eligible),unnecessary_withholding_yes=yes,unnecessary_withholding_unknown=len(eligible)-evaluated,
            withholding_lowerbound=yes/len(eligible) if eligible else None,withholding_conditional=yes/evaluated if evaluated else None,
            unsupported_assertion_yes=sum(r['unsupported_assertion'] is True for r in sub),unsupported_assertion_unknown=sum(r['unsupported_assertion'] is None for r in sub),
            review_pointers=dict(Counter(r['review_pointer'] for r in sub)),
            claims=dict(Counter(c for r in sub for c in r['claim_support'])),
            citations_in_selected=sum(c for r in sub for c in r['citation_ids']),citations_total=sum(len(r['citation_ids']) for r in sub))
    paired=[]
    rby={(r['question_id'],r['arm']):r for r in rows}
    for q in sorted({r['question_id'] for r in rows}):
        c,d=rby[q,'C'],rby[q,'D']
        paired.append(dict(question_id=q,C=c['target_outcome'],D=d['target_outcome'],C_status=c['status'],D_status=d['status'],
                           C_unsupported=c['unsupported_assertion'],D_unsupported=d['unsupported_assertion']))
    if len(paired)!=24:raise ValueError('pair count')
    result=dict(planned=72,attempts=len(attempts),reserved_usd=str(sum(Decimal(a['reserved_usd']) for a in attempts.values())),
                reported_usd=str(sum(Decimal(a['reported_usd']) for a in attempts.values() if a['reported_usd'] is not None)),
                unresolved_attempts=sum(a['state']!='resolved' for a in attempts.values()),arms=arms,pairs=paired,rows=rows,
                limitations=['Consumed development cohort; unblinded coordinator annotations, not independent expert grading.',
                            'Claim support counts are claim-array items, NOT deduplicated proposition metrics. Answer-level unsupported assertion includes prose.',
                            'Selected citation-ID membership does not certify locator resolution or entailment. Locator validity not aggregated.',
                            'Review relevance judged from text; human usefulness unmeasured. C/D includes added-context-length difference.'],
                hashes={str(p):sha(p) for p in [INPUT,TARGETS,ROOT/'adjudications.json',ROOT/'campaign-budget.json',Path(__file__)]})
    (ROOT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:result[k] for k in ['planned','attempts','reserved_usd','reported_usd','arms']},ensure_ascii=False))
if __name__=='__main__':main()
