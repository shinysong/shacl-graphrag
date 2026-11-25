"""Durable registered-DB model routing over existing approved query execution."""
from copy import deepcopy
from hashlib import sha256
import json

from . import workspace_database_question as coordinator
from . import workspace_query_service as queries
from . import workspace_exploration as exploration
from .workspace_query_contracts import ReviewedQueryContracts
from .workspace_store import ExecutionCancelled, cancellation_callback, check_cancel

MAX_SCAN = 200


class ChildCancelled(RuntimeError):
    """Propagate a saved cancellation past ordinary invalid-tool handling."""



def _binding(row):
    return {'id': row['id'], 'revision': row['revision'], 'draft_digest': row['digest']}


def _current(service, row):
    current = service.store.get(row['id'])
    if _binding(current) != _binding(row) or current.get('archived'):
        raise ValueError('Question requires the current workspace revision and digest')


def validate_approval(service, row, approval_id):
    """Rebuild an exact saved approval using the existing query validators."""
    _current(service, row)
    store = service.store
    op = store.operation(row['id'], approval_id)
    approved = queries._saved(store, row['id'], approval_id, 'database_query_approve')
    proposal_op = store.operation(row['id'], op['request']['proposal_operation_id'])
    pending = queries._saved(store, row['id'], proposal_op['id'], 'database_query_propose')
    binding = _binding(row)
    if (any(result['workspace'] != binding for result in (approved, pending)) or
            any(record['revision'] != row['revision'] for record in (op, proposal_op))):
        raise ValueError('Query approval requires the exact current review revision')
    artifact = approved['artifact']
    relation_ids = approved['relation_operation_ids']
    if pending['relation_operation_ids'] != relation_ids:
        raise ValueError('Query relation references changed')
    relations = queries._relations(store, row['id'], relation_ids, row)
    documents = queries._documents(service, row, artifact['spec'])
    if any(result['reviewed_document_evidence'] != documents for result in (approved, pending)):
        raise ValueError('Query document evidence changed')
    engine = ReviewedQueryContracts(service._database())
    draft = service._database().restore(row['draft'])
    review = artifact['review']
    rebuilt = engine.approve(draft, pending['artifact'], relations=relations,
        actor=review['actor'], note=review['note'], revision=review['revision'],
        human_confirmed=review['human_confirmed'])
    if rebuilt != artifact or review['revision'] != row['revision']:
        raise ValueError('Saved query approval or dependencies changed')
    return deepcopy(artifact)


