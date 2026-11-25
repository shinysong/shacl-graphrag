"""Explicit local adoption of an external field proposal; no upstream authority.

Review records are portable annotations, not authenticated attestations. Imported
SQL, new schema targets and implicit source-ID matching are never executable.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import PurePath
import re

from . import preparation as p
from . import workspace_store as storage

REVIEW_FIELDS = {'operation_id', 'candidate_id', 'entry_id', 'target',
                 'interpretation', 'note', 'manual_binding'}


def validated_records(draft):
    records = draft.get('extension_reviews', [])
    if not isinstance(records, list) or len(records) > 500:
        raise ValueError('Invalid external review history')
    keys = {'operation_id', 'candidate_id', 'entry_id', 'target', 'interpretation',
            'note', 'manual_binding', 'binding_method', 'source', 'source_hashes',
            'base_digest', 'base_revision', 'adopted_revision', 'review_operation_id',
            'raw_sha256', 'upstream', 'producer_authenticated', 'identity_basis',
            'invalidated', 'annotation_origin'}
    for record in records:
        if not isinstance(record, dict) or set(record) != keys:
            raise ValueError('Invalid external review record')
        text_fields = REVIEW_FIELDS | {'review_operation_id', 'identity_basis'}
        if any(not isinstance(record[k], str) or len(record[k]) > 4000 for k in text_fields):
            raise ValueError('Invalid external review text')
        if (record['producer_authenticated'] is not False or
                record['annotation_origin'] != 'local_review_or_imported_annotation_not_authenticated' or
                type(record['invalidated']) is not bool or
                record['binding_method'] not in ('exact_column_and_table_name', 'explicit_manual_binding')):
            raise ValueError('External review cannot authenticate an upstream producer')
        if any(type(record[k]) is not int or record[k] < 1 for k in ('base_revision', 'adopted_revision')):
            raise ValueError('Invalid external review revision')
        if record['adopted_revision'] != record['base_revision'] + 1:
            raise ValueError('Invalid external review revision transition')
        if any(not isinstance(record[k], str) or not re.fullmatch('[a-f0-9]{64}', record[k]) for k in ('base_digest', 'raw_sha256')):
            raise ValueError('Invalid external review hash')
        source = record['source']
        if not isinstance(source, dict) or set(source) != {'file', 'column', 'sha256'} or any(not isinstance(v, str) for v in source.values()):
            raise ValueError('Invalid external review source')
        hashes = record['source_hashes']
        if not isinstance(hashes, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not re.fullmatch('[a-f0-9]{64}', v) for k, v in hashes.items()):
            raise ValueError('Invalid external review source hashes')
        if hashes.get(source['file']) != source['sha256']:
            raise ValueError('External review source hash mismatch')
        if not isinstance(record['upstream'], dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in record['upstream'].items()):
            raise ValueError('Invalid upstream schema annotation')
    return deepcopy(records)


def active_annotations(draft, entry):
    hashes = {s['name']: s['sha256'] for s in draft['sources']}
    return [r for r in validated_records(draft) if not r['invalidated'] and
            r['entry_id'] == entry['id'] and r['source_hashes'] == hashes and
            all(r['source'][k] == entry['source'][k] for k in ('file', 'column')) and entry['status'] == 'approved' and
            all(r[k] == entry[k] for k in ('target', 'interpretation', 'note'))]


def _adopt(draft, digest, revision, operation, request, review_id, database_adapter=None):
    proposal = operation['result']
    hashes = {s['name']: s['sha256'] for s in draft['sources']}
    if (operation['kind'] != 'extension_import' or operation['state'] != 'completed' or
            operation['revision'] != revision or not isinstance(proposal, dict) or
            proposal.get('base_workspace_digest') != digest or proposal.get('source_hashes') != hashes):
        raise ValueError('External proposal must match the current source/review revision and digest')
    if proposal.get('unresolved_references'):
        raise ValueError('Resolve external references before importing a new proposal')
    candidate = next((c for c in proposal['fields'] if c['id'] == request['candidate_id']), None)
    if candidate is None or candidate['kind'] not in ('column', 'column_attribute'):
        raise ValueError('Only imported columns or column attributes can be reviewed; SQL is unsupported')
    column = candidate
    if candidate['kind'] == 'column_attribute':
        column = next((c for c in proposal['fields'] if c['kind'] == 'column' and
                       c['source_id'] == candidate['source_payload'].get('column_id')), None)
        if column is None:
            raise ValueError('Attribute requires a resolved physical column')
    table = next((c for c in proposal['concepts'] if c['kind'] == 'table' and c['id'] == column['parent_id']), None)
    if table is None:
        raise ValueError('Column requires a resolved physical table')
    paths = (candidate['source_path'], column['source_path'])
    if any(any(u['path'] == path or u['path'].startswith(path + '.') for path in paths)
           for u in proposal['unsupported']):
        raise ValueError('Candidate has unsupported fields; import a supported proposal')
    entry = next((e for e in draft['entries'] if e['id'] == request['entry_id'] and e['kind'] == 'mapping'), None)
    if entry is None:
        raise ValueError('Choose an existing source column mapping')
    source = next((s for s in draft['sources'] if s['name'] == entry['source']['file']), None)
    generic=draft.get('adapter')=='registered-database-1'
    if source is None or source['kind'] != ('database_table' if generic else 'table') or entry['source']['column'] not in source['headers']:
        raise ValueError('Selected source column is unavailable')
    matches = (column['source_payload'].get('name') == entry['source']['column'] and
               table['source_payload'].get('name') in ((source['name'],) if generic else
                                                      (source['name'], PurePath(source['name']).stem)))
    if not matches and not request['manual_binding'].strip():
        raise ValueError('Column/table names differ; record an explicit manual source binding reason')
    if not request['interpretation'].strip():
        raise ValueError('Record the reviewed field interpretation')
    if generic and database_adapter is None:
        raise ValueError('Registered database adapter is not configured')
    change=database_adapter.change if generic else p.change
    revised = change(draft, request['entry_id'], 'approved', request['target'],
                       request['note'], request['interpretation'])
    record = {**deepcopy(request), 'review_operation_id': review_id,
              'binding_method': 'explicit_manual_binding' if request['manual_binding'].strip() else 'exact_column_and_table_name',
              'source': {**deepcopy(entry['source']), 'sha256': source['sha256']}, 'source_hashes': hashes,
              'base_digest': digest, 'base_revision': revision, 'adopted_revision': revision + 1,
              'raw_sha256': proposal['raw_sha256'], 'upstream': deepcopy(proposal['upstream']),
              'identity_basis': proposal['identity_basis'], 'producer_authenticated': False,
              'invalidated': False, 'annotation_origin': 'local_review_or_imported_annotation_not_authenticated'}
    revised['extension_reviews'] = validated_records(draft) + [record]
    validated_records(revised)
    return revised, record


def review(store, key, revision, request_key, request, *, database_adapter=None):
    """Reserve attempt once, then atomically commit its decision and revision.

    A crash before commit leaves an inspectable running/interrupted attempt;
    replay never retries it. Failure writes no partial source decision.
    """
    if set(request) == {'operation_id', 'decisions'}:
        decisions = request['decisions']
        if not isinstance(decisions, list) or not 1 <= len(decisions) <= p.MAX_ENTRIES:
            raise ValueError('Provide a bounded external review decision group')
        if any(not isinstance(d, dict) or set(d) != REVIEW_FIELDS - {'operation_id'} for d in decisions):
            raise ValueError('Invalid external review decision fields')
        requests = [{**d, 'operation_id': request['operation_id']} for d in decisions]
    else:
        requests = [request]
    if any(set(r) != REVIEW_FIELDS or any(not isinstance(v, str) or len(v) > 4000 for v in r.values()) for r in requests):
        raise ValueError('Invalid external review fields')
    if any(len({r[k] for r in requests}) != len(requests) for k in ('entry_id', 'candidate_id')):
        raise ValueError('Duplicate external candidate or source entry in review group')
    operation, created = store.begin(key, revision, request_key, 'extension_review', request)
    if created:
        try:
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                workspace = db.execute('SELECT * FROM workspaces WHERE id=?', (key,)).fetchone()
                if workspace['archived'] or workspace['revision'] != revision:
                    raise ValueError('External review requires the current active revision')
                pending = db.execute('SELECT state FROM operations WHERE id=?', (operation['id'],)).fetchone()
                if pending['state'] != 'running':
                    raise ValueError('Review attempt is no longer running')
                original = db.execute('SELECT * FROM operations WHERE workspace=? AND id=?', (key, request['operation_id'])).fetchone()
                if original is None:
                    raise ValueError('Unknown external operation in this workspace')
                original = dict(original)
                original['result'] = json.loads(original['result']) if original['result'] else None
                saved = db.execute('SELECT * FROM revisions WHERE workspace=? AND number=?', (key, revision)).fetchone()
                revised = json.loads(saved['content'])
                if revised.get('adapter')=='registered-database-1':
                    if database_adapter is None:
                        raise ValueError('Registered database adapter is not configured')
                    revised=database_adapter.restore(revised)
                records = []
                for decision in requests:
                    revised, record = _adopt(revised, saved['digest'], revision, original, decision, operation['id'], database_adapter)
                    records.append(record)
                content = storage.encode(revised)
                digest = sha256(content.encode()).hexdigest()
                result = storage.encode({'adopted_revision': revision + 1, 'draft_digest': digest, 'reviews': records, **({'review': records[0]} if len(records) == 1 else {})})
                if revision >= storage.MAX_REVISIONS:
                    raise ValueError('Workspace revision limit reached')
                storage.require_capacity(db, len(content.encode()) + len(result.encode()))
                stamp = storage.now()
                db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)', (key, revision + 1, content, digest, stamp))
                db.execute('UPDATE workspaces SET revision=?,updated=? WHERE id=?', (revision + 1, stamp, key))
                db.execute("UPDATE operations SET state='completed',result=?,updated=? WHERE id=? AND state='running'", (result, stamp, operation['id']))
        except (ValueError, TypeError, KeyError) as exc:
            store.finish(operation['id'], 'failed', error=str(exc)[:1000])
    return {'operation': store.operation(key, operation['id']), 'reused': not created}
