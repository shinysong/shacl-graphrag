"""Reviewed, bounded relational queries over immutable registered snapshots.

Artifacts live outside database drafts. The caller persists returned artifacts and
records attempts before execution. Human review metadata is an annotation, never
an authenticated identity or proof of policy truth. No supplied SQL is executed.
Only child-to-parent LEFT joins are supported: each root row retains its grain.
Execution timeout/step limits cover the final snapshot execution phase after
restore, approval verification and compilation. Preparatory registry reads and
relation checks have their own registry connection timeouts; the configured
execution timeout is not a whole-invocation deadline.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
import math
import re
import sqlite3
import time

from .workspace_database import DatabaseSourceError, _quote
from .workspace_store import check_cancel, ExecutionCancelled
from .workspace_database_adapter import DatabaseWorkspaceAdapter
from .workspace_extension_review import active_annotations

VERSION = 'reviewed-query-1'
PRODUCT_VERSION = 'reviewed-query-2'
SCALAR_VERSION = 'reviewed-query-3'
REACHABILITY_VERSION = 'reviewed-query-reachability-1'


def _artifact_version(kind, spec):
    if kind == 'query' and spec.get('query_kind') == 'directed_reachability':
        return REACHABILITY_VERSION
    if kind == 'query' and 'scalar_bindings' in spec:
        return SCALAR_VERSION
    return (PRODUCT_VERSION if kind == 'query' and any(
        isinstance(a, dict) and a.get('op') == 'sum_product'
        for a in spec.get('aggregates', [])) else VERSION)


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    except (TypeError, ValueError):
        raise DatabaseSourceError('Contract must contain finite JSON') from None


def fingerprint(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise DatabaseSourceError(message)


def _keys(obj, keys):
    _require(isinstance(obj, dict) and set(obj) == set(keys.split()), 'Unsupported or missing contract fields')


def _name(value):
    _require(isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', value), 'Invalid contract identifier')
    return value


def _text(value):
    _require(isinstance(value, str) and 0 < len(value.strip()) <= 4000, 'Provide bounded interpretation text')


def _typed(value, kind):
    valid = ((kind == 'text' and isinstance(value, str) and len(value) <= 2000) or
             (kind == 'integer' and type(value) is int and -(2**63) <= value < 2**63) or
             (kind == 'number' and type(value) in (int, float) and math.isfinite(value) and abs(value) < 2**63))
    if kind == 'date' and isinstance(value, str):
        try:
            valid = date.fromisoformat(value).isoformat() == value
        except ValueError:
            valid = False
    _require(valid, 'Value does not match declared contract type')
    return value


def _fk_predicate(parent, child):
    # SQLite FK comparisons apply parent affinity and collation. A bare child
    # column can contribute a different affinity to an ordinary SQL comparison.
    # Unary + removes that affinity without changing the child's stored value.
    return f'{parent} = +{child}'


class ReviewedQueryContracts:
    """Pure artifact boundary; service owns persistence, ACLs and revision checks."""

    def __init__(self, adapter, *, max_rows=200, max_bytes=262144, timeout=5, max_steps=2000000):
        _require(isinstance(adapter, DatabaseWorkspaceAdapter), 'Inject a registered database adapter')
        _require(type(max_rows) is int and 1 <= max_rows <= 1000 and
                 type(max_bytes) is int and 1024 <= max_bytes <= 1048576 and
                 type(timeout) in (int, float) and 0 < timeout <= 30 and
                 type(max_steps) is int and 1 <= max_steps <= 10000000, 'Invalid query resource limits')
        self.adapter = adapter
        self.max_rows, self.max_bytes = max_rows, max_bytes
        self.timeout, self.max_steps = timeout, max_steps

    def _fields(self, draft):
        return {e['id']: e for e in draft['entries'] if e['status'] == 'approved'}

    def _dependencies(self, draft, ids):
        fields = self._fields(draft)
        _require(all(i in fields for i in ids), 'Every dependency field needs human approval')
        return {i: {'entry': deepcopy(fields[i]), 'external_annotations': active_annotations(draft, fields[i])}
                for i in sorted(ids)}

    def _envelope(self, draft, kind, spec, dependencies, origin):
        _require(isinstance(origin, dict) and len(_json(origin).encode()) <= 16384, 'Invalid proposal origin')
        body = {'version': _artifact_version(kind, spec), 'kind': kind, 'spec': deepcopy(spec),
                'source': deepcopy(draft['database']), 'dependencies': dependencies,
                'origin': deepcopy(origin)}
        return {**body, 'fingerprint': fingerprint(body), 'status': 'pending', 'review': None}

    @staticmethod
    def _verify(artifact, *, approved=False):
        _keys(artifact, 'version kind spec source dependencies origin fingerprint status review')
        body = {k: v for k, v in artifact.items() if k not in ('fingerprint', 'status', 'review')}
        _require(artifact['version'] == _artifact_version(artifact['kind'], artifact['spec']) and
                 artifact['fingerprint'] == fingerprint(body), 'Contract artifact changed')
        _require(artifact['status'] in ('pending', 'approved'), 'Invalid contract status')
        if approved:
            _require(artifact['status'] == 'approved', 'Explicit human contract approval required')
            _keys(artifact['review'], 'actor note revision approved_fingerprint human_confirmed')
            _text(artifact['review']['actor'])
            _text(artifact['review']['note'])
            _require(artifact['review']['human_confirmed'] is True and
                     type(artifact['review']['revision']) is int and artifact['review']['revision'] >= 1 and
                     artifact['review']['approved_fingerprint'] == artifact['fingerprint'], 'Invalid human approval binding')

    def propose_relation(self, draft, spec, *, origin):
        draft = self.adapter.restore(draft)
        _keys(spec, 'id child_entry_id parent_entry_id interpretation join_policy')
        _name(spec['id']); _text(spec['interpretation'])
        _require(spec['join_policy'] == 'left_many_to_one_preserve_root', 'Unsupported join multiplicity policy')
        deps = self._dependencies(draft, [spec['child_entry_id'], spec['parent_entry_id']])
        child, parent = (deps[spec[k]]['entry']['source'] for k in ('child_entry_id', 'parent_entry_id'))
        table = next(s for s in draft['sources'] if s['name'] == child['file'])
        declarations = table['foreign_keys']
        matching = [f for f in declarations if f['from'] == child['column'] and f['table'] == parent['file']]
        ptable = next(s for s in draft['sources'] if s['name'] == parent['file'])
        _require(any(sum(x['id'] == f['id'] for x in declarations) == 1 and
                     (f['to'] == parent['column'] or f['to'] is None and ptable['primary_key'] == [parent['column']])
                     for f in matching), 'Only declared single-column foreign keys are supported')
        # Validate actual parent uniqueness, including nullable keys. Snapshot
        # contents, not a possibly unenforced declaration, establish multiplicity.
        record = self.adapter.registry._record(draft['database']['source_id'])
        with self.adapter.registry._connection(self.adapter.registry._data(record)) as con:
            column, name = _quote(parent['column']), _quote(parent['file'])
            duplicate = con.execute(f'SELECT 1 FROM {name} WHERE {column} IS NOT NULL GROUP BY {column} HAVING count(*) > 1 LIMIT 1').fetchone()
            _require(duplicate is None, 'Parent key is not unique; join would multiply root rows')
            child_column = 'c.' + _quote(child['column'])
            parent_column = 'p.' + column
            predicate = _fk_predicate(parent_column, child_column)
            multiplied = con.execute(
                f'SELECT 1 FROM {_quote(child["file"])} AS c '
                f'WHERE (SELECT count(*) FROM {name} AS p WHERE {predicate}) > 1 LIMIT 1'
            ).fetchone()
            _require(multiplied is None, 'Actual foreign-key comparison multiplies child rows')
        return self._envelope(draft, 'relation', spec, deps, origin)

    def _approve(self, pending, *, actor, note, revision, human_confirmed):
        self._verify(pending)
        _require(pending['status'] == 'pending' and human_confirmed is True, 'Explicit human approval of a pending artifact required')
        _text(actor); _text(note)
        _require(type(revision) is int and revision >= 1, 'Invalid approval revision')
        result = deepcopy(pending)
        result.update(status='approved', review={'actor': actor, 'note': note, 'revision': revision,
                      'approved_fingerprint': pending['fingerprint'], 'human_confirmed': True})
        return result

    def approve_relation(self, draft, pending, **review):
        self._verify(pending)
        current = self.propose_relation(draft, pending['spec'], origin=pending['origin'])
        _require(current['fingerprint'] == pending['fingerprint'], 'Relation dependencies changed; renewed review required')
        return self._approve(pending, **review)

    def _compile(self, draft, spec, relations):
        if spec.get('query_kind') == 'directed_reachability':
            from .workspace_query_reachability import compile_spec
            return compile_spec(self, draft, spec, relations)
        scalar_version = 'scalar_bindings' in spec
        _keys(spec, 'id title question_scope root joins parameters filters projection group_by aggregates distinct output_kind limitations policy_references null_policy empty_groups measure_grain' + (' scalar_bindings' if scalar_version else ''))
        _name(spec['id']); _text(spec['title']); _text(spec['question_scope'])
        _require(spec['output_kind'] in ('recorded_facts', 'prerequisite_candidates', 'potential_impact_candidates'), 'Unsupported output claim')
        _require(spec['null_policy'] == 'exclude_from_aggregates_preserve_projection' and spec['empty_groups'] == 'absent', 'Unsupported null or empty-group policy')
        _require(isinstance(spec['limitations'], list) and all(isinstance(v, str) for v in spec['limitations']) and
                 isinstance(spec['policy_references'], list), 'Invalid scope annotations')
        for key, bound in [('joins', 8), ('filters', 20), ('projection', 30), ('group_by', 20), ('aggregates', 20)]:
            _require(isinstance(spec[key], list) and len(spec[key]) <= bound, 'Contract operator bound exceeded')
        _require(type(spec['distinct']) is bool, 'Distinct must be explicitly boolean')
        _keys(spec['root'], 'entry_id alias')
        fields = self._fields(draft); used = set(); aliases = {}; rel_deps = {}
        def field(ref):
            _keys(ref, 'entry_id alias')
            _require(isinstance(ref['entry_id'], str) and ref['entry_id'] in fields, 'Query requires an approved field')
            entry = fields[ref['entry_id']]
            _require(ref['alias'] in aliases and aliases[ref['alias']] == entry['source']['file'], 'Field alias does not match source table')
            used.add(entry['id'])
            return _quote(ref['alias']) + '.' + _quote(entry['source']['column'])
        root = spec['root']
        _require(isinstance(root['entry_id'], str) and root['entry_id'] in fields, 'Root field needs approval')
        aliases[_name(root['alias'])] = fields[root['entry_id']]['source']['file']
        field(root)
        _require(spec['measure_grain'] == root['alias'], 'Measure grain must be the preserved root row')
        sql_from = _quote(aliases[root['alias']]) + ' AS ' + _quote(root['alias'])
        _require(isinstance(relations, dict), 'Relations must be keyed artifacts')
        for join in spec['joins']:
            _keys(join, 'relation_id child_alias parent_alias')
            _require(join['relation_id'] in relations, 'Relation approval missing')
            rel = relations[join['relation_id']]; self._verify(rel, approved=True)
            fresh = self.propose_relation(draft, rel['spec'], origin=rel['origin'])
            _require(rel['kind'] == 'relation' and rel['spec']['id'] == join['relation_id'] and fresh['fingerprint'] == rel['fingerprint'], 'Relation approval is stale')
            rs = rel['spec']; parent = fields[rs['parent_entry_id']]['source']
            _require(join['child_alias'] in aliases and join['parent_alias'] not in aliases, 'Join must extend an existing child alias')
            aliases[_name(join['parent_alias'])] = parent['file']
            child_sql = field({'entry_id': rs['child_entry_id'], 'alias': join['child_alias']})
            parent_sql = field({'entry_id': rs['parent_entry_id'], 'alias': join['parent_alias']})
            predicate = _fk_predicate(parent_sql, child_sql)
            sql_from += f' LEFT JOIN {_quote(parent["file"])} AS {_quote(join["parent_alias"])} ON {predicate}'
            rel_deps[join['relation_id']] = deepcopy(rel)
        params = spec['parameters']
        _require(isinstance(params, dict) and len(params) <= 20, 'Invalid parameter schema')
        for name, kind in params.items():
            _name(name); _require(kind in ('text', 'integer', 'number', 'date'), 'Unsupported parameter type')
        scalars = {}
        if scalar_version:
            _require(isinstance(spec['scalar_bindings'], list) and len(spec['scalar_bindings']) <= 4,
                     'Scalar binding bound exceeded')
            for binding in spec['scalar_bindings']:
                _keys(binding, 'name table_entry_id selector_entry_id selector_type parameter value_entry_id value_type cardinality null_policy comparison')
                name = _name(binding['name'])
                _require(name not in scalars, 'Duplicate scalar binding name')
                _require(binding['cardinality'] == 'exactly_one' and binding['null_policy'] == 'require_nonnull'
                         and binding['comparison'] == 'binary_exact', 'Unsupported scalar policy')
                _require(binding['selector_type'] in ('text', 'integer', 'number', 'date') and
                         binding['value_type'] in ('text', 'integer', 'number', 'date'), 'Unsupported scalar type')
                _require(isinstance(binding['parameter'], str) and binding['parameter'] in params and
                         params[binding['parameter']] == binding['selector_type'], 'Scalar selector parameter type mismatch')
                ids = [binding[k] for k in ('table_entry_id', 'selector_entry_id', 'value_entry_id')]
                _require(all(isinstance(i, str) and i in fields for i in ids), 'Scalar requires approved fields')
                sources = [fields[i]['source'] for i in ids]
                _require(len({e['file'] for e in sources}) == 1, 'Scalar fields must share one table')
                used.update(ids)
                scalars[name] = {'spec': binding, 'table': sources[0]['file'],
                                 'selector': sources[1]['column'], 'value': sources[2]['column']}
        where, bindings, typed, comparisons = [], [], [], []
        for index, pred in enumerate(spec['filters']):
            _require(isinstance(pred, dict) and pred.get('op') in ('eq', 'lt', 'lte', 'gt', 'gte', 'is_null'), 'Unsupported filter operator')
            if 'left' in pred or 'right' in pred:
                _require(scalar_version and pred['op'] != 'is_null', 'Typed comparisons require version 3')
                _keys(pred, 'op left right value_type null_policy comparison')
                kind = pred['value_type']
                _require(kind in ('text', 'integer', 'number', 'date') and
                         pred['null_policy'] == 'unknown_excluded' and pred['comparison'] == 'binary_exact',
                         'Unsupported comparison type or policy')
                def operand(value, *, left=False):
                    _require(isinstance(value, dict), 'Invalid comparison operand')
                    if value.get('kind') == 'field':
                        _keys(value, 'kind entry_id alias')
                        ref = {k: value[k] for k in ('entry_id', 'alias')}
                        expression = field(ref)
                        typed.append((ref, kind))
                        return expression
                    _require(not left and value.get('kind') == 'scalar', 'Unsupported comparison operand')
                    _keys(value, 'kind binding')
                    _require(isinstance(value['binding'], str) and value['binding'] in scalars,
                             'Unknown scalar binding')
                    _require(scalars[value['binding']]['spec']['value_type'] == kind,
                             'Scalar comparison type mismatch')
                    bindings.append(('scalar', value['binding']))
                    return '?'
                left = operand(pred['left'], left=True)
                right = operand(pred['right'])
                operator = {'eq': '=', 'lt': '<', 'lte': '<=', 'gt': '>', 'gte': '>='}[pred['op']]
                # Strip affinity and override column collation without conversion.
                where.append(f'(+{left} COLLATE BINARY) {operator} (+{right} COLLATE BINARY)')
                comparisons.append({'filter_index': index, 'null_expression': left + ' IS NULL' +
                                    ((' OR ' + right + ' IS NULL') if right != '?' else '')})
                continue
            if pred['op'] == 'is_null':
                _keys(pred, 'field op'); where.append(field(pred['field']) + ' IS NULL'); continue
            _keys(pred, 'field op parameter')
            _require(pred['parameter'] in params, 'Unknown filter parameter')
            expression = field(pred['field'])
            operator = {'eq': '=', 'lt': '<', 'lte': '<=', 'gt': '>', 'gte': '>='}[pred['op']]
            where.append(f'{expression} {operator} ?'); bindings.append(pred['parameter'])
            typed.append((pred['field'], params[pred['parameter']]))
        outputs, names, null_measures, product_measures = [], [], {}, {}
        for item in spec['projection']:
            _keys(item, 'field name'); outputs.append(field(item['field']) + ' AS ' + _quote(_name(item['name']))); names.append(item['name'])
        groups = [field(ref) for ref in spec['group_by']]
        _require(not groups or spec['aggregates'], 'Group-by requires an aggregate')
        if spec['aggregates']:
            _require(all(item['field'] in spec['group_by'] for item in spec['projection']), 'Aggregate projections must be group keys')
        for agg in spec['aggregates']:
            _require(isinstance(agg, dict) and agg.get('op') in ('sum', 'count_rows', 'count_distinct', 'sum_product'), 'Unsupported aggregate')
            _keys(agg, ('op name left right numeric_type unit null_policy' if agg['op'] == 'sum_product'
                        else 'op name' if agg['op'] == 'count_rows' else 'op name field'))
            name = _name(agg['name']); names.append(name)
            if agg['op'] == 'sum_product':
                _require(agg['numeric_type'] == 'integer' and
                         agg['null_policy'] == 'exclude_if_any_operand_null', 'Unsupported product numeric or null policy')
                _text(agg['unit'])
                left, right = field(agg['left']), field(agg['right'])
                _require(all(agg[side]['alias'] == root['alias'] for side in ('left', 'right')),
                         'SUM product must use root-grain operands')
                typed.extend([(agg['left'], 'integer'), (agg['right'], 'integer')])
                expr = f'checked_sum_product({left}, {right})'
                null_measures[name] = f'(CASE WHEN {left} IS NULL OR {right} IS NULL THEN NULL ELSE 1 END)'
                product_measures[name] = {'left': left, 'right': right, 'unit': agg['unit']}
            elif agg['op'] == 'count_rows':
                expr = 'count(*)'
            else:
                f = field(agg['field'])
                null_measures[name] = f
                expr = ('sum(' if agg['op'] == 'sum' else 'count(DISTINCT ') + f + ')'
                if agg['op'] == 'sum':
                    _require(agg['field']['alias'] == root['alias'], 'SUM must use a root-grain measure')
                    typed.append((agg['field'], 'number'))
            outputs.append(expr + ' AS ' + _quote(name))
        _require(outputs and len(names) == len(set(names)), 'Output names must be distinct and nonempty')
        base = ' FROM ' + sql_from + (' WHERE ' + ' AND '.join(where) if where else '')
        query = 'SELECT ' + ('DISTINCT ' if spec['distinct'] else '') + ', '.join(outputs) + base
        if groups:
            query += ' GROUP BY ' + ', '.join(groups)
        # A scalar empty aggregate is explicitly absent rather than a synthetic
        # group with NULL SUM. COUNT over a nonempty all-null measure stays zero.
        elif spec['aggregates']:
            query += ' HAVING count(*) > 0'
        return {'query': query, 'base': base, 'bindings': bindings, 'typed': typed,
                'names': names, 'null_measures': null_measures, 'product_measures': product_measures,
                'scalars': scalars, 'comparisons': comparisons, 'sql_from': sql_from,
                'dependencies': {'fields': self._dependencies(draft, used), 'relations': rel_deps}}

    def propose(self, draft, spec, *, relations=None, origin):
        _require(len(_json(spec).encode()) <= 65536, 'Contract exceeds byte bound')
        draft = self.adapter.restore(draft)
        compiled = self._compile(draft, spec, relations or {})
        return self._envelope(draft, 'query', spec, compiled['dependencies'], origin)

    def approve(self, draft, pending, *, relations=None, **review):
        self._verify(pending)
        current = self.propose(draft, pending['spec'], relations=relations, origin=pending['origin'])
        _require(current['fingerprint'] == pending['fingerprint'], 'Query dependencies changed; renewed review required')
        return self._approve(pending, **review)

    def execute(self, draft, approved, parameters, *, relations=None, cancel_requested=None):
        callback = cancel_requested
        observed_cancel = False
        def poll():
            nonlocal observed_cancel
            observed_cancel = observed_cancel or (callback is not None and callback())
            return observed_cancel
        cancel_requested = poll
        partial = {'status': 'cancelled', 'rows': [], 'closure_complete': False,
                   'scope': 'incomplete_execution_evidence_not_a_query_answer'}
        try:
            check_cancel(cancel_requested)
            result = self._execute(draft, approved, parameters, relations=relations,
                                   cancel_requested=cancel_requested, partial=partial)
            check_cancel(cancel_requested)
            return result
        except (sqlite3.Error, DatabaseSourceError, ExecutionCancelled) as exc:
            if isinstance(exc, ExecutionCancelled) or observed_cancel:
                cancelled = ExecutionCancelled('Query cancelled; partial evidence retained; no automatic retry')
                cancelled.evidence = partial
                raise cancelled from exc
            raise

    def _execute(self, draft, approved, parameters, *, relations=None, cancel_requested=None, partial=None):
        if isinstance(approved, dict) and approved.get('version') == REACHABILITY_VERSION:
            from .workspace_query_reachability import execute
            return execute(self, draft, approved, parameters, relations or {}, cancel_requested=cancel_requested, partial=partial)
        self._verify(approved, approved=True)
        draft = self.adapter.restore(draft)
        check_cancel(cancel_requested)
        current = self.propose(draft, approved['spec'], relations=relations, origin=approved['origin'])
        _require(approved['kind'] == 'query' and current['fingerprint'] == approved['fingerprint'], 'Query approval is stale')
        spec = approved['spec']
        _require(isinstance(parameters, dict) and set(parameters) == set(spec['parameters']), 'Supply exactly the approved parameters')
        for name, kind in spec['parameters'].items():
            _typed(parameters[name], kind)
        compiled = self._compile(draft, spec, relations or {})
        registry = self.adapter.registry
        record = registry._record(draft['database']['source_id'])
        _require(record['snapshot_sha256'] == approved['source']['snapshot_sha256'], 'Snapshot binding changed')
        started = time.monotonic(); steps = 0
        def interrupted():
            nonlocal steps
            steps += 1
            return int((cancel_requested is not None and cancel_requested()) or steps > self.max_steps or time.monotonic() - started > self.timeout)
        check_cancel(cancel_requested)
        with registry._connection(registry._data(record)) as con:
            con.set_progress_handler(interrupted, 1)
            # Bindings and main query share one read transaction and VM budget.
            if 'scalar_bindings' in spec:
                con.execute('BEGIN')
            resolved, scalar_observations = {}, []
            for name, scalar in compiled['scalars'].items():
                binding = scalar['spec']
                table, selector, value = (_quote(scalar[k]) for k in ('table', 'selector', 'value'))
                for row in con.execute(f'SELECT {selector} FROM {table} WHERE {selector} IS NOT NULL'):
                    try:
                        _typed(row[0], binding['selector_type'])
                    except DatabaseSourceError:
                        raise DatabaseSourceError(f'unresolved_binding:{name}:invalid_type') from None
                    _require(time.monotonic() - started <= self.timeout, 'Query exceeded time limit')
                selected = con.execute(f'SELECT {value} FROM {table} WHERE '
                    f'(+{selector} COLLATE BINARY) = (+? COLLATE BINARY) LIMIT 2',
                    (parameters[binding['parameter']],)).fetchall()
                reason = 'absent' if not selected else 'multiple' if len(selected) > 1 else None
                if reason is None and selected[0][0] is None:
                    reason = 'null_value'
                if reason is not None:
                    raise DatabaseSourceError(f'unresolved_binding:{name}:{reason}')
                try:
                    resolved[name] = _typed(selected[0][0], binding['value_type'])
                except DatabaseSourceError:
                    raise DatabaseSourceError(f'unresolved_binding:{name}:invalid_type') from None
                scalar_observations.append({'name': name, 'parameter': binding['parameter'],
                    'selector_value': str(parameters[binding['parameter']]) if type(parameters[binding['parameter']]) is int else parameters[binding['parameter']],
                    'resolved_value': str(resolved[name]) if type(resolved[name]) is int else resolved[name],
                    'selector_value_encoding': 'decimal_integer_string' if type(parameters[binding['parameter']]) is int else 'json',
                    'resolved_value_encoding': 'decimal_integer_string' if type(resolved[name]) is int else 'json',
                    'selector_type': binding['selector_type'], 'value_type': binding['value_type'],
                    'matched_rows': 1, 'cardinality': 'exactly_one', 'null_policy': 'require_nonnull',
                    'comparison': 'binary_exact', 'source': deepcopy(approved['source']),
                    'binding_fingerprint': fingerprint(binding),
                    'field_entry_ids': {k: binding[k] for k in ('table_entry_id', 'selector_entry_id', 'value_entry_id')}})
            values = [resolved[k[1]] if isinstance(k, tuple) else parameters[k] for k in compiled['bindings']]
            comparison_nulls = [{'filter_index': item['filter_index'],
                'null_rows': con.execute('SELECT count(*) FROM ' + compiled['sql_from'] +
                    ' WHERE ' + item['null_expression']).fetchone()[0],
                'scope': 'whole_joined_root_before_query_filters'} for item in compiled['comparisons']]
            arithmetic_errors = set()
            class ExactProductSum:
                def __init__(self):
                    self.total = 0
                    self.included = False

                def step(self, left, right):
                    if left is None or right is None:
                        return
                    product = left * right
                    if not -(2**63) <= product < 2**63:
                        arithmetic_errors.add('product')
                        return
                    self.included = True
                    # Python integers preserve cancellation without order-dependent
                    # intermediate overflow. SQLite's VM budget bounds term count.
                    self.total += product

                def finalize(self):
                    if not -(2**63) <= self.total < 2**63:
                        arithmetic_errors.add('final sum')
                        return None
                    return self.total if self.included else None

            if compiled['product_measures']:
                con.create_aggregate('checked_sum_product', 2, ExactProductSum)
            # SQLite dynamic types must not silently coerce malformed numeric or
            # calendar operands. Validate every non-null source value, not samples.
            checked = set()
            for ref, kind in compiled['typed']:
                e = self._fields(draft)[ref['entry_id']]['source']
                key = (e['file'], e['column'], kind)
                if key in checked:
                    continue
                checked.add(key)
                for row in con.execute(f'SELECT {_quote(e["column"])} FROM {_quote(e["file"])} WHERE {_quote(e["column"])} IS NOT NULL'):
                    check_cancel(cancel_requested)
                    _typed(row[0], kind)
                    _require(time.monotonic() - started <= self.timeout, 'Query exceeded time limit')
            matched = con.execute('SELECT count(*)' + compiled['base'], values).fetchone()[0]
            null_exclusions = {name: con.execute(
                'SELECT count(*)' + compiled['base'] +
                (' AND ' if spec['filters'] else ' WHERE ') + expression + ' IS NULL', values).fetchone()[0]
                for name, expression in compiled['null_measures'].items()}
            product_observations = {}
            for name, measure in compiled['product_measures'].items():
                counts = con.execute(
                    f'SELECT count(*) FILTER (WHERE {measure["left"]} IS NULL), '
                    f'count(*) FILTER (WHERE {measure["right"]} IS NULL)' + compiled['base'], values).fetchone()
                product_observations[name] = {
                    'numeric_type': 'integer', 'unit': measure['unit'],
                    'value_encoding': 'decimal_integer_string',
                    'unit_status': 'reviewed_annotation_not_dimensional_verification',
                    'null_policy': 'exclude_if_any_operand_null',
                    'left_null_rows': counts[0], 'right_null_rows': counts[1],
                    'excluded_rows': null_exclusions[name],
                    'included_terms': matched - null_exclusions[name],
                    'scope': 'all_matched_root_rows_before_output_truncation'}
            join_observations = []
            for join in spec['joins']:
                rs = relations[join['relation_id']]['spec']
                child = self._fields(draft)[rs['child_entry_id']]['source']
                parent = self._fields(draft)[rs['parent_entry_id']]['source']
                c = _quote(child['column']); p = _quote(parent['column'])
                # Whole declared child-table scope, before question filters.
                nulls = con.execute(f'SELECT count(*) FROM {_quote(child["file"])} WHERE {c} IS NULL').fetchone()[0]
                predicate = _fk_predicate('p.' + p, 'c.' + c)
                dangling = con.execute(f'SELECT count(*) FROM {_quote(child["file"])} AS c '
                    f'WHERE c.{c} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {_quote(parent["file"])} AS p '
                    f'WHERE {predicate})').fetchone()[0]
                join_observations.append({'relation_id': join['relation_id'], 'child_alias': join['child_alias'],
                    'scope': 'whole_child_table_before_query_filters', 'null_child_keys': nulls,
                    'unmatched_nonnull_child_keys': dangling, 'join_policy': rs['join_policy']})
            total = con.execute('SELECT count(*) FROM (' + compiled['query'] + ')', values).fetchone()[0]
            order = ', '.join(_quote(n) for n in compiled['names'])
            rows = partial['rows']
            for item in con.execute(compiled['query'] + ' ORDER BY ' + order + ' LIMIT ?', (*values, self.max_rows)):
                check_cancel(cancel_requested)
                candidate = dict(item)
                _require(len(_json(rows + [candidate]).encode()) <= self.max_bytes, 'Query result exceeds byte limit')
                rows.append(candidate)
            _require(not arithmetic_errors, 'Integer product aggregate exceeds signed64 range: ' +
                     ', '.join(sorted(arithmetic_errors)))
            # JSON numbers above 2**53 lose precision in browser JSON.parse.
            # Only the new product outputs use strings; v1 outputs stay intact.
            for row in rows:
                for name in compiled['product_measures']:
                    if row[name] is not None:
                        row[name] = str(row[name])
            # Bytes, BLOBs and nonfinite arithmetic are rejected, never silently
            # replaced by a hash/prefix that could look like the requested value.
            _require(len(_json(rows).encode()) <= self.max_bytes, 'Query result exceeds byte limit')
        result = {'version': approved['version'], 'status': 'complete', 'rows': rows,
                'aggregate_null_exclusions': null_exclusions, 'join_observations': join_observations,
                'returned_count': len(rows), 'total_output_rows': total, 'matched_root_rows': matched,
                'truncated': total > len(rows), 'output_kind': spec['output_kind'],
                'scope': 'complete_registered_snapshot_query_not_external_truth',
                'null_policy': spec['null_policy'], 'empty_groups': spec['empty_groups'],
                'limitations': deepcopy(spec['limitations']),
                'policy_references': deepcopy(spec['policy_references']),
                'policy_reference_status': 'annotations_only_not_document_verification',
                'provenance': {'contract_fingerprint': approved['fingerprint'], 'review': deepcopy(approved['review']),
                               'origin': deepcopy(approved['origin']), 'source': deepcopy(approved['source']),
                               'dependency_fingerprint': fingerprint(approved['dependencies']),
                               'dependencies': deepcopy(approved['dependencies']), 'parameters': deepcopy(parameters)}}

        if 'scalar_bindings' in spec:
            result['scalar_binding_observations'] = scalar_observations
            result['comparison_null_exclusions'] = comparison_nulls
            result['provenance']['scalar_bindings'] = deepcopy(scalar_observations)
        if compiled['product_measures']:
            result['product_aggregate_observations'] = product_observations
        _require(len(_json(result).encode()) <= self.max_bytes, 'Query result and provenance exceed byte limit')
        return result
