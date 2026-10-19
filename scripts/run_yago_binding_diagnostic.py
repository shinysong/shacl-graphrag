"""One explicitly scaffolded follow-up, separate from the unassisted 12 episodes."""
import json
from pathlib import Path
from datetime import UTC,datetime
import run_yago_tool_study as study

GUIDE = '''Additional generic query-interface scaffold, not a source answer: all projected s/p/o variables must be bound. A constant subject pattern does not bind ?s. For inspection of this small snapshot, a valid generic query is SELECT ?s ?p ?o WHERE { ?s ?p ?o }. To narrow it, FILTER on a bound ?s or use VALUES ?s { <the supplied subject IRI> }. Preserve RDF types and linked-object descriptions for validation. This example changes the interface condition: it is not an unassisted free-query result. You choose queries and interpret the returned data yourself.'''

def main():
    people,source,manifest=study.inputs()
    assert len(people)==4
    ledger=json.loads(study.LEDGER.read_text())
    if ledger['attempts']+12>study.CAP_CALLS or any(x['reported_usd'] is None for x in ledger['reservations']):
        raise study.BudgetStop('NoResolvedBudgetForDiagnostic')
    guard=study.LEDGER.parent/'binding-diagnostic-reservation.json'
    with guard.open('x') as f:
        json.dump({'at':study.stamp(),'person':people[0]['subject'],'planned':1,'cap_turns':12,'previous_attempts':ledger['attempts']},f)
    run=study.ROOT/'runs'/datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ-yago-binding-diagnostic')
    run.mkdir(exist_ok=False)
    study.PROMPT=study.PROMPT+'\n'+GUIDE
    record={'protocol':'yago-native-tools-1-binding-diagnostic','status':'running','assigned':1,'scaffold':GUIDE,'source_hashes':manifest['sha256'],'comparison':'posthoc single repeated consumed subject; not replacement/independent efficacy result','code_hashes':{str(p):study.sha(p) for p in [Path(__file__),study.ROOT/'scripts/run_yago_tool_study.py',study.ROOT/'scripts/yago_native_tools.py']}}
    study.atomic_write(run/'record.json',record)
    gateway=study.Gateway(run)
    try:
        row=study.episode(gateway,run/'episode-01-C',people[0],'C',source)
        record.update(status='completed',rows=[row]);print(json.dumps(row),flush=True)
    except BaseException as exc:
        record.update(status='stopped',error_type=type(exc).__name__);raise
    finally:
        study.atomic_write(run/'record.json',record);gateway.close();print(run,flush=True)

if __name__=='__main__':main()
