"""Saved real-file paragraph review, not a policy correctness benchmark."""
from copy import deepcopy

import pytest

from apps.factory_lab.workspace_service import WorkspaceService
from apps.factory_lab.workspace_source_documents import DocumentSources
from tests.test_workspace_database_adapter import workspace


def test_review_reuse_restart_and_failed_wrong_binding(workspace, tmp_path):
    adapter, draft, _ = workspace
    binding = {'source_id': draft['database']['source_id'],
               'snapshot_sha256': draft['database']['snapshot_sha256']}
    path = tmp_path / 'policy.md'
    path.write_text('Return policy\n\nA receipt is one prerequisite.\n\nExceptions need separate review.\n')
    docs = DocumentSources(tmp_path/'documents', adapter.registry)
    descriptor = docs.register(path, **binding, label='Returns', version='1')
    service = WorkspaceService(tmp_path/'workspace.sqlite', database_registry=adapter.registry, source_documents=docs)
    row = service.handle({'action':'create_database','title':'Own source','source_id':binding['source_id'], 'metadata':{},'domain':'generic'})
    detail = docs.inspect(descriptor['document_id'], **binding)
    paragraph = detail['paragraphs'][1]
    request = {'action':'database_document_review','id':row['id'],'revision':1,'request_key':'review',
               'document_id':descriptor['document_id'],'paragraph_id':paragraph['paragraph_id'],
               'document_sha256':descriptor['document_sha256'],'interpretation':'Receipt alone does not establish eligibility.'}
    preview = service.handle({k:v for k,v in request.items() if k not in ('request_key','interpretation')} | {'action':'database_document_preview'})
    assert preview['status']=='unapproved_source_preview'
    assert preview['paragraph']['text']=='A receipt is one prerequisite.\n'
    assert service.store.operations(row['id'])==[]
    reviewed = service.handle(request)
    assert reviewed['operation']['state']=='completed', reviewed
    assert not reviewed['operation']['result']['executable_policy']
    assert service.handle(request)['reused']
    read = {'action':'database_document_read','id':row['id'],'revision':1,'request_key':'read',
            'review_operation_id':reviewed['operation']['id']}
    result=service.handle(read)['operation']
    assert result['state']=='completed'
    assert result['result']['paragraph']==reviewed['operation']['result']['paragraph']
    path.write_text('Changed original, preserved snapshot')
    restarted=WorkspaceService(tmp_path/'workspace.sqlite',database_registry=adapter.registry,source_documents=docs)
    assert restarted.handle(read)['operation']==result
    other=restarted.handle({'action':'create_database','title':'Other workspace','source_id':binding['source_id'],'metadata':{},'domain':'generic'})
    failed=restarted.handle({**read,'id':other['id']})['operation']
    assert failed['state']=='failed'
    bad=deepcopy(request);bad.update(request_key='wrong-hash',document_sha256='0'*64)
    assert restarted.handle(bad)['operation']['state']=='failed'
    assert restarted.view(row['id'])['revision']==1


def test_disabled_document_dependency(workspace,tmp_path):
    adapter,draft,_=workspace
    service=WorkspaceService(tmp_path/'workspace.sqlite',database_registry=adapter.registry)
    row=service.handle({'action':'create_database','title':'No docs','source_id':draft['database']['source_id'],'metadata':{},'domain':'generic'})
    with pytest.raises(ValueError,match='not configured'):
        service.handle({'action':'database_documents','id':row['id'],'revision':1,'offset':0})
