"""Durable reviewed queries; clients select saved artifacts, never approve by flag.

Typed execution is separate from natural-language interpretation. Review records
are local user decisions, not authenticated identities or correctness guarantees.
"""
from copy import deepcopy
from .workspace_store import cancellation_callback, check_cancel, ExecutionCancelled
from .workspace_query_contracts import ReviewedQueryContracts
from .workspace_extension_relations import (
    ORIGIN_FORMAT, ORIGIN_KIND, relation_origin, rejection_origin,
)

ACTIONS = {
    'database_review_catalog': {'id','revision','category','cursor'},
    'database_relation_propose': {'id','revision','request_key','spec','origin'},
    'database_external_relation_propose': {'id','revision','request_key','operation_id','candidate_id','spec','edit_reason'},
    'database_external_relation_reject': {'id','revision','request_key','operation_id','candidate_id','reason'},
    'database_relation_approve': {'id','revision','request_key','proposal_operation_id','note','human_confirmed'},
    'database_query_propose': {'id','revision','request_key','spec','origin','relation_operation_ids'},
    'database_query_approve': {'id','revision','request_key','proposal_operation_id','note','human_confirmed'},
    'database_query_execute': {'id','revision','request_key','approval_operation_id','parameters'},
}

CATALOG_KINDS = {
    'relation': {'database_relation_propose', 'database_relation_approve',
                 'database_external_relation_propose', 'database_external_relation_reject'},
    'query': {'database_query_propose', 'database_query_approve'},
    'paragraph': {'database_document_review'},
}


def _public_fields(value, names):
    return {name: deepcopy(value[name]) for name in names.split() if name in value}


def _descriptor(operation):
    """Saved navigation metadata, never a verification or approval decision."""
    result = operation.get('result') or {}
    artifact = result.get('artifact') or {}
    spec = artifact.get('spec') or {}
    request = operation.get('request') or {}
    completed = operation['state'] == 'completed'
    approval = operation['kind'].endswith('_approve')
    paragraph = operation['kind'] == 'database_document_review'
    item = _public_fields(operation, 'id kind revision created updated')
    item.update(operation_id=operation['id'], operation_state=operation['state'],
                artifact_state=(result.get('status', 'unknown') if paragraph else
                                artifact.get('status', 'unknown')) if completed else 'not_saved',
                readiness='unknown', readiness_check='not_checked',
                readiness_reasons=[{'code': 'authoritative_checks_not_run',
                                    'dependency_ids': []}],
                proposal_operation_id=(request.get('proposal_operation_id') if approval else
                                       None if paragraph else operation['id']),
                approval_operation_id=operation['id'] if approval and completed else None,
                source_binding=_public_fields(result.get('binding') or artifact.get('source') or {},
                                              'source_id label snapshot_sha256'))
    if operation['kind'] == 'database_external_relation_reject':
        rejected = result.get('rejection') or {}
        item.update(artifact_state='rejected' if completed else 'not_saved',
                    proposal_operation_id=None, approval_operation_id=None,
                    external_relation=True, decision='rejected',
                    scope=result.get('scope'), reason=rejected.get('reason'),
                    import_operation_id=request.get('operation_id'),
                    candidate_id=request.get('candidate_id'),
                    source_binding=_public_fields(rejected.get('source') or {},
                        'source_id label snapshot_sha256'))
        return item
    if paragraph:
        item.update(review_operation_id=operation['id'],
                    interpretation=result.get('interpretation'),
                    document=_public_fields(result.get('paragraph') or {},
                        'document_id label version document_sha256 paragraph_id paragraph_sha256 line_start line_end'))
    else:
        item.update(_public_fields(spec, 'title question_scope parameters output_kind interpretation join_policy query_kind direction budgets seed_parameter node_key_type'))
        # Logical IDs must not replace the saved operation's identity.
        item['logical_id'] = spec.get('id')
        item['fingerprint'] = artifact.get('fingerprint')
        item['review_revision'] = (artifact.get('review') or {}).get('revision')
        item['relation_operation_ids'] = deepcopy(result.get('relation_operation_ids', []))
        origin = artifact.get('origin') or {}
        if origin.get('format') == ORIGIN_FORMAT:
            item.update(external_relation=True, import_operation_id=origin.get('import_operation_id'),
                        candidate_id=origin.get('candidate_id'), raw_sha256=origin.get('raw_sha256'),
                        endpoint_edit=origin.get('endpoint_edit'))
        item['policy_review_operation_ids'] = [ref['review_operation_id'] for ref in
            spec.get('policy_references', []) if isinstance(ref, dict) and 'review_operation_id' in ref]
        for side in ('child', 'parent'):
            entry_id = spec.get(side + '_entry_id')
            if entry_id is not None:
                dependency = artifact.get('dependencies', {}).get(entry_id, {})
                source = dependency.get('entry', {}).get('source', {})
                item[side] = {'entry_id': entry_id, 'table': source.get('file'),
                              'column': source.get('column')}
    return item


