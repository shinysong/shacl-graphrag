import pytest
from scripts.retail_row_shacl import evaluate_rows
from scripts.evaluate_retail_policies import evaluate_python

@pytest.mark.parametrize('invoice,qty,price,customer,expected',[
 ('A',2,1,'x',('pass','pass','pass')),
 ('c1',-2,0,None,('violation','pass','pass')),
 ('C1',2,-1,' ',('violation','violation','violation')),
 (' C1',-2,'bad',False,('pass','violation','unknown')),
 (None,2,1,'x',('pass','unknown','pass')),
 ('A','NaN',None,'x',('pass','unknown','unknown')),
 ('A',0,0,'x',('pass','violation','pass')),
 ('A','2.5e-3','-0','x',('pass','pass','pass')),
])
def test_declared_policy_cases(invoice,qty,price,customer,expected):
    row={'InvoiceNo':invoice,'Quantity':qty,'UnitPrice':price,'CustomerID':customer}
    out=evaluate_rows([{'row_id':'a/b','data':row}])
    by_policy={d['policy']:d for d in out['decisions']}
    for policy,want in zip(('customer_analysis','quantity_sign','nonnegative_price'),expected):
        d=by_policy[policy]
        assert d['status']==want==evaluate_python(row,d['policy'])
        assert out['traces'][d['policy']]['executed']==(want!='unknown')

def test_multiple_targets_and_unknown_not_pass():
    rows=[{'row_id':'a','data':{'UnitPrice':1}}, {'row_id':'b','data':{'UnitPrice':-1}}, {'row_id':'c','data':{}}]
    out=evaluate_rows(rows)
    assert {(d['row_id'],d['status']) for d in out['decisions'] if d['policy']=='nonnegative_price'}=={('a','pass'),('b','violation'),('c','unknown')}
    assert out['traces']['nonnegative_price']['target_count']==2
    assert out['traces']['nonnegative_price']['report_turtle']
    assert not out['traces']['quantity_sign']['executed']

def test_validator_failure_preserved(monkeypatch):
    import scripts.retail_row_shacl as module
    def fail(*args,**kwargs):raise RuntimeError('injected failure')
    monkeypatch.setattr(module,'validate',fail)
    out=evaluate_rows([{'row_id':'a','data':{'UnitPrice':1}}])
    assert {d['policy']:d['status'] for d in out['decisions']}=={'customer_analysis':'error','quantity_sign':'unknown','nonnegative_price':'error'}
    assert out['traces']['nonnegative_price']['error']=='injected failure'
