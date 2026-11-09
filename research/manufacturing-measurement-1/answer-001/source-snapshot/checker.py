"""Advisory on two declared evidence-boundary constraints, never answer repair."""
import json,math
from rdflib import Graph,Namespace,Literal,RDF,XSD
from pyshacl import validate
E=Namespace('urn:measurement-review:');SH=Namespace('http://www.w3.org/ns/shacl#')
SHAPES='''@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix e: <urn:measurement-review:> .
e:IntervalShape a sh:NodeShape; sh:targetNode e:Draft;
 sh:sparql [a sh:SPARQLConstraint; sh:message "unsupported_interval_claim";
 sh:select "SELECT $this ?value WHERE { $this <urn:measurement-review:verifiedMean> ?value . <urn:measurement-review:Context> <urn:measurement-review:alignmentKnown> false . }"] .
e:VersionShape a sh:NodeShape; sh:targetNode e:Draft;
 sh:sparql [a sh:SPARQLConstraint; sh:message "unsupported_version_claim";
 sh:select "SELECT $this ?value WHERE { $this <urn:measurement-review:documentVersion> ?value . <urn:measurement-review:Context> <urn:measurement-review:versionKnown> false . }"] .
'''
KEYS={'nominal_idc_a','recorded_current_channel','verified_defect_interval_mean_a','applicable_document_version','review_pointers','citations','basis'}
def structural(x):
 number=lambda v:v is None or (type(v) in (float,int) and math.isfinite(v))
 return (isinstance(x,dict) and set(x)==KEYS and number(x['nominal_idc_a']) and type(x['recorded_current_channel']) is bool and number(x['verified_defect_interval_mean_a']) and (x['applicable_document_version'] is None or isinstance(x['applicable_document_version'],str) and bool(x['applicable_document_version'].strip())) and isinstance(x['review_pointers'],list) and all(isinstance(v,str) for v in x['review_pointers']) and isinstance(x['citations'],list) and all(isinstance(v,dict) and set(v)=={'claim','source_id'} and all(isinstance(z,str) for z in v.values()) for v in x['citations']) and isinstance(x['basis'],str) and bool(x['basis'].strip()))
def report(answer,context):
 if not structural(answer):return {'status':'unknown','reason':'draft_response_schema','flags':[],'advisory_only':True},None,None
 if set(context)!= {'alignment_known','version_known'} or any(type(v)is not bool for v in context.values()):raise ValueError('context_contract')
 py=[]
 if answer['verified_defect_interval_mean_a'] is not None and not context['alignment_known']:py.append('unsupported_interval_claim')
 if answer['applicable_document_version'] is not None and not context['version_known']:py.append('unsupported_version_claim')
 g=Graph();g.add((E.Context,E.alignmentKnown,Literal(context['alignment_known'],datatype=XSD.boolean)));g.add((E.Context,E.versionKnown,Literal(context['version_known'],datatype=XSD.boolean)))
 if answer['verified_defect_interval_mean_a'] is not None:g.add((E.Draft,E.verifiedMean,Literal(answer['verified_defect_interval_mean_a'])))
 if answer['applicable_document_version'] is not None:g.add((E.Draft,E.documentVersion,Literal(answer['applicable_document_version'])))
 conforms,rg,_=validate(g,shacl_graph=Graph().parse(data=SHAPES,format='turtle'),advanced=False,inference='none')
 flags=sorted({str(msg) for result in rg.subjects(RDF.type,SH.ValidationResult) for msg in rg.objects(result,SH.resultMessage)})
 if flags!=sorted(py) or bool(conforms)!=(not bool(flags)):raise ValueError('checker_policy_parity')
 return {'status':'completed','flags':flags,'advisory_only':True,'checked_scope':['verified interval claim requires known alignment','document version claim requires known applicability'],'not_checked':['nominal value correctness','citations','free-text entailment','calibration','external truth'],'meaning_of_no_flags':'No violation of these two constraints; not an answer correctness certificate'},g,rg