def _catalog(service, engine, body, row):
    category = body['category']
    if not isinstance(category, str) or category not in CATALOG_KINDS:
        raise ValueError('Choose relation, query, or paragraph catalog')
    page = service.store.operation_page(row['id'], before=body['cursor'])
    items = [_descriptor(service.store.operation(row['id'], summary['id']))
             for summary in page['operations'] if summary['kind'] in CATALOG_KINDS[category]]
    return {'category': category, 'items': items, 'next_cursor': page['operations_next'],
            'scanned_count': len(page['operations']), 'page_scan_limit': 20,
            'workspace': {'id': row['id'], 'revision': row['revision']},
            'capabilities': {
                'documents_configured': service.source_documents is not None,
                'readiness_preflight': False,
                'query_families': ['relational', 'directed_reachability'],
                'directed_reachability': {
                    'version': 'reviewed-query-reachability-1',
                    'directions': ['forward', 'reverse'],
                    'node_key_types': ['integer', 'text'],
                    'comparison': 'binary_exact', 'endpoint_relation_approvals': 2,
                    'seed_policy': 'require_existing_node', 'include_seed': False,
                    'max_depth': 128, 'max_nodes': 10000, 'max_edges': 100000,
                    'node_budget_includes_seed': True,
                    'incomplete_total': None,
                    'display_truncation_separate_from_closure': True,
                    'identity_integer_encoding': 'decimal_integer_string',
                    'timeout_scope': 'invocation_elapsed_checked_after_restore_and_during_snapshot_work',
                    'restore_interruption': 'registry_owned_limits_not_traversal_progress_handler',
                },
                'parameter_types': ['text', 'integer', 'number', 'date'],
                'filter_operators': ['eq', 'lt', 'lte', 'gt', 'gte', 'is_null'],
                'filter_combination': 'and',
                'aggregate_operators': ['sum', 'count_rows', 'count_distinct', 'sum_product'],
                'scalar_bindings': {
                    'max_bindings': 4, 'source_scope': 'same_immutable_snapshot',
                    'selector': 'single_field_equality', 'cardinality': 'exactly_one',
                    'null_policy': 'require_nonnull', 'comparison': 'binary_exact',
                    'client_value_override': False,
                },
                'typed_comparisons': {
                    'operators': ['eq', 'lt', 'lte', 'gt', 'gte'],
                    'right_operands': ['field', 'scalar'],
                    'null_policy': 'unknown_excluded', 'comparison': 'binary_exact',
                },
                'sum_product': {
                    'operand_count': 2, 'operand_scope': 'root_alias',
                    'numeric_type': 'integer', 'range': 'signed_64_bit',
                    'null_policy': 'exclude_if_any_operand_null',
                    'overflow_policy': 'fail_product_or_final_sum',
                    'value_encoding': 'decimal_integer_string',
                    'unit': 'reviewed_annotation_not_dimensional_verification',
                },
                'join_policy': 'left_many_to_one_preserve_root',
                'sum_grain': 'root', 'measure_grain': 'root_alias',
                'null_policy': 'exclude_from_aggregates_preserve_projection',
                'empty_groups': 'absent', 'distinct': True,
                'output_kinds': ['recorded_facts', 'prerequisite_candidates', 'potential_impact_candidates'],
                'limits': {'max_rows': engine.max_rows, 'max_bytes': engine.max_bytes,
                           'timeout_seconds': engine.timeout, 'max_steps': engine.max_steps,
                           'joins': 8, 'filters': 20, 'projection': 30, 'group_by': 20,
                           'aggregates': 20, 'parameters': 20, 'policy_references': 20,
                           'contract_bytes': 65536},
                'timeout_scope': 'final_snapshot_execution_after_preparatory_validation',
            }}


