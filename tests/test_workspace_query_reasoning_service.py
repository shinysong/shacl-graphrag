"""Local software boundary checks with fabricated receipts, never native efficacy."""
import base64
from copy import deepcopy
from hashlib import sha256
import sqlite3
from unittest.mock import patch

import pytest
from rdflib import Graph, RDF, URIRef
from apps.factory_lab.workspace_database import SQLiteSources
from apps.factory_lab.workspace_service import WorkspaceService
from apps.factory_lab.workspace_reasoning import LocalReasoner
from apps.factory_lab.workspace_query_reasoning_service import _receipt_statements

NS = 'urn:factory-lab:semantics:'

@pytest.fixture
def prepared(tmp_path):
    source = tmp_path / 'source.sqlite'
    with sqlite3.connect(source) as con:
        con.executescript('CREATE TABLE records(code TEXT); INSERT INTO records VALUES ("a"),("b");')
    registry = SQLiteSources(tmp_path / 'registry')
    pack = registry.register(source, label='Authored reasoning source')
    binary = tmp_path / 'fake-binary'
    binary.write_bytes(b'not executed')
    binary.chmod(0o700)
    service = WorkspaceService(tmp_path / 'store.sqlite', database_registry=registry)
    service.local_reasoner = LocalReasoner(binary)
    row = service.handle({'action': 'create_database', 'title': 'Reasoning', 'source_id': pack['source_id'], 'metadata': {}, 'domain': 'generic'})
    row = service.handle({'action': 'change', 'id': row['id'], 'revision': row['revision'], 'decisions': [
        {'entry_id': e['id'], 'status': 'approved', 'target': 'source_only', 'note': 'Fixture', 'interpretation': 'Recorded field'} for e in row['draft']['entries']]})
    def call(action, key, **kwargs):
        return service.handle({'action': action, 'id': row['id'], 'revision': row['revision'], 'request_key': key, **kwargs})['operation']
    field = {'entry_id': row['draft']['entries'][0]['id'], 'alias': 'r'}
    spec = {'id': 'records', 'title': 'Records', 'question_scope': 'Recorded codes', 'root': field,
        'joins': [], 'parameters': {}, 'filters': [], 'projection': [{'field': field, 'name': 'code'}],
        'group_by': [], 'aggregates': [], 'distinct': False, 'output_kind': 'recorded_facts',
        'limitations': ['Authored software test'], 'policy_references': [],
        'null_policy': 'exclude_from_aggregates_preserve_projection', 'empty_groups': 'absent', 'measure_grain': 'r'}
    pending = call('database_query_propose', 'qp', spec=spec, origin={'kind': 'test'}, relation_operation_ids=[])
    approval = call('database_query_approve', 'qa', proposal_operation_id=pending['id'], note='Fixture review', human_confirmed=True)
    execution = call('database_query_execute', 'qe', approval_operation_id=approval['id'], parameters={})
    assert execution['state'] == 'completed', execution
    projection = {'row_class_iri': NS+'Row', 'columns': [{'output_name': 'code', 'predicate_iri': NS+'code', 'datatype': 'text'}],
        'null_policy': 'omit_with_manifest', 'subject_policy': 'execution_row_ordinal',
        'interpretation': 'Recorded observations', 'limitations': ['No external truth']}
    proposal_args = {'execution_operation_id': execution['id'], 'projection_spec': projection,
        'ontology_base64': base64.b64encode(f'<{NS}Row> <http://www.w3.org/2000/01/rdf-schema#subClassOf> <{NS}Evidence> .'.encode()).decode(), 'profile': 'rdfs'}
    return service, row, call, execution, proposal_args


