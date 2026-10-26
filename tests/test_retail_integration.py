"""Development integration only; injected outputs are not LLM observations."""
import json
from pathlib import Path
import pytest
from scripts.retail_io import build_packet, expected_keys, parse_output
from scripts.evaluate_retail_policies import evaluate_python, evaluate_shacl
from scripts.score_retail_decisions import score

# Explicit authored expectations; never passed to runtime functions.
CASES = [
 ('a',{'InvoiceNo':'123','CustomerID':'1','Quantity':2,'UnitPrice':1},('pass','pass','pass')),
 ('b',{'InvoiceNo':'C123','CustomerID':None,'Quantity':-2,'UnitPrice':0},('violation','pass','pass')),
 ('c',{'InvoiceNo':'123','CustomerID':'1','Quantity':-2,'UnitPrice':-1},('pass','violation','violation')),
 ('d',{'InvoiceNo':None,'CustomerID':'1','Quantity':None,'UnitPrice':None},('pass','unknown','unknown')),
]

def setup():
    protocol=json.loads(Path('research/retail-evaluation/protocol.json').read_text())
    policies=protocol['policies']
    packet=build_packet([{'row_id':k,'data':v} for k,v,_ in CASES],policies,[{'name':c} for c in CASES[0][1]])
    refs=[{'row_id':k,'policy':p['id'],'status':gold[i]} for k,_,gold in CASES for i,p in enumerate(policies)]
    return packet,refs

def execute(packet,engine):
    return [{'row_id':r['row_id'],'policy':p['id'],'status':engine(r['data'],p['id'])} for r in packet['common_input']['rows'] for p in packet['common_input']['policies']]

@pytest.mark.parametrize('engine',[evaluate_python,evaluate_shacl])
def test_full_development_path(engine):
    packet,refs=setup();before=json.dumps(packet,sort_keys=True)
    decisions=execute(packet,engine);raw=json.dumps({'decisions':decisions})
    parsed=parse_output(raw,expected_keys(packet));r=score(refs,parsed['predictions'])['overall']
    assert json.dumps(packet,sort_keys=True)==before
    assert parsed['schema_error'] is None and parsed['raw']==raw
    assert r['n']==12 and r['violation_tp']==3 and r['violation_fn']==0 and r['violation_fp']==0
    assert r['coverage_all']==pytest.approx(10/12) and r['coverage_known_refs']==1
    assert r['unsupported_decision_unknown_refs_n']==0 and r['runtime_error_n']==0

@pytest.mark.parametrize('fault',['wrong','omit','malformed','unsupported'])
def test_injected_failures_reach_score(fault):
    packet,refs=setup();decisions=execute(packet,evaluate_python)
    target=next(d for d in decisions if d['row_id']=='c' and d['policy']=='quantity_sign')
    if fault=='wrong':target['status']='pass'
    elif fault=='omit':decisions.remove(target)
    elif fault=='unsupported':
        next(d for d in decisions if d['row_id']=='d' and d['policy']=='quantity_sign')['status']='pass'
    raw='not JSON' if fault=='malformed' else json.dumps({'decisions':decisions})
    parsed=parse_output(raw,expected_keys(packet));r=score(refs,parsed['predictions'])['overall']
    assert parsed['raw']==raw
    if fault=='wrong':assert r['false_pass_n']==1 and r['violation_recall_known_refs']==pytest.approx(2/3)
    elif fault=='omit':assert r['missing_output_n']==1 and r['violation_fn']==1
    elif fault=='malformed':assert r['runtime_error_n']==12 and r['violation_fn']==3 and r['coverage_all']==0
    else:assert r['unsupported_decision_unknown_refs_n']==1 and r['violation_recall_known_refs']==1
