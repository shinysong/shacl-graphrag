"""Independent Python and SHACL evaluations of the SAME selected evidence."""
import json
from rdflib import Graph, Namespace, Literal, RDF, XSD
from pyshacl import validate
from .graph import DATA
EX = Namespace('urn:factory-review:')
SH = Namespace('http://www.w3.org/ns/shacl#')
POLICY = json.loads((DATA/'policy.json').read_text())

def candidates(evidence):
    records = {}
    for item in evidence:
        if item.get('tool')=='qualification_records':
            mid=item['arguments']['machine_id']
            records.setdefault(mid,[]).extend(r['qualification'] for r in item['rows'] if r.get('qualification'))
        elif item.get('tool')=='inspect_entity':
            for row in item['rows']:
                if row.get('relation')!='HAS_QUALIFICATION':
                    continue
                entity,neighbor=row.get('entity') or {},row.get('neighbor') or {}
                if entity.get('kind')=='Machine' and neighbor.get('kind')=='Qualification' and row.get('from_id')==entity.get('id'):
                    records.setdefault(entity['id'],[]).append(neighbor)
                elif entity.get('kind')=='Qualification' and neighbor.get('kind')=='Machine' and row.get('from_id')==neighbor.get('id'):
                    records.setdefault(neighbor['id'],[]).append(entity)
    result={}
    for item in evidence:
        if item.get('tool')!='replacement_candidates':
            continue
        for row in item['rows']:
            m,o,c=row['machine'],row['order'],row['required_capability']
            key=o['id']+'|'+m['id']+'|'+c
            result[key]={'key':key,'machine_id':m['id'],'order_id':o['id'],
                         'status':m.get('status'),'capability':c,'required':c,'product':o['product'],
                         'at':item['as_of'],'records':records.get(m['id'],[])}
    return list(result.values())

def python_flags(rows):
    out=[]
    for r in rows:
        codes=[]
        if r['status']!='available': codes.append('status-not-available')
        if r['capability']!=r['required']: codes.append('capability-missing')
        if not r['records']: codes.append('qualification-not-retrieved')
        elif not any(x.get('product')==r['product'] and x.get('capability')==r['required']
                     and x.get('valid_from','9999')<=r['at']<=x.get('valid_until','0000') for x in r['records']):
            codes.append('qualification-not-applicable')
        out.extend({'candidate':r['key'],'code':code} for code in codes)
    return sorted(out,key=lambda x:(x['candidate'],x['code']))

def rdf_input(rows):
    g=Graph()
    for i,r in enumerate(rows):
        n=EX['candidate/'+str(i)];g.add((n,RDF.type,EX.Candidate));g.add((n,EX.key,Literal(r['key'])))
        for field in ['status','capability','required','product','at']:
            if r.get(field) is not None: g.add((n,EX[field],Literal(r[field])))
        for j,rec in enumerate(r['records']):
            q=EX[f'candidate/{i}/record/{j}'];g.add((n,EX.record,q))
            for field in ['product','capability','valid_from','valid_until']:
                if field in rec:g.add((q,EX[field],Literal(rec[field])))
    return g

# Strings use fixed ISO dates; no physical constraints or learned policy.
SHAPES = '''@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <urn:factory-review:> .
ex:Status a sh:NodeShape; sh:targetClass ex:Candidate; sh:sparql [
 sh:message "status-not-available";
 sh:select """SELECT $this WHERE { FILTER NOT EXISTS { $this <urn:factory-review:status> "available" } }""" ].
ex:Capability a sh:NodeShape; sh:targetClass ex:Candidate; sh:sparql [
 sh:message "capability-missing";
 sh:select """SELECT $this WHERE { $this <urn:factory-review:required> ?r . FILTER NOT EXISTS { $this <urn:factory-review:capability> ?r } }""" ].
ex:Missing a sh:NodeShape; sh:targetClass ex:Candidate; sh:sparql [
 sh:message "qualification-not-retrieved";
 sh:select """SELECT $this WHERE { FILTER NOT EXISTS { $this <urn:factory-review:record> ?r } }""" ].
ex:Applicable a sh:NodeShape; sh:targetClass ex:Candidate; sh:sparql [
 sh:message "qualification-not-applicable";
 sh:select """SELECT DISTINCT $this WHERE {
 $this <urn:factory-review:record> ?any ; <urn:factory-review:product> ?p ; <urn:factory-review:required> ?c ; <urn:factory-review:at> ?at .
 FILTER NOT EXISTS { $this <urn:factory-review:record> ?r .
 ?r <urn:factory-review:product> ?p ; <urn:factory-review:capability> ?c ; <urn:factory-review:valid_from> ?f ; <urn:factory-review:valid_until> ?u . FILTER (?f <= ?at && ?at <= ?u) }
 }""" ].
'''

def shacl_flags(rows):
    data=rdf_input(rows)
    conforms,report,_=validate(data,shacl_graph=Graph().parse(data=SHAPES,format='turtle'),advanced=True,inference='none')
    if not isinstance(report,Graph):raise RuntimeError('SHACL execution failed')
    out=[]
    for node in report.subjects(RDF.type,SH.ValidationResult):
        focus=report.value(node,SH.focusNode)
        out.append({'candidate':str(data.value(focus,EX.key)),'code':str(report.value(node,SH.resultMessage))})
    return sorted(out,key=lambda x:(x['candidate'],x['code']))

def review(evidence,mode):
    rows=candidates(evidence)
    if mode not in ('python','shacl','self'):raise ValueError('Unknown review mode')
    flags=[] if mode=='self' else (python_flags(rows) if mode=='python' else shacl_flags(rows))
    return {'engine':mode,'policy_revision':POLICY['id'],'candidate_count':len(rows),
            'flags':flags,'checked_candidates':[r['key'] for r in rows] if mode!='self' else [],
            'scope':'Advisory on retrieved replacement candidates only. No additional lookup. No candidates means NOT ASSESSED, not conforming. No flags do not certify truth, complete retrieval, or physical suitability.',
            'assessment':'not_assessed' if mode=='self' or not rows else 'selected_candidates_checked'}
