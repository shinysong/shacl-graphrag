# Same-database authored change diagnostic
Continue consumed 7source records4relations from previousbackend/inference studies. Previous224slots showed query-set parity, notdynamicmaintenance. New8orderedstates initialtwo supportpaths, deleteprimary,deletealternate,restorepaths,deleteonefact,restorefact,deleteallschema,restoreschema. Eightstates x4querysets x5arms=160live slots;64offline slots. SamepolicyPython recomputes current, staleoffline fixedinitial; native n10s updates asserted schema/fact edges inplace inownedemptydedicatedNeo4j7475; Neptune currentgraph replaces recomputed externalRDFSclosure eachstate; separate Neptune stalegraph intentionallyunchanged. Notincrementalreasoning/truthmaintenancealgorithm, notlatency/QA benchmark. Afterquiescent updates query same4sets, storecounts before/after prove only count-level noaddedtriples, notcomplete byteidentity. Adapters use existing signedendpoint/account/deadlines, native samefixed7475, allownednamespaces; noAWSnewresources/restarts/paidLLM. Original10:10:52UTC hardcutoff, livecallsstop120searlier. Cleanup allconstructed stores finally, verifyempty; preserveplan/failure/receipts, stoponmutationcountnot1 orstoragecountmismatch. Eachnative mutation committed separately; noatomic/concurrenttransactionclaim. Onlythisprocess in dedicatedn10s; nooutsidewriters expected. Reference-only evaluator notreadruntime, uses prioralreadyconsumed manualreference querysets mappedtoevents; notfreshheldout. Contenthash excludeseventname so identicalrestorationsdo not falsely appear stale. Samefullscope advertisedhash acrossarms, no gold runtime. Guard finalreport against labeling stalecontrol mismatches engineweakness orautomatically concludingSHACL benefit. Nativecapabilityreceipt current containerexists withprocs/version, noinstallneeded. Review scripts supplied below and imported modules by pathname; do notread any otherreviewresults. Tests4methods planned, offline64 beforelive; scorer checks fullplan/statusdenominators, no silentrepair.

Revision2: each native mutation attempt/result fsync append journal; anomalous count and unknown request outcome recorded before abort; no retry. Failure-injection regression covers prior success then count0 or exception. Scorer included separately for denominator review.

FILE scripts/backend_updates.py
"""Quiescent in-place change diagnostic; no incremental reasoner/performance claim."""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
from rdflib import URIRef
from scripts.backend_parity import canonical,digest,CUTOFF,NeptuneStore
from scripts.backend_inference import (NativeN10s,build_variants,external_closure,answer,query_store,QUERIES,TYPE,SC,SP,DEF,term,RELATION_NAMES,verified_cleanup)


def states(source):
    variants={v['id']:v for v in build_variants(source)}
    dual=variants['two_supports']
    sequence=[]
    for name,base in [('initial','two_supports'),('delete_primary','remove_primary'),('delete_alternate','remove_both_annotation_supports'),('restore_paths','two_supports'),('delete_fact','two_supports'),('restore_fact','two_supports'),('delete_schema','missing_schema'),('restore_schema','two_supports')]:
        v=json.loads(canonical(variants[base]));v['id']=name
        if name=='delete_fact':v['facts']=[t for t in v['facts'] if tuple(t)!=(term('PP6:2'),DEF,term('PP6:defect_code:4'))]
        sequence.append(v)
    return sequence


def input_digest(state):
    return digest({k:sorted(state[k]) for k in ('facts','schema')})


def delta(old,new):
    a={tuple(t) for k in ('facts','schema') for t in old[k]};b={tuple(t) for k in ('facts','schema') for t in new[k]}
    return {'deleted':sorted(a-b),'added':sorted(b-a)}


class UpdatingNative(NativeN10s):
    def update(self,old,new,journal=None,event=None):
        changes=delta(old,new);receipts=[]
        for action in ('deleted','added'):
            for s,p,o in changes[action]:
                if p==TYPE:sl,ol,key,rel='InferenceRecord','InferenceClass','id','INSTANCE_OF'
                elif p==SC:sl,ol,key,rel='InferenceClass','InferenceClass','id','SUBCLASS'
                elif p==SP:
                    sl,ol,key,rel='InferenceProperty','InferenceProperty','name','SUBPROPERTY'
                    s,o=RELATION_NAMES[s],RELATION_NAMES[o]
                else:sl,ol,key,rel='InferenceRecord','InferenceRecord','id',RELATION_NAMES[p]
                nodes=f'(s:{sl} {{run:$run,{key}:$s}}),(o:{ol} {{run:$run,{key}:$o}})'
                if action=='deleted':q=f'MATCH {nodes} MATCH (s)-[r:{rel}]->(o) DELETE r RETURN count(*) AS changed'
                else:q=f'MATCH {nodes} CREATE (s)-[:{rel}]->(o) RETURN count(*) AS changed'
                attempt={'event':event,'action':action,'triple':[s,p,o],'sequence':len(receipts)}
                if journal:journal({**attempt,'status':'attempted'})
                try:count=self.request(q,{'s':s,'o':o})[0]['changed']
                except Exception as exc:
                    if journal:journal({**attempt,'status':'outcome_unknown','error':type(exc).__name__+': '+str(exc)})
                    raise
                receipt={**attempt,'changed':count,'status':'completed' if count==1 else 'anomalous_count'}
                if journal:journal(receipt)
                receipts.append(receipt)
                if count!=1:raise RuntimeError('mutation count differs from one')
        return {'delta':changes,'receipts':receipts}
    def counts(self):
        return self.request('MATCH (n:InferenceOwned {run:$run}) OPTIONAL MATCH (n)-[r]->() RETURN count(DISTINCT n) AS nodes,count(r) AS edges')[0]


