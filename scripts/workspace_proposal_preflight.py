"""Offline packet/provider preflight. No API key, network or execution authorization.

Metadata snapshots describe one observation, not guaranteed future availability.
Reservation estimate matches PublicGateway's conservative byte-based formula;
this is not an actual tokenizer count or a forecast of billed cost.
"""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from apps.factory_lab.store import dumps


def inspect(packet_dir, endpoints_path, config):
    if set(config)-{"reasoning_effort"}!={"model","provider","prompt_per_million","completion_per_million","max_tokens","max_calls","max_usd","hours"}:
        raise ValueError("Use exact gateway config fields")
    if 'reasoning_effort' in config and config['reasoning_effort'] not in ('low','medium','high'):
        raise ValueError('Unsupported reasoning effort')
    root=Path(packet_dir)
    raw=(root/'manifest.json').read_bytes();manifest=json.loads(raw)
    endpoint_raw=Path(endpoints_path).read_bytes();data=json.loads(endpoint_raw)['data']
    if data.get('id') != config['model']:
        raise ValueError('Endpoint model mismatch')
    matches=[e for e in data['endpoints'] if e.get('tag')==config['provider']]
    if len(matches)!=1:raise ValueError('One exact provider tag required')
    endpoint=matches[0]
    if endpoint.get('status')!=0:raise ValueError('Provider snapshot unavailable')
    if not {'temperature','max_tokens'} <= set(endpoint.get('supported_parameters',[])):
        raise ValueError('Required generation parameters unsupported')
    for field in ('prompt_per_million','completion_per_million','max_usd'):
        value=Decimal(str(config[field]))
        if not value.is_finite() or value<=0:raise ValueError('Finite positive prices/cap required')
    for field,low,high in [('max_tokens',256,4096),('max_calls',1,100),('hours',1,8)]:
        if type(config[field]) is not int or not low<=config[field]<=high:raise ValueError('Unsupported limit')
    if Decimal(str(config['max_usd']))>5:raise ValueError('Gateway cap exceeded')
    for field,price in [('prompt_per_million','prompt'),('completion_per_million','completion')]:
        if Decimal(str(config[field])) < Decimal(endpoint['pricing'][price])*1000000:
            raise ValueError('Configured price below provider snapshot')
    if 'reasoning_effort' in config and 'reasoning' not in endpoint.get('supported_parameters',[]):
        raise ValueError('Provider does not advertise reasoning configuration')
    if config['max_tokens']>endpoint['max_completion_tokens']:raise ValueError('Output limit exceeds provider snapshot')
    records=[];seen=set();total=Decimal(0)
    for capture in manifest['records']:
        cid=capture['id']
        if not isinstance(cid,str) or not cid.isascii() or not cid.replace('_','').isalnum() or cid in seen:
            raise ValueError('Unsafe or duplicate case')
        seen.add(cid)
        if capture['state']!='captured_before_response':raise ValueError('Uncaptured packet; preserve failed capture')
        packet=(root/(cid+'-messages.json')).read_bytes()
        if hashlib.sha256(packet).hexdigest()!=capture['messages_sha256']:raise ValueError('Packet hash mismatch')
        messages=json.loads(packet)
        if not isinstance(messages,list) or not messages or any(not isinstance(m,dict) or not isinstance(m.get('content'),str) for m in messages):
            raise ValueError('Invalid messages')
        size=len(dumps(messages).encode())
        if size>40000:raise ValueError('Gateway context byte limit exceeded')
        inp=size+4096+512*len(messages)
        amount=2*(Decimal(inp)*Decimal(str(config['prompt_per_million']))+Decimal(config['max_tokens'])*Decimal(str(config['completion_per_million'])))/1000000
        records.append({'case_id':cid,'packet_sha256':capture['messages_sha256'],'gateway_message_bytes':size,'input_reservation_units':inp,'reserved_usd':str(amount)})
        total+=amount
    if not records or len(records)>config['max_calls'] or total>Decimal(str(config['max_usd'])):
        raise ValueError('Whole packet set exceeds declared attempt/reservation cap')
    return {'scope':'Offline compatibility and reservation estimate only','config':config,
            'config_sha256':hashlib.sha256(dumps(config).encode()).hexdigest(),
            'manifest_sha256':hashlib.sha256(raw).hexdigest(),'endpoints_sha256':hashlib.sha256(endpoint_raw).hexdigest(),
            'records':records,'total_reserved_usd':str(total),'paid_execution_ready':False,
            'remaining':['Explicit new bounded human authorization and absolute deadline','Independent live runner review and durable attempt export','Recheck provider metadata before execution; tokenizer/output adequacy unmeasured'],
            'limitations':['No calls or semantic quality results','No actual tokenizer count; reservation formula not billed-cost prediction','Reasoning effort is pinned; actual provider allocation remains unmeasured' if 'reasoning_effort' in config else 'Model reasoning defaults are not pinned by this gateway config','Metadata compatibility is not successful provider execution']}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet_dir');parser.add_argument('endpoints');parser.add_argument('config');parser.add_argument('output')
    args=parser.parse_args();report=inspect(args.packet_dir,args.endpoints,json.loads(Path(args.config).read_text()))
    with Path(args.output).open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))
