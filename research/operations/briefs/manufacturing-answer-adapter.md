# Manufacturing answer adapter implementation review
Offline only. Prior design approved under job20261107T151431Z-manufacturing-continuity-20261107-12986f.36savedslots9questions4backends. Newoutput notnewLLM/liveDB. Sharedmanualpolicy explicit; Q8emptybindingoriginundetermined. Originalresultsunaltered. Source/evaluator data notreadbyadapter; policyfromquestions/headers, nottruth. Q3subtracts second-minusfirst;Q4checksboundeduniverse; Q5/9partial preservevalues butnoactualmeasurementclaim;Q6sameworkbookdeclaredpolicy;Q7unsupported. Unitcontrols covermissingoperand/candidate,duplicates,irrelevantrow,missingrolepolicy,wrongworkbookandinconsistentidentity. Hiddenwrongpolicy/edgeomissionnotguaranteeddetected. No source/posthocscorer yet: noaccuracyclaim from execution. Reviewer gatebefore36slotreplay. No paid/livepermission implied. Fullnewcode below, oldsourcebytesomitted. Five direct tests pass.

## scripts/manufacturing_answer_adapter.py
```
"""Offline answers from saved query bindings and declared policy; no source/gold IO."""
import json
from decimal import Decimal
from urllib.parse import unquote
from rdflib import Literal, URIRef
from rdflib.util import from_n3

BASE='urn:shacl-study:backend:'


def decode(value):
    term=from_n3(value)
    if isinstance(term,URIRef):
        return unquote(str(term)[len(BASE):]) if str(term).startswith(BASE) else str(term)
    if isinstance(term,Literal):
        return json.loads(str(term))
    raise ValueError('unsupported_binding_term')


def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        raise ValueError('non_numeric_operand')
    result=Decimal(str(value))
    if not result.is_finite():raise ValueError('non_finite_operand')
    return result


def adapt(saved,policy):
    """All facts must come from saved bindings; policy contains no expected answers."""
    result={'question_id':saved['case_id'],'backend':saved['backend'],
            'original_status':saved['status'],'status':'partial','claims':{},
            'policy_id':policy['id'],'limits':['declared policy, not external truth',
            'same adapter across backends is not independent answer generation']}
    def claim(key,value=None,state='supported',basis=None):
        result['claims'][key]={'state':state,'value':value,'basis':basis or []}
    if saved['status']!='completed':
        result['status']='unsupported' if saved['status']=='unsupported' else 'upstream_failure'
        return result
    try:
        raw=saved['bindings'];unique={json.dumps(r,sort_keys=True):r for r in raw}
        rows=[{k:decode(v) for k,v in r.items()} for r in unique.values()]
        result['duplicate_bindings_removed']=len(raw)-len(rows)
        q=saved['case_id']
        # Absence of a result does not establish where evidence was lost.
        if q=='Q8':
            for key in ('nominal_current','actual_current','applicable_document_version'):
                claim(key,state='not_established_by_this_projection')
            result['empty_binding_origin']='undetermined'
            return result
        if q=='Q7':
            result['status']='unsupported';return result
        if q=='Q4':
            universe=set(policy['Q4']['universe'])
            selected=[r for r in rows if r.get('?s') in universe]
            result['irrelevant_rows_ignored']=len(rows)-len(selected)
            present={r['?s'] for r in selected}
            if len(selected)!=len(present):
                result['status']='ambiguous_bindings';return result
            hits=[r['?s'] for r in selected if '?x' in r and '?label' in r
                  and number(policy['Q4']['lower'])<=number(r['?x'])<=number(policy['Q4']['upper'])
                  and r['?label']==policy['Q4']['label']]
            claim('observed_matching_rows',sorted(hits),basis=['?s','?x','?label'])
            complete=present==universe and all({'?x','?label'}<=r.keys() for r in selected)
            claim('count',len(hits) if complete else None,
                  'supported_under_declared_universe' if complete else 'incomplete_candidates',
                  ['declared two-row universe','?s'])
            result['status']='completed' if complete else 'partial';return result
        if len(rows)!=1:
            result['status']='missing_bindings' if not rows else 'ambiguous_bindings';return result
        row=rows[0]
        def field(key,var):
            if var in row:claim(key,row[var],basis=[var]);return True
            claim(key,state='missing_binding',basis=[var]);return False
        if q=='Q1':field('x_init', '?v')
        elif q=='Q2':
            field('defect_label','?v');field('dictionary_reference','?d')
        elif q=='Q3':
            a=field('first_nominal_current','?v1');b=field('second_nominal_current','?v2')
            if a and b:claim('second_minus_first',str(number(row['?v2'])-number(row['?v1'])),basis=['?v2','?v1'])
            else:claim('second_minus_first',state='missing_operand')
        elif q=='Q5':
            field('position','?mm');field('sample_index','?sample');field('nominal_current','?nominal')
            roles=policy.get('Q5',{}).get('roles')
            claim('field_roles',roles,'declared_policy' if roles else 'policy_missing')
            claim('actual_measured_current',state='not_established_by_this_projection')
        elif q=='Q6':
            field('linked_dictionary','?d')
            rule=policy.get('Q6',{})
            if rule.get('same_workbook_only') is not True:
                claim('applicable_sources',state='policy_missing')
            elif {'?same','?other','?d'}<=row.keys():
                if not isinstance(row['?d'],str) or row['?d'].split(':',1)[0]!=row['?same']:
                    claim('applicable_sources',state='source_identity_conflict')
                    return result
                claim('linked_dictionary_applicable',row['?same']==rule['target_workbook'],basis=['?same','declared same-workbook policy'])
                claim('other_workbook_applicable',row['?other']==rule['target_workbook'],basis=['?other','declared same-workbook policy'])
                claim('same_label_suffices',False,'declared_policy')
            else:claim('applicable_sources',state='missing_binding')
        elif q=='Q9':
            draft=policy['Q9']['authored_draft']
            if '?label' in row:
                claim('draft_label_agrees',draft['defect_label']==row['?label'],basis=['?label','authored draft'])
                field('supported_label','?label')
            else:claim('draft_label_agrees',state='missing_binding')
            field('nominal_current','?nominal')
            claim('draft_measured_current',state='not_established_by_this_projection',basis=['nominal is not measured under declared policy'])
        else:result['status']='unsupported';return result
        states=[c['state'] for c in result['claims'].values()]
        result['status']='completed' if all(s in ('supported','declared_policy') for s in states) else 'partial'
        return result
    except (ValueError,TypeError,KeyError) as exc:
        result['status']='input_error';result['error']=type(exc).__name__+':'+str(exc)
        return result

```