class UpdatingNeptune(NeptuneStore):
    def replace(self,triples):
        if not self.owned:raise RuntimeError('graph not owned')
        data=' .\n'.join(' '.join(t) for t in triples)+' .'
        self.request(f'CLEAR GRAPH {self.graph}; INSERT DATA {{GRAPH {self.graph} {{{data}}}}}',update=True)
    def count(self):
        r=self.request(f'SELECT (COUNT(*) AS ?n) WHERE {{GRAPH {self.graph} {{?s ?p ?o}}}}')
        return int(r['results']['bindings'][0]['n']['value'])


def append_journal(path,row):
    with Path(path).open('a') as handle:
        handle.write(canonical(row)+'\n');handle.flush();os.fsync(handle.fileno())


def encoded(triples):return [tuple(URIRef(x).n3() for x in t) for t in triples]


def run(source_path,output,live=False):
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    source=json.loads(Path(source_path).read_text());sequence=states(source)
    arms=['python_current','stale_offline']+(['n10s_live_update','neptune_recomputed','neptune_stale'] if live else [])
    plan=[{'event':s['id'],'arm':a,'query_id':q['id']} for s in sequence for a in arms for q in QUERIES]
    for file,obj in [('source.json',source),('states.json',sequence),('queries.json',QUERIES),('plan.json',plan)]: (out/file).write_text(canonical(obj)+'\n')
    (out/'runtime.py').write_bytes(Path(__file__).read_bytes())
    stores={};cleanup=[];mutations=[];stale=external_closure(sequence[0]['facts'],sequence[0]['schema']);initial_hash=input_digest(sequence[0])
    try:
        if live:
            for arm,constructor,suffix in [('n10s_live_update',UpdatingNative,'-native'),('neptune_recomputed',UpdatingNeptune,'-fresh'),('neptune_stale',UpdatingNeptune,'-stale')]:
                store=constructor('backend-'+out.name+suffix);stores[arm]=store
                store.load(sequence[0] if arm=='n10s_live_update' else encoded(stale))
        with (out/'results.jsonl').open('a') as h:
            for i,state in enumerate(sequence):
                if live and dt.datetime.now(dt.timezone.utc)>=CUTOFF-dt.timedelta(seconds=120):raise RuntimeError('live launch cutoff')
                current=external_closure(state['facts'],state['schema'])
                from scripts.run_ontology_reasoning_study import json_closure
                python,_=json_closure(state['schema'],state['facts'])
                if live and i:
                    mutation=stores['n10s_live_update'].update(sequence[i-1],state,journal=lambda row:append_journal(out/'native-mutation-attempts.jsonl',row),event=state['id'])
                    mutations.append({'event':state['id'],'native':mutation,'refresh':'full closure recomputation and replacement, not incremental inference'})
                    (out/'mutations.json').write_text(canonical(mutations)+'\n')
                    stores['neptune_recomputed'].replace(encoded(current))
                counts_before=stores['n10s_live_update'].counts() if live else None
                fresh_count=stores['neptune_recomputed'].count() if live else None
                stale_count=stores['neptune_stale'].count() if live else None
                for arm in arms:
                    for q in QUERIES:
                        row={'event':state['id'],'arm':arm,'query_id':q['id'],'current_input_hash':input_digest(state),'used_input_hash':initial_hash if arm in ('stale_offline','neptune_stale') else input_digest(state)}
                        try:
                            if arm=='n10s_live_update':result=stores[arm].query(q)
                            elif arm in stores:result=query_store(stores[arm],q)
                            else:result=answer(python if arm=='python_current' else stale,q)
                            row.update(status='completed',answer=result)
                        except Exception as exc:row.update(status='query_failure',error=type(exc).__name__+': '+str(exc))
                        h.write(canonical(row)+'\n');h.flush()
                if live:
                    counts_after=stores['n10s_live_update'].counts()
                    receipt={'event':state['id'],'native_before':counts_before,'native_after':counts_after,'fresh_stored_triples':fresh_count,'fresh_expected_triples':len(current),'stale_stored_triples':stale_count,'stale_initial_triples':len(stale)}
                    with (out/'storage.jsonl').open('a') as sh:sh.write(canonical(receipt)+'\n')
                    if counts_before!=counts_after or fresh_count!=len(current) or stale_count!=len(stale):raise RuntimeError('unexpected storage-count change')
    except Exception as exc:
        (out/'failure.json').write_text(canonical({'error':type(exc).__name__+': '+str(exc)})+'\n');raise
    finally:
        for arm,store in stores.items():
            try:cleanup.append({'arm':arm,'status':'completed','receipt':verified_cleanup(store)})
            except Exception as exc:cleanup.append({'arm':arm,'status':'failed','error':str(exc)})
            (out/'cleanup.json').write_text(canonical(cleanup)+'\n')
        if any(x['status']=='failed' for x in cleanup):raise RuntimeError('unresolved cleanup; no continuation')
    return plan

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--live',action='store_true');a=p.parse_args();run(a.source,a.output,a.live)

Packet compacted after synthesis ContextLimit; unchanged reviewed source. Unit test body omitted; actual direct unit check reports4pass but not evidence suppliedforreview. Priorreviews retained, not overwritten.
