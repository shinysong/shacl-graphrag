"""Behavioral checks for full-snapshot reviewed query contracts."""
from copy import deepcopy
import sqlite3

import pytest

from apps.factory_lab.workspace_database import DatabaseSourceError, SQLiteSources
from apps.factory_lab.workspace_database_adapter import DatabaseWorkspaceAdapter
from apps.factory_lab.workspace_query_contracts import ReviewedQueryContracts


@pytest.fixture
def setup_query(tmp_path):
    db = tmp_path / 'input.sqlite'
    with sqlite3.connect(db) as con:
        con.executescript('''
            CREATE TABLE owners (id INTEGER PRIMARY KEY, status TEXT);
            CREATE TABLE facts (id INTEGER PRIMARY KEY, owner INTEGER REFERENCES owners(id), quantity INTEGER, day TEXT);
            INSERT INTO owners VALUES (1, 'ready'), (2, 'pending');
            INSERT INTO facts VALUES (1,1,3,'2026-01-01'), (2,1,5,'2026-01-02'),
              (3,2,7,'2026-01-03'), (4,NULL,NULL,'2026-01-04'), (5,999,11,'2026-01-05');
        ''')
    registry = SQLiteSources(tmp_path / 'registry')
    source = registry.register(db)
    adapter = DatabaseWorkspaceAdapter(registry)
    draft = adapter.create(source['source_id'])
    for e in draft['entries']:
        e.update(status='approved', interpretation='Source column, human reviewed')
    ids = {(e['source']['file'], e['source']['column']): e['id'] for e in draft['entries']}
    engine = ReviewedQueryContracts(adapter)
    def ref(table, column, alias=None):
        return {'entry_id': ids[table, column], 'alias': alias or table}
    relation = engine.propose_relation(draft, {
        'id': 'owner_link', 'child_entry_id': ids['facts', 'owner'],
        'parent_entry_id': ids['owners', 'id'], 'interpretation': 'Recorded owner reference',
        'join_policy': 'left_many_to_one_preserve_root'}, origin={'kind': 'human_configuration'})
    review = dict(actor='operator', note='Reviewed exact interpretation', revision=1, human_confirmed=True)
    relation = engine.approve_relation(draft, relation, **review)
    spec = {'id': 'quantity', 'title': 'Quantity by owner', 'question_scope': 'Recorded ready-owner quantities',
            'root': ref('facts', 'id'),
            'joins': [{'relation_id': 'owner_link', 'child_alias': 'facts', 'parent_alias': 'owners'}],
            'parameters': {'status': 'text'},
            'filters': [{'field': ref('owners', 'status'), 'op': 'eq', 'parameter': 'status'}],
            'projection': [{'field': ref('facts', 'owner'), 'name': 'owner'}],
            'group_by': [ref('facts', 'owner')],
            'aggregates': [{'op': 'sum', 'field': ref('facts', 'quantity'), 'name': 'quantity'}],
            'distinct': False, 'output_kind': 'recorded_facts',
            'limitations': ['No policy eligibility or current freshness claim'], 'policy_references': [],
            'null_policy': 'exclude_from_aggregates_preserve_projection', 'empty_groups': 'absent', 'measure_grain': 'facts'}
    return engine, draft, {'owner_link': relation}, spec, review, ref


def approve(setup_query, spec=None):
    engine, draft, relations, original, review, _ = setup_query
    proposed = engine.propose(draft, spec or original, relations=relations, origin={'kind': 'human_configuration'})
    return engine.approve(draft, proposed, relations=relations, **review)


def test_join_sum_over_complete_snapshot(setup_query):
    engine, draft, relations, _, _, _ = setup_query
    artifact = approve(setup_query)
    result = engine.execute(draft, artifact, {'status': 'ready'}, relations=relations)
    assert result['rows'] == [{'owner': 1, 'quantity': 8}]
    assert result['matched_root_rows'] == 2
    assert result['provenance']['contract_fingerprint'] == artifact['fingerprint']
    assert result['scope'] == 'complete_registered_snapshot_query_not_external_truth'


def test_no_implicit_approval_and_tamper(setup_query):
    engine, draft, relations, spec, review, _ = setup_query
    pending = engine.propose(draft, spec, relations=relations, origin={})
    with pytest.raises(DatabaseSourceError, match='approval'):
        engine.execute(draft, pending, {'status': 'ready'}, relations=relations)
    with pytest.raises(DatabaseSourceError, match='approval'):
        engine.approve(draft, pending, relations=relations, **{**review, 'human_confirmed': False})
    approved = approve(setup_query)
    approved['spec']['filters'] = []
    with pytest.raises(DatabaseSourceError, match='changed'):
        engine.execute(draft, approved, {}, relations=relations)


