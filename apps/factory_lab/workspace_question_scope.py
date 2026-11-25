"""Durable operator scope assessments, never automatic semantic absence detection.

The server verifies source inventory and selected saved evidence provenance. The
user's requirement and reason text remains a claim by the reviewer, not a finding
that a business fact is absent, false, or impossible to retrieve.
"""
from copy import deepcopy
import hashlib
import json

ACTIONS = {
    'database_question_scope': {
        'id', 'revision', 'request_key', 'question', 'unresolved_requirements',
        'reason_kind', 'assessment_note', 'evidence_operation_ids', 'human_confirmed',
    },
}
REASON_KINDS = {
    'source_not_supplied', 'retrieval_not_performed', 'unsupported_operation',
    'needs_external_verification',
}
MAX_RECORD_BYTES = 262144


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _hash(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


def _text(value, name, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'Provide bounded nonempty {name} (maximum {maximum} characters)')


def _validate(body):
    if set(body) - {'action'} != ACTIONS['database_question_scope']:
        raise ValueError('Invalid question scope fields')
    _text(body['question'], 'question', 4000)
    _text(body['assessment_note'], 'assessment note', 4000)
    requirements = body['unresolved_requirements']
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 20:
        raise ValueError('Provide 1 to 20 unresolved requirements')
    for requirement in requirements:
        _text(requirement, 'unresolved requirement', 1000)
    if not isinstance(body['reason_kind'], str) or body['reason_kind'] not in REASON_KINDS:
        raise ValueError('Choose a supported scope reason')
    if body['human_confirmed'] is not True:
        raise ValueError('Explicit human confirmation is required')
    ids = body['evidence_operation_ids']
    if (not isinstance(ids, list) or len(ids) > 20 or
            any(not isinstance(oid, str) or not oid or len(oid) > 200 for oid in ids) or
            len(set(ids)) != len(ids)):
        raise ValueError('Select at most 20 distinct saved evidence operations')


def _evidence(service, row, source, operation_id):
    operation = service.store.operation(row['id'], operation_id)
    if operation['state'] != 'completed' or operation['kind'] not in (
            'database_query_execute', 'database_document_read'):
        raise ValueError('Select completed query executions or document reads in this workspace')
    result = operation['result']
    expected = {'id': row['id'], 'revision': row['revision'], 'draft_digest': row['digest']}
    if operation['revision'] != row['revision'] or result.get('workspace') != expected:
        raise ValueError('Evidence requires the same workspace revision and digest')
    binding = {k: source[k] for k in ('source_id', 'snapshot_sha256')}
    if operation['kind'] == 'database_query_execute':
        artifact = result['artifact']
        query_source = artifact['provenance']['source']
        if any(query_source.get(k) != v for k, v in binding.items()):
            raise ValueError('Query evidence source binding changed')
        # Summarize saved output only. Never rerun answer SQL, interpret column
        # names, or treat a zero-row result as proof of business-world absence.
        summary = {k: deepcopy(artifact[k]) for k in (
            'status', 'returned_count', 'total_output_rows', 'matched_root_rows', 'truncated',
            'output_kind', 'complete', 'limitations') if k in artifact}
        summary['saved_row_count'] = len(artifact.get('rows', []))
        summary['provenance_sha256'] = _hash(artifact['provenance'])
    else:
        if result['binding'] != binding or service.source_documents is None:
            raise ValueError('Document evidence source is unavailable or changed')
        reference = result['reference']
        paragraph = service.source_documents.read_paragraph(
            reference['document_id'], reference['paragraph_id'], **binding,
            document_sha256=reference['document_sha256'])
        if paragraph != result['paragraph']:
            raise ValueError('Document evidence paragraph changed')
        summary = {k: deepcopy(paragraph[k]) for k in (
            'document_id', 'label', 'version', 'document_sha256', 'paragraph_id',
            'paragraph_sha256', 'line_start', 'line_end') if k in paragraph}
        summary['text_excerpt'] = paragraph['text'][:1000]
        summary['text_excerpt_truncated'] = len(paragraph['text']) > 1000
    return {'operation_id': operation_id, 'kind': operation['kind'],
            'result_sha256': _hash(result), 'summary': summary}


def handle(service, action, body, row):
    """Reserve first; repeated keys return durable results before dependencies."""
    request = {k: deepcopy(v) for k, v in body.items()
               if k not in ('action', 'id', 'revision', 'request_key')}
    operation, created = service.store.begin(
        row['id'], row['revision'], body['request_key'], action, request)
    if created:
        try:
            if action != 'database_question_scope':
                raise ValueError('Unknown question scope action')
            _validate(body)
            draft = service._database().restore(row['draft'])
            source = deepcopy(draft['database'])
            inventory = [{k: deepcopy(table[k]) for k in
                          ('name', 'columns', 'primary_key', 'foreign_keys', 'row_count')}
                         for table in draft['sources']]
            evidence = [_evidence(service, row, source, oid)
                        for oid in body['evidence_operation_ids']]
            result = {
                'format': 'reviewed-question-scope-1',
                'status': 'reviewer_stated_unresolved',
                **{k: deepcopy(body[k]) for k in (
                    'question', 'unresolved_requirements', 'reason_kind', 'assessment_note')},
                'scope_verified': False, 'absence_verified': False,
                'source': source, 'schema_inventory': inventory,
                'schema_inventory_sha256': _hash(inventory), 'evidence': evidence,
                'scope': {
                    'schema': 'restored_registered_snapshot',
                    'evidence': 'explicitly_selected_saved_operations_only',
                    'unsearched': 'Everything beyond selected evidence; no automatic retrieval or absence test',
                },
                'review': {'actor': 'local_workspace_user', 'human_confirmed': True,
                           'origin': 'explicit_local_user_review_not_authenticated_attestation'},
                'notice': 'The reviewer states these requirements remain unresolved. Source inventory '
                          'and selected evidence provenance were checked; requirement interpretation, '
                          'absence, completeness and external truth were not verified.',
                'workspace': {'id': row['id'], 'revision': row['revision'],
                              'draft_digest': row['digest']},
            }
            if len(_encoded(result)) > MAX_RECORD_BYTES:
                raise ValueError('Question scope record exceeds the 262144 byte bound')
            service.store.finish(operation['id'], 'completed', result=result)
        except (ValueError, TypeError, KeyError) as exc:
            service.store.finish(operation['id'], 'failed', error=str(exc)[:1000])
        except Exception:
            service.store.finish(operation['id'], 'failed',
                                 error='Question scope recording failed; inspect saved attempt before retry')
            raise
    return {'operation': service.store.operation(row['id'], operation['id']), 'reused': not created}
