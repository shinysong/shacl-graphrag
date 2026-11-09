"""Bounded alternative: selected-source RDF paths checked by SHACL-SPARQL.

No computed observed/expected comparison records. Both engines share source
projection, declared policy and missing-path gates. Python walks RDF paths;
pySHACL evaluates SPARQL path constraints. This is not independent NLP, external
truth, a database benchmark or a replacement for the historical compiler.
"""
import hashlib
from rdflib import Graph, Namespace, URIRef, Literal, RDF
from pyshacl import validate
from scripts.post_answer_review import token
from scripts.postreview_lookup import POLICIES, validate_sources, cell_value

EX=Namespace('urn:postreview-native:')
SH=Namespace('http://www.w3.org/ns/shacl#')
CLAIM=EX.claim
# Stable shape vocabulary, no claim/source values compiled into shapes.
RULES={
 'declared_reference':(('anchor','declaredDictionary'),('dictionary',)),
 'dictionary_key':(('anchor','anchorKey'),('dictionary','code')),
 'lookup_value':(('claimedValue',),('dictionary','lookupValue')),
 'workbook_hash':(('anchor','workbookHash'),('dictionary','workbookHash')),
 'workbook_path':(('anchor','workbookPath'),('dictionary','workbookPath')),
 'declared_header':(('dictionary','header'),('policy','expectedHeader')),
}

def source_uri(sid):
    return URIRef('urn:postreview-source:'+hashlib.sha256(sid.encode()).hexdigest())

def project(claim,sources):
    if not isinstance(claim,dict) or set(claim)!={'claim_id','lookup_kind','anchor_id','dictionary_id','value','unit'}:raise ValueError('claim shape')
    for key in ('claim_id','lookup_kind','anchor_id','dictionary_id'):
        if not isinstance(claim[key],str) or not claim[key].strip():raise ValueError('claim binding')
    if claim['lookup_kind'] not in POLICIES:raise ValueError('lookup kind')
    token(claim['value'])
    if claim['unit'] is not None and not isinstance(claim['unit'],str):raise ValueError('unit')
    by=validate_sources(sources);p=POLICIES[claim['lookup_kind']];g=Graph();g.bind('ex',EX)
    g.add((CLAIM,RDF.type,EX.LookupClaim));g.add((CLAIM,EX.claimId,Literal(claim['claim_id'])))
    g.add((CLAIM,EX.anchor,source_uri(claim['anchor_id'])));g.add((CLAIM,EX.dictionary,source_uri(claim['dictionary_id'])))
    policy=EX['policy/'+claim['lookup_kind']];g.add((CLAIM,EX.policy,policy));g.add((policy,EX.expectedHeader,Literal(token(p['header']))))
    if claim['value'] is not None:g.add((CLAIM,EX.claimedValue,Literal(token(claim['value']))))
    for sid,s in by.items():
        node=source_uri(sid)
        for pred,value in [('sourceId',sid),('sheet',s['sheet']),('workbookHash',s['sha256']),('workbookPath',s['archive_path'])]:g.add((node,EX[pred],Literal(token(value))))
        ref=s.get('dictionary_refs',{}).get(p['selector'])
        if ref is not None:g.add((node,EX.declaredDictionary,source_uri(ref)))
        address=s.get('field_cells',{}).get(p['selector'])
        row=s.get('excel_row')
        for pred,addr in [('anchorKey',address),('code','A'+str(row) if row else None),('lookupValue',p['column']+str(row) if row else None)]:
            if addr is None:continue
            value=cell_value(s,addr)
            if value is not None:g.add((node,EX[pred],Literal(token(value))))
            g.add((node,EX[pred+'Cell'],Literal(addr)))
        header=next((c for r in s['header_rows'] for c in r['cells'] if c['cell']==p['header_cell']),None)
        if header and header.get('formula') is None and header['value'] is not None:g.add((node,EX.header,Literal(token(header['value']))))
        g.add((node,EX.headerCell,Literal(p['header_cell'])))
    return g

def values(g,path):
    nodes={CLAIM}
    for step in path:nodes={obj for node in nodes for obj in g.objects(node,EX[step])}
    if len(nodes)>1:raise ValueError('ambiguous path multiplicity')
    return nodes

def shapes():
    g=Graph();g.bind('sh',SH);g.bind('ex',EX)
    for name,(left,right) in RULES.items():
        shape=EX['shape/'+name];constraint=EX['constraint/'+name]
        g.add((shape,RDF.type,SH.NodeShape));g.add((shape,SH.targetClass,EX.LookupClaim));g.add((shape,SH.sparql,constraint));g.add((constraint,RDF.type,SH.SPARQLConstraint));g.add((constraint,SH.message,Literal(name)))
        a='/'.join(EX[x].n3() for x in left);b='/'.join(EX[x].n3() for x in right)
        g.add((constraint,SH.select,Literal(f'SELECT $this ?left ?right WHERE {{ $this {a} ?left . $this {b} ?right . FILTER (!sameTerm(?left, ?right)) }}')))
    return g

def review_native_paths(claim,sources,engine='python'):
    if engine not in ('python','pyshacl'):raise ValueError('engine')
    data=project(claim,sources);shape=shapes();observed={k:(values(data,l),values(data,r)) for k,(l,r) in RULES.items()}
    # pySHACL may enrich the supplied shape graph with base ontology triples.
    # Freeze input serializations before validation and retain effective shapes
    # separately, so provenance never confuses pre- and post-execution graphs.
    data_turtle=data.serialize(format='turtle');shapes_turtle=shape.serialize(format='turtle')
    raw=None;raw_conforms=None;failed=set();effective_shapes=None
    if engine=='pyshacl':
        raw_conforms,report,_=validate(data,shacl_graph=shape,inference='none',advanced=False,abort_on_first=False)
        if not isinstance(report,Graph):raise RuntimeError('SHACL validation failure')
        for result in report.subjects(RDF.type,SH.ValidationResult):
            source=report.value(result,SH.sourceShape)
            names=[name for name in RULES if source==EX['shape/'+name]]
            if len(names)!=1:raise RuntimeError('unrecognized SHACL result')
            failed.add(names[0])
        if bool(raw_conforms)!=(not failed):raise RuntimeError('SHACL result consistency')
        raw=report.serialize(format='turtle')
        effective_shapes=shape.serialize(format='turtle')
    results=[]
    for name,(left,right) in observed.items():
        # Availability only: Python does not decide equality for the SHACL arm.
        if not left or not right:status='unknown'
        elif engine=='python':status='pass' if left==right else 'flag'
        else:status='flag' if name in failed else 'pass'
        results.append({'check_id':name,'status':status,'left_path':list(RULES[name][0]),'right_path':list(RULES[name][1]),'left_nodes':[str(x) for x in left],'right_nodes':[str(x) for x in right]})
    return {'engine':engine,'claim_id':claim['claim_id'],'results':results,'answer_modified':False,
            'data_turtle':data_turtle,'shapes_turtle':shapes_turtle,'effective_shapes_turtle':effective_shapes,'raw_report_turtle':raw,'raw_shacl_conforms':None if raw_conforms is None else bool(raw_conforms),
            'scope':'six declared relation checks; unit agreement excluded; no whole-answer verdict',
            'encoding':'exact typed JSON tokens in RDF string literals; no numeric/unit normalization',
            'shared_components':['source projection','two manual policies','missing-path applicability'],
            'limits':['raw SHACL conformance can coexist with unknown application checks','wrong anchor/policy and consistently wrong source may pass','no ontology generation, external truth or LLM efficacy']}