def test_exact_dependency_change_invalidates_but_unrelated_field_does_not(setup_query):
    engine, draft, relations, _, _, ref = setup_query
    approved = approve(setup_query)
    changed = deepcopy(draft)
    next(e for e in changed['entries'] if e['id'] == ref('facts', 'day')['entry_id'])['interpretation'] = 'Other calendar meaning'
    assert engine.execute(changed, approved, {'status': 'ready'}, relations=relations)['rows']
    next(e for e in changed['entries'] if e['id'] == ref('facts', 'quantity')['entry_id'])['interpretation'] = 'Changed units'
    with pytest.raises(DatabaseSourceError, match='stale'):
        engine.execute(changed, approved, {'status': 'ready'}, relations=relations)


def test_left_join_retains_orphans_and_nulls_no_silent_loss(setup_query):
    engine, draft, relations, spec, _, ref = setup_query
    spec = deepcopy(spec); spec.update(parameters={}, filters=[], group_by=[], aggregates=[],
        projection=[{'field': ref('facts', 'id'), 'name': 'id'}, {'field': ref('owners', 'status'), 'name': 'status'}])
    result = engine.execute(draft, approve(setup_query, spec), {}, relations=relations)
    assert result['matched_root_rows'] == 5
    assert result['rows'][-2:] == [{'id': 4, 'status': None}, {'id': 5, 'status': None}]


def test_parameter_values_are_not_sql_and_dates_are_typed(setup_query):
    engine, draft, relations, spec, _, ref = setup_query
    artifact = approve(setup_query)
    assert engine.execute(draft, artifact, {'status': "ready' OR 1=1 --"}, relations=relations)['rows'] == []
    with pytest.raises(DatabaseSourceError, match='type'):
        engine.execute(draft, artifact, {'status': 3}, relations=relations)
    spec = deepcopy(spec)
    spec['parameters'] = {'cutoff': 'date'}
    spec['filters'] = [{'field': ref('facts', 'day'), 'op': 'lte', 'parameter': 'cutoff'}]
    artifact = approve(setup_query, spec)
    assert engine.execute(draft, artifact, {'cutoff': '2026-01-02'}, relations=relations)['rows'] == [{'owner': 1, 'quantity': 8}]
    with pytest.raises(DatabaseSourceError, match='type'):
        engine.execute(draft, artifact, {'cutoff': '2026-02-30'}, relations=relations)


def test_output_limit_after_full_aggregation(setup_query):
    engine, draft, relations, spec, _, _ = setup_query
    spec = deepcopy(spec); spec.update(parameters={}, filters=[])
    artifact = approve(setup_query, spec)
    bounded = ReviewedQueryContracts(engine.adapter, max_rows=1)
    result = bounded.execute(draft, artifact, {}, relations=relations)
    assert result['returned_count'] == 1
    assert result['total_output_rows'] == 4
    assert result['matched_root_rows'] == 5
    assert result['truncated'] is True


def test_count_distinct_and_all_null_sum(setup_query):
    engine, draft, relations, spec, _, ref = setup_query
    spec = deepcopy(spec); spec.update(parameters={}, filters=[], projection=[], group_by=[],
        aggregates=[{'op': 'count_distinct', 'field': ref('facts', 'owner'), 'name': 'owners'},
                    {'op': 'count_rows', 'name': 'rows'}])
    assert engine.execute(draft, approve(setup_query, spec), {}, relations=relations)['rows'] == [{'owners': 3, 'rows': 5}]
    spec['filters'] = [{'field': ref('facts', 'quantity'), 'op': 'is_null'}]
    spec['aggregates'] = [{'op': 'sum', 'field': ref('facts', 'quantity'), 'name': 'quantity'}]
    assert engine.execute(draft, approve(setup_query, spec), {}, relations=relations)['rows'] == [{'quantity': None}]


def test_no_free_sql_and_no_parent_measure_fanout(setup_query):
    engine, draft, relations, spec, _, ref = setup_query
    bad = deepcopy(spec); bad['sql'] = 'SELECT * FROM facts'
    with pytest.raises(DatabaseSourceError, match='fields'):
        engine.propose(draft, bad, relations=relations, origin={})
    bad = deepcopy(spec); bad['aggregates'][0]['field'] = ref('owners', 'id')
    with pytest.raises(DatabaseSourceError, match='root-grain'):
        engine.propose(draft, bad, relations=relations, origin={})


def test_snapshot_byte_drift_is_not_a_new_source(setup_query):
    engine, draft, relations, _, _, _ = setup_query
    approved = approve(setup_query)
    path = engine.adapter.registry.root / (draft['database']['source_id'] + '.sqlite')
    path.chmod(0o600); path.write_bytes(path.read_bytes() + b'drift')
    with pytest.raises(DatabaseSourceError, match='integrity'):
        engine.execute(draft, approved, {'status': 'ready'}, relations=relations)