def fake_receipt(binary, raw, **kwargs):
    graph = Graph().parse(data=raw.decode(), format='nt')
    for subject in list(graph.subjects(RDF.type, URIRef(NS+'Row'))):
        graph.add((subject, RDF.type, URIRef(NS+'Evidence')))
    closure = graph.serialize(format='nt')
    names = ['stdout', 'stderr', 'closure.ttl', 'certificate/asserted.tsv', 'certificate/asserted.sha256', 'certificate/scope.tsv', 'certificate/derivations.tsv']
    return {'status': 'completed', 'reasoning_complete': True, 'artifact_completeness': 'complete',
        'output_limit_reached': False, 'binary_sha256': sha256(binary.read_bytes()).hexdigest(),
        'input_sha256': sha256(raw).hexdigest(), 'input_bytes': len(raw), 'asserted_turtle': raw.decode(),
        'profile': 'rdfs', 'certificate_verification': 'not_run', 'closure_turtle': closure,
        'closure_sha256': sha256(closure.encode()).hexdigest(),
        'output_files': {name: {'truncated': False, 'limit_reached': False, 'sha256_scope': 'whole_file', 'file_bytes': 0, 'retained_bytes': 0} for name in names},
        'derivation_artifacts': {name.split('/')[-1]: {'text': '', 'sha256': sha256(b'').hexdigest()} for name in names if name.startswith('certificate/')}}


def approved(prepared):
    service, row, call, execution, args = prepared
    proposal = call('database_reasoning_propose', 'rp', **args)
    assert proposal['state'] == 'completed', proposal.get('error')
    approval = call('database_reasoning_approve', 'ra', proposal_operation_id=proposal['id'], note='Reviewed ontology', human_confirmed=True)
    assert approval['state'] == 'completed', approval
    return proposal, approval


def test_lifecycle_replay_advice_preserves_answer(prepared):
    service, row, call, execution, args = prepared
    proposal, approval = approved(prepared)
    service.local_reasoner.runner = fake_receipt
    with patch.object(service.local_reasoner, 'run', wraps=service.local_reasoner.run) as run:
        result = call('database_reasoning_execute', 're', approval_operation_id=approval['id'])
        assert result['state'] == 'completed', result
        assert run.call_count == 1
    statements = result['result']['derived_statements']
    assert len(statements) == 2
    assert all(s['advisory_eligible'] for s in statements)
    advice = call('database_reasoning_advisory_use', 'use', reasoning_operation_id=result['id'],
        execution_operation_id=execution['id'], selected_statement_ids=[statements[0]['id']],
        interpretation='Reviewed row evidence under declared hierarchy', note='Fixture only', human_confirmed=True)
    assert advice['state'] == 'completed', advice
    assert service.store.operation(row['id'], execution['id']) == execution
    service.local_reasoner = None
    assert call('database_reasoning_execute', 're', approval_operation_id=approval['id']) == result
    page = service.handle({'action': 'database_reasoning_catalog', 'id': row['id'], 'revision': row['revision'], 'execution_operation_id': execution['id'], 'cursor': None})
    assert len(page['items']) == 4


@pytest.mark.parametrize('fault', ['missing_derivation', 'partial', 'closure_omission', 'input', 'limit'])
def test_incomplete_receipts_retained_never_retried(prepared, fault):
    service, row, call, execution, args = prepared
    proposal, approval = approved(prepared)
    def runner(*a, **kw):
        receipt = fake_receipt(*a, **kw)
        if fault == 'missing_derivation': receipt['output_files'].pop('certificate/derivations.tsv')
        if fault == 'partial': receipt['reasoning_complete'] = False
        if fault == 'closure_omission':
            receipt['closure_turtle'] = ''
            receipt['closure_sha256'] = sha256(b'').hexdigest()
        if fault == 'input': receipt['input_sha256'] = 'bad'
        if fault == 'limit': receipt['output_limit_reached'] = True
        return receipt
    service.local_reasoner.runner = runner
    with patch.object(service.local_reasoner, 'run', wraps=service.local_reasoner.run) as run:
        failed = call('database_reasoning_execute', 're', approval_operation_id=approval['id'])
        assert failed['state'] == 'failed', failed
        assert failed['result']['receipt'] is not None
        assert failed['result']['derived_statements'] == []
        assert call('database_reasoning_execute', 're', approval_operation_id=approval['id']) == failed
        assert run.call_count == 1


def test_binary_swap_and_reservation_block_launch(prepared):
    service, row, call, execution, args = prepared
    proposal, approval = approved(prepared)
    with patch.object(service.local_reasoner, 'run') as run:
        with patch('apps.factory_lab.workspace_store.MAX_STORED_BYTES', 100000):
            failed = call('database_reasoning_execute', 'capacity', approval_operation_id=approval['id'])
        assert failed['state'] == 'failed'
        assert not run.called
        service.local_reasoner.binary.write_bytes(b'changed binary')
        failed = call('database_reasoning_execute', 'swap', approval_operation_id=approval['id'])
        assert failed['state'] == 'failed'
        assert not run.called