## scripts/replay_manufacturing_answers.py
```
"""Bounded offline replay; freezes inputs before writing answers, keeps all slots."""
import argparse
import hashlib
import json
from pathlib import Path
from scripts.manufacturing_answer_adapter import adapt

BACKENDS={'sqlite_python','rdflib_offline','neo4j_cypher','neptune_sparql'}
QUESTIONS={f'Q{i}' for i in range(1,10)}


def run(source,policy_path,out,expected_source_hash,expected_policy_hash):
    out.mkdir(parents=True,exist_ok=False)
    manifest={'expected_source_hash':expected_source_hash,'expected_policy_hash':expected_policy_hash,
              'planned':36,'mode':'offline replay of historical backend bindings; no DB calls'}
    try:
        raw=source.read_bytes();policy_bytes=policy_path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_source_hash:raise ValueError('source_hash_mismatch')
        if hashlib.sha256(policy_bytes).hexdigest()!=expected_policy_hash:raise ValueError('policy_hash_mismatch')
        rows=[json.loads(x) for x in raw.decode().splitlines()]
        rows=[r for r in rows if r['case_id'] in QUESTIONS]
        keys=[(r['backend'],r['case_id']) for r in rows]
        if len(keys)!=36 or set(keys)!={(b,q) for b in BACKENDS for q in QUESTIONS}:raise ValueError('slot_universe_mismatch')
        policy=json.loads(policy_bytes)
    except Exception as exc:
        manifest.update(status='input_failure',completed=0,not_executed=36,error=type(exc).__name__+':'+str(exc))
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        return manifest
    (out/'inputs.json').write_text(json.dumps({'rows':rows,'policy':policy},indent=2)+'\n')
    outputs=[]
    for saved in rows:
        try:result=adapt(saved,policy)
        except Exception as exc:result={'backend':saved['backend'],'question_id':saved['case_id'],'status':'adapter_failure','error':type(exc).__name__+':'+str(exc)}
        outputs.append(result)
        with (out/'results.jsonl').open('a') as stream:stream.write(json.dumps(result,ensure_ascii=False)+'\n')
    counts={s:sum(r['status']==s for r in outputs) for s in sorted({r['status'] for r in outputs})}
    manifest.update(status='replay_complete',emitted=len(outputs),not_executed=36-len(outputs),counts=counts,
                    limits='Same hand-authored adapter/policy; not new LLM answers or live backend comparison. No external-truth assessment.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('source','policy','out'):parser.add_argument(name,type=Path)
    parser.add_argument('source_hash');parser.add_argument('policy_hash')
    args=parser.parse_args();print(json.dumps(run(args.source,args.policy,args.out,args.source_hash,args.policy_hash)))

```

