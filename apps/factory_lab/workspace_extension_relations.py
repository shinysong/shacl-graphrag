"""Inert native relation resolution; no approval, SQL, registry or store writes.

resolve_relation(operation, workspace, *, candidate_id, child_entry_id,
parent_entry_id, interpretation, edit_reason='') accepts trusted store rows:
workspace has id/revision/digest/draft; operation is its saved extension_import.
Returns an origin dictionary suitable for ReviewedQueryContracts. The caller must
still restore source bytes and run the physical-FK/uniqueness and approval gates.
Import-time snapshot binding is NOT proof of the upstream generator's input.
"""
import base64
import binascii
from copy import deepcopy
from hashlib import sha256

from .workspace_extensions import import_auto_ontology
from .workspace_store import encode

MAX_ORIGIN_BYTES = 16384
ORIGIN_FORMAT = 'external-relation-origin-1'
ORIGIN_KIND = 'reviewed_external_candidate_binding'


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def resolve_relation(operation, workspace, *, candidate_id, child_entry_id,
                     parent_entry_id, interpretation, edit_reason=''):
    """Resolve one candidate against exact saved/current bindings, without I/O.

    Unsupported/malformed/stale data raises ValueError. Inputs are never mutated.
    All identities are local annotations, not authenticated attestations.
    """
    try:
        return _resolve(operation, workspace, candidate_id, child_entry_id,
                        parent_entry_id, interpretation, edit_reason)
    except (KeyError, TypeError, StopIteration, binascii.Error) as exc:
        raise ValueError('Malformed external relation binding') from exc


def _candidate(op, row, candidate_id):
    _require(isinstance(candidate_id, str) and 0 < len(candidate_id) <= 4000,
             'Provide bounded candidate ID')
    draft = row['draft']
    _require(draft['adapter'] == 'registered-database-1', 'Registered database required')
    _require(type(row['revision']) is int and row['revision'] >= 1, 'Invalid revision')
    _require(sha256(encode(draft).encode()).hexdigest() == row['digest'], 'Workspace digest mismatch')
    _require(op['kind'] == 'extension_import' and op['state'] == 'completed' and
             op['workspace'] == row['id'] and op['revision'] == row['revision'],
             'Import must belong to the current workspace revision')
    proposal = op['result']
    hashes = {s['name']: s['sha256'] for s in draft['sources']}
    _require(len(hashes) == len(draft['sources']) and hashes and
             all(v == draft['database']['snapshot_sha256'] for v in hashes.values()),
             'Source snapshot binding mismatch')
    _require(proposal['base_workspace_digest'] == row['digest'] and
             proposal['source_hashes'] == hashes, 'Stale import binding')
    encoded = proposal['raw_base64']
    _require(isinstance(encoded, str) and len(encoded) <= 1333336, 'Invalid raw export size')
    raw = base64.b64decode(encoded, validate=True)
    fresh = import_auto_ontology(raw, base_workspace_digest=row['digest'], source_hashes=hashes)
    _require(fresh == proposal, 'Saved proposal differs from original native bytes')
    matches = [c for c in fresh['relations'] if c['id'] == candidate_id]
    _require(len(matches) == 1, 'Choose one unambiguous external candidate')
    return fresh, matches[0]


def rejection_origin(operation, workspace, *, candidate_id, reason):
    """Current-bound rejection evidence, including unsupported candidate kinds.

    Scope is candidate selection only, never revocation of existing relations.
    Caller persists this value; no store mutation occurs here.
    """
    _require(isinstance(reason, str) and 0 < len(reason.strip()) <= 4000,
             'Rejection requires a bounded reason')
    try:
        proposal, candidate = _candidate(operation, workspace, candidate_id)
        result = {'format': 'external-relation-rejection-1', 'status': 'rejected',
                  'scope': 'candidate_selection_only_not_existing_relation_revocation',
                  'import_operation_id': operation['id'], 'candidate_id': candidate_id,
                  'candidate_kind': candidate['kind'], 'candidate_path': candidate['source_path'],
                  'candidate_payload_sha256': sha256(encode(candidate['source_payload']).encode()).hexdigest(),
                  'raw_sha256': proposal['raw_sha256'], 'reason': reason,
                  'source': deepcopy(workspace['draft']['database']),
                  'source_hashes': deepcopy(proposal['source_hashes']),
                  'workspace_id': workspace['id'], 'revision': workspace['revision'],
                  'draft_digest': workspace['digest'], 'producer_authenticated': False,
                  'upstream_input_verified': False, 'approval': 'not_granted'}
        _require(len(encode(result).encode()) <= MAX_ORIGIN_BYTES, 'Rejection evidence exceeds limit')
        return result
    except (KeyError, TypeError, StopIteration, binascii.Error) as exc:
        raise ValueError('Malformed external relation binding') from exc


def relation_origin(operation, workspace, *, candidate_id, spec, edit_reason):
    """Construct the reserved origin from a saved import and explicit edited spec."""
    _require(isinstance(spec, dict) and set(spec) == {
        'id', 'child_entry_id', 'parent_entry_id', 'interpretation', 'join_policy'},
        'Invalid external relation spec fields')
    origin = resolve_relation(operation, workspace, candidate_id=candidate_id,
        child_entry_id=spec['child_entry_id'], parent_entry_id=spec['parent_entry_id'],
        interpretation=spec['interpretation'], edit_reason=edit_reason)
    origin.update(upstream=deepcopy(operation['result']['upstream']),
                  edited_spec=deepcopy(spec))
    _require(len(encode(origin).encode()) <= MAX_ORIGIN_BYTES, 'External relation origin exceeds limit')
    return origin