def test_nonunique_declared_parent_is_rejected(tmp_path):
    path = tmp_path / 'duplicates.sqlite'
    with sqlite3.connect(path) as con:
        con.executescript('CREATE TABLE parents (id TEXT); CREATE TABLE children (id TEXT REFERENCES parents(id)); INSERT INTO parents VALUES (\'a\'), (\'a\');')
    registry = SQLiteSources(tmp_path / 'registry'); source = registry.register(path)
    adapter = DatabaseWorkspaceAdapter(registry); draft = adapter.create(source['source_id'])
    for entry in draft['entries']:
        entry.update(status='approved', interpretation='Reviewed')
    ids = {e['source']['file']: e['id'] for e in draft['entries']}
    with pytest.raises(DatabaseSourceError, match='not unique'):
        ReviewedQueryContracts(adapter).propose_relation(draft, {'id': 'link', 'child_entry_id': ids['children'],
            'parent_entry_id': ids['parents'], 'interpretation': 'Reference',
            'join_policy': 'left_many_to_one_preserve_root'}, origin={})


def test_relation_review_note_change_invalidates_query(setup_query):
    engine, draft, relations, _, _, _ = setup_query
    artifact = approve(setup_query)
    changed = deepcopy(relations); changed['owner_link']['review']['note'] = 'New review annotation'
    with pytest.raises(DatabaseSourceError, match='stale'):
        engine.execute(draft, artifact, {'status': 'ready'}, relations=changed)


def test_null_and_missing_parent_diagnostics(setup_query):
    engine, draft, relations, spec, _, _ = setup_query
    spec = deepcopy(spec); spec.update(parameters={}, filters=[])
    result = engine.execute(draft, approve(setup_query, spec), {}, relations=relations)
    assert result['aggregate_null_exclusions'] == {'quantity': 1}
    assert result['join_observations'][0]['null_child_keys'] == 1
    assert result['join_observations'][0]['unmatched_nonnull_child_keys'] == 1


def test_step_limit_interrupts_instead_of_returning_partial_aggregate(setup_query):
    engine, draft, relations, _, _, _ = setup_query
    artifact = approve(setup_query)
    limited = ReviewedQueryContracts(engine.adapter, max_steps=1)
    with pytest.raises(DatabaseSourceError, match='failed|limit'):
        limited.execute(draft, artifact, {'status': 'ready'}, relations=relations)


def test_dynamic_numeric_garbage_is_not_coerced_to_zero(tmp_path):
    path = tmp_path / 'badnumeric.sqlite'
    with sqlite3.connect(path) as con:
        con.executescript("CREATE TABLE facts (quantity INTEGER); INSERT INTO facts VALUES (2), ('bad');")
    registry = SQLiteSources(tmp_path / 'registry'); source = registry.register(path)
    adapter = DatabaseWorkspaceAdapter(registry); draft = adapter.create(source['source_id'])
    draft['entries'][0].update(status='approved', interpretation='Reviewed numeric measure')
    ref = {'entry_id': draft['entries'][0]['id'], 'alias': 'f'}
    spec = {'id': 'total', 'title': 'Total quantity', 'question_scope': 'Recorded quantity', 'root': ref,
        'joins': [], 'parameters': {}, 'filters': [], 'projection': [], 'group_by': [],
        'aggregates': [{'op': 'sum', 'name': 'total', 'field': ref}], 'distinct': False,
        'output_kind': 'recorded_facts', 'limitations': [], 'policy_references': [],
        'null_policy': 'exclude_from_aggregates_preserve_projection', 'empty_groups': 'absent', 'measure_grain': 'f'}
    engine = ReviewedQueryContracts(adapter)
    pending = engine.propose(draft, spec, origin={})
    artifact = engine.approve(draft, pending, actor='operator', note='Reviewed', revision=1, human_confirmed=True)
    with pytest.raises(DatabaseSourceError, match='type'):
        engine.execute(draft, artifact, {})


