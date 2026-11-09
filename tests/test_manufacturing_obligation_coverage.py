import json
from rdflib import Literal
from scripts.manufacturing_obligation_coverage import coverage, inspect_path


def test_missing_null_empty_and_zero_are_distinct():
    row={'null':None,'empty':'','zero':0,'list':[4]}
    assert [inspect_path(row,[k]) for k in ('absent','null','empty','zero')]==['missing','explicit_null','empty','present']
    assert inspect_path(row,['list',1])=='missing'


def test_empty_binding_and_one_missing_row_do_not_pass():
    c={'obligations':[{'id':'value','label':'requested scalar','paths':[['?v']]}]}
    s={'backend':'test','case_id':'Q1','status':'completed','bindings':[]}
    assert coverage(s,c)['available_count']==0
    s['bindings']=[{'?v':Literal(json.dumps(0)).n3()},{}]
    assert coverage(s,c)['available_count']==0
    s['bindings']=s['bindings'][:1]
    assert coverage(s,c)['available_count']==1


def test_same_valued_wrong_source_is_not_detected_by_presence():
    c={'obligations':[{'id':'location','label':'source','paths':[['?payload','archive_path']]}]}
    s={'backend':'test','case_id':'Q6','status':'completed',
       'bindings':[{'?payload':Literal(json.dumps({'archive_path':'wrong.xlsx'})).n3()}]}
    assert coverage(s,c)['available_count']==1  # Deliberate known limit, not a semantic check.
