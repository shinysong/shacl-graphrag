"""Selected annotation dictionary-binding subset; no corpus/question/gold reader."""
import json
from urllib.parse import quote
from rdflib import Graph,Namespace,RDF,Literal,URIRef
from rdflib.namespace import SH
from pyshacl import validate
from scripts.graphrag_check import _parse,canonical_bytes
EX=Namespace('urn:binding:')
RELATIONS={'defect':'defect_code','welding_setting':'welding_settings_code'}


def comparisons(envelope):
    nodes,_=_parse(envelope);bindings=[]
    for nid,n in sorted(nodes.items()):
        for field,tid in sorted(n.get('dictionary_refs',{}).items()):
            target=nodes.get(tid)
            pairs=[('selected_target',None,None)] if target is None else [
                *[(k,n.get(k),target.get(k)) for k in ('coupon','archive_path','sha256')],
                ('code',n.get('values',{}).get(field),target.get('code')),
                ('sheet',RELATIONS.get(field),target.get('sheet')),
                ('annotation_namespace',n.get('coupon'),nid.split(':')[0]),
                ('target_namespace',target.get('coupon'),tid.split(':')[0])]
            bindings.append({'id':nid+':dictionary_ref:'+field,'evidence_ids':['node:'+nid]+(['node:'+tid] if target else []),'pairs':pairs})
    return bindings


def python_binding(bindings):
    results=[]
    for b in bindings:
        missing=[];conflicts=[]
        for name,left,right in b['pairs']:
            if left is None or right is None:missing.append(name)
            elif canonical_bytes(left)!=canonical_bytes(right):conflicts.append(name)
        results.append({'check_id':b['id'],'status':'violation' if conflicts else 'unknown' if missing else 'pass','missing':missing,'conflicts':conflicts,'evidence_ids':b['evidence_ids']})
    return results


def shacl_binding(envelope,shapes):
    before=canonical_bytes(envelope);bindings=comparisons(envelope);g=Graph();lookup={}
    for bi,b in enumerate(bindings):
        for pi,(name,left,right) in enumerate(b['pairs']):
            uri=URIRef(f'urn:binding:pair:{bi}:{pi}');lookup[uri]=(bi,name,left is not None and right is not None)
            g.add((uri,RDF.type,EX.Comparison));g.add((uri,EX.checkId,Literal(b['id'])));g.add((uri,EX.field,Literal(name)))
            for eid in b['evidence_ids']:g.add((uri,EX.evidence,URIRef('urn:chunk:'+quote(eid,safe=''))))
            for pred,val in ((EX.left,left),(EX.right,right)):
                if val is not None:g.add((uri,pred,Literal(canonical_bytes(val).decode())))
    conforms,report,text=validate(g,shacl_graph=shapes,inference='none',advanced=False,do_owl_imports=False)
    missing=[set() for b in bindings];conflicts=[set() for b in bindings]
    for res in report.subjects(RDF.type,SH.ValidationResult):
        bi,name,both=lookup[report.value(res,SH.focusNode)];component=report.value(res,SH.sourceConstraintComponent)
        if component==SH.EqualsConstraintComponent:
            (conflicts if both else missing)[bi].add(name)
        elif component==SH.MinCountConstraintComponent:missing[bi].add(name)
        else:raise ValueError('unsupported SHACL result component')
    results=[]
    for i,b in enumerate(bindings):
        order=[x[0] for x in b['pairs']]
        results.append({'check_id':b['id'],'status':'violation' if conflicts[i] else 'unknown' if missing[i] else 'pass','missing':[n for n in order if n in missing[i]],'conflicts':[n for n in order if n in conflicts[i]],'evidence_ids':b['evidence_ids']})
    assert before==canonical_bytes(envelope)
    return {'raw_conforms':bool(conforms),'results':results,'python_results':python_binding(bindings),'parity':results==python_binding(bindings),'applicable_bindings':len(bindings),'coverage':'selected declared dictionary references only; no question applicability, edge provenance or process-rule checks','no_bindings_status':'unknown' if not bindings else None},g,report,text
