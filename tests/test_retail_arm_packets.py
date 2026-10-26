import json
import pytest
from scripts.retail_arm_packets import preview

ROWS=[{'row_id':'dev1','data':{'InvoiceNo':'C1','Quantity':-1,'CustomerID':None,'UnitPrice':1}}]
VARIABLES=[{'name':k} for k in ROWS[0]['data']]

def test_same_evidence_all_five_arms():
    p=preview(ROWS,VARIABLES)
    assert len(p)==5
    assert len({v['common_input_sha256'] for v in p.values()})==1
    assert len({v['messages'][1]['content'] for v in p.values()})==1
    assert len({v['messages_sha256'] for v in p.values()})==5
    common=json.loads(next(iter(p.values()))['messages'][1]['content'])
    assert len(common['policies'])==3 and 'number' in common['common_semantics']
    assert 'reference_generation' not in common and 'expected' not in common

def test_repeatable_and_input_change_bound():
    a=preview(ROWS,VARIABLES);assert a==preview(ROWS,VARIABLES)
    changed=[{'row_id':'dev1','data':dict(ROWS[0]['data'],Quantity=2)}]
    b=preview(changed,VARIABLES)
    assert all(a[k]['common_input_sha256']!=b[k]['common_input_sha256'] for k in a)

def test_reference_field_rejected():
    with pytest.raises(ValueError):preview([dict(ROWS[0],reference='pass')],VARIABLES)

def test_unresolved_runner_explicit():
    p=preview(ROWS,VARIABLES)
    assert all(v['pending'] and v['readiness'].startswith('offline preview') for v in p.values())
    assert 'isolated runner' in p['llm_ad_hoc_code']['messages'][0]['content']

def test_shared_mapping_and_unknown_metadata():
    rows=[{'row_id':'a/b','data':{'Quantity':'bad','UnitPrice':None}}]
    packets=preview(rows,[{'name':'Quantity'},{'name':'UnitPrice'}])
    for packet in packets.values():
        common=json.loads(packet['messages'][1]['content'])
        assert common['field_mapping']['namespace']=='urn:retail:field:'
        row=common['normalized_rows'][0]
        assert row['uri']=='urn:retail:row:a%2Fb'
        fields=row['fields']
        assert fields['Quantity']['state']=='invalid' and fields['Quantity']['raw']=='bad'
        assert fields['UnitPrice']['state']=='missing' and fields['UnitPrice']['source_key_present']
        assert fields['InvoiceNo']['state']=='missing' and not fields['InvoiceNo']['source_key_present']
        assert 'status' not in row and common['rows']==rows


def test_mapping_spec_changes_input_hash(monkeypatch,tmp_path):
    import scripts.retail_arm_packets as module
    from pathlib import Path
    import shutil
    target=tmp_path/'research/retail-evaluation'
    shutil.copytree(module.ROOT/'research/retail-evaluation',target)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    before=preview(ROWS,VARIABLES)
    path=target/'rdf-mapping.json';spec=json.loads(path.read_text())
    spec['version']='test-only-version';path.write_text(json.dumps(spec))
    after=preview(ROWS,VARIABLES)
    assert all(before[k]['common_input_sha256']!=after[k]['common_input_sha256'] for k in before)