def _saved(store, key, operation_id, kind):
    if not isinstance(operation_id,str):
        raise ValueError('Choose a saved operation')
    operation=store.operation(key,operation_id)
    if operation['kind']!=kind or operation['state']!='completed':
        raise ValueError('Choose the required completed operation in this workspace')
    return operation['result']


def _reject_reserved_origin(origin):
    if isinstance(origin, dict) and (origin.get('format') == ORIGIN_FORMAT or
                                    origin.get('kind') == ORIGIN_KIND):
        raise ValueError('External relation provenance requires a saved external candidate proposal')


def _relation_proposal(store, row, operation_id):
    """Rebuild reserved external origin from its saved import on every use."""
    operation = store.operation(row['id'], operation_id)
    if operation['state'] != 'completed' or operation['kind'] not in (
            'database_relation_propose', 'database_external_relation_propose'):
        raise ValueError('Choose a completed local or external relation proposal')
    artifact = operation['result']['artifact']
    if operation['kind'] == 'database_relation_propose':
        _reject_reserved_origin(artifact['origin'])
    else:
        request = operation['request']
        imported = store.operation(row['id'], request['operation_id'])
        origin = relation_origin(imported, row, candidate_id=request['candidate_id'],
                                 spec=request['spec'], edit_reason=request['edit_reason'])
        if artifact['origin'] != origin or artifact['spec'] != request['spec']:
            raise ValueError('Saved external relation provenance changed')
    return artifact


def _relations(store,key,ids,row):
    if (not isinstance(ids,list) or len(ids)>8 or any(not isinstance(i,str) for i in ids)
            or len(set(ids))!=len(ids)):
        raise ValueError('Choose distinct saved relation approvals')
    result={}
    for oid in ids:
        approved = store.operation(key, oid)
        artifact=_saved(store,key,oid,'database_relation_approve')['artifact']
        proposal = _relation_proposal(store, row, approved['request']['proposal_operation_id'])
        if (artifact['origin'] != proposal['origin'] or artifact['spec'] != proposal['spec'] or
                artifact['fingerprint'] != proposal['fingerprint']):
            raise ValueError('Relation approval differs from its saved proposal')
        rid=artifact['spec']['id']
        if rid in result:raise ValueError('Duplicate relation identifier')
        result[rid]=artifact
    return result


def _documents(service,row,spec):
    refs=spec.get('policy_references')
    if not isinstance(refs,list) or len(refs)>20:
        raise ValueError('Provide bounded reviewed policy references')
    evidence=[]
    for ref in refs:
        if not isinstance(ref,dict) or set(ref)!={'review_operation_id'}:
            raise ValueError('Policy references must select saved paragraph reviews')
        saved=_saved(service.store,row['id'],ref['review_operation_id'],'database_document_review')
        binding={'source_id':row['draft']['database']['source_id'],
                 'snapshot_sha256':row['draft']['database']['snapshot_sha256']}
        if saved['binding']!=binding or service.source_documents is None:
            raise ValueError('Reviewed document source is unavailable or changed')
        r=saved['reference']
        paragraph=service.source_documents.read_paragraph(r['document_id'],r['paragraph_id'],
            **binding,document_sha256=r['document_sha256'])
        if paragraph!=saved['paragraph']:raise ValueError('Reviewed paragraph changed')
        evidence.append({'review_operation_id':ref['review_operation_id'],**deepcopy(saved)})
    return evidence


