# Selected manufacturing evidence cards v2
Offline projection of18 saved outputs (16 completed,2 unsupported). No paid/live/source lookup, no evaluation gold. Require each data cell to contain cell,value,data_type,formula,cached_value; explicit null remains null but missing keys fail. Header cells require value; skip None,empty,whitespace-only strings; keep original nonblank value, zero accepted. All original header rows retained. Other source fields not claimed lossless. Partial extraction marked projection_failure, downstream must not consume as complete. Raw archives retained. Report serialized JSON bytes, not tokenizer tokens. Direct tests8 pass; raw data omitted and execution fidelity unverified for review. Previous job blocked preserved; fresh job for revised code.

```python
"""Compact selected payloads into traceable cell cards. No source lookup or gold."""
import json
import re
from rdflib import Literal
from rdflib.util import from_n3


def column(address):
    match=re.fullmatch(r'([A-Z]+)[1-9][0-9]*',address)
    if not match:raise ValueError('invalid_cell_address')
    return match.group(1)


def card(payload):
    required={'archive_path','sheet','sha256','cells','header_rows'}
    if not isinstance(payload,dict) or not required<=payload.keys():raise ValueError('missing_payload_provenance')
    headers={}
    for row in payload['header_rows']:
        for c in row['cells']:
            if 'value' not in c:raise ValueError('missing_header_value')
            value=c['value']
            if value is not None and not (isinstance(value,str) and not value.strip()):
                headers[column(c['cell'])]={'value':c['value'],'cell':c['cell']}
    cells=[];seen=set()
    for c in payload['cells']:
        if not {'cell','value','data_type','formula','cached_value'}<=c.keys():
            raise ValueError('missing_required_cell_field')
        address=c['cell']
        if address in seen:raise ValueError('duplicate_cell')
        seen.add(address)
        header=headers.get(column(address))
        cells.append({'cell':address,'header':header,'value':c['value'],
                      'data_type':c['data_type'],'formula':c['formula'],
                      'cached_value':c['cached_value']})
    return {'archive_path':payload['archive_path'],'sheet':payload['sheet'],'sha256':payload['sha256'],
            'coupon':payload.get('coupon'),'cells':cells,'header_rows':payload['header_rows'],
            'header_interpretation':'last nonempty header in each column; does not infer domain semantics',
            'limits':'Selected record only; formulas not evaluated; null values retained; no world completeness claim'}


def package(saved):
    result={'backend':saved['backend'],'question_id':saved['case_id'],'original_status':saved['status'],
            'source_snapshot_hash':saved.get('source_hash'),'query_contract_hash':saved.get('contract_hash'),
            'status':saved['status'],'cards':[],'bindings':[]}
    if saved['status']!='completed':return result
    seen={}
    try:
        for binding in saved['bindings']:
            projected={}
            for key,value in binding.items():
                if key.endswith('_payload'):
                    term=from_n3(value)
                    if not isinstance(term,Literal):raise ValueError('payload_not_literal')
                    payload=json.loads(str(term));c=card(payload)
                    ident=json.dumps(c,sort_keys=True,separators=(',',':'),ensure_ascii=False)
                    if ident not in seen:
                        seen[ident]=len(result['cards']);result['cards'].append(c)
                    projected[key]={'card_index':seen[ident]}
                else:projected[key]=value
            result['bindings'].append(projected)
        result['status']='completed'
    except Exception as exc:
        result['status']='projection_failure';result['error']=type(exc).__name__+':'+str(exc)
        # Partial extraction is preserved as incomplete, never a completed packet.
    return result

```

```python
from scripts.manufacturing_evidence_cards import card,package
from rdflib import Literal
import json
import pytest


def fixture():
    return {'archive_path':'test.xlsx','sheet':'settings','sha256':'a'*64,'coupon':'PP6',
            'header_rows':[{'cells':[{'cell':'A1','value':'setting group'},{'cell':'B1','value':'parent'}]},
                           {'cells':[{'cell':'A2','value':None},{'cell':'B2','value':'Idc (A)'}]}],
            'cells':[{'cell':'A3','value':None,'data_type':'n','formula':None,'cached_value':None},
                     {'cell':'B3','value':'=1+1','data_type':'f','formula':'=1+1','cached_value':2}]}


def test_null_formula_and_two_header_rows_retained():
    c=card(fixture())
    assert c['header_rows']==fixture()['header_rows']
    assert c['cells'][0]['value'] is None
    assert c['cells'][0]['header']['cell']=='A1'
    assert c['cells'][1]['value']=='=1+1' and c['cells'][1]['cached_value']==2
    assert c['cells'][1]['header']['value']=='Idc (A)'


def test_identical_payload_deduplication_and_invalid_payload_preserved():
    v=Literal(json.dumps(fixture())).n3()
    saved={'backend':'fixture','case_id':'Q3','status':'completed','bindings':[{'?a_payload':v,'?b_payload':v}]}
    r=package(saved)
    assert r['status']=='completed' and len(r['cards'])==1
    assert r['bindings'][0]['?a_payload']['card_index']==r['bindings'][0]['?b_payload']['card_index']
    saved['bindings'].append({'?bad_payload':Literal('{}').n3()})
    failed=package(saved)
    assert failed['status']=='projection_failure' and len(failed['cards'])==1


@pytest.mark.parametrize('blank',['','  \t'])
def test_blank_headers_preserve_previous_header_and_original_rows(blank):
    p=fixture();p['header_rows'][1]['cells'][0]['value']=blank
    result=card(p)
    assert result['cells'][0]['header']=={'cell':'A1','value':'setting group'}
    assert result['header_rows']==p['header_rows']


@pytest.mark.parametrize('field',['value','data_type','formula','cached_value'])
def test_missing_cell_field_is_failure_not_null(field):
    p=fixture();del p['cells'][0][field]
    saved={'backend':'fixture','case_id':'Q1','status':'completed',
           'bindings':[{'?row_payload':Literal(json.dumps(p)).n3()}]}
    assert package(saved)['status']=='projection_failure'

```
