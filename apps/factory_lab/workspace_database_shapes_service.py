"""Saved declaration-derived drafts and sample diagnostics, never active guardrails."""
from . import workspace_database_shapes as shapes

ACTIONS = {
    'database_shapes_propose': {'id', 'revision', 'request_key'},
    'database_shapes_validate': {'id', 'revision', 'request_key', 'proposal_operation_id', 'shapes_turtle'},
}


def handle(service, action, body, row):
    adapter = service._database()
    draft = adapter.restore(row['draft'])
    request = {k: body[k] for k in ACTIONS[action] - {'id', 'revision', 'request_key'}}
    operation, created = service.store.begin(row['id'], row['revision'], body['request_key'], action, request)
    if created:
        try:
            if action == 'database_shapes_propose':
                artifact = shapes.propose(draft)
                result = {'artifact': artifact, 'status': 'draft_for_review',
                          'workspace_digest': row['digest'], 'model_called': False,
                          'answer_policy_changed': False, 'automatic_approval': False}
            else:
                source = service.store.operation(row['id'], body['proposal_operation_id'])
                if (source['kind'] != 'database_shapes_propose' or source['state'] != 'completed'
                        or source['revision'] != row['revision']
                        or source['result']['workspace_digest'] != row['digest']):
                    raise ValueError('Generate a SHACL draft for the current workspace version first')
                artifact = source['result']['artifact']
                if artifact['source_binding']['snapshot_sha256'] != draft['database']['snapshot_sha256']:
                    raise ValueError('SHACL sample does not match the current registered snapshot')
                if not isinstance(body['shapes_turtle'], str) or len(body['shapes_turtle'].encode()) > shapes.MAX_BYTES:
                    raise ValueError('SHACL text exceeds the supported diagnostic boundary')
                report = shapes.validate(artifact, body['shapes_turtle'])
                result = {'report': report, 'shapes_turtle': body['shapes_turtle'],
                          'proposal_operation_id': source['id'], 'workspace_digest': row['digest'],
                          'model_called': False, 'answer_policy_changed': False,
                          'automatic_approval': False}
            service.store.finish(operation['id'], 'completed', result=result)
        except (ValueError, TypeError, KeyError) as exc:
            service.store.finish(operation['id'], 'failed', error=str(exc)[:1000])
    return {'operation': service.store.operation(row['id'], operation['id']), 'reused': not created}