@pytest.mark.parametrize('parent_type,parent_values,child_type,child_values,expected_parent,orphans', [
    ('TEXT', "('01'), ('1')", 'INTEGER', '(1,3), (2,7)', '1', 1),
    ('TEXT COLLATE NOCASE', "('Alpha'), ('Beta')", 'TEXT COLLATE BINARY', "('alpha',3), ('missing',7)", 'Alpha', 1),
    ('TEXT', "('01'), ('02')", 'INTEGER', '(1,3), (2,7)', None, 2),
])
def test_fk_parent_affinity_preserves_actual_child_grain(tmp_path, parent_type, parent_values,
                                                        child_type, child_values, expected_parent, orphans):
    path = tmp_path / 'mixed-affinity.sqlite'
    with sqlite3.connect(path) as con:
        # These are fixed test constants, never caller SQL or identifiers.
        con.executescript(f'CREATE TABLE parents (id {parent_type} PRIMARY KEY); '
            f'CREATE TABLE children (owner {child_type} REFERENCES parents(id), quantity INTEGER); '
            f'INSERT INTO parents VALUES {parent_values}; '
            f'INSERT INTO children VALUES {child_values};')
    registry = SQLiteSources(tmp_path / 'registry'); source = registry.register(path)
    adapter = DatabaseWorkspaceAdapter(registry); draft = adapter.create(source['source_id'])
    for entry in draft['entries']:
        entry.update(status='approved', interpretation='Reviewed source column')
    ids = {(e['source']['file'], e['source']['column']): e['id'] for e in draft['entries']}
    engine = ReviewedQueryContracts(adapter)
    review = dict(actor='operator', note='Reviewed parent comparison and grain', revision=1, human_confirmed=True)
    pending = engine.propose_relation(draft, {'id': 'link', 'child_entry_id': ids['children', 'owner'],
        'parent_entry_id': ids['parents', 'id'], 'interpretation': 'Recorded parent',
        'join_policy': 'left_many_to_one_preserve_root'}, origin={})
    relations = {'link': engine.approve_relation(draft, pending, **review)}
    quantity = {'entry_id': ids['children', 'quantity'], 'alias': 'c'}
    parent = {'entry_id': ids['parents', 'id'], 'alias': 'p'}
    spec = {'id': 'mixed', 'title': 'Mixed affinity join', 'question_scope': 'Preserve child quantities',
        'root': quantity, 'joins': [{'relation_id': 'link', 'child_alias': 'c', 'parent_alias': 'p'}],
        'parameters': {}, 'filters': [], 'projection': [{'field': quantity, 'name': 'quantity'},
                                                      {'field': parent, 'name': 'parent'}],
        'group_by': [], 'aggregates': [], 'distinct': False, 'output_kind': 'recorded_facts',
        'limitations': [], 'policy_references': [], 'null_policy': 'exclude_from_aggregates_preserve_projection',
        'empty_groups': 'absent', 'measure_grain': 'c'}
    def execute():
        pending_query = engine.propose(draft, spec, relations=relations, origin={})
        approved = engine.approve(draft, pending_query, relations=relations, **review)
        return engine.execute(draft, approved, {}, relations=relations)
    result = execute()
    assert result['rows'] == [{'quantity': 3, 'parent': expected_parent}, {'quantity': 7, 'parent': None}]
    assert result['matched_root_rows'] == result['total_output_rows'] == 2
    assert result['join_observations'][0]['unmatched_nonnull_child_keys'] == orphans
    spec.update(projection=[], aggregates=[{'op': 'sum', 'field': quantity, 'name': 'total'},
                                           {'op': 'count_rows', 'name': 'rows'}])
    assert execute()['rows'] == [{'total': 10, 'rows': 2}]


def product_case(tmp_path, rows):
    """Independent authored arithmetic fixtures; no domain evaluation inputs."""
    path = tmp_path / 'products.sqlite'
    with sqlite3.connect(path) as con:
        # No affinity: malformed text numerals and REAL values remain observable.
        con.execute('CREATE TABLE lines (id INTEGER PRIMARY KEY, bucket TEXT, quantity, price)')
        con.executemany('INSERT INTO lines VALUES (?, ?, ?, ?)', rows)
    registry = SQLiteSources(tmp_path / 'registry')
    source = registry.register(path)
    adapter = DatabaseWorkspaceAdapter(registry)
    draft = adapter.create(source['source_id'])
    for entry in draft['entries']:
        entry.update(status='approved', interpretation='Reviewed source field')
    fields = {entry['source']['column']: {'entry_id': entry['id'], 'alias': 'line'}
              for entry in draft['entries']}
    spec = {'id': 'line_value', 'title': 'Recorded line value', 'question_scope': 'Recorded integer products by bucket',
            'root': fields['id'], 'joins': [], 'parameters': {}, 'filters': [],
            'projection': [{'field': fields['bucket'], 'name': 'bucket'}], 'group_by': [fields['bucket']],
            'aggregates': [{'op': 'sum_product', 'name': 'value', 'left': fields['quantity'],
                            'right': fields['price'], 'numeric_type': 'integer', 'unit': 'cents',
                            'null_policy': 'exclude_if_any_operand_null'}],
            'distinct': False, 'output_kind': 'recorded_facts', 'limitations': [], 'policy_references': [],
            'null_policy': 'exclude_from_aggregates_preserve_projection', 'empty_groups': 'absent',
            'measure_grain': 'line'}
    engine = ReviewedQueryContracts(adapter)
    review = dict(actor='operator', note='Reviewed recorded integer operands', revision=1, human_confirmed=True)
    return engine, draft, {}, spec, review, fields


def test_product_counts_physical_lines_and_null_union(tmp_path):
    case = product_case(tmp_path, [(1, 'a', 3, 7), (2, 'a', 3, 7), (3, 'a', -2, 5),
                                  (4, 'a', 0, 50), (5, 'b', None, 4), (6, 'b', 2, None),
                                  (7, 'b', None, None)])
    engine, draft, _, _, _, _ = case
    artifact = approve(case)
    result = engine.execute(draft, artifact, {})
    assert artifact['version'] == result['version'] == 'reviewed-query-2'
    assert result['rows'] == [{'bucket': 'a', 'value': '32'}, {'bucket': 'b', 'value': None}]
    assert result['aggregate_null_exclusions'] == {'value': 3}
    assert result['product_aggregate_observations']['value'] == {
        'numeric_type': 'integer', 'unit': 'cents', 'value_encoding': 'decimal_integer_string',
        'unit_status': 'reviewed_annotation_not_dimensional_verification',
        'null_policy': 'exclude_if_any_operand_null', 'left_null_rows': 2, 'right_null_rows': 2,
        'excluded_rows': 3, 'included_terms': 4,
        'scope': 'all_matched_root_rows_before_output_truncation'}
    bounded = ReviewedQueryContracts(engine.adapter, max_rows=1)
    limited = bounded.execute(draft, artifact, {})
    assert limited['truncated'] and limited['total_output_rows'] == 2
    assert limited['product_aggregate_observations'] == result['product_aggregate_observations']


