import json
import pytest
from rdflib import URIRef,Literal,XSD
from rdflib.compare import isomorphic
from scripts.retail_rdf_mapping import map_rows,NS

def test_missing_invalid_valid_and_raw():
    g,rows=map_rows([{'row_id':'r1','data':{'Quantity':'bad','UnitPrice':'0','CustomerID':None}}])
    f=rows[0]['fields'];node=URIRef(rows[0]['uri'])
    assert f['Quantity']['state']=='invalid' and f['UnitPrice']['value']=='0'
    assert f['CustomerID']['state']=='missing' and f['CustomerID']['source_key_present']
    assert not f['InvoiceNo']['source_key_present']
    assert not list(g.objects(node,NS.Quantity))
    assert (node,NS.UnitPrice,Literal('0.0',datatype=XSD.decimal)) in g
    for name,v in f.items():
        assert str(g.value(node,NS[name+'State']))==v['state']
        assert json.loads(str(g.value(node,NS[name+'RawJSON'])))==v['raw']

@pytest.mark.parametrize('value',[True,'NaN','Infinity','£1','1,000'])
def test_non_numeric_preserved(value):
    _,r=map_rows([{'row_id':'r','data':{'Quantity':value}}]);assert r[0]['fields']['Quantity']['state']=='invalid'

def test_row_uri_injective_and_roundtrip():
    g,r=map_rows([{'row_id':'a/b','data':{'Quantity':-2}},{'row_id':'a%2Fb','data':{}}])
    assert r[0]['uri']!=r[1]['uri']
    parsed=type(g)().parse(data=g.serialize(format='turtle'),format='turtle')
    assert isomorphic(g,parsed)

def test_no_policy_verdicts():
    _,r=map_rows([{'row_id':'r','data':{'InvoiceNo':'C1','Quantity':2,'UnitPrice':-1}}])
    assert r[0]['fields']['Quantity']['state']=='valid' and r[0]['fields']['UnitPrice']['state']=='valid'
    assert 'status' not in r[0]

@pytest.mark.parametrize('rows',[[{'row_id':'r','data':{'extra':1}}],[{'row_id':'r','data':{}},{'row_id':'r','data':{}}],[{'row_id':'r','data':{'Quantity':float('inf')}}]])
def test_invalid_source(rows):
    with pytest.raises(ValueError):map_rows(rows)

@pytest.mark.parametrize('value',['1.25','-0','-0.00','1e3','2.50e-3',0.125])
def test_numeric_roundtrip_and_metadata_parity(value):
    from decimal import Decimal
    g, rows = map_rows([{'row_id':'numeric','data':{'Quantity':value,'UnitPrice':value}}])
    parsed = type(g)().parse(data=g.serialize(format='turtle'),format='turtle')
    assert isomorphic(g, parsed)
    node = URIRef(rows[0]['uri'])
    for field in ('Quantity','UnitPrice'):
        info = rows[0]['fields'][field]
        literal = parsed.value(node,NS[field])
        assert literal.datatype == XSD.decimal
        assert Decimal(str(literal)) == Decimal(info['value']) == Decimal(str(value))
        assert json.loads(str(parsed.value(node,NS[field+'RawJSON']))) == value


def test_all_fields_metadata_and_typed_values_after_roundtrip():
    data={'InvoiceNo':' C1','StockCode':123,'Description':'부품\n"A"',
          'Quantity':'bad','UnitPrice':None,'CustomerID':' ', 'Country':False}
    g,rows=map_rows([{'row_id':'row / 한글','data':data}])
    parsed=type(g)().parse(data=g.serialize(format='turtle'),format='turtle')
    node=URIRef(rows[0]['uri'])
    expected={'InvoiceNo':('valid',' C1'),'StockCode':('valid','123'),
              'Description':('valid','부품\n"A"'),'Quantity':('invalid',None),
              'UnitPrice':('missing',None),'InvoiceDate':('missing',None),
              'CustomerID':('missing',None),'Country':('valid','False')}
    assert isomorphic(g,parsed)
    for field, (state, value) in expected.items():
        info=rows[0]['fields'][field]
        assert info['source_key_present'] == (field in data)
        assert parsed.value(node,NS[field+'KeyPresent']).toPython() == (field in data)
        assert info['raw'] == json.loads(str(parsed.value(node,NS[field+'RawJSON']))) == data.get(field)
        assert info['state'] == str(parsed.value(node,NS[field+'State'])) == state
        assert info['value'] == value
        literals=list(parsed.objects(node,NS[field]))
        if value is None:
            assert literals == []
        else:
            assert len(literals)==1 and literals[0].datatype==XSD.string
            assert str(literals[0])==value
