"""Advisory validation of a saved draft against declared selected-source policy.

No source fetches, evaluator references, model calls, or repair operations.
"""
from rdflib import Graph, Namespace, Literal, RDF, BNode
from rdflib.namespace import SH, XSD
from pyshacl import validate

EX = Namespace('https://example.org/shacl-study/source-semantics/')


def valid_response(value):
    return (isinstance(value,dict) and set(value)=={'classification','basis'}
            and isinstance(value['classification'],str)
            and value['classification'] in {'required','optional','excluded','explicit_empty','reported_nonempty','unknown','established','not_established'}
            and isinstance(value['basis'],str) and bool(value['basis'].strip()))


def make_report(evidence, task, metadata, draft):
    if not valid_response(draft):
        return {'status':'input_rejected', 'conforms':None, 'python_conforms':None,
                'codes':['response_structure'], 'action':'Review output format using supplied source and policy; no replacement answer supplied.'}
    if task not in ('consumer_scope','dependency_knowledge'):
        return {'status':'unknown', 'conforms':None, 'python_conforms':None, 'codes':['unsupported_task']}
    component=evidence['component'];ref=component['bom-ref']
    if task=='dependency_knowledge' and evidence['source_field_presence']['dependencies'] and 'dependencies' not in evidence:
        return {'status':'unknown','conforms':None,'python_conforms':None,'codes':['projection_missing_dependency_field']}
    entries=[e for e in evidence.get('dependencies',[]) if e['ref']==ref]
    if len(entries)>1:
        return {'status':'unknown','conforms':None,'python_conforms':None,'codes':['duplicate_source_entry']}
    if task=='consumer_scope':
        expected=component.get('scope',metadata['scope']['default'])
    else:
        expected=('unknown' if not entries else 'reported_nonempty' if entries[0].get('dependsOn',[]) else 'explicit_empty')
    python_conforms = draft['classification']==expected
    data,shapes=Graph(),Graph();node=EX.review;shape=EX.PolicyShape
    data.add((node,RDF.type,EX.Review))
    for name,value in [('task',task),('classification',draft['classification']),('scopeDefault',metadata['scope']['default'])]:
        data.add((node,EX[name],Literal(value,datatype=XSD.string)))
    if 'scope' in component:data.add((node,EX.declaredScope,Literal(component['scope'],datatype=XSD.string)))
    data.add((node,EX.hasDependencyEntry,Literal(bool(entries))))
    data.add((node,EX.dependencyCount,Literal(len(entries[0].get('dependsOn',[])) if entries else 0)))
    shapes.add((shape,RDF.type,SH.NodeShape));shapes.add((shape,SH.targetClass,EX.Review))
    queries=[('consumer_scope_policy','''SELECT $this WHERE {
      $this ex:task ?task; ex:classification ?actual; ex:scopeDefault ?fallback.
      FILTER(STR(?task) = "consumer_scope")
      OPTIONAL { $this ex:declaredScope ?declared }
      BIND(COALESCE(?declared,?fallback) AS ?expected)
      FILTER(STR(?actual) != STR(?expected))
    }'''),('dependency_entry_policy','''SELECT $this WHERE {
      $this ex:task ?task; ex:classification ?actual;
        ex:hasDependencyEntry ?present; ex:dependencyCount ?count.
      FILTER(STR(?task) = "dependency_knowledge")
      BIND(IF(!?present,"unknown",IF(?count = 0,"explicit_empty","reported_nonempty")) AS ?expected)
      FILTER(STR(?actual) != STR(?expected))
    }''')]
    for code,query in queries:
        constraint=BNode();shapes.add((shape,SH.sparql,constraint))
        shapes.add((constraint,SH.select,Literal('PREFIX ex: <'+str(EX)+'>\n'+query)))
        shapes.add((constraint,SH.message,Literal(code)))
    conforms,report,_=validate(data,shacl_graph=shapes,inference='none',advanced=False)
    codes=sorted({str(m) for m in report.objects(None,SH.resultMessage)})
    return {'status':'completed','conforms':bool(conforms),'python_conforms':python_conforms,'codes':codes,
            'policy_source_sha256':metadata['source_sha256'],
            'component_pointer':evidence['source_component_pointer'],
            'limits':'Conformance to supplied task and declared source-field policy, not correct question interpretation, explanation truth or real deployment truth.',
            'action':'Consider these findings; you may revise or retain the draft. No compulsory veto.',
            'data_turtle':data.serialize(format='turtle'),'shapes_turtle':shapes.serialize(format='turtle')}
