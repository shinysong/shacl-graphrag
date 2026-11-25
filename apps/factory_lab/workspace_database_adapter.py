"""Generic reviewed-field reuse over operator-registered complete DB snapshots.

This boundary is deliberately independent of fixed commerce/factory contracts.
It needs an injected SQLiteSources registry, never a browser path or SQL string.
Schema and declared foreign keys are observations/proposals, not approvals.
There are no joins, document-policy evaluation, or business completeness claims.
Saved approvals are human-review records, not authenticated attestations.
"""
from copy import deepcopy
import hashlib
import json

from .workspace_database import DatabaseSourceError, SQLiteSources, _quote

ADAPTER = 'registered-database-1'
VERSION = 'database-workspace-draft-1'
STATES = {'pending', 'approved', 'excluded', 'insufficient'}
SOURCE_ONLY = 'source_only'


def _text(value, label, *, maximum=4000, required=False):
    if not isinstance(value, str) or len(value) > maximum or required and not value.strip():
        raise DatabaseSourceError(f'Invalid {label}')
    return value


def _entry_id(table, column):
    raw = json.dumps([table, column], ensure_ascii=False).encode()
    return 'db-map:' + hashlib.sha256(raw).hexdigest()


class DatabaseWorkspaceAdapter:
    """Trusted service dependency; register databases separately as an operator.

    The public draft carries opaque source IDs and hash-bound schema only.
    Samples are explicitly bounded and never copied into a CSV/row-prefix source.
    Exact lookups use all snapshot rows, projecting only approved columns.
    """

    def __init__(self, registry):
        if not isinstance(registry, SQLiteSources):
            raise TypeError('Inject an operator-configured SQLiteSources registry')
        self.registry = registry

    def create(self, source_id, metadata=None, *, domain='generic'):
        _text(domain, 'domain label', maximum=80, required=True)
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise DatabaseSourceError('Metadata must be an object')
        try:
            encoded = json.dumps(metadata, allow_nan=False)
        except (TypeError, ValueError):
            raise DatabaseSourceError('Metadata must be finite JSON') from None
        if len(encoded.encode()) > 65536:
            raise DatabaseSourceError('Metadata exceeds the allowed bound')
        info = self.registry.inspect(source_id, sample_limit=5)
        sources, entries, relationships = [], [], []
        for table in info['tables']:
            name = table['name']
            source = {
                'name': name, 'kind': 'database_table',
                'source_id': info['source_id'], 'sha256': info['snapshot_sha256'],
                'headers': [c['name'] for c in table['columns'] if c['hidden'] != 1],
                'columns': deepcopy(table['columns']),
                'primary_key': deepcopy(table['primary_key']),
                'foreign_keys': deepcopy(table['foreign_keys']),
                'row_count': table['row_count'],
                'sample': deepcopy(table['sample']), 'sample_limit': info['sample_limit'],
                'scope': 'whole_snapshot_table_with_bounded_sample',
            }
            sources.append(source)
            for column in source['headers']:
                entries.append({
                    'id': _entry_id(name, column), 'kind': 'mapping',
                    'source': {'file': name, 'column': column, 'sha256': source['sha256']},
                    'status': 'pending', 'target': SOURCE_ONLY,
                    'note': '', 'interpretation': '',
                })
            # Preserve composite-key grouping, column sequence, and actions.
            # Declared constraints neither authorize joins nor prove semantics.
            for foreign_key in table['foreign_keys']:
                relationships.append({
                    'table': name, 'source_id': info['source_id'],
                    'sha256': source['sha256'], 'declaration': deepcopy(foreign_key),
                    'status': 'pending', 'executable': False,
                    'origin': 'sqlite_declared_foreign_key',
                })
        return {
            'version': VERSION, 'adapter': ADAPTER, 'domain': domain,
            'metadata': deepcopy(metadata),
            'database': {k: deepcopy(info[k]) for k in (
                'source_id', 'label', 'snapshot_sha256', 'snapshot_bytes', 'format')},
            'sources': sources, 'entries': entries,
            'relationship_proposals': relationships,
            'capabilities': {'source_rows': True, 'joins': False,
                             'document_policy': 'unsupported',
                             'business_completeness': 'unknown'},
        }

    def sources(self):
        """List only hash-verified operator registrations, never private paths."""
        candidates=sorted(self.registry.root.glob('*.json'))
        result=[]
        for manifest in candidates[:100]:
            info=self.registry.inspect(manifest.stem, sample_limit=1)
            result.append({k:info[k] for k in ('source_id','label','snapshot_sha256')})
            result[-1].update(table_count=len(info['tables']),
                              total_rows=sum(t['row_count'] for t in info['tables']))
        return {'enabled':True,'sources':result,'truncated':len(candidates)>100}

    def restore(self, draft):
        """Validate live registry binding, schema, and every saved decision.

        A changed source needs a newly registered ID and a fresh pending draft.
        Source-file drift does not mutate an immutable registered snapshot.
        """
        if not isinstance(draft, dict) or draft.get('adapter') != ADAPTER:
            raise DatabaseSourceError('Unsupported database workspace draft')
        database = draft.get('database')
        if not isinstance(database, dict) or not isinstance(database.get('source_id'), str):
            raise DatabaseSourceError('Invalid registered source binding')
        baseline = self.create(database['source_id'], draft.get('metadata'),
                               domain=draft.get('domain'))
        if set(draft)-{'extension_reviews'} != set(baseline):
            raise DatabaseSourceError('Invalid database draft fields')
        for key in baseline.keys() - {'entries'}:
            if draft[key] != baseline[key]:
                raise DatabaseSourceError('Database source binding or schema changed; renewed review required')
        entries = draft['entries']
        if not isinstance(entries, list) or len(entries) != len(baseline['entries']):
            raise DatabaseSourceError('Missing or duplicate database fields')
        for entry, original in zip(entries, baseline['entries']):
            if not isinstance(entry, dict) or set(entry) != set(original):
                raise DatabaseSourceError('Invalid database mapping fields')
            if any(entry[k] != original[k] for k in ('id', 'kind', 'source')):
                raise DatabaseSourceError('Database field binding changed')
            self._validate_decision(entry)
        from .workspace_extension_review import validated_records
        validated_records(draft)
        return deepcopy(draft)

    @staticmethod
    def _validate_decision(entry):
        if not isinstance(entry['status'], str) or entry['status'] not in STATES:
            raise DatabaseSourceError('Invalid database review status')
        if entry['target'] != SOURCE_ONLY:
            raise DatabaseSourceError('Only reviewed source-column reuse is supported')
        _text(entry['note'], 'review note', required=entry['status'] == 'excluded')
        _text(entry['interpretation'], 'reviewed interpretation',
              required=entry['status'] == 'approved')

    def change(self, draft, entry_id, status, target=SOURCE_ONLY, note='', interpretation=''):
        updated = self.restore(draft)
        if not isinstance(entry_id, str):
            raise DatabaseSourceError('Unknown database field')
        entry = next((e for e in updated['entries'] if e['id'] == entry_id), None)
        if entry is None:
            raise DatabaseSourceError('Unknown database field')
        decision = dict(entry, status=status, target=target, note=note, interpretation=interpretation)
        self._validate_decision(decision)
        entry.update(decision)
        return updated

    @staticmethod
    def _catalog(draft):
        from .workspace_extension_review import active_annotations
        sources = {s['name']: s for s in draft['sources']}
        return [{
            'entry_id': e['id'], 'file': e['source']['file'],
            'column': e['source']['column'], 'sha256': e['source']['sha256'],
            'source_id': draft['database']['source_id'],
            'source_version': draft['database']['snapshot_sha256'],
            'reviewed_target': e['target'], 'reviewed_interpretation': e['interpretation'],
            'interpretation_origin': 'user_review_not_source_fact',
            'extension_reviews': active_annotations(draft,e),
            'total_source_rows': sources[e['source']['file']]['row_count'],
            'lookup_kind': 'source_rows', 'scope': 'whole_snapshot_table_exact_lookup',
        } for e in draft['entries'] if e['status'] == 'approved']

    def row_catalog(self, draft):
        return self._catalog(self.restore(draft))

    def execute_rows(self, draft, selection, *, limit=50):
        """Exact SQLite equality, preserving duplicates and explicit truncation.

        NULL and numeric filters retain SQLite types; this is not fuzzy search.
        Text/BLOB display truncation follows SQLiteSources, independently of the
        matched-row limit. No returned index is claimed to be a stable row ID.
        """
        draft = self.restore(draft)
        if (not isinstance(selection, dict) or set(selection) != {'entry_id', 'value'}
                or not isinstance(selection['entry_id'], str)):
            raise DatabaseSourceError('Choose an approved field and an exact value')
        catalog = self._catalog(draft)
        chosen = next((c for c in catalog if c['entry_id'] == selection['entry_id']), None)
        if chosen is None:
            raise DatabaseSourceError('Review the source column before querying its rows')
        reviewed = [c for c in catalog if c['file'] == chosen['file']]
        columns = [c['column'] for c in reviewed]
        source_id = chosen['source_id']
        result = self.registry.lookup(source_id, table=chosen['file'],
                                      filters={chosen['column']: selection['value']},
                                      columns=columns, limit=limit)
        if result['snapshot_sha256'] != chosen['source_version']:
            raise DatabaseSourceError('Database source version changed')
        # Exact count uses the same immutable, hash-verified snapshot binding.
        # Identifiers were checked by restore/lookup; values stay parameterized.
        # Kept inside this trusted adapter, never exposed as arbitrary SQL.
        record = self.registry._record(source_id)
        if record['snapshot_sha256'] != chosen['source_version']:
            raise DatabaseSourceError('Database source version changed')
        with self.registry._connection(self.registry._data(record)) as con:
            total = con.execute(
                f'SELECT count(*) FROM {_quote(chosen["file"])} '
                f'WHERE {_quote(chosen["column"])} IS ?', (selection['value'],)
            ).fetchone()[0]
        records = [{
            'values': row, 'columns': {c: c for c in columns},
            'source': {'file': chosen['file'], 'table': chosen['file'],
                       'source_id': source_id, 'sha256': chosen['source_version'],
                       'match_index': index},
        } for index, row in enumerate(result['rows'], 1)]
        source = next(s for s in draft['sources'] if s['name'] == chosen['file'])
        return {
            'mode': 'source_lookup', 'lookup_kind': 'source_rows',
            'status': 'matched_rows' if records else 'not_found_in_snapshot',
            'records': records, 'returned_count': len(records),
            'limit': result['limit'], 'total_matching_rows': total,
            'total_source_rows': source['row_count'], 'truncated': result['truncated'],
            'source_version': chosen['source_version'],
            'unreviewed_fields': [c for c in source['headers'] if c not in columns],
            'metadata': deepcopy(draft['metadata']),
            'scope': {**chosen, 'value': selection['value'], 'reviewed_columns': reviewed},
            'question': f'{chosen["file"]} · {chosen["column"]} exact source lookup',
            'answer': f'Returned {len(records)} of {total} matching snapshot rows.',
            'notice': 'Exact SQLite equality over the complete registered snapshot table. '
                      'Only approved columns are projected. Duplicate matches are retained. '
                      'No joins, policy decisions, current-source freshness or global absence claims.',
        }
