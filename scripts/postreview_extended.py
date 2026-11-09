"""Typed advisory checks for arithmetic, bounded sets, roles and synthetic history.

Inputs are explicit shared contracts and selected facts, never evaluator keys.
Projection/admission/completeness declarations are shared. Python evaluates the
policy directly; SHACL-SPARQL evaluates source/claim RDF. No NLP or truth claim.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
from rdflib import Graph, Namespace, Literal, RDF, XSD
from pyshacl import validate

EX = Namespace('urn:postreview-extended:')
SH = Namespace('http://www.w3.org/ns/shacl#')
ROOT = EX.request

def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('nonempty string required')
    return value

def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('finite JSON number required')
    try:
        n = Decimal(str(value))
    except InvalidOperation as e:
        raise ValueError('number') from e
    if not n.is_finite():
        raise ValueError('finite number required')
    return n

def ids(value):
    if not isinstance(value, list):
        raise ValueError('ID list required')
    for x in value:
        text(x)
    if len(set(value)) != len(value):
        raise ValueError('duplicate IDs')
    return value

def day(value):
    text(value)
    try:
        d = date.fromisoformat(value)
    except ValueError as e:
        raise ValueError('ISO date required') from e
    if d.isoformat() != value:
        raise ValueError('canonical ISO date required')
    return d

def graph(packet):
    """Strict core admission; provenance is an audit annotation, not verified here."""
    kind = packet['kind']; c = packet['claim']; e = packet['evidence']
    if not isinstance(c, dict) or not isinstance(e, dict):
        raise ValueError('claim/evidence objects required')
    g = Graph(); g.bind('ex', EX); g.add((ROOT, RDF.type, EX.Request))
    def put(pred, value, node=ROOT, datatype=None):
        g.add((node, EX[pred], Literal(value, datatype=datatype)))
    available = {}
    if kind == 'difference':
        number(c['value']); text(c['unit']); put('claimValue', str(number(c['value'])), datatype=XSD.decimal); put('claimUnit', c['unit'])
        for side in ('left', 'right'):
            row = e.get(side)
            if row is not None:
                number(row['value']); text(row['unit']); text(row['source_id'])
                put(side, str(number(row['value'])), datatype=XSD.decimal)
        ready = all(e.get(x) is not None for x in ('left', 'right'))
        same_units = ready and e['left']['unit'] == e['right']['unit']
        if same_units: put('unit', e['left']['unit'])
        available = {'signed_difference': same_units, 'difference_unit': same_units}
    elif kind == 'selection':
        ids(e['universe_ids']); ids(c['selected_ids']); number(e['lower']); number(e['upper']); text(e['target_label'])
        if number(e['lower']) > number(e['upper']): raise ValueError('reversed bounds')
        if type(c['count']) is not int or c['count'] < 0: raise ValueError('nonnegative integer count')
        if not isinstance(e['rows'], list): raise ValueError('rows list')
        rowids = []
        for i, row in enumerate(e['rows']):
            sid = text(row['id']); rowids.append(sid); number(row['position']); text(row['label'])
            node = EX['row/'+str(i)]; g.add((ROOT, EX.row, node)); put('id', sid, node); put('position', str(number(row['position'])), node, XSD.decimal); put('label', row['label'], node)
        ids(rowids)
        if not set(rowids).issubset(e['universe_ids']): raise ValueError('row outside declared universe')
        for sid in c['selected_ids']: put('selected', sid)
        put('lower', str(number(e['lower'])), datatype=XSD.decimal); put('upper', str(number(e['upper'])), datatype=XSD.decimal); put('targetLabel', e['target_label']); put('claimCount', c['count'])
        complete = set(rowids) == set(e['universe_ids'])
        available = {k: complete for k in ('missing_member', 'extra_member', 'matching_count')}
        available['list_count_consistency'] = True
    elif kind == 'role':
        text(c['role']); put('claimRole', c['role'])
        role = e.get('declared_role')
        if role is not None: text(role); put('sourceRole', role)
        available = {'declared_role': role is not None}
    elif kind == 'temporal':
        day(e['event_date']); text(e['scope']); put('event', e['event_date'], datatype=XSD.date); put('scope', e['scope'])
        if type(e['history_complete']) is not bool: raise ValueError('explicit history completeness required')
        if c['state'] not in ('selected', 'ambiguous', 'unknown'): raise ValueError('temporal state')
        put('state', c['state']); ids(c['latest_ids'])
        if c['state'] == 'selected': text(c['selected_id']); put('chosen', c['selected_id'])
        elif c['selected_id'] is not None: raise ValueError('nonselected state requires null selection')
        for sid in c['latest_ids']: put('latest', sid)
        if not isinstance(e['documents'], list): raise ValueError('document list')
        docids = []
        for i, doc in enumerate(e['documents']):
            text(doc['id']); text(doc['scope']); docids.append(doc['id'])
            start, end = day(doc['valid_from']), day(doc['valid_to']); day(doc['release_date'])
            if start >= end: raise ValueError('invalid validity interval')
            node = EX['doc/'+str(i)]; g.add((ROOT, EX.document, node)); put('id', doc['id'], node); put('scope', doc['scope'], node)
            for pred, key in [('start','valid_from'),('end','valid_to'),('release','release_date')]: put(pred, doc[key], node, XSD.date)
        ids(docids)
        available = {k:e['history_complete'] for k in ('temporal_state','selected_binding','missing_latest','extra_latest')}
    else:
        raise ValueError('unsupported kind')
    return g, available

PREFIX = 'PREFIX ex: <urn:postreview-extended:>\n'
MATCH = '$this ex:row ?r; ex:lower ?lo; ex:upper ?hi; ex:targetLabel ?target . ?r ex:id ?id; ex:position ?x; ex:label ?label . FILTER(?x >= ?lo && ?x <= ?hi && ?label = ?target)'

def valid(doc, suffix):
    return f'$this ex:document ?{doc}; ex:scope ?scope{suffix}; ex:event ?event{suffix} . ?{doc} ex:scope ?scope{suffix}; ex:start ?start{suffix}; ex:end ?end{suffix} . FILTER(?start{suffix} <= ?event{suffix} && ?event{suffix} < ?end{suffix})'

def latest(doc='doc', suffix=''):
    return f'$this ex:document ?{doc}; ex:scope ?scope{suffix} . ?{doc} ex:scope ?scope{suffix}; ex:release ?release{suffix}; ex:id ?id . FILTER NOT EXISTS {{ $this ex:document ?new{suffix} . ?new{suffix} ex:scope ?scope{suffix}; ex:release ?later{suffix} . FILTER(?later{suffix} > ?release{suffix}) }}'

def queries(kind):
    if kind == 'difference':
        return {'signed_difference':'$this ex:left ?l; ex:right ?r; ex:claimValue ?v . FILTER(?v != (?r - ?l))', 'difference_unit':'$this ex:unit ?u; ex:claimUnit ?v . FILTER(?u != ?v)'}
    if kind == 'role':
        return {'declared_role':'$this ex:sourceRole ?r; ex:claimRole ?c . FILTER(?r != ?c)'}
    if kind == 'selection':
        return {'missing_member':MATCH+' FILTER NOT EXISTS { $this ex:selected ?id }',
                'extra_member':'$this ex:selected ?id . FILTER NOT EXISTS { '+MATCH+' }',
                'matching_count':'{ SELECT $this (COUNT(?id) AS ?n) WHERE { $this a ex:Request . OPTIONAL { '+MATCH+' } } GROUP BY $this } $this ex:claimCount ?c . FILTER(?n != ?c)',
                'list_count_consistency':'{ SELECT $this (COUNT(?id) AS ?n) WHERE { $this a ex:Request . OPTIONAL { $this ex:selected ?id } } GROUP BY $this } $this ex:claimCount ?c . FILTER(?n != ?c)'}
    if kind == 'temporal':
        one=valid('doc','1'); two=valid('a','2')+' '+valid('b','3')+' FILTER(?a != ?b)'
        return {'temporal_state':f'$this ex:state ?state . FILTER((NOT EXISTS {{ {one} }} && ?state != "unknown") || (EXISTS {{ {one} }} && NOT EXISTS {{ {two} }} && ?state != "selected") || (EXISTS {{ {two} }} && ?state != "ambiguous"))',
                'selected_binding':'$this ex:state "selected"; ex:chosen ?id . FILTER NOT EXISTS { '+one+' ?doc ex:id ?id }',
                'missing_latest':latest()+' FILTER NOT EXISTS { $this ex:latest ?id }',
                'extra_latest':'$this ex:latest ?id . FILTER NOT EXISTS { '+latest()+' }'}
    raise ValueError('kind')

def python_flags(packet):
    c,e,k = packet['claim'],packet['evidence'],packet['kind']
    if k == 'difference':
        ready=all(e.get(x) is not None for x in ('left','right'))
        return {'signed_difference': ready and number(c['value']) != number(e['right']['value'])-number(e['left']['value']), 'difference_unit':ready and c['unit'] != e['left']['unit']}
    if k == 'role': return {'declared_role':c['role'] != e.get('declared_role')}
    if k == 'selection':
        target={r['id'] for r in e['rows'] if number(e['lower'])<=number(r['position'])<=number(e['upper']) and r['label']==e['target_label']};chosen=set(c['selected_ids'])
        return {'missing_member':bool(target-chosen),'extra_member':bool(chosen-target),'matching_count':len(target)!=c['count'],'list_count_consistency':len(chosen)!=c['count']}
    valid_docs=[d for d in e['documents'] if d['scope']==e['scope'] and day(d['valid_from'])<=day(e['event_date'])<day(d['valid_to'])]
    expected='selected' if len(valid_docs)==1 else 'ambiguous' if valid_docs else 'unknown'
    same_scope=[d for d in e['documents'] if d['scope']==e['scope']]
    max_release=max((day(d['release_date']) for d in same_scope),default=None)
    latest_ids={d['id'] for d in same_scope if day(d['release_date'])==max_release};chosen_latest=set(c['latest_ids'])
    return {'temporal_state':c['state']!=expected,'selected_binding':c['state']=='selected' and c['selected_id'] not in {d['id'] for d in valid_docs},'missing_latest':bool(latest_ids-chosen_latest),'extra_latest':bool(chosen_latest-latest_ids)}

def review_extended(packet, engine='python'):
    if engine not in ('python','pyshacl'): raise ValueError('engine')
    data, available = graph(packet); qs=queries(packet['kind']); shapes=Graph();shapes.bind('sh',SH);shapes.bind('ex',EX)
    for name, body in qs.items():
        node=EX['shape/'+name];constraint=EX['constraint/'+name]
        shapes.add((node,RDF.type,SH.NodeShape));shapes.add((node,SH.targetClass,EX.Request));shapes.add((node,SH.sparql,constraint));shapes.add((constraint,SH.message,Literal(name)));shapes.add((constraint,SH.select,Literal(PREFIX+'SELECT $this WHERE { '+body+' }')))
    frozen_data=data.serialize(format='turtle');frozen_shapes=shapes.serialize(format='turtle');raw=None;raw_conforms=None
    if engine=='python': flags=python_flags(packet)
    else:
        raw_conforms, report, _=validate(data,shacl_graph=shapes,inference='none',advanced=False,abort_on_first=False)
        if not isinstance(report,Graph): raise RuntimeError('validation failure')
        flags={name:False for name in qs}
        for result in report.subjects(RDF.type,SH.ValidationResult):
            shape=report.value(result,SH.sourceShape);names=[n for n in qs if shape==EX['shape/'+n]]
            if len(names)!=1: raise RuntimeError('unrecognized validation result')
            flags[names[0]]=True
        if bool(raw_conforms)!=(not any(flags.values())): raise RuntimeError('report mismatch')
        raw=report.serialize(format='turtle')
    return {'kind':packet['kind'],'engine':engine,'results':[{'check_id':k,'status':'unknown' if not available[k] else 'flag' if flags[k] else 'pass'} for k in qs],
            'data_turtle':frozen_data,'shapes_turtle':frozen_shapes,'effective_shapes_turtle':shapes.serialize(format='turtle') if engine=='pyshacl' else None,'raw_report_turtle':raw,'raw_conforms':raw_conforms,
            'answer_modified':False,'scope':'declared contract and selected facts only; not whole-answer correctness',
            'limits':['shared typed projection/admission and declared evidence completeness','source role catalog is supplied policy, not inferred semantic truth','natural-language projection and question applicability unverified','raw SHACL conformance can differ from application unknown status','no new lookup, answer repair, provider or evaluation keys']}
