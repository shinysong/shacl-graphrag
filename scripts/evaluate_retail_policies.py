"""Development-only matched policy checks. Authored policies are not retailer truth."""
from decimal import Decimal, InvalidOperation
from rdflib import Graph, Namespace, BNode, Literal, RDF, SH, XSD
from pyshacl import validate

P = Namespace('urn:retail-policy:')
POLICIES = ('customer_analysis', 'quantity_sign', 'nonnegative_price')

def blank(v):
    return v is None or str(v).strip() == ''

def number(v):
    if isinstance(v, bool) or blank(v):
        return None
    try:
        x = Decimal(str(v))
        return x if x.is_finite() else None
    except InvalidOperation:
        return None

def contract(row, policy):
    if policy == 'customer_analysis':
        return Decimal(0 if blank(row.get('CustomerID')) else 1), 'minInclusive', Decimal(1)
    if policy == 'nonnegative_price':
        return number(row.get('UnitPrice')), 'minInclusive', Decimal(0)
    if policy == 'quantity_sign':
        if blank(row.get('InvoiceNo')):
            return None, 'minExclusive', Decimal(0)
        bound = 'maxExclusive' if str(row['InvoiceNo']).lower().startswith('c') else 'minExclusive'
        return number(row.get('Quantity')), bound, Decimal(0)
    raise ValueError('Unknown policy')

def evaluate_python(row, policy):
    value, op, bound = contract(row, policy)
    if value is None:
        return 'unknown'
    ok = {'minInclusive': value >= bound, 'minExclusive': value > bound, 'maxExclusive': value < bound}[op]
    return 'pass' if ok else 'violation'

def evaluate_shacl(row, policy):
    value, op, bound = contract(row, policy)
    if value is None:
        return 'unknown'
    data, shapes = Graph(), Graph()
    data.add((P.row, P.value, Literal(value, datatype=XSD.decimal)))
    prop = BNode()
    shapes.add((P.shape, RDF.type, SH.NodeShape))
    shapes.add((P.shape, SH.targetNode, P.row))
    shapes.add((P.shape, SH.property, prop))
    shapes.add((prop, SH.path, P.value))
    shapes.add((prop, SH[op], Literal(bound, datatype=XSD.decimal)))
    conforms, _, _ = validate(data, shacl_graph=shapes, inference='none')
    return 'pass' if conforms else 'violation'
