"""Source-bound, explicitly reviewed advisory reasoning; immutable answer lineage."""
import base64
from copy import deepcopy
from hashlib import sha256
import os
from pathlib import Path

from rdflib import BNode, Graph, Literal, RDF, URIRef, XSD
from .workspace_query_contracts import fingerprint
from .workspace_query_service import validate_saved_execution
from .workspace_reasoning import RECEIPT_RESERVATION
from .workspace_store import encode, cancellation_callback, check_cancel, ExecutionCancelled

ACTIONS = {
    'database_reasoning_propose': {'id', 'revision', 'request_key', 'execution_operation_id', 'projection_spec', 'ontology_base64', 'profile'},
    'database_reasoning_approve': {'id', 'revision', 'request_key', 'proposal_operation_id', 'note', 'human_confirmed'},
    'database_reasoning_execute': {'id', 'revision', 'request_key', 'approval_operation_id'},
    'database_reasoning_advisory_use': {'id', 'revision', 'request_key', 'reasoning_operation_id', 'execution_operation_id', 'selected_statement_ids', 'interpretation', 'note', 'human_confirmed'},
    'database_reasoning_catalog': {'id', 'revision', 'execution_operation_id', 'cursor'},
}


def _saved(service, row, oid, kind):
    op = service.store.operation(row['id'], oid)
    if op['kind'] != kind or op['state'] != 'completed':
        raise ValueError('Choose the required completed operation in this workspace')
    return op


def _binary(service):
    if service.local_reasoner is None:
        raise ValueError('Local reasoning is not configured')
    path = Path(service.local_reasoner.binary).resolve(strict=True)
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError('Configured binary is unavailable')
    digest = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def _review(body):
    if body['human_confirmed'] is not True:
        raise ValueError('Explicit human confirmation required')
    if not isinstance(body['note'], str) or not body['note'].strip() or len(body['note']) > 4000:
        raise ValueError('Provide a bounded review note')
    return {'note': body['note'], 'human_confirmed': True, 'actor': 'local_workspace_user',
            'identity_authenticated': False}