def build_catalog(service, row, report, cancel):
    """Bounded complete scan; navigation catalogs are not execution authority."""
    catalog = []; cursor = None
    report.update(scanned_count=0, exclusions=[], complete=False, scan_limit=MAX_SCAN,
                  candidate_limit=coordinator.MAX_CATALOG)
    while True:
        check_cancel(cancel)
        page = service.store.operation_page(row['id'], before=cursor)
        # Includes the newly reserved parent operation, explicitly reported below.
        if page['operation_count'] > MAX_SCAN:
            report['operation_count'] = page['operation_count']
            raise ValueError('Model query catalog exceeds 200-operation scan limit')
        for summary in page['operations']:
            report['scanned_count'] += 1
            if report['scanned_count'] > MAX_SCAN:
                raise ValueError('Model query catalog exceeds 200-operation scan limit')
            if summary['kind'] != 'database_query_approve':
                continue
            check_cancel(cancel)
            if summary['state'] != 'completed':
                report['exclusions'].append({'approval_operation_id': summary['id'],
                    'reason': 'Approval operation is not completed', 'state': summary['state']})
                continue
            try:
                artifact = validate_approval(service, row, summary['id'])
            except (ValueError, KeyError, TypeError) as exc:
                report['exclusions'].append({'approval_operation_id': summary['id'],
                    'reason': str(exc)[:1000], 'state': 'unavailable'})
                continue
            spec = artifact['spec']
            # Preserve every validated semantic setting (including distinct and
            # traversal endpoint roles). Dropping settings makes different
            # approved contracts indistinguishable to the selector.
            descriptor = deepcopy(spec)
            fields = artifact['dependencies']['fields']
            if len(fields) > 128:
                raise ValueError('Model query descriptor exceeds 128 approved fields')
            descriptor['fields'] = []
            for entry_id, dependency in sorted(fields.items()):
                entry = dependency['entry']; source = entry['source']
                descriptor['fields'].append({'entry_id': entry_id,
                    'table': source['file'], 'column': source['column'],
                    'source_sha256': source['sha256'], 'reviewed_target': entry['target'],
                    'reviewed_interpretation': entry['interpretation'],
                    'interpretation_origin': 'user_review_not_source_fact'})
            descriptor['relations'] = [{'relation_id': relation_id,
                'child_entry_id': relation['spec']['child_entry_id'],
                'parent_entry_id': relation['spec']['parent_entry_id'],
                'interpretation': relation['spec']['interpretation'],
                'join_policy': relation['spec']['join_policy']}
                for relation_id, relation in sorted(artifact['dependencies']['relations'].items())]
            descriptor.update(approval_operation_id=summary['id'],
                version=artifact['version'], fingerprint=artifact['fingerprint'],
                source=deepcopy(artifact['source']), review_revision=artifact['review']['revision'],
                policy_references=deepcopy(spec.get('policy_references', [])))
            catalog.append(descriptor)
            if len(catalog) > coordinator.MAX_CATALOG:
                raise ValueError('Model query catalog exceeds 20 executable approvals')
        cursor = page['operations_next']
        if cursor is None:
            break
    _current(service, row)
    report.update(complete=True, executable_count=len(catalog))
    return catalog


