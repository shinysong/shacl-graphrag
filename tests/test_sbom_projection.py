from scripts.sbom_projection import answers, rdf_roundtrip


def record():
    return dict(id='doc:ref',ref='ref',document_hash='a'*64,pointer='/components/0',
                spec_version='1.4',dependency_field_present=True,dependency_entry_present=True,
                scope_present=False,scope_value='',scope_default='required',targets=[],policy_hash='b'*64)


def test_presence_collisions_and_provenance():
    a=record();b={**a,'dependency_entry_present':False}
    assert a['targets']==b['targets']
    assert answers(a)['dependency']=='explicit_empty'
    assert answers(b)['dependency']=='unknown'
    c={**a,'scope_present':True,'scope_value':'required'}
    assert answers(a)['scope']==answers(c)['scope']=='required'
    assert rdf_roundtrip(a)==a and rdf_roundtrip(b)==b and rdf_roundtrip(c)==c
    assert rdf_roundtrip(a)!=rdf_roundtrip(c)


def test_projection_loss_is_not_source_absence():
    a=record();del a['dependency_entry_present']
    assert answers(a)['dependency']=='projection_unknown'
    assert answers(record())['dependency']=='explicit_empty'


def test_missing_frozen_source_retains_denominator(tmp_path):
    from scripts.sbom_projection import evaluate
    expected={'planned_nodes':7,'files':[{'name':'missing.json','nodes':7,'sha256':'a'*64}]}
    result=evaluate(tmp_path,tmp_path/'out',expected)
    assert result['planned_nodes']==7 and result['emitted_nodes']==0
    assert result['not_emitted_nodes']==7 and len(result['source_failures'])==1
    a=record();del a['dependency_entry_present']
    assert answers(a)['scope']=='required'
