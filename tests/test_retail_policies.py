"""Hand-authored development cases, not independent business accuracy gold."""
import pytest
from scripts.evaluate_retail_policies import evaluate_python, evaluate_shacl, POLICIES

CASES = [
 ({'InvoiceNo':'123456','CustomerID':'17850','Quantity':2,'UnitPrice':2.5}, ('pass','pass','pass')),
 ({'InvoiceNo':'C123456','CustomerID':'17850','Quantity':-2,'UnitPrice':2.5}, ('pass','pass','pass')),
 ({'InvoiceNo':'123456','CustomerID':None,'Quantity':2,'UnitPrice':2.5}, ('violation','pass','pass')),
 ({'InvoiceNo':'123456','CustomerID':'  ','Quantity':2,'UnitPrice':2.5}, ('violation','pass','pass')),
 ({'InvoiceNo':'C123456','CustomerID':'17850','Quantity':2,'UnitPrice':2.5}, ('pass','violation','pass')),
 ({'InvoiceNo':'123456','CustomerID':'17850','Quantity':-2,'UnitPrice':2.5}, ('pass','violation','pass')),
 ({'InvoiceNo':'123456','CustomerID':'17850','Quantity':0,'UnitPrice':0}, ('pass','violation','pass')),
 ({'InvoiceNo':None,'CustomerID':'17850','Quantity':-2,'UnitPrice':-1}, ('pass','unknown','violation')),
 ({'InvoiceNo':'123456','CustomerID':'17850','Quantity':'bad','UnitPrice':None}, ('pass','unknown','unknown')),
 ({'InvoiceNo':'123456','CustomerID':'17850','Quantity':'NaN','UnitPrice':'Infinity'}, ('pass','unknown','unknown')),
 ({'InvoiceNo':'c123456','CustomerID':'17850','Quantity':'-0.5','UnitPrice':'0.01'}, ('pass','pass','pass')),
 ({'InvoiceNo':'123456','CustomerID':'17850','Quantity':True,'UnitPrice':False}, ('pass','unknown','unknown')),
]

@pytest.mark.parametrize('row,expected', CASES)
@pytest.mark.parametrize('engine', [evaluate_python,evaluate_shacl])
def test_declared_policy(row,expected,engine):
    assert tuple(engine(row,p) for p in POLICIES)==expected
