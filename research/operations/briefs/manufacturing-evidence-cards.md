# Selected manufacturing evidence cards
Offline transform only from18savedaugmentedquery outputs.16completed2unsupportedQ7. No source lookup or gold. Preservecellvalues/null/formula/cache, alloriginalheaderrows, sourcefile/sheet/hash; attachlastnonemptyper-columnheader as declared mechanical rule notdomaininterpretation. Originalrawpayloads remainarchived. Deduplicateidenticalcardswithinquestion only; scope notglobalmetadata. Reportrawbindingbytes andcardpackagebytes separately, nottokens. On malformedpayload preservepartialextraction butmarkprojection_failure; neverfeedpartialfailedpacket ascomplete. No paid/livecalls. Code/testsbelow; rawdataomittedunverified. Two tests pass.

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
            if c.get('value') is not None:
                headers[column(c['cell'])]={'value':c['value'],'cell':c['cell']}
    cells=[];seen=set()
    for c in payload['cells']:
        address=c['cell']
        if address in seen:raise ValueError('duplicate_cell')
        seen.add(address)
        header=headers.get(column(address))
        cells.append({'cell':address,'header':header,'value':c.get('value'),
                      'data_type':c.get('data_type'),'formula':c.get('formula'),
                      'cached_value':c.get('cached_value')})
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

```