@pytest.mark.parametrize('rows,message', [
    ([(1, 'a', 2**62, 2)], 'product'),
    ([(1, 'a', -(2**63), -1)], 'product'),
    ([(1, 'a', 2**63-1, 1), (2, 'a', 1, 1)], 'final sum'),
    ([(1, 'a', -(2**63), 1), (2, 'a', -1, 1)], 'final sum'),
])
def test_product_and_final_sum_overflow_fail(tmp_path, rows, message):
    case = product_case(tmp_path, rows)
    with pytest.raises(DatabaseSourceError, match='signed64.*' + message):
        case[0].execute(case[1], approve(case), {})


@pytest.mark.parametrize('values', [[2**63-1, 1, -1], [-1, 1, 2**63-1], [-(2**63), -1, 1]])
def test_product_exact_cancellation_and_signed64_boundary(tmp_path, values):
    case = product_case(tmp_path, [(i+1, 'a', value, 1) for i, value in enumerate(values)])
    result = case[0].execute(case[1], approve(case), {})
    assert result['rows'] == [{'bucket': 'a', 'value': str(sum(values))}]


@pytest.mark.parametrize('bad', ['2', 'bad', 1.5, b'2', float('inf')])
@pytest.mark.parametrize('side', ['quantity', 'price'])
def test_product_fullsnapshot_operand_validation_before_filters(tmp_path, bad, side):
    malformed = (2, 'excluded', bad, None) if side == 'quantity' else (2, 'excluded', None, bad)
    case = product_case(tmp_path, [(1, 'included', 2, 3), malformed])
    engine, draft, _, spec, _, fields = case
    spec['parameters'] = {'bucket': 'text'}
    spec['filters'] = [{'op': 'eq', 'field': fields['bucket'], 'parameter': 'bucket'}]
    with pytest.raises(DatabaseSourceError, match='type'):
        engine.execute(draft, approve(case), {'bucket': 'included'})


def test_product_empty_groups_and_scalar_empty_are_absent(tmp_path):
    case = product_case(tmp_path, [])
    engine, draft, _, spec, _, _ = case
    assert engine.execute(draft, approve(case), {})['rows'] == []
    spec.update(projection=[], group_by=[])
    result = engine.execute(draft, approve(case), {})
    assert result['rows'] == []
    assert result['product_aggregate_observations']['value']['included_terms'] == 0


def test_product_rejects_parent_operand_and_unsupported_expression(setup_query):
    engine, draft, relations, spec, _, ref = setup_query
    spec = deepcopy(spec)
    spec['aggregates'] = [{'op': 'sum_product', 'name': 'value', 'left': ref('facts', 'quantity'),
                           'right': ref('owners', 'id'), 'numeric_type': 'integer', 'unit': 'cents',
                           'null_policy': 'exclude_if_any_operand_null'}]
    with pytest.raises(DatabaseSourceError, match='root-grain'):
        engine.propose(draft, spec, relations=relations, origin={})
    spec['aggregates'][0]['right'] = {'sql': 'quantity * 2'}
    with pytest.raises(DatabaseSourceError, match='fields'):
        engine.propose(draft, spec, relations=relations, origin={})


def test_product_dependencies_and_version_are_bound(tmp_path):
    from apps.factory_lab.workspace_query_contracts import fingerprint
    case = product_case(tmp_path, [(1, 'a', 2, 3)])
    engine, draft, _, _, _, fields = case
    artifact = approve(case)
    for column in ('quantity', 'price'):
        changed = deepcopy(draft)
        next(e for e in changed['entries'] if e['id'] == fields[column]['entry_id'])['interpretation'] = 'Changed meaning'
        with pytest.raises(DatabaseSourceError, match='stale'):
            engine.execute(changed, artifact, {})
    changed = deepcopy(artifact)
    changed['version'] = 'reviewed-query-1'
    changed['fingerprint'] = fingerprint({k: v for k, v in changed.items() if k not in ('fingerprint', 'status', 'review')})
    changed['review']['approved_fingerprint'] = changed['fingerprint']
    with pytest.raises(DatabaseSourceError, match='changed'):
        engine.execute(draft, changed, {})
    with pytest.raises(DatabaseSourceError, match='limit|failed'):
        ReviewedQueryContracts(engine.adapter, max_steps=1).execute(draft, artifact, {})


