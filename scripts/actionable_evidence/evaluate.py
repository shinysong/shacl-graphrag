"""Posthoc scorer. Runtime outputs must exist completely before labels are read."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT/'research/actionable-evidence-1'


def fraction(n, d):
    return dict(numerator=n, denominator=d, rate=n/d if d else None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if not args.run_id.replace('-', '').isalnum():
        raise SystemExit('Invalid run ID')
    out = STUDY/'runs'/args.run_id
    if (out/'evaluation.json').exists():
        raise SystemExit('Refusing to overwrite scored results')
    completion = json.loads((out/'completion.json').read_text())
    freeze = json.loads((out/'freeze.json').read_text())
    assert completion['rows'] == completion['expected_rows'] == freeze['expected_rows']
    assert not completion['changed_inputs']
    rows = [json.loads(line) for line in (out/'outputs.jsonl').read_text().splitlines()]
    assert len(rows) == freeze['expected_rows']
    assert len({(r['case_id'],r['arm'],r['postcheck']) for r in rows}) == len(rows)
    # First semantic read of scorer occurs only after saved complete output checks.
    scorer_path = STUDY/'fixtures/scorer.json'
    assert hashlib.sha256(scorer_path.read_bytes()).hexdigest() == freeze['hashes'][str(scorer_path.relative_to(ROOT))]
    scorer = {r['case_id']:r for r in json.loads(scorer_path.read_text())}
    scored, groups = [], {}
    for row in rows:
        gold = scorer[row['case_id']]
        ok = row['status'] == 'ok'
        result = row.get('result', {})
        propose = ok and result.get('disposition') == 'propose_patch'
        value = (result.get('candidate_patch') or {}).get('new')
        supported = gold['contract_eligible'] and value == gold['expected_candidate_value']
        item = dict(case_id=row['case_id'], arm=row['arm'], postcheck=row['postcheck'],
                    state=gold['state'], depth=gold['depth'], field=gold['field'], error=not ok,
                    proposed=propose, contract_eligible=gold['contract_eligible'],
                    correct_known_eligible=gold['correct_known_eligible'],
                    unsupported_proposal=propose and not supported,
                    unnecessary_withholding=ok and gold['correct_known_eligible'] and not propose,
                    eligible_execution_failure=not ok and gold['correct_known_eligible'],
                    externally_wrong_proposal=propose and value != gold['external_truth'],
                    contract_agreement=ok and ((propose and supported) or (not propose and not gold['contract_eligible'])),
                    original_unchanged=result.get('original_unchanged'),
                    validator_agreement=ok and all(result[k] is None or result[k]['validators_agree'] for k in ('before_report','after_report')))
        scored.append(item)
        groups.setdefault((row['arm'],row['postcheck']),[]).append(item)
    summary = []
    for (arm,post), group in groups.items():
        n=len(group); proposals=sum(r['proposed'] for r in group)
        eligible=sum(r['correct_known_eligible'] for r in group)
        counts={k:sum(r[k] is True for r in group) for k in ('error','proposed','contract_eligible','correct_known_eligible','unsupported_proposal','unnecessary_withholding','eligible_execution_failure','externally_wrong_proposal','contract_agreement','original_unchanged','validator_agreement')}
        summary.append(dict(arm=arm,postcheck=post,cases=n,counts=counts,rates={
            'proposals_all':fraction(proposals,n),
            'unsupported_all':fraction(counts['unsupported_proposal'],n),
            'unsupported_proposals':fraction(counts['unsupported_proposal'],proposals),
            'unnecessary_withholding_eligible':fraction(counts['unnecessary_withholding'],eligible),
            'unnecessary_withholding_all':fraction(counts['unnecessary_withholding'],n),
            'external_wrong_all':fraction(counts['externally_wrong_proposal'],n),
            'external_wrong_proposals':fraction(counts['externally_wrong_proposal'],proposals)}))
    indexed={(r['case_id'],r['arm'],r['postcheck']):r for r in rows}
    parity=[]
    keys=('candidate_reference_ids','candidate_citations','candidate_patch','diff','disposition','before_report','after_report','original_unchanged')
    for post in ('no_postcheck','shadow_revalidation'):
        mismatches=[]; valid=0
        ids=sorted({r['case_id'] for r in rows})
        for cid in ids:
            a=indexed[(cid,'matched_Python_relation_candidate',post)]
            b=indexed[(cid,'SHACL_AF_relation_candidate',post)]
            if a['status']!='ok' or b['status']!='ok':
                mismatches.append(dict(case_id=cid,reason='execution_failure')); continue
            differences=[k for k in keys if a['result'][k]!=b['result'][k]]
            if differences:mismatches.append(dict(case_id=cid,keys=differences))
            else:valid+=1
        parity.append(dict(postcheck=post,matched=valid,paired_cases=len(ids),mismatches=mismatches))
    result=dict(kind='authored_consumed_development',run_id=args.run_id,smoke=freeze['smoke'],
                rows=len(rows),independent_case_count=len({r['case_id'] for r in rows}),
                summaries=summary,python_shacl_parity=parity,scored_rows=scored,
                limitations=['Authored expectations, not independently observed truth','No latency comparison: both post arms compute identical diagnostics','Direct arm deliberately omits second hop','No real source corrections or paid LLM calls'])
    (out/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='scored_rows'},indent=2))


if __name__ == '__main__':
    main()