def _resolve(op, row, candidate_id, child_id, parent_id, interpretation, reason):
    for value in (candidate_id, child_id, parent_id, interpretation):
        _require(isinstance(value, str) and 0 < len(value.strip()) <= 4000,
                 'Provide bounded candidate, field IDs and interpretation')
    _require(isinstance(reason, str) and len(reason) <= 4000, 'Invalid edit reason')
    fresh, candidate = _candidate(op, row, candidate_id)
    draft = row['draft']
    hashes = fresh['source_hashes']
    _require(candidate['kind'] in ('foreign_keys', 'semantic_fks'), 'Unsupported relation kind')
    touched = [candidate['source_path']]
    chain = []

    def item(kind, sid):
        found = [x for x in fresh['fields'] + fresh['concepts']
                 if x['kind'] == kind and x['source_id'] == sid]
        _require(len(found) == 1, 'Unresolved or ambiguous native endpoint')
        x = found[0]
        touched.append(x['source_path'])
        chain.append({'kind': kind, 'source_id': sid, 'source_path': x['source_path']})
        return x

    def physical(sid):
        col = item('column', sid)
        tables = [x for x in fresh['concepts'] if x['id'] == col['parent_id'] and x['kind'] == 'table']
        _require(len(tables) == 1, 'Missing physical table')
        table = tables[0]
        same_name = [x for x in fresh['concepts'] if x['kind'] == 'table' and
                     x['source_payload'].get('name') == table['source_payload']['name']]
        _require(len(same_name) == 1, 'Ambiguous native table name')
        siblings = [x for x in fresh['fields'] if x['kind'] == 'column' and
                    x['parent_id'] == table['id'] and
                    x['source_payload'].get('name') == col['source_payload']['name']]
        _require(len(siblings) == 1, 'Ambiguous native column name')
        # Table PK annotations are intentionally inert; unknown table metadata is
        # not silently inherited. Column descendants are checked separately.
        prefix = table['source_path'] + '.'
        _require(not any(u['path'].startswith(prefix) and
                         not u['path'].startswith(prefix + 'columns[') and
                         u['path'] != prefix + 'pk' for u in fresh['unsupported']),
                 'Unsupported physical table content')
        return {'table': table['source_payload']['name'], 'column': col['source_payload']['name']}

    payload = candidate['source_payload']
    if candidate['kind'] == 'foreign_keys':
        child = physical(payload['source_column_id'])
        parent = physical(payload['target_column_id'])
    else:
        if 'use_in_join_paths' in payload:
            _require(type(payload['use_in_join_paths']) is bool, 'Invalid upstream join hint')
        child = physical(payload['column_id'])
        targets = []
        if payload.get('concept_key_id'):
            key = item('concept_key', payload['concept_key_id'])
            ids = key['source_payload']['column_ids']
            _require(isinstance(ids, list) and len(ids) == 1, 'Only single-column concept keys supported')
            targets.append(physical(ids[0]))
        if payload.get('column_attribute_id'):
            attr = item('column_attribute', payload['column_attribute_id'])
            targets.append(physical(attr['source_payload']['column_id']))
        _require(targets and all(t == targets[0] for t in targets), 'Missing or conflicting semantic targets')
        parent = targets[0]
    _require(not any(any(u['path'] == p or u['path'].startswith(p + '.') for p in touched)
                     for u in fresh['unsupported']), 'Unsupported touched candidate content')

    chosen = {}
    for side, entry_id in (('child', child_id), ('parent', parent_id)):
        entries = [e for e in draft['entries'] if e['id'] == entry_id]
        _require(len(entries) == 1, 'Unknown or duplicate current field')
        e = entries[0]
        _require(e['kind'] == 'mapping' and e['status'] == 'approved', 'Endpoint field needs approval')
        source = e['source']
        tables = [s for s in draft['sources'] if s['name'] == source['file']]
        _require(len(tables) == 1 and source['column'] in tables[0]['headers'] and
                 source['sha256'] == hashes[source['file']], 'Endpoint source mismatch')
        chosen[side] = {'entry_id': entry_id, 'table': source['file'],
                        'column': source['column'], 'sha256': source['sha256']}
    original = {'child': child, 'parent': parent}
    edited = any(any(chosen[s][k] != original[s][k] for k in ('table', 'column')) for s in original)
    _require(not edited or reason.strip(), 'Endpoint edits require an explicit reason')
    origin = {'format': ORIGIN_FORMAT, 'kind': ORIGIN_KIND,
              'import_operation_id': op['id'], 'candidate_id': candidate_id,
              'candidate_kind': candidate['kind'], 'candidate_path': candidate['source_path'],
              'raw_sha256': fresh['raw_sha256'], 'candidate_payload_sha256': sha256(encode(payload).encode()).hexdigest(),
              'original_candidate': deepcopy(candidate),
              'resolution_chain': chain, 'native_endpoints': original, 'chosen_endpoints': chosen,
              'endpoint_edit': edited, 'edit_reason': reason, 'interpretation': interpretation,
              'upstream_join_hint': payload.get('use_in_join_paths'),
              'source': deepcopy(draft['database']), 'source_hashes': hashes,
              'workspace_id': row['id'], 'import_revision': row['revision'], 'import_digest': row['digest'],
              'producer_authenticated': False, 'upstream_input_verified': False,
              'binding_scope': 'current_import_snapshot_not_generator_input_attestation',
              'approval': 'not_granted', 'execution': 'not_performed'}
    _require(len(encode(origin).encode()) <= MAX_ORIGIN_BYTES, 'External relation origin exceeds limit')
    return origin
