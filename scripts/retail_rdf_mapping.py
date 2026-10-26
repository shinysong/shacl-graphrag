"""Policy-neutral field mapping for development, with JSON parity metadata."""
import json
import math
from urllib.parse import quote
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD
from scripts.evaluate_retail_policies import blank, number

NS=Namespace('urn:retail:field:')
FIELDS=('InvoiceNo','StockCode','Description','Quantity','InvoiceDate','UnitPrice','CustomerID','Country')
NUMERIC={'Quantity','UnitPrice'}

def map_rows(rows):
    graph=Graph();normalized=[];seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'row_id','data'}:
            raise ValueError('Expected row_id/data only')
        row_id=row['row_id'];data=row['data']
        if not isinstance(row_id,str) or not row_id.strip() or row_id in seen:
            raise ValueError('Invalid/duplicate row ID')
        if not isinstance(data,dict) or set(data)-set(FIELDS):
            raise ValueError('Unknown source columns')
        if any(not isinstance(v,(str,int,float,bool,type(None))) or isinstance(v,float) and not math.isfinite(v) for v in data.values()):
            raise ValueError('JSON finite scalar cells required; nonfinite strings remain parse-invalid')
        seen.add(row_id);node=URIRef('urn:retail:row:'+quote(row_id,safe=''))
        graph.add((node,RDF.type,NS.SourceRow));graph.add((node,NS.rowId,Literal(row_id)))
        fields={}
        for field in FIELDS:
            value=data.get(field);present=field in data
            state='missing' if blank(value) else 'valid'
            typed=None
            if state=='valid':
                if field in NUMERIC:
                    typed=number(value)
                    if typed is None:state='invalid'
                else:typed=str(value)
            info={'source_key_present':present,'raw':value,'state':state,'value':None if typed is None else str(typed),'datatype':'decimal' if field in NUMERIC else 'string'}
            fields[field]=info
            graph.add((node,NS[field+'State'],Literal(state)))
            graph.add((node,NS[field+'KeyPresent'],Literal(present)))
            graph.add((node,NS[field+'RawJSON'],Literal(json.dumps(value,ensure_ascii=False,allow_nan=False))))
            if typed is not None:
                lexical = format(typed, 'f') if field in NUMERIC else typed
                if field in NUMERIC and '.' not in lexical:
                    lexical += '.0'
                graph.add((node,NS[field],Literal(lexical,datatype=XSD.decimal if field in NUMERIC else XSD.string)))
        normalized.append({'row_id':row_id,'uri':str(node),'fields':fields})
    return graph,normalized