def handle(service,action,body,row, *, parent_cancel=None):
    store=service.store
    if action == 'database_review_catalog':
        return _catalog(service, ReviewedQueryContracts(service._database()), body, row)
    key=row['id']; revision=row['revision']
    request={k:deepcopy(v) for k,v in body.items() if k not in ('action','id','revision','request_key')}
    op,created=store.begin(key,revision,body['request_key'],action,request)
    if created:
        try:
            # Reserve before touching source configuration or snapshot bytes.
            # Replays return their durable outcome even when a source goes away.
            own_cancel = cancellation_callback(store, op['id']) if action == 'database_query_execute' else None
            cancel = ((lambda: own_cancel() or bool(parent_cancel and parent_cancel()))
                      if own_cancel is not None else None)
            check_cancel(cancel)
            adapter=service._database(); engine=ReviewedQueryContracts(adapter)
            draft=adapter.restore(row['draft'])
            relations_ids=[]; documents=[]
            if action=='database_relation_propose':
                _reject_reserved_origin(body['origin'])
                artifact=engine.propose_relation(draft,body['spec'],origin=body['origin'])
            elif action=='database_external_relation_propose':
                imported=store.operation(key,body['operation_id'])
                origin=relation_origin(imported,row,candidate_id=body['candidate_id'],
                                       spec=body['spec'],edit_reason=body['edit_reason'])
                artifact=engine.propose_relation(draft,body['spec'],origin=origin)
            elif action=='database_external_relation_reject':
                imported=store.operation(key,body['operation_id'])
                rejection=rejection_origin(imported,row,candidate_id=body['candidate_id'],reason=body['reason'])
                result={'status':'rejected','scope':rejection['scope'],'rejection':rejection,
                        'workspace':{'id':key,'revision':revision,'draft_digest':row['digest']}}
                store.finish(op['id'],'completed',result=result)
                return {'operation':store.operation(key,op['id']),'reused':False}
            elif action=='database_relation_approve':
                pending=_relation_proposal(store,row,body['proposal_operation_id'])
                artifact=engine.approve_relation(draft,pending,actor='local_workspace_user',note=body['note'],
                    revision=revision,human_confirmed=body['human_confirmed'])
            elif action=='database_query_propose':
                relations_ids=body['relation_operation_ids']
                relations=_relations(store,key,relations_ids,row)
                _reject_reserved_origin(body['origin'])
                documents=_documents(service,row,body['spec'])
                artifact=engine.propose(draft,body['spec'],relations=relations,origin=body['origin'])
            elif action=='database_query_approve':
                pending=_saved(store,key,body['proposal_operation_id'],'database_query_propose')
                relations_ids=pending['relation_operation_ids'];relations=_relations(store,key,relations_ids,row)
                documents=_documents(service,row,pending['artifact']['spec'])
                artifact=engine.approve(draft,pending['artifact'],relations=relations,
                    actor='local_workspace_user',note=body['note'],revision=revision,human_confirmed=body['human_confirmed'])
            elif action=='database_query_execute':
                approved=_saved(store,key,body['approval_operation_id'],'database_query_approve')
                relations_ids=approved['relation_operation_ids'];relations=_relations(store,key,relations_ids,row)
                documents=_documents(service,row,approved['artifact']['spec'])
                check_cancel(cancel)
                artifact=engine.execute(draft,approved['artifact'],body['parameters'],relations=relations, cancel_requested=cancel)
            else:
                raise ValueError('Unknown reviewed query action')
            result={'artifact':artifact,'relation_operation_ids':deepcopy(relations_ids),
                    'reviewed_document_evidence':documents,
                    'policy_interpretation_verified':False,
                    'workspace':{'id':key,'revision':revision,'draft_digest':row['digest']}}
            store.finish(op['id'],'completed',result=result)
        except ExecutionCancelled as exc:
            store.finish(op['id'],'cancelled', result={'artifact': getattr(exc, 'evidence', {'status': 'cancelled', 'rows': [], 'closure_complete': False})}, error=str(exc))
        except (ValueError,TypeError,KeyError) as exc:
            store.finish(op['id'],'failed',error=str(exc)[:1000])
        except Exception:
            store.finish(op['id'],'failed',error='Reviewed query failed; inspect saved attempt before retry')
            raise
    return {'operation':store.operation(key,op['id']),'reused':not created}