def test_legacy_envelope_and_result_shape_are_unchanged(setup_query):
    from apps.factory_lab.workspace_query_contracts import fingerprint
    engine, draft, relations, spec, _, _ = setup_query
    pending = engine.propose(draft, spec, relations=relations, origin={})
    # Explicit legacy envelope construction guards accidental version/schema migration.
    body = {'version': 'reviewed-query-1', 'kind': 'query', 'spec': deepcopy(spec),
            'source': deepcopy(draft['database']), 'dependencies': deepcopy(pending['dependencies']), 'origin': {}}
    assert pending == {**body, 'fingerprint': fingerprint(body), 'status': 'pending', 'review': None}
    result = engine.execute(draft, approve(setup_query), {'status': 'ready'}, relations=relations)
    assert result['version'] == 'reviewed-query-1'
    assert 'product_aggregate_observations' not in result
    assert all(rel['version'] == 'reviewed-query-1' for rel in relations.values())


@pytest.mark.parametrize('value', [2**53-1, 2**53, 2**53+1, 2**63-1, -(2**63)])
def test_product_json_wire_preserves_exact_integer(tmp_path, value):
    import json
    case = product_case(tmp_path, [(1, 'a', value, 1)])
    result = case[0].execute(case[1], approve(case), {})
    decoded = json.loads(json.dumps(result, allow_nan=False))
    assert decoded['rows'][0]['value'] == str(value)
    assert decoded['product_aggregate_observations']['value']['value_encoding'] == 'decimal_integer_string'


def test_product_overflow_in_group_beyond_display_limit_is_rejected(tmp_path):
    case = product_case(tmp_path, [(1, 'a', 2, 3), (2, 'z', 2**62, 2)])
    with pytest.raises(DatabaseSourceError, match='signed64.*product'):
        ReviewedQueryContracts(case[0].adapter, max_rows=1).execute(case[1], approve(case), {})


@pytest.mark.parametrize('key,value', [('numeric_type', 'number'), ('null_policy', 'zero'),
                                       ('unit', ''), ('expression', 'quantity * price')])
def test_product_schema_is_closed(tmp_path, key, value):
    case = product_case(tmp_path, [(1, 'a', 2, 3)])
    case[3]['aggregates'][0][key] = value
    with pytest.raises(DatabaseSourceError):
        approve(case)


def test_product_join_preserves_root_rows_and_mixed_legacy_outputs(setup_query):
    engine, draft, relations, spec, _, ref = setup_query
    spec = deepcopy(spec)
    spec['aggregates'] = [{'op': 'sum_product', 'name': 'value', 'left': ref('facts', 'quantity'),
                           'right': ref('facts', 'id'), 'numeric_type': 'integer', 'unit': 'units',
                           'null_policy': 'exclude_if_any_operand_null'},
                          {'op': 'sum', 'name': 'quantity', 'field': ref('facts', 'quantity')}]
    artifact = approve(setup_query, spec)
    result = engine.execute(draft, artifact, {'status': 'ready'}, relations=relations)
    assert result['rows'] == [{'owner': 1, 'value': '13', 'quantity': 8}]
    assert result['matched_root_rows'] == 2
    changed = deepcopy(artifact)
    changed['spec']['aggregates'][0]['unit'] = 'different units'
    with pytest.raises(DatabaseSourceError, match='changed'):
        engine.execute(draft, changed, {'status': 'ready'}, relations=relations)


def scalar_case(tmp_path, selections=None, candidates=None):
    """Independent selector fixtures: duplicate physical rows are intentional."""
    path = tmp_path / 'scalars.sqlite'
    with sqlite3.connect(path) as con:
        con.executescript('CREATE TABLE selections (id, tier TEXT COLLATE NOCASE); '
                          'CREATE TABLE candidates (id INTEGER, tier TEXT COLLATE NOCASE, other TEXT COLLATE NOCASE);')
        con.executemany('INSERT INTO selections VALUES (?, ?)', [(1, 'Gold')] if selections is None else selections)
        con.executemany('INSERT INTO candidates VALUES (?, ?, ?)',
                        [(1, 'Gold', 'Gold'), (2, 'gold', 'Gold'), (3, None, 'Gold')]
                        if candidates is None else candidates)
    registry = SQLiteSources(tmp_path / 'registry'); source = registry.register(path)
    adapter = DatabaseWorkspaceAdapter(registry); draft = adapter.create(source['source_id'])
    for entry in draft['entries']:
        entry.update(status='approved', interpretation='Reviewed authored field')
    ids = {(e['source']['file'], e['source']['column']): e['id'] for e in draft['entries']}
    ref = lambda col: {'entry_id': ids['candidates', col], 'alias': 'c'}
    spec = {'id': 'selected', 'title': 'Selected tier', 'question_scope': 'Exact selected tier',
        'root': ref('id'), 'joins': [], 'parameters': {'customer': 'integer'},
        'scalar_bindings': [{'name': 'tier', 'table_entry_id': ids['selections', 'id'],
            'selector_entry_id': ids['selections', 'id'], 'selector_type': 'integer', 'parameter': 'customer',
            'value_entry_id': ids['selections', 'tier'], 'value_type': 'text', 'cardinality': 'exactly_one',
            'null_policy': 'require_nonnull', 'comparison': 'binary_exact'}],
        'filters': [{'op': 'eq', 'left': {'kind': 'field', **ref('tier')},
            'right': {'kind': 'scalar', 'binding': 'tier'}, 'value_type': 'text',
            'null_policy': 'unknown_excluded', 'comparison': 'binary_exact'}],
        'projection': [{'field': ref('id'), 'name': 'id'}], 'group_by': [], 'aggregates': [],
        'distinct': False, 'output_kind': 'recorded_facts', 'limitations': [], 'policy_references': [],
        'null_policy': 'exclude_from_aggregates_preserve_projection', 'empty_groups': 'absent', 'measure_grain': 'c'}
    review = dict(actor='operator', note='Reviewed exact selection', revision=1, human_confirmed=True)
    return ReviewedQueryContracts(adapter), draft, {}, spec, review, ref