def test_invalid_proposal_is_durable_before_source_restore(prepared):
    service, row, call, execution, args = prepared
    service.database_adapter = None
    failed = call('database_reasoning_propose', 'rp', **args)
    assert failed['state'] == 'failed'
    service.local_reasoner = None
    assert call('database_reasoning_propose', 'rp', **args) == failed


def test_source_validator_never_executes_answer_and_foreign_kind_retained(prepared):
    service, row, call, execution, args = prepared
    with patch('apps.factory_lab.workspace_query_contracts.ReviewedQueryContracts.execute', side_effect=AssertionError('Answer rerun forbidden')):
        proposal, approval = approved(prepared)
    bad = call('database_reasoning_propose', 'wrong-kind', **{**args, 'execution_operation_id': proposal['id']})
    assert bad['state'] == 'failed'
    foreign = service.store.create('Other workspace', row['draft'])
    with pytest.raises(ValueError):
        service.store.operation(foreign['id'], execution['id'])


def test_forged_statement_and_stale_revision_no_launch(prepared):
    service, row, call, execution, args = prepared
    proposal, approval = approved(prepared)
    service.local_reasoner.runner = fake_receipt
    completed = call('database_reasoning_execute', 're', approval_operation_id=approval['id'])
    bad = call('database_reasoning_advisory_use', 'forged', reasoning_operation_id=completed['id'],
        execution_operation_id=execution['id'], selected_statement_ids=['f'*64], interpretation='Unknown', note='Test', human_confirmed=True)
    assert bad['state'] == 'failed'
    changed = service.store.save(row['id'], {**row['draft'], 'test_change': True}, row['revision'])
    with patch.object(service.local_reasoner, 'run') as run:
        stale = service.handle({'action': 'database_reasoning_execute', 'id': row['id'], 'revision': changed['revision'],
            'request_key': 'stale', 'approval_operation_id': approval['id']})['operation']
        assert stale['state'] == 'failed'
        assert not run.called


def test_changed_parameters_and_missing_source_block_before_launch(prepared):
    service, row, call, execution, args = prepared
    proposal, approval = approved(prepared)
    original = service.store.operation
    def tampered(wid, oid):
        value = original(wid, oid)
        if oid == execution['id']:
            value['request']['parameters'] = {'injected': 1}
        return value
    with patch.object(service.store, 'operation', side_effect=tampered), patch.object(service.local_reasoner, 'run') as run:
        failure = call('database_reasoning_execute', 'tampered', approval_operation_id=approval['id'])
        assert failure['state'] == 'failed'
        assert not run.called

@pytest.mark.parametrize('replacement', ['plain', 'language', 'different'])
def test_turtle_string_abbreviation_only(prepared, replacement):
    """Actual OO uses plain Turtle strings; language/value changes are not equal."""
    from rdflib import Literal, XSD
    service, row, call, execution, args = prepared
    proposal, approval = approved(prepared)
    def runner(*a, **kw):
        receipt = fake_receipt(*a, **kw)
        graph = Graph().parse(data=receipt['closure_turtle'], format='turtle')
        for s, p, o in list(graph):
            if isinstance(o, Literal) and o.datatype == XSD.string:
                graph.remove((s, p, o))
                value = Literal(str(o)) if replacement == 'plain' else (
                    Literal(str(o), lang='en') if replacement == 'language' else Literal(str(o)+'changed'))
                graph.add((s, p, value))
        receipt['closure_turtle'] = graph.serialize(format='turtle')
        receipt['closure_sha256'] = sha256(receipt['closure_turtle'].encode()).hexdigest()
        return receipt
    service.local_reasoner.runner = runner
    result = call('database_reasoning_execute', 'abbreviation', approval_operation_id=approval['id'])
    assert result['state'] == ('completed' if replacement == 'plain' else 'failed')
    assert result['result']['receipt'] is not None
    if replacement == 'plain':
        assert len(result['result']['derived_statements']) == 2
        assert all(s['advisory_eligible'] for s in result['result']['derived_statements'])
    else:
        assert 'omitted' in result['error']
