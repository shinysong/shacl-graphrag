"""Loss indicators must survive portable JSON, including inside ZIP bundles."""
import copy
import io
import json
import zipfile

import pytest
from rule_workbench.core import new_project
from rule_workbench.exports import export_json, export_bundle, import_json
from rule_workbench.linkage_ui import inspect_linkage


def project():
    p=new_project()
    for name in ('source','target'):
        p['tables'].append({'id':name,'name':name,'columns':['code'],
                            'rows':[{'code':'A'}],
                            'source':{'kind':'fixture','complete':True,'redacted':True,
                                      'connection_string':'PRIVATE-CONNECTION'}})
    return p


@pytest.mark.parametrize('bundle',[False,True])
@pytest.mark.parametrize('include_data',[False,True])
def test_redaction_survives_portable_export_and_import(bundle,include_data):
    p=project();before=copy.deepcopy(p)
    if bundle:
        raw=zipfile.ZipFile(io.BytesIO(export_bundle(p,include_data=include_data))).read('project.json')
    else:
        raw=export_json(p,include_data=include_data)
    restored=import_json(raw)
    assert p==before
    for table in restored['tables']:
        assert table['source']['redacted'] is True
        assert 'complete' not in table['source']  # No portable approval restored.
        assert 'connection_string' not in table['source']
        if not include_data:
            assert table['source']['data_omitted'] is True
            assert table['rows']==[]
    assert b'PRIVATE-CONNECTION' not in raw
    if include_data:
        selection=dict(source_table='source',source_column='code',target_table='target',target_column='code')
        result=inspect_linkage(restored,selection,[],complete=True,confirmed=True)['report']
        assert result['source_redacted'] is True
        assert result['target_complete_declared'] is False
        assert result['results'][0]['status']=='unknown_target_scope'


def test_import_raw_redacted_project_cannot_erase_loss_flag():
    p=project()
    restored=import_json(json.dumps(p).encode())
    assert restored['tables'][1]['source']['redacted'] is True
    assert restored['tables'][0]['rows']==p['tables'][0]['rows']


def test_false_redacted_and_absent_flags_preserved_without_invention():
    p=project();p['tables'][0]['source']['redacted']=False
    del p['tables'][1]['source']['redacted']
    restored=import_json(export_json(p,True))
    assert restored['tables'][0]['source']['redacted'] is False
    assert 'redacted' not in restored['tables'][1]['source']
