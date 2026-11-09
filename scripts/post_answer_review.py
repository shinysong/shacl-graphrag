"""Advisory review of explicitly bound atomic claims against selected evidence.

No retrieval, LLM, evaluation targets, automatic projection or answer rewriting.
Python and pySHACL receive identical typed packets. Exact JSON scalar comparison
is a declared policy, not semantic equivalence or external truth assessment.
"""
from __future__ import annotations
import json
from typing import Any

CHECKS = ('source_binding', 'field_binding', 'value_agreement', 'unit_agreement')

def token(value: Any) -> str:
    if not (value is None or type(value) in (str, int, float, bool)):
        raise ValueError('non-scalar value')
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)

def validate_packet(packet):
    if set(packet) != {'claims', 'sources'}: raise ValueError('packet keys')
    if not isinstance(packet['claims'], list) or not isinstance(packet['sources'], list): raise ValueError('lists')
    for rows, key in [(packet['claims'], 'claim_id'), (packet['sources'], 'source_id')]:
        ids = [r.get(key) for r in rows]
        if any(not isinstance(x, str) or not x.strip() for x in ids) or len(ids) != len(set(ids)):
            raise ValueError('invalid or duplicate IDs')
    for source in packet['sources']:
        if set(source) != {'source_id', 'fields'} or not isinstance(source['fields'], dict): raise ValueError('source shape')
        for field, cell in source['fields'].items():
            if not isinstance(field, str) or not field.strip(): raise ValueError('field ID')
            if set(cell) != {'value', 'unit', 'locator'}: raise ValueError('cell keys')
            token(cell['value'])
            if cell['unit'] is not None and not isinstance(cell['unit'], str): raise ValueError('unit')
            if not isinstance(cell['locator'], str) or not cell['locator'].strip(): raise ValueError('locator')
    for claim in packet['claims']:
        if set(claim) != {'claim_id','kind','source_id','field','value','unit'}: raise ValueError('claim shape')
        if claim['kind'] not in ('recorded','derived'): raise ValueError('kind')
        for key in ('source_id','field','unit'):
            if claim[key] is not None and (not isinstance(claim[key],str) or not claim[key].strip()): raise ValueError(key)
        token(claim['value'])

def applicability(packet):
    """Shared, disclosed review scope. Unknown is not a SHACL truth verdict."""
    validate_packet(packet)
    sources={s['source_id']:s for s in packet['sources']}
    result=[]
    for claim in packet['claims']:
        source=sources.get(claim['source_id'])
        cell=source['fields'].get(claim['field']) if source else None
        for check in CHECKS:
            item={'claim_id':claim['claim_id'],'check_id':check,'source_id':claim['source_id'],
                  'field':claim['field'],'locator':cell['locator'] if cell else None}
            if claim['kind']=='derived': status,reason='not_applicable','derived_claim_not_supported'
            elif check=='source_binding':
                status,reason=('check','selected_source') if source is not None else ('unknown','source_not_selected_or_not_bound')
            elif cell is None: status,reason='unknown','field_not_available_in_selected_source'
            elif check=='field_binding': status,reason='check','selected_field'
            elif check=='value_agreement' and (cell['value'] is None or claim['value'] is None): status,reason='unknown','value_unspecified'
            elif check=='unit_agreement' and cell['unit'] is None: status,reason='unknown','source_unit_unspecified'
            elif check=='unit_agreement' and claim['unit'] is None: status,reason='unknown','claim_unit_unspecified'
            else: status,reason='check','exact_scalar_policy'
            item.update(status=status,reason=reason)
            result.append((item,claim,cell))
    return result

def review_python(packet):
    output=[]
    for item,claim,cell in applicability(packet):
        if item['status']=='check':
            check=item['check_id']
            equal=True if check in ('source_binding','field_binding') else token(claim['value' if check=='value_agreement' else 'unit'])==token(cell['value' if check=='value_agreement' else 'unit'])
            item['status']='pass' if equal else 'flag'
        output.append(item)
    return {'engine':'python','results':output,'answer_modified':False}

def review_shacl(packet):
    from rdflib import Graph, Namespace, BNode, Literal
    from rdflib.namespace import RDF, SH
    from rdflib.collection import Collection
    from pyshacl import validate
    ns=Namespace('urn:post-answer-review:')
    data,shapes=Graph(),Graph()
    items=applicability(packet)
    targets={}
    for i,(item,claim,cell) in enumerate(items):
        if item['status']!='check': continue
        target=ns[f'check/{i}']; targets[target]=i
        shape=ns[f'shape/{i}']; prop=BNode()
        shapes.add((shape,RDF.type,SH.NodeShape)); shapes.add((shape,SH.targetNode,target))
        shapes.add((shape,SH.property,prop)); shapes.add((prop,SH.path,ns.observed))
        shapes.add((prop,SH.minCount,Literal(1))); shapes.add((prop,SH.maxCount,Literal(1)))
        check=item['check_id']
        if check=='source_binding': observed=claim['source_id']; expected=claim['source_id']
        elif check=='field_binding': observed=claim['field']; expected=claim['field']
        else:
            field='value' if check=='value_agreement' else 'unit'
            observed=claim[field]; expected=cell[field]
        data.add((target,ns.observed,Literal(token(observed))))
        if check in ('source_binding','field_binding'):
            allowed = [s['source_id'] for s in packet['sources']] if check=='source_binding' else list(next(s for s in packet['sources'] if s['source_id']==claim['source_id'])['fields'])
            head=BNode(); Collection(shapes,head,[Literal(token(v)) for v in allowed]); shapes.add((prop,SH['in'],head))
        else:
            shapes.add((prop,SH.hasValue,Literal(token(expected))))
    conforms,report,report_text=validate(data,shacl_graph=shapes,inference='none',advanced=False,allow_infos=False,allow_warnings=False)
    failed=set()
    for r in report.subjects(RDF.type,SH.ValidationResult):
        target=report.value(r,SH.focusNode)
        if target not in targets: raise ValueError('unmapped SHACL result')
        failed.add(targets[target])
    if conforms != (not failed): raise ValueError('SHACL result inconsistency')
    output=[]
    for i,(item,_,_) in enumerate(items):
        if item['status']=='check': item['status']='flag' if i in failed else 'pass'
        output.append(item)
    return {'engine':'pyshacl','results':output,'answer_modified':False,
            'raw_conforms':bool(conforms),'executed_checks':len(targets),
            'data_turtle':data.serialize(format='turtle'),
            'shapes_turtle':shapes.serialize(format='turtle'),
            'report_turtle':report.serialize(format='turtle'),'report_text':report_text}

def review(packet,engine='python'):
    if engine not in ('python','pyshacl'): raise ValueError('engine')
    return review_python(packet) if engine=='python' else review_shacl(packet)