def _plan(service, row, request):
    from .workspace_query_projection import build_projection
    binding = validate_saved_execution(service, row, request['execution_operation_id'])
    if request['profile'] != 'rdfs':
        raise ValueError('Source-bound reasoning supports rdfs only')
    encoded = request['ontology_base64']
    if not isinstance(encoded, str) or len(encoded) > 4 * ((16384 + 2) // 3):
        raise ValueError('Ontology exceeds bounded input')
    raw = base64.b64decode(encoded, validate=True)
    projection = build_projection(binding['execution_artifact'], workspace_id=row['id'],
        execution_operation_id=request['execution_operation_id'],
        approved_query_artifact=binding['approved_query_artifact'],
        projection_spec=request['projection_spec'], ontology_bytes=raw)
    # Immutable references/hashes avoid duplicating the complete saved query.
    refs = {k: v for k, v in binding.items() if k not in ('execution_artifact', 'approved_query_artifact')}
    plan = {'binding': refs, 'projection': projection, 'profile': 'rdfs',
            'binary_sha256': _binary(service), 'ontology_base64': encoded,
            'projection_spec': deepcopy(request['projection_spec'])}
    return {**plan, 'fingerprint': fingerprint(plan)}


def _checked_plan(service, row, proposal):
    current = _plan(service, row, proposal['request'])
    if current != proposal['result']['plan']:
        raise ValueError('Reasoning plan, source, ontology, or binary changed; propose and approve again')
    if not proposal['result']['eligible']:
        raise ValueError('Reasoning proposal is ineligible')
    return current


def _receipt_statements(receipt, plan, oid, workspace_id, execution_id):
    """Check complete retained evidence before exposing any selectable advice."""
    raw = plan['projection']['combined_input']['text'].encode('utf-8')
    if (receipt.get('status') != 'completed' or receipt.get('reasoning_complete') is not True
            or receipt.get('artifact_completeness') != 'complete'
            or receipt.get('output_limit_reached') is not False
            or receipt.get('binary_sha256') != plan['binary_sha256']
            or receipt.get('profile') != 'rdfs' or receipt.get('input_sha256') != sha256(raw).hexdigest()
            or receipt.get('input_bytes') != len(raw) or receipt.get('asserted_turtle') != raw.decode()):
        raise ValueError('Receipt is incomplete or differs from approved inputs')
    required = {'stdout', 'stderr', 'closure.ttl', 'certificate/asserted.tsv',
                'certificate/asserted.sha256', 'certificate/scope.tsv', 'certificate/derivations.tsv'}
    files = receipt.get('output_files', {})
    if not required.issubset(files):
        raise ValueError('Required complete derivation evidence missing')
    for metadata in files.values():
        if (metadata.get('truncated') is not False or metadata.get('limit_reached') is not False
                or metadata.get('sha256_scope') != 'whole_file'
                or metadata.get('file_bytes') != metadata.get('retained_bytes')):
            raise ValueError('Evidence files are not retained whole')
    closure_text = receipt['closure_turtle']
    if sha256(closure_text.encode()).hexdigest() != receipt['closure_sha256']:
        raise ValueError('Closure hash mismatch')
    for name in ('asserted.tsv', 'asserted.sha256', 'scope.tsv', 'derivations.tsv'):
        item = receipt.get('derivation_artifacts', {}).get(name, {})
        if sha256(item.get('text', '').encode()).hexdigest() != item.get('sha256'):
            raise ValueError('Derivation artifact hash mismatch')
    # Parse saved closure locally; no URL/publicID is passed and no imports fetched.
    closure = Graph().parse(data=closure_text, format='turtle')
    asserted = Graph().parse(data=raw.decode(), format='nt')
    if any(isinstance(term, BNode) for triple in closure for term in triple):
        raise ValueError('Blank nodes unsupported in closure comparison')
    # Turtle may abbreviate xsd:string to a plain literal. Compare these RDF
    # strings identically without changing retained bytes or other datatypes.
    def canonical(triples):
        return {tuple(Literal(str(term), datatype=XSD.string, normalize=False)
                      if isinstance(term, Literal) and term.datatype is None and term.language is None
                      else term for term in triple) for triple in triples}
    asserted_set, closure_set = canonical(asserted), canonical(closure)
    if not asserted_set.issubset(closure_set):
        raise ValueError('Closure omitted approved asserted facts')
    row_prefix = f'urn:factory-lab:query-result:{workspace_id}:{execution_id}:row:'
    rows = {s for s in asserted.subjects() if isinstance(s, URIRef) and str(s).startswith(row_prefix)}
    statements = []
    for triple in sorted(closure_set - asserted_set, key=lambda t: tuple(x.n3() for x in t)):
        canonical = ' '.join(term.n3() for term in triple) + ' .'
        statements.append({'id': sha256((oid + '\n' + canonical).encode()).hexdigest(),
            'triple': canonical, 'subject': str(triple[0]), 'predicate': str(triple[1]),
            'object': str(triple[2]), 'advisory_eligible': triple[0] in rows and triple[1] == RDF.type and isinstance(triple[2], URIRef),
            'classification': 'query_row_classification' if triple[0] in rows and triple[1] == RDF.type else 'other_derived_statement'})
    return statements


def _catalog(service, row, body):
    # Even failed execution sources remain inspectable, but foreign IDs cannot be selected.
    source = service.store.operation(row['id'], body['execution_operation_id'])
    if source['kind'] != 'database_query_execute':
        raise ValueError('Choose a saved query execution')
    page = service.store.operation_page(row['id'], before=body['cursor'])
    items = []
    for summary in page['operations']:
        if summary['kind'] not in ACTIONS:
            continue
        op = service.store.operation(row['id'], summary['id'])
        result = op.get('result') or {}
        execution_id = result.get('execution_operation_id') or op['request'].get('execution_operation_id')
        if execution_id == body['execution_operation_id']:
            items.append({k: deepcopy(op[k]) for k in ('id', 'kind', 'state', 'revision', 'error')} | {
                'execution_operation_id': execution_id, 'status': result.get('status'),
                'eligible': result.get('eligible', False), 'stale': op['revision'] != row['revision']})
    return {'items': items, 'next_cursor': page['operations_next'], 'scanned_count': len(page['operations']),
            'page_scan_limit': 20, 'execution_operation_id': body['execution_operation_id']}


def handle(service, action, body, row):
    if action == 'database_reasoning_catalog':
        return _catalog(service, row, body)
    request = {k: deepcopy(v) for k, v in body.items() if k not in ('action', 'id', 'revision', 'request_key')}
    op, created = service.store.begin(row['id'], row['revision'], body['request_key'], action, request)
    if not created:
        return {'operation': service.store.operation(row['id'], op['id']), 'reused': True}
    result = {'status': 'pending', 'eligible': False, 'receipt': None,
              'execution_operation_id': request.get('execution_operation_id'),
              'workspace': {'id': row['id'], 'revision': row['revision'], 'draft_digest': row['digest']}}
    try:
        if action == 'database_reasoning_propose':
            plan = _plan(service, row, request)
            result.update(plan=plan, status='pending', eligible=True)
        elif action == 'database_reasoning_approve':
            proposal = _saved(service, row, request['proposal_operation_id'], 'database_reasoning_propose')
            result['execution_operation_id'] = proposal['request']['execution_operation_id']
            plan = _checked_plan(service, row, proposal)
            result.update(plan_fingerprint=plan['fingerprint'], review=_review(request),
                          proposal_operation_id=proposal['id'], eligible=True, status='approved')
        elif action == 'database_reasoning_execute':
            approval = _saved(service, row, request['approval_operation_id'], 'database_reasoning_approve')
            proposal = _saved(service, row, approval['request']['proposal_operation_id'], 'database_reasoning_propose')
            result['execution_operation_id'] = proposal['request']['execution_operation_id']
            plan = _checked_plan(service, row, proposal)
            if (approval['result']['plan_fingerprint'] != plan['fingerprint']
                    or approval['result']['review'] != _review(approval['request'])):
                raise ValueError('Reasoning approval binding changed')
            result.update(plan_fingerprint=plan['fingerprint'], proposal_operation_id=proposal['id'],
                          approval_operation_id=approval['id'], policy='advisory', derived_statements=[])
            service.store.checkpoint(op['id'], {**result, 'status': 'reserved_before_launch',
                                      'storage_reservation': ' ' * RECEIPT_RESERVATION})
            cancel = cancellation_callback(service.store, op['id'])
            check_cancel(cancel)
            receipt = service.local_reasoner.run(plan['projection']['combined_input']['text'].encode(), 'rdfs', cancel_requested=cancel)
            result['receipt'] = receipt
            if len(encode(result).encode()) > RECEIPT_RESERVATION:
                result['receipt'] = None
                raise ValueError('Trusted runner exceeded receipt storage boundary')
            # Preserve raw receipt before parsing/qualification, including parser failure.
            service.store.checkpoint(op['id'], result)
            if receipt.get('status') == 'cancelled' or service.store.cancel_requested(op['id']):
                raise ExecutionCancelled('Reasoning cancelled; raw receipt retained')
            statements = _receipt_statements(receipt, plan, op['id'], row['id'], result['execution_operation_id'])
            result.update(status='completed', eligible=True, derived_statements=statements,
                          certificate_verification=receipt.get('certificate_verification', 'not_run'))
        elif action == 'database_reasoning_advisory_use':
            reasoning = _saved(service, row, request['reasoning_operation_id'], 'database_reasoning_execute')
            saved = reasoning['result']
            if saved['execution_operation_id'] != request['execution_operation_id'] or not saved['eligible']:
                raise ValueError('Advice must select this exact complete reasoning result')
            proposal = _saved(service, row, saved['proposal_operation_id'], 'database_reasoning_propose')
            plan = _checked_plan(service, row, proposal)
            if saved['plan_fingerprint'] != plan['fingerprint']:
                raise ValueError('Reasoning binding changed')
            verified_statements = _receipt_statements(saved['receipt'], plan, reasoning['id'], row['id'], request['execution_operation_id'])
            if verified_statements != saved['derived_statements']:
                raise ValueError('Saved derived statements differ from complete receipt')
            selected = request['selected_statement_ids']
            valid = {s['id']: s for s in saved['derived_statements'] if s['advisory_eligible']}
            if (not isinstance(selected, list) or not 1 <= len(selected) <= 200 or
                    any(not isinstance(s, str) or s not in valid for s in selected) or len(set(selected)) != len(selected)):
                raise ValueError('Select distinct derived row classification IDs from the saved receipt')
            interpretation = request['interpretation']
            if not isinstance(interpretation, str) or not interpretation.strip() or len(interpretation) > 4000:
                raise ValueError('Provide a bounded advisory interpretation')
            result.update(status='advisory_use', eligible=True, review=_review(request),
                reasoning_operation_id=reasoning['id'], selected_statement_ids=selected,
                interpretation=interpretation, policy='advisory', original_answer_modified=False)
        else:
            raise ValueError('Unknown source-bound reasoning action')
        if len(encode(result).encode()) > RECEIPT_RESERVATION:
            raise ValueError('Bound result exceeds reserved storage boundary')
        service.store.finish(op['id'], 'completed', result=result)
    except Exception as exc:
        state = 'cancelled' if isinstance(exc, ExecutionCancelled) else 'failed'
        result.update(status=state, eligible=False)
        error = str(exc)[:1000] if isinstance(exc, (ValueError, TypeError, KeyError)) else 'Source-bound reasoning failed (' + type(exc).__name__ + ')'
        try:
            service.store.finish(op['id'], state, result=result, error=error)
        except Exception:
            service.store.fail_preserving_checkpoint(op['id'], error)
    return {'operation': service.store.operation(row['id'], op['id']), 'reused': False}