def test_scalar_binary_exact_provenance_and_candidate_null(tmp_path):
    case = scalar_case(tmp_path)
    artifact = approve(case)
    result = case[0].execute(case[1], artifact, {'customer': 1})
    assert artifact['version'] == result['version'] == 'reviewed-query-3'
    assert result['rows'] == [{'id': 1}]
    assert result['matched_root_rows'] == 1
    assert result['comparison_null_exclusions'] == [{'filter_index': 0, 'null_rows': 1,
        'scope': 'whole_joined_root_before_query_filters'}]
    binding = result['scalar_binding_observations'][0]
    assert (binding['selector_value'], binding['resolved_value'], binding['matched_rows']) == ('1', 'Gold', 1)
    assert binding['source'] == artifact['source']
    assert result['provenance']['scalar_bindings'] == [binding]


@pytest.mark.parametrize('rows,reason', [([], 'absent'), ([(1, 'Gold'), (1, 'Gold')], 'multiple'),
    ([(1, 'Gold'), (1, 'Silver')], 'multiple'), ([(1, None)], 'null_value'),
    ([('1', 'Gold')], 'invalid_type'), ([(1, b'Gold')], 'invalid_type')])
def test_scalar_unresolved_is_not_successful_empty(tmp_path, rows, reason):
    case = scalar_case(tmp_path, selections=rows)
    with pytest.raises(DatabaseSourceError, match='unresolved_binding:tier:' + reason):
        case[0].execute(case[1], approve(case), {'customer': 1})


def test_scalar_resolved_with_no_candidate_is_complete_empty(tmp_path):
    case = scalar_case(tmp_path, selections=[(1, 'Silver')])
    result = case[0].execute(case[1], approve(case), {'customer': 1})
    assert result['status'] == 'complete' and result['rows'] == []
    assert result['scalar_binding_observations'][0]['resolved_value'] == 'Silver'


def test_scalar_field_comparison_has_no_collation_inheritance(tmp_path):
    case = scalar_case(tmp_path)
    case[3]['scalar_bindings'] = []
    case[3]['parameters'] = {}
    case[3]['filters'][0]['right'] = {'kind': 'field', **case[5]('other')}
    assert case[0].execute(case[1], approve(case), {})['rows'] == [{'id': 1}]


@pytest.mark.parametrize('mutation', ['duplicate', 'cross_table', 'parameter_type', 'wrong_alias',
                                      'scalar_type', 'sql', 'too_many', 'old_version'])
def test_scalar_schema_closed_and_type_linked(tmp_path, mutation):
    case = scalar_case(tmp_path); spec = case[3]; binding = spec['scalar_bindings'][0]
    if mutation == 'duplicate': spec['scalar_bindings'].append(deepcopy(binding))
    elif mutation == 'cross_table': binding['value_entry_id'] = case[5]('tier')['entry_id']
    elif mutation == 'parameter_type': binding['selector_type'] = 'text'
    elif mutation == 'wrong_alias': spec['filters'][0]['left']['alias'] = 'unjoined'
    elif mutation == 'scalar_type': binding['value_type'] = 'integer'
    elif mutation == 'sql': binding['sql'] = 'SELECT tier FROM selections'
    elif mutation == 'too_many': spec['scalar_bindings'] *= 5
    elif mutation == 'old_version': del spec['scalar_bindings']
    with pytest.raises(DatabaseSourceError): approve(case)


def test_scalar_dependency_drift_caller_injection_and_budget(tmp_path):
    case = scalar_case(tmp_path)
    engine, draft, _, spec, _, _ = case; artifact = approve(case)
    for key in ('table_entry_id', 'selector_entry_id', 'value_entry_id'):
        changed = deepcopy(draft)
        next(e for e in changed['entries'] if e['id'] == spec['scalar_bindings'][0][key])['interpretation'] = 'Changed'
        with pytest.raises(DatabaseSourceError, match='stale'):
            engine.execute(changed, artifact, {'customer': 1})
    with pytest.raises(DatabaseSourceError, match='exactly'):
        engine.execute(draft, artifact, {'customer': 1, 'tier': 'Silver'})
    with pytest.raises(DatabaseSourceError, match='type'):
        engine.execute(draft, artifact, {'customer': True})
    with pytest.raises(DatabaseSourceError, match='failed|limit'):
        ReviewedQueryContracts(engine.adapter, max_steps=10).execute(draft, artifact, {'customer': 1})