def handle(service, body, row):
    question = body['question']
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 6000:
        raise ValueError('Question must contain 1..6000 characters')
    store = service.store
    op, created = store.begin(row['id'], row['revision'], body['request_key'],
                             'question', {'question': question})
    if not created:
        return {'operation': store.operation(row['id'], op['id']), 'reused': True}
    trace = {'mode': 'database_question', 'version': coordinator.VERSION, 'question': question,
             'workspace': _binding(row), 'phase': 'catalog', 'evidence': [],
             'answer': None, 'catalog_preflight': {}, 'child_operations': []}
    cancel = cancellation_callback(store, op['id'])

    def checkpoint(value):
        trace.update(deepcopy(value))
        store.checkpoint(op['id'], trace)

    def model_call(messages):
        check_cancel(cancel)
        _current(service, row)
        gateway = service.question_gateway
        receipt_call = getattr(gateway, 'call_with_receipt', None)
        response = (receipt_call(op['id'], messages) if callable(receipt_call) else
                    gateway.call(op['id'], messages))
        try:
            _current(service, row)
        except ValueError:
            trace['response_after_revision_change'] = deepcopy(response)
            checkpoint({})
            raise
        return response

    def explore(arguments):
        check_cancel(cancel)
        _current(service, row)
        result = exploration.execute(row['draft'], arguments)
        result['available_tools'] = [
            {'tool': 'explore_repository', 'descriptor_count': 1},
            {'tool': 'approved_database_query', 'descriptor_count': len(catalog),
             'approval_operation_ids': [item['approval_operation_id'] for item in catalog]}]
        result['capability_notice'] = (
            'Advertised capabilities only. Approved database queries still require exact '
            'typed parameters and dependency/source revalidation at execution. Empty approval '
            'catalog means no advertised business query, not absent source data.')
        _current(service, row)
        return result

    def source_execute(arguments, evidence_id):
        from . import workspace_source_query
        check_cancel(cancel); _current(service,row)
        key='db-source-'+sha256((op['id']+':'+evidence_id).encode()).hexdigest()
        child,created=store.begin(row['id'],row['revision'],key,'database_source_query',{'selection':arguments})
        if not created:
            saved=store.operation(row['id'],child['id'])
            if saved['state']!='completed':raise ValueError('Original source query did not complete; no automatic retry')
            return {'execution_operation_id':child['id'],**deepcopy(saved['result'])}
        try:
            result=workspace_source_query.execute(service._database(),row['draft'],arguments)
            check_cancel(cancel); _current(service,row)
            store.finish(child['id'],'completed',result=result)
            return {'execution_operation_id':child['id'],**result}
        except ExecutionCancelled as exc:
            store.finish(child['id'],'cancelled',error=str(exc)[:1000])
            raise
        except Exception as exc:
            store.finish(child['id'],'failed',error=str(exc)[:1000])
            raise
        finally:
            trace['child_operations'].append({'evidence_id':evidence_id,'operation_id':child['id'],
                'request_key':key,'state':store.operation(row['id'],child['id'])['state'],'reused':not created})
            store.checkpoint(op['id'],trace)

    def execute(approval_id, parameters, evidence_id):
        check_cancel(cancel)
        validate_approval(service, row, approval_id)
        child_key = 'db-question-' + sha256((op['id'] + ':' + evidence_id).encode()).hexdigest()
        child_request = {'action': 'database_query_execute', 'id': row['id'],
            'revision': row['revision'], 'request_key': child_key,
            'approval_operation_id': approval_id, 'parameters': parameters}
        # The normal fixed-query handler owns source checks, limits and durability.
        outcome = None
        try:
            outcome = queries.handle(service, 'database_query_execute', child_request, row,
                                     parent_cancel=cancel)
        finally:
            # The child handler may save a failure and then propagate an unexpected
            # exception. Link that durable attempt even when it did not return.
            progress = store.progress(row['id'], child_key)
            if progress.get('id'):
                trace['child_operations'].append({'evidence_id': evidence_id,
                    'operation_id': progress['id'], 'request_key': child_key,
                    'state': progress['state'],
                    'reused': outcome['reused'] if outcome is not None else None})
                store.checkpoint(op['id'], trace)
        child = outcome['operation']
        if child['state'] == 'cancelled':
            raise ChildCancelled('Child query cancelled; retained saved child evidence')
        if child['state'] != 'completed':
            raise ValueError('Saved query execution failed: ' + str(child.get('error', 'unknown'))[:1000])
        return {'execution_operation_id': child['id'], **deepcopy(child['result'])}

    try:
        checkpoint({})
        check_cancel(cancel)
        if service.question_gateway is None:
            raise ValueError('Question model is not enabled on this server')
        config = service.question_gateway.config
        trace['model'] = config.get('model')
        trace['provider_requested'] = config.get('provider')
        trace['provider_returned'] = None  # Per-call receipts, when available, are authoritative.
        trace['gateway_config_sha256'] = sha256(json.dumps(config, sort_keys=True,
            ensure_ascii=False, allow_nan=False).encode()).hexdigest()
        catalog = build_catalog(service, row, trace['catalog_preflight'], cancel)
        checkpoint({})
        from . import workspace_source_query
        source_catalog=workspace_source_query.catalog(service._database(),row['draft'])
        trace['source_query_catalog']=source_catalog
        coordinator.ask(question, catalog=catalog, call=model_call, execute=execute,
                        checkpoint=checkpoint, check_cancel=lambda: check_cancel(cancel),
                        exploration_catalog=exploration.catalog(row['draft']), explore=explore,
                        source_catalog=source_catalog,source_execute=source_execute)
        check_cancel(cancel)
        _current(service, row)
        store.finish(op['id'], 'completed', result=trace)
    except (ExecutionCancelled, ChildCancelled) as exc:
        store.finish(op['id'], 'cancelled', result=trace, error=str(exc)[:1000])
    except Exception as exc:
        error = (str(exc)[:1000] if isinstance(exc, (ValueError, KeyError, TypeError)) else
                 'Database question failed; original partial evidence retained; no automatic retry')
        try:
            store.finish(op['id'], 'failed', result=trace, error=error)
        except ValueError:
            store.fail_preserving_checkpoint(op['id'], 'Latest trace could not be persisted. ' + error[:850])
    return {'operation': store.operation(row['id'], op['id']), 'reused': False}
