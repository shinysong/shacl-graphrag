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