def test_scalar_spec_and_version_tamper(tmp_path):
    from apps.factory_lab.workspace_query_contracts import fingerprint
    case = scalar_case(tmp_path); artifact = approve(case)
    artifact['version'] = 'reviewed-query-2'
    artifact['fingerprint'] = fingerprint({k: v for k, v in artifact.items() if k not in ('fingerprint', 'status', 'review')})
    artifact['review']['approved_fingerprint'] = artifact['fingerprint']
    with pytest.raises(DatabaseSourceError, match='changed'):
        case[0].execute(case[1], artifact, {'customer': 1})


def test_field_comparison_validates_both_full_columns_before_filtering(tmp_path):
    case = scalar_case(tmp_path, candidates=[(1, 'Gold', 'Gold'), (2, 'Silver', b'bad')])
    case[3]['filters'][0]['right'] = {'kind': 'field', **case[5]('other')}
    with pytest.raises(DatabaseSourceError, match='type'):
        case[0].execute(case[1], approve(case), {'customer': 1})


def test_scalar_selector_uses_binary_exact_even_with_nocase_column(tmp_path):
    case = scalar_case(tmp_path, selections=[(1, 'Gold'), (2, 'gold')])
    binding = case[3]['scalar_bindings'][0]
    binding['selector_entry_id'] = binding['value_entry_id']
    binding['selector_type'] = case[3]['parameters']['customer'] = 'text'
    result = case[0].execute(case[1], approve(case), {'customer': 'Gold'})
    assert result['rows'] == [{'id': 1}]
    assert result['scalar_binding_observations'][0]['matched_rows'] == 1
    with pytest.raises(DatabaseSourceError, match='absent'):
        case[0].execute(case[1], approve(case), {'customer': 'GOLD'})


def test_scalar_lookup_fullscan_consumes_execution_budget(tmp_path):
    case = scalar_case(tmp_path, selections=[(i, 'Gold') for i in range(1000)])
    artifact = approve(case)
    with pytest.raises(DatabaseSourceError, match='failed|limit'):
        ReviewedQueryContracts(case[0].adapter, max_steps=500).execute(case[1], artifact, {'customer': 1})
    assert case[0].execute(case[1], artifact, {'customer': 1})['rows'] == [{'id': 1}]


def test_typed_field_comparison_within_approved_join_preserves_root(setup_query):
    engine, draft, relations, spec, _, ref = setup_query
    spec = deepcopy(spec)
    spec.update(scalar_bindings=[], parameters={}, projection=[{'field': ref('facts', 'id'), 'name': 'id'}],
                group_by=[], aggregates=[])
    spec['filters'] = [{'op': 'eq', 'left': {'kind': 'field', **ref('facts', 'owner')},
        'right': {'kind': 'field', **ref('owners', 'id')}, 'value_type': 'integer',
        'comparison': 'binary_exact', 'null_policy': 'unknown_excluded'}]
    result = engine.execute(draft, approve(setup_query, spec), {}, relations=relations)
    assert result['rows'] == [{'id': 1}, {'id': 2}, {'id': 3}]
    assert result['matched_root_rows'] == 3
    assert result['comparison_null_exclusions'][0]['null_rows'] == 2


def test_typed_comparison_numeric_text_is_rejected_not_affinity_coerced(tmp_path):
    case = scalar_case(tmp_path, selections=[(1, '1')], candidates=[(1, '1', '1')])
    case[3]['scalar_bindings'][0]['value_type'] = 'integer'
    case[3]['filters'][0]['value_type'] = 'integer'
    with pytest.raises(DatabaseSourceError, match='invalid_type'):
        case[0].execute(case[1], approve(case), {'customer': 1})


@pytest.mark.parametrize('value', [2**53+1, 2**63-1, -(2**63)])
def test_scalar_integer_provenance_preserves_json_wire_precision(tmp_path, value):
    import json
    case = scalar_case(tmp_path, selections=[(value, 'Gold')])
    binding = case[3]['scalar_bindings'][0]
    binding['value_entry_id'] = binding['selector_entry_id']
    binding['value_type'] = 'integer'
    # Resolve even an unused reviewed binding; typed SQL values remain internal.
    case[3]['filters'] = []
    result = json.loads(json.dumps(case[0].execute(case[1], approve(case), {'customer': value})))
    observation = result['scalar_binding_observations'][0]
    assert observation['selector_value'] == observation['resolved_value'] == str(value)
    assert observation['selector_value_encoding'] == observation['resolved_value_encoding'] == 'decimal_integer_string'
