"""Authored row-graph policy baseline; not LLM-generated shape evaluation."""
from rdflib import Graph, Namespace, SH, URIRef
from pyshacl import validate
from scripts.retail_rdf_mapping import map_rows

P = Namespace('urn:retail:shape:')
SHAPES = {
 'customer_analysis': '''@prefix sh: <http://www.w3.org/ns/shacl#> .
 @prefix f: <urn:retail:field:> . @prefix p: <urn:retail:shape:> .
 p:customer_analysis a sh:NodeShape; sh:property [sh:path f:CustomerID; sh:minCount 1].''',
 'nonnegative_price': '''@prefix sh: <http://www.w3.org/ns/shacl#> .
 @prefix f: <urn:retail:field:> . @prefix p: <urn:retail:shape:> .
 p:nonnegative_price a sh:NodeShape; sh:property [sh:path f:UnitPrice; sh:minCount 1; sh:minInclusive 0].''',
 'quantity_sign': '''@prefix sh: <http://www.w3.org/ns/shacl#> .
 @prefix p: <urn:retail:shape:> .
 p:quantity_sign a sh:NodeShape; sh:sparql [sh:select """
 SELECT $this WHERE {
  $this <urn:retail:field:InvoiceNo> ?invoice; <urn:retail:field:Quantity> ?quantity .
  FILTER ((REGEX(STR(?invoice), "^c", "i") && ?quantity >= 0) ||
          (!REGEX(STR(?invoice), "^c", "i") && ?quantity <= 0))
 }"""].'''
}
REQUIRED = {'customer_analysis': (), 'nonnegative_price': ('UnitPrice',),
            'quantity_sign': ('InvoiceNo','Quantity')}

def evaluate_rows(rows):
    data, normalized = map_rows(rows)
    decisions=[]; traces={}
    for policy, ttl in SHAPES.items():
        shapes=Graph().parse(data=ttl,format='turtle'); eligible=[]
        for row in normalized:
            if any(row['fields'][f]['state']!='valid' for f in REQUIRED[policy]):
                decisions.append({'row_id':row['row_id'],'policy':policy,'status':'unknown'})
            else:
                eligible.append(row)
                shapes.add((P[policy],SH.targetNode,URIRef(row['uri'])))
        trace={'target_count':len(eligible),'shape_turtle':shapes.serialize(format='turtle'),
               'executed':False,'conforms':None,'report_turtle':None,'report_text':None}
        if eligible:
            try:
                conforms,report,text=validate(data,shacl_graph=shapes,inference='none')
                if not isinstance(report,Graph):
                    raise RuntimeError(str(report))
                failed={str(node) for node in report.objects(None,SH.focusNode)}
                trace.update(executed=True,conforms=bool(conforms),report_turtle=report.serialize(format='turtle'),report_text=text)
                for row in eligible:
                    decisions.append({'row_id':row['row_id'],'policy':policy,'status':'violation' if row['uri'] in failed else 'pass'})
            except Exception as exc:
                trace.update(executed=True,error_type=type(exc).__name__,error=str(exc))
                decisions.extend({'row_id':r['row_id'],'policy':policy,'status':'error'} for r in eligible)
        traces[policy]=trace
    return {'decisions':decisions,'traces':traces,'data_turtle':data.serialize(format='turtle')}
