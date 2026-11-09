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
