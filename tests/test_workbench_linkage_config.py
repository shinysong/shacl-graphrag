import copy,json
import pytest
from rule_workbench.core import new_project
from rule_workbench.linkage_config import encode_linkage_config,decode_linkage_config

S={'source_table':'receipts','source_column':'qi','target_table':'checks','target_column':'id'}
P=[{'source_column':'item','target_column':'item'}]
A=[{'source_value':'OLD','target_value':'Q1','evidence':'PRIVATE-CROSSWALK'}]

def project():
    p=new_project()
    for name,cols,row in [('receipts',['qi','item'],{'qi':'Q1','item':'PRIVATE-ROW'}),
                          ('checks',['id','item'],{'id':'Q1','item':'PRIVATE-ROW'})]:
        p['tables'].append(dict(id=name,name=name,columns=cols,rows=[row],source={'complete':True}))
    return p

def test_roundtrip_always_requires_review_and_scope():
    p=project();before=copy.deepcopy(p)
    raw=encode_linkage_config(p,S,A,P);r=decode_linkage_config(p,raw)
    assert p==before
    assert r['config']['selection']==S and r['config']['aliases']==A and r['config']['equality_pairs']==P
    assert r['snapshot_status']=='same_snapshot'
    assert r['review_status']==r['equality_review_status']=='draft' and r['target_complete'] is False
    assert b'PRIVATE-ROW' not in raw
    assert b'PRIVATE-CROSSWALK' in raw  # Explicit configuration includes alias evidence, not anonymous.

@pytest.mark.parametrize('change',['row','provenance'])
def test_changed_snapshot_retained_but_not_approved(change):
    p=project();raw=encode_linkage_config(p,S)
    if change=='row':p['tables'][0]['rows'][0]['item']='CHANGED'
    else:p['tables'][0]['source']['file']='changed.csv'
    r=decode_linkage_config(p,raw)
    assert r['snapshot_status']=='changed_snapshot' and r['review_status']=='draft'

def test_missing_table_or_column_rejected():
    p=project();raw=encode_linkage_config(p,S)
    p['tables'][0]['columns']=['qi'];p['tables'][0]['rows']=[{'qi':'Q1'}]
    paired=encode_linkage_config(project(),S,[],P)
    with pytest.raises(ValueError):decode_linkage_config(p,paired)
    p['tables'].pop()
    with pytest.raises(ValueError):decode_linkage_config(p,raw)

@pytest.mark.parametrize('field,value',[('review_status','confirmed'),('target_complete',True),('version',True),('snapshot',{})])
def test_untrusted_fields_and_version_rejected(field,value):
    p=project();c=json.loads(encode_linkage_config(p,S));c[field]=value
    with pytest.raises(ValueError):decode_linkage_config(p,json.dumps(c).encode())

def test_duplicate_json_keys_rejected():
    p=project();raw=encode_linkage_config(p,S)
    raw=raw.replace(b'"version": 1',b'"version": 1, "version": 1')
    with pytest.raises(ValueError,match='Duplicate'):decode_linkage_config(p,raw)

@pytest.mark.parametrize('raw',[b'x'*100001,b'not-json',b'\xff'])
def test_bad_payload(raw):
    with pytest.raises(ValueError):decode_linkage_config(project(),raw)

def test_result_file_cannot_be_loaded_as_configuration():
    with pytest.raises(ValueError):decode_linkage_config(project(),b'{"schema_version":1,"report":{}}')
