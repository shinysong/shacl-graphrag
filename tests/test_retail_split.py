from scripts.freeze_retail_split import key, select_invoices

def test_no_development_or_blank():
    assert set(select_invoices({'a','b',None},{'a'},10))=={'b'}

def test_order_independent_unique():
    assert select_invoices(['a','b','a','c'],[],2)==select_invoices(['c','b','a'],[],2)
    assert len(select_invoices(['a','b','a','c'],[],2))==2

def test_keys_keep_distinctions():
    assert key(None) is None and key('  ') is None
    assert key('C123')!='123' and key('c123')!='C123'
    assert key(' 123')!='123' and key(123)=='123'

def test_zero_selection():
    assert select_invoices(['a'],[],0)==[]