def validate_saved_execution(service, row, execution_operation_id):
    """Read-only source/dependency validation, with no execution of answer SQL.

    Restores the registered immutable source and recompiles the saved contracts.
    Conservatively requires this exact workspace revision and digest. Returns only
    server-loaded artifacts; callers must bind their hashes in subsequent plans.
    """
    from .workspace_query_contracts import fingerprint
    store = service.store
    execution = store.operation(row['id'], execution_operation_id)
    result = _saved(store, row['id'], execution_operation_id, 'database_query_execute')
    expected_workspace = {'id': row['id'], 'revision': row['revision'], 'draft_digest': row['digest']}
    if result['workspace'] != expected_workspace or execution['revision'] != row['revision']:
        raise ValueError('Saved query execution requires the same workspace revision and digest')
    approval_id = execution['request']['approval_operation_id']
    approval_op = store.operation(row['id'], approval_id)
    approved = _saved(store, row['id'], approval_id, 'database_query_approve')
    pending = _saved(store, row['id'], approval_op['request']['proposal_operation_id'], 'database_query_propose')
    if any(item['workspace'] != expected_workspace for item in (approved, pending)):
        raise ValueError('Query review revision changed')
    artifact = approved['artifact']
    if artifact['spec'].get('query_kind') or artifact['version'].endswith('reachability-1'):
        raise ValueError('Only ordinary relational query results support reasoning')
    adapter = service._database()
    engine = ReviewedQueryContracts(adapter)
    draft = adapter.restore(row['draft'])
    relation_ids = approved['relation_operation_ids']
    if pending['relation_operation_ids'] != relation_ids or result['relation_operation_ids'] != relation_ids:
        raise ValueError('Query relation references changed')
    relations = _relations(store, row['id'], relation_ids, row)
    documents = _documents(service, row, artifact['spec'])
    review = artifact['review']
    rebuilt = engine.approve(draft, pending['artifact'], relations=relations,
        actor=review['actor'], note=review['note'], revision=review['revision'],
        human_confirmed=review['human_confirmed'])
    if rebuilt != artifact or review['revision'] != row['revision']:
        raise ValueError('Query approval or dependencies changed')
    if any(item['reviewed_document_evidence'] != documents for item in (result, approved, pending)):
        raise ValueError('Query document evidence changed')
    provenance = result['artifact']['provenance']
    expected = {'contract_fingerprint': artifact['fingerprint'], 'review': artifact['review'],
        'origin': artifact['origin'], 'source': artifact['source'],
        'dependency_fingerprint': fingerprint(artifact['dependencies']),
        'dependencies': artifact['dependencies'], 'parameters': execution['request']['parameters']}
    if provenance != expected:
        raise ValueError('Saved result provenance or parameters changed')
    return {'execution_artifact': deepcopy(result['artifact']),
            'approved_query_artifact': deepcopy(artifact),
            'execution_operation_id': execution_operation_id, 'approval_operation_id': approval_id,
            'execution_sha256': fingerprint(result), 'approval_sha256': fingerprint(approved),
            'proposal_sha256': fingerprint(pending), 'workspace': expected_workspace}