## tests/test_manufacturing_answer_adapter.py
```
import json
from copy import deepcopy
from pathlib import Path
from rdflib import Literal,URIRef
from scripts.manufacturing_answer_adapter import adapt

POLICY=json.loads(Path('research/manufacturing-answer-trace-1/design-001/policy.json').read_text())

def val(x):return Literal(json.dumps(x)).n3()
def row(q,bindings):return {'case_id':q,'backend':'fixture','status':'completed','bindings':bindings}

def test_partial_operands_do_not_repair_or_discard_supported_part():
    r=adapt(row('Q3',[{'?v1':val(450)}]),POLICY)
    assert r['claims']['first_nominal_current']['value']==450
    assert r['claims']['second_minus_first']['state']=='missing_operand'
    assert r['status']=='partial'

def test_declared_universe_and_duplicates():
    a={'?s':val('PP6:12'),'?x':val(239),'?label':val('Porosity')}
    b={'?s':val('PP6:2'),'?x':val(106),'?label':val('Metallic inclusion')}
    missing=adapt(row('Q4',[a]),POLICY)
    assert missing['claims']['observed_matching_rows']['value']==['PP6:12']
    assert missing['claims']['count']['state']=='incomplete_candidates'
    full=adapt(row('Q4',[a,a,b,{'?s':val('PP7:9'),'?x':val(150),'?label':val('Porosity')}]),POLICY)
    assert full['claims']['count']['value']==1
    assert full['duplicate_bindings_removed']==1 and full['irrelevant_rows_ignored']==1

def test_absence_failure_unsupported_separate():
    empty=adapt(row('Q8',[]),POLICY)
    assert empty['empty_binding_origin']=='undetermined'
    assert all(x['value'] is None for x in empty['claims'].values())
    failed=row('Q8',[]);failed['status']='timeout'
    assert adapt(failed,POLICY)['status']=='upstream_failure'
    q7=row('Q7',[]);q7['status']='unsupported'
    assert adapt(q7,POLICY)['status']=='unsupported'

def test_missing_role_policy_keeps_values():
    p=deepcopy(POLICY);p.pop('Q5')
    result=adapt(row('Q5',[{'?mm':val(106),'?sample':val(66244),'?nominal':val(450)}]),p)
    assert result['claims']['position']['value']==106
    assert result['claims']['field_roles']['state']=='policy_missing'
    assert result['claims']['actual_measured_current']['value'] is None


def test_wrong_workbook_same_label_does_not_establish_applicability():
    r=adapt(row('Q6',[{'?d':val('PP7:defect_code:4'),'?same':val('PP7'),'?other':val('PP7')}]),POLICY)
    assert r['claims']['linked_dictionary_applicable']['value'] is False
    inconsistent=adapt(row('Q6',[{'?d':val('PP7:defect_code:4'),'?same':val('PP6'),'?other':val('PP7')}]),POLICY)
    assert inconsistent['claims']['applicable_sources']['state']=='source_identity_conflict'

```

## research/manufacturing-answer-trace-1/design-001/policy.json
```
{
  "id": "manufacturing-answer-policy-v1",
  "origin": "authored experiment interpretation of supplied questions and headers; not automatically learned ontology",
  "Q4": {
    "universe": [
      "PP6:2",
      "PP6:12"
    ],
    "lower": 100,
    "upper": 250,
    "label": "Porosity",
    "origin": "explicit question bounded universe and predicate"
  },
  "Q5": {
    "roles": {
      "?mm": {
        "unit": "mm",
        "role": "position"
      },
      "?sample": {
        "unit": "sample index",
        "role": "index"
      },
      "?nominal": {
        "unit": "A",
        "role": "nominal setting"
      }
    },
    "origin": "original headers plus declared codebook-versus-measured interpretation; does not prove physical truth"
  },
  "Q6": {
    "same_workbook_only": true,
    "target_workbook": "PP6",
    "origin": "explicit question policy, not universal manufacturing rule"
  },
  "Q9": {
    "authored_draft": {
      "defect_label": "Porosity",
      "actual_measured_current": 450
    },
    "origin": "question-supplied artificial draft, not actual model mistake"
  }
}

```
