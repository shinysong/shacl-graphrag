"""Fixed single-table reads over approved fields; no generated SQL or policy decision."""
from copy import deepcopy
import json
import math
from .workspace_database import DatabaseSourceError, _quote

OPS = {'eq': '=', 'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<='}


def catalog(adapter, draft):
    fields = adapter.row_catalog(draft)
    if len(fields) > 128:
        return {'name': 'query_source', 'enabled': False, 'fields': [],
                'reason': 'Approved field catalog exceeds 128 fields; no fields silently omitted.'}
    return {'name': 'query_source', 'enabled': bool(fields), 'fields': fields,
            'arguments': {'projection': '1..12 approved entry IDs from ONE table',
                          'filters': '0..4 objects: entry_id, op (eq/gt/gte/lt/lte), value'},
            'scope': 'Whole saved snapshot, approved fields only, AND filters, max50 rows; '
                     'numeric inequalities accept SQLite integer/real cells only; NULL/text excluded and counted. '
                     'No joins, policy evaluation, inventory reservation or order eligibility.'}


def execute(adapter, draft, arguments):
    draft = adapter.restore(draft)
    if not isinstance(arguments, dict) or set(arguments) != {'projection', 'filters'}:
        raise DatabaseSourceError('Provide projection and filters only')
    projection, filters = arguments['projection'], arguments['filters']
    if (not isinstance(projection, list) or not 1 <= len(projection) <= 12
            or any(not isinstance(i, str) for i in projection) or len(set(projection)) != len(projection)
            or not isinstance(filters, list) or len(filters) > 4):
        raise DatabaseSourceError('Source query exceeds field/filter bounds')
    approved = {f['entry_id']: f for f in adapter._catalog(draft)}
    used = set(projection)
    clauses, values, type_guards = [], [], []
    for item in filters:
        if (not isinstance(item, dict) or set(item) != {'entry_id', 'op', 'value'}
                or not isinstance(item['entry_id'], str) or item['entry_id'] not in approved
                or not isinstance(item['op'], str) or item['op'] not in OPS):
            raise DatabaseSourceError('Filter requires an approved field and supported operator')
        value = item['value']; numeric = type(value) in (int, float)
        if not (value is None or isinstance(value, str) and len(value) <= 2000
                or numeric and abs(value) <= 1e100 and math.isfinite(value)):
            raise DatabaseSourceError('Filter value must be bounded text, NULL or a finite number')
        if item['op'] != 'eq' and not numeric:
            raise DatabaseSourceError('Inequality requires a finite numeric value')
        col = _quote(approved[item['entry_id']]['column'])
        if numeric:
            guard = f"typeof({col}) IN ('integer','real')"
        elif value is None:
            guard = f'{col} IS NULL'
        else:
            guard = f"typeof({col})='text'"
        type_guards.append(guard)
        clauses.append(f'({guard} AND {col} {"IS" if value is None else OPS[item["op"]]} ?)')
        values.append(value); used.add(item['entry_id'])
    if not used <= set(approved):
        raise DatabaseSourceError('Projection requires approved fields')
    tables = {approved[i]['file'] for i in used}
    if len(tables) != 1:
        raise DatabaseSourceError('Source query requires one table; joins are unsupported')
    table = tables.pop(); selected = [approved[i] for i in projection]
    record = adapter.registry._record(draft['database']['source_id'])
    if record['snapshot_sha256'] != draft['database']['snapshot_sha256']:
        raise DatabaseSourceError('Source snapshot changed; renewed review required')
    sql_from = ' FROM ' + _quote(table)
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    with adapter.registry._connection(adapter.registry._data(record)) as con:
        total = con.execute('SELECT count(*)' + sql_from).fetchone()[0]
        matched = con.execute('SELECT count(*)' + sql_from + where, values).fetchone()[0]
        valid_types = (con.execute('SELECT count(*)' + sql_from + ' WHERE ' + ' AND '.join(type_guards)).fetchone()[0]
                       if type_guards else total)
        rows = adapter.registry._rows(con.execute('SELECT ' + ','.join(_quote(f['column']) for f in selected)
                                                 + sql_from + where + ' LIMIT 51', values))
    result = {'mode': 'approved_source_query', 'output_kind': 'recorded_facts',
              'source_id': record['source_id'], 'source_version': record['snapshot_sha256'],
              'table': table, 'selection': deepcopy(arguments), 'reviewed_columns': selected,
              'records': rows[:50], 'returned_count': min(len(rows), 50), 'limit': 50,
              'total_source_rows': total, 'total_matching_rows': matched, 'truncated': len(rows) > 50,
              'excluded_by_filter_type_rows': total-valid_types,
              'notice': 'Recorded snapshot rows only. Numeric text is not coerced. Duplicates retained; '
                        'row ordering is unspecified. Does not establish current stock, reservation or order eligibility.'}
    if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode()) > 180000:
        raise DatabaseSourceError('Source query evidence exceeds 180000 bytes; narrow projection')
    return result
