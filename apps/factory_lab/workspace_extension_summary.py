"""Small read-only receipts for saved proposals, never an approval decision."""
import json


def summarize(operation, generation=None, current_revision=None):
    proposal = operation.get('result') or {}
    if operation.get('kind') != 'extension_import' or operation.get('state') != 'completed':
        return None
    observed = (generation or {}).get('result') or {}
    model = observed.get('native_model_execution') or {}
    semantic = ((generation or {}).get('state') == 'completed' and observed.get('mode') == 'semantic'
                and observed.get('import_operation_id') == operation['id']
                and not model.get('internal_model_error_observed', True)
                and bool(model.get('new_provider_attempts') or model.get('new_cache_hits')))
    return {'operation_id': operation['id'], 'workspace': operation['workspace'],
            'revision': operation['revision'], 'created': operation.get('created'),
            'origin': 'observed_native_semantic_generation' if semantic else 'external_proposal',
            'physical_columns': sum(x.get('kind') == 'column' for x in proposal.get('fields', [])),
            'semantic_fields': sum(x.get('kind') != 'column' for x in proposal.get('fields', [])),
            'semantic_concepts': sum(x.get('kind') in ('term', 'concept') for x in proposal.get('concepts', [])),
            'relation_candidates': len(proposal.get('relations', [])),
            'declared_relations': sum(x.get('kind') == 'foreign_keys' for x in proposal.get('relations', [])),
            'semantic_relations': sum(x.get('kind') == 'semantic_fks' for x in proposal.get('relations', [])),
            'other_relations': sum(x.get('kind') not in ('foreign_keys', 'semantic_fks') for x in proposal.get('relations', [])),
            'unsupported': len(proposal.get('unsupported', [])),
            'unresolved_references': len(proposal.get('unresolved_references', [])),
            'status': 'saved_proposal_not_automatically_applied',
            'stale': current_revision is not None and operation['revision'] != current_revision}


def latest(store, workspace, revision):
    with store.connect() as db:
        row = db.execute("SELECT * FROM operations WHERE workspace=? AND kind='extension_import' AND state='completed' ORDER BY created DESC,id DESC LIMIT 1", (workspace,)).fetchone()
        if row is None:
            return None
        operation = dict(row)
        operation['result'] = json.loads(operation['result'])
        generation = None
        # A bound generation can predate a busy import; never infer model use from YAML alone.
        for item in db.execute("SELECT * FROM operations WHERE workspace=? AND kind='extension_generation' AND state='completed' ORDER BY created DESC LIMIT 100", (workspace,)):
            candidate = dict(item)
            candidate['result'] = json.loads(candidate['result'] or '{}')
            if candidate['result'].get('import_operation_id') == operation['id']:
                generation = candidate
                break
        return summarize(operation, generation, revision)
