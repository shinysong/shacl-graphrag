import sqlite3
from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_service import WorkspaceService


def test_saved_draft_and_actual_sample_report_never_approve_source(tmp_path):
    source=tmp_path/'input.sqlite'
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE items(id INTEGER PRIMARY KEY,name TEXT NOT NULL)')
        db.execute("INSERT INTO items VALUES(1,'test')")
    registry=SQLiteSources(tmp_path/'registry');record=registry.register(source)
    service=WorkspaceService(tmp_path/'workspaces.sqlite',database_registry=registry)
    row=service.handle({'action':'create_database','title':'Shape diagnostic','source_id':record['source_id'],
        'metadata':{'as_of':'2026-11-24','currency':'unknown','completeness':'partial'},'domain':'sample'})
    before=service.store.get(row['id'])
    request={'action':'database_shapes_propose','id':row['id'],'revision':1,'request_key':'shape-draft'}
    op=service.handle(request)['operation'];assert op['state']=='completed'
    assert not op['result']['model_called'] and not op['result']['answer_policy_changed']
    assert service.handle(request)['reused']
    artifact=op['result']['artifact']
    check={'action':'database_shapes_validate','id':row['id'],'revision':1,'request_key':'shape-check',
        'proposal_operation_id':op['id'],'shapes_turtle':artifact['shapes_turtle']}
    report=service.handle(check)['operation'];assert report['state']=='completed'
    assert report['result']['report']['engine']=='pySHACL'
    assert report['result']['report']['conforms'] is True
    assert report['result']['report']['target_count']==1
    assert service.store.get(row['id'])['digest']==before['digest']
    assert all(e['status']=='pending' for e in service.view(row['id'])['draft']['entries'])
    # A stale proposal cannot silently validate a new review version.
    draft=service._database().restore(before['draft']);draft['entries'][0]['interpretation']='new review'
    service.store.save(row['id'],draft,1)
    stale=service.handle({**check,'revision':2,'request_key':'stale-check'})['operation']
    assert stale['state']=='failed'
