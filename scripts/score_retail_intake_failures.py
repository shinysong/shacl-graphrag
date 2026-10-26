"""Scorer-only entry for terminal intake failures; never accepts pending artifacts."""
from collections import Counter
from scripts.retail_artifact_outcomes import FAILURES
from scripts.score_retail_decisions import indexed,score,REFERENCE

def score_intake_failures(references,outcomes):
    refs=indexed(references,REFERENCE)
    predictions=[];seen_keys=set();attempts=set();stage_attempts=Counter();stage_keys=Counter()
    for outcome in outcomes:
        if outcome.get('ready_for_scoring') is not True or outcome.get('state')!='terminal_intake_failure':
            raise ValueError('Only terminal intake failures can be scored here')
        attempt=outcome.get('attempt_id');stage=outcome.get('failure_stage')
        if not isinstance(attempt,str) or not attempt.strip() or attempt in attempts:raise ValueError('Invalid/duplicate attempt ID')
        intake=outcome.get('intake',{})
        if stage not in FAILURES or intake.get('status')!=stage or intake.get('executed') is not False:
            raise ValueError('Inconsistent intake failure stage')
        declared=outcome.get('declared_keys')
        if not isinstance(declared,list) or not declared:raise ValueError('Declared keys required')
        keys=[]
        for k in declared:
            if not isinstance(k,(tuple,list)) or len(k)!=2 or any(not isinstance(v,str) or not v.strip() for v in k):raise ValueError('Invalid key')
            keys.append(tuple(k))
        if len(set(keys))!=len(keys) or set(keys)&seen_keys:raise ValueError('Duplicate/overlapping keys')
        preds=outcome.get('predictions',[]);pmap=indexed(preds,{'error'})
        if set(pmap)!=set(keys):raise ValueError('Prediction keys do not match declared keys')
        attempts.add(attempt);seen_keys.update(keys);predictions.extend(preds)
        stage_attempts[stage]+=1;stage_keys[stage]+=len(keys)
    if not refs or seen_keys!=set(refs):raise ValueError('Reference and declared evaluation scope must match exactly')
    return {'metrics':score(references,predictions),'failure_attempts_by_stage':dict(stage_attempts),
            'affected_keys_by_stage':dict(stage_keys),'actual_execution_attempts':0,
            'note':'metrics runtime_error_n is a legacy generic error bucket, not actual runtime failure count. This entry handles only terminal intake failures, not successful or pending execution outcomes. Caller annotations are not authenticated provenance.'}
