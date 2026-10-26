"""Offline information-parity previews; never execute generated code or call models."""
import hashlib
import json
from pathlib import Path
from scripts.retail_io import build_packet
from scripts.retail_rdf_mapping import map_rows

ROOT=Path(__file__).resolve().parents[1]

def encode(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,allow_nan=False)

def preview(rows, variables):
    base=ROOT/'research/retail-evaluation'
    protocol=json.loads((base/'protocol.json').read_text())
    semantics=json.loads((base/'evaluation-contract.json').read_text())['common_semantics']
    instructions=json.loads((base/'arm-instructions.json').read_text())
    common=build_packet(rows,protocol['policies'],variables)['common_input']
    common['common_semantics']=semantics
    _, normalized = map_rows(rows)
    common['field_mapping'] = json.loads((base/'rdf-mapping.json').read_text())
    common['normalized_rows'] = normalized
    content=encode(common)
    digest=hashlib.sha256(content.encode()).hexdigest()
    result={}
    for arm,spec in instructions['arms'].items():
        messages=[{'role':'system','content':instructions['shared']+'\n'+spec['instruction']}, {'role':'user','content':content}]
        result[arm]={'stage':spec['stage'],'messages':messages,'common_input_sha256':digest,'messages_sha256':hashlib.sha256(encode(messages).encode()).hexdigest(),'readiness':'offline preview only; pending launch prerequisites','pending':instructions['pending']}
    return result
