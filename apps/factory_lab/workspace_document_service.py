"""Saved human paragraph review, separate from executable policy interpretation.

The registry is operator-injected. Public requests contain opaque IDs/hashes, not
paths. Review operations do not mutate the source or certify policy applicability.
"""
from copy import deepcopy

ACTIONS = {
    'database_documents': {'id', 'revision', 'offset'},
    'database_document': {'id', 'revision', 'document_id', 'offset'},
    'database_document_preview': {'id', 'revision', 'document_id', 'paragraph_id', 'document_sha256'},
    'database_document_review': {'id', 'revision', 'request_key', 'document_id',
                                 'paragraph_id', 'document_sha256', 'interpretation'},
    'database_document_read': {'id', 'revision', 'request_key', 'review_operation_id'},
}


def handle(store, documents, adapter, action, body, row):
    if documents is None:
        raise ValueError('Registered source documents are not configured')
    draft = adapter.restore(row['draft'])
    binding = {'source_id': draft['database']['source_id'],
               'snapshot_sha256': draft['database']['snapshot_sha256']}
    if action == 'database_documents':
        return documents.catalog(**binding, offset=body['offset'], limit=20)
    if action == 'database_document':
        return documents.inspect(body['document_id'], **binding, offset=body['offset'], limit=50)
    if action == 'database_document_preview':
        return {'paragraph': documents.read_paragraph(body['document_id'], body['paragraph_id'],
                    **binding, document_sha256=body['document_sha256']),
                'status': 'unapproved_source_preview', 'policy_applicability': 'unassessed',
                'notice': 'Original text for review; preview does not approve this reference.'}
    request = {k: deepcopy(v) for k, v in body.items()
               if k not in ('action', 'id', 'revision', 'request_key')}
    operation, created = store.begin(row['id'], row['revision'], body['request_key'], action, request)
    if created:
        try:
            if action == 'database_document_review':
                interpretation = body['interpretation']
                if not isinstance(interpretation, str) or not interpretation.strip() or len(interpretation) > 4000:
                    raise ValueError('Record a bounded reviewed interpretation')
                paragraph = documents.read_paragraph(body['document_id'], body['paragraph_id'],
                    **binding, document_sha256=body['document_sha256'])
                result = {'format': 'reviewed-source-paragraph-1', 'status': 'approved_reference',
                          'binding': binding, 'reference': {k: body[k] for k in
                              ('document_id', 'paragraph_id', 'document_sha256')},
                          'paragraph': paragraph, 'interpretation': interpretation,
                          'origin': 'explicit_local_user_review_not_authenticated_attestation',
                          'policy_applicability': 'unassessed', 'executable_policy': False}
            elif action == 'database_document_read':
                review = store.operation(row['id'], body['review_operation_id'])
                if review['kind'] != 'database_document_review' or review['state'] != 'completed':
                    raise ValueError('Choose a completed paragraph review in this workspace')
                saved = review['result']
                if saved['binding'] != binding:
                    raise ValueError('Document review requires the same registered source version')
                ref = saved['reference']
                paragraph = documents.read_paragraph(ref['document_id'], ref['paragraph_id'],
                    **binding, document_sha256=ref['document_sha256'])
                if paragraph != saved['paragraph']:
                    raise ValueError('Reviewed paragraph content changed')
                result = {'format': 'reviewed-source-paragraph-read-1', 'binding': binding,
                          'review_operation_id': review['id'], 'reference': deepcopy(ref),
                          'paragraph': paragraph, 'interpretation': saved['interpretation'],
                          'policy_applicability': 'unassessed', 'executable_policy': False}
            else:
                raise ValueError('Unknown source document action')
            result['workspace'] = {'id': row['id'], 'revision': row['revision'], 'draft_digest': row['digest']}
            store.finish(operation['id'], 'completed', result=result)
        except (ValueError, TypeError, KeyError) as exc:
            store.finish(operation['id'], 'failed', error=str(exc)[:1000])
        except Exception:
            store.finish(operation['id'], 'failed', error='Source document operation failed; inspect before retry')
            raise
    return {'operation': store.operation(row['id'], operation['id']), 'reused': not created}
