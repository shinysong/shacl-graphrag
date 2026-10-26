import ast
from pathlib import Path
import pytest
from scripts import retail_reference as ref

@pytest.mark.parametrize('row,expected',[
 ({},('violation','unknown','unknown')),
 ({'CustomerID':'0','InvoiceNo':'C1','Quantity':-1,'UnitPrice':0},('pass','pass','pass')),
 ({'CustomerID':0,'InvoiceNo':'c1','Quantity':'-0.1','UnitPrice':'0.00'},('pass','pass','pass')),
 ({'CustomerID':'  ','InvoiceNo':'1','Quantity':0,'UnitPrice':-1},('violation','violation','violation')),
 ({'CustomerID':None,'InvoiceNo':'1','Quantity':-2,'UnitPrice':'NaN'},('violation','violation','unknown')),
 ({'CustomerID':'x','InvoiceNo':'C1','Quantity':2,'UnitPrice':'Infinity'},('pass','violation','unknown')),
 ({'CustomerID':'x','InvoiceNo':' C1','Quantity':-1,'UnitPrice':'1,000'},('pass','violation','unknown')),
 ({'CustomerID':True,'InvoiceNo':'1','Quantity':True,'UnitPrice':False},('pass','unknown','unknown')),
 ({'CustomerID':'x','InvoiceNo':'  ','Quantity':2,'UnitPrice':'£1'},('pass','unknown','unknown')),
 ({'CustomerID':'x','InvoiceNo':'1','Quantity':'1e2','UnitPrice':'-0'},('pass','pass','pass')),
])
def test_handwritten_policy_boundaries(row,expected):
    before=dict(row);records=ref.reference_for('r1',row,'a'*64)
    assert tuple(r['status'] for r in records)==expected and row==before
    assert all(r['source_sha256']=='a'*64 and r['policy_contract_sha256']==ref.CONTRACT_SHA256 for r in records)
    assert [r['source_columns'] for r in records]==[['CustomerID'],['InvoiceNo','Quantity'],['UnitPrice']]

def test_import_boundary():
    tree=ast.parse(Path(ref.__file__).read_text())
    names=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]+[a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
    assert set(names)<={'hashlib','json','re','decimal','pathlib'}

def test_changed_contract_rejected(tmp_path,monkeypatch):
    p=tmp_path/'contract.json';p.write_text('{}');monkeypatch.setattr(ref,'CONTRACT',p)
    with pytest.raises(ValueError,match='contract changed'):ref.reference_for('r1',{},'a'*64)

@pytest.mark.parametrize('row_id,row,digest',[('',{},'a'*64),('r',{},'bad'),('r',{'Quantity':[]},'a'*64)])
def test_invalid_source_contract(row_id,row,digest):
    with pytest.raises(ValueError):ref.reference_for(row_id,row,digest)
