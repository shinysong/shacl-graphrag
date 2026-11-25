"""Local operator receipt association, never upstream identity authentication.

Only trusted Python/CLI callers may select invocation_dir. An HTTP upload or a
JSON ``verified`` field cannot cross this boundary. The operator must protect the
directory and its ancestors from replacement and must trust its provenance; UID
and mode checks cannot distinguish a forged receipt written by that same user.
No signatures, model quality, semantic success, or human approval are inferred.
"""
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat

from .auto_ontology_bridge import UPSTREAM_COMMIT
from .workspace_extensions import import_auto_ontology, MAX_BYTES
from .workspace_store import encode


def _hash(raw):
    return sha256(raw).hexdigest()


def _read(directory_fd, name, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o022 or info.st_size > limit):
            raise ValueError('Untrusted or oversized invocation file')
        raw = stream.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('Invocation file exceeds byte limit')
        return raw


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate receipt key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def associate_invocation(proposal, *, invocation_dir, current_source_id,
                         current_source_bytes, current_workspace_digest, operator_id):
    """Return a linked/rejected audit record; never mutate the pending proposal.

    current_source_bytes must be read by the caller from the verified registered
    snapshot, not supplied by an HTTP client. Receipt read failures are explicit;
    exact original receipt bytes are retained whenever safely readable.
    """
    if not isinstance(operator_id, str) or not 1 <= len(operator_id.strip()) <= 120:
        raise ValueError('Provide a bounded local operator annotation')
    result = {'format': 'workspace-invocation-association-1', 'status': 'rejected',
              'trust_basis': 'local_operator_filesystem', 'operator_id': operator_id,
              'producer_authenticated': False, 'upstream_input_verified': False,
              'approval': 'not_granted', 'proposal_status': 'pending',
              'raw_receipt_base64': None, 'receipt_sha256': None,
              'errors': [], 'losses': [],
              'limitations': ['Operator provenance assertion, not authenticated upstream identity.',
                              'Returned stages do not verify semantic completeness or fallback absence.',
                              'Filesystem protection and trusted receipt creation are operator responsibilities.']}
    directory_fd = None
    try:
        directory_fd = os.open(Path(invocation_dir), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(directory_fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('Invocation directory must be private and operator-owned')
        raw_receipt = _read(directory_fd, 'receipt.json', MAX_BYTES)
        result.update(raw_receipt_base64=base64.b64encode(raw_receipt).decode(),
                      receipt_sha256=_hash(raw_receipt))
        receipt = _json(raw_receipt)
        if not isinstance(receipt, dict):
            raise ValueError('Receipt must be an object')
        # Preserve every original status/failure in raw_receipt_base64; never
        # upgrade upstream semantic_status or infer success from native return.
        for key in ('invocation_id', 'mode', 'status', 'semantic_status', 'fallback_status',
                    'cost_status', 'request_id', 'reservation_id', 'upstream_commit', 'stages'):
            result['invocation_' + key] = receipt.get(key)
        def require(condition, message):
            if not condition:
                raise ValueError(message)
        require(receipt.get('format') == 'auto-ontology-invocation-1', 'Unsupported receipt format')
        require(receipt.get('upstream_commit') == UPSTREAM_COMMIT, 'Upstream pin mismatch')
        iid = receipt.get('invocation_id')
        require(isinstance(iid, str) and re.fullmatch('[a-f0-9]{32}', iid), 'Invalid invocation identity')
        require(receipt.get('status') == 'returned_requires_review' and
                type(receipt.get('returncode')) is int and receipt['returncode'] == 0,
                'Invocation did not return successfully; original failure retained')
        mode = receipt.get('mode')
        require(mode in ('catalog', 'semantic'), 'Unsupported invocation mode')
        required = (['official_catalog_ingest_without_embeddings'] if mode == 'catalog' else
                    ['official_catalog_and_embedding_ingest', 'official_semantic_compile'])
        required += ['official_scoped_native_export']
        stages = receipt.get('stages')
        require(isinstance(stages, list) and all(isinstance(s, dict) for s in stages), 'Invalid stages')
        require([s.get('stage') for s in stages] == required and
                all(s.get('status') == 'returned' for s in stages), 'Incomplete or failed native stages')
        require(isinstance(current_source_bytes, bytes), 'Verified current source bytes required')
        source_digest = _hash(current_source_bytes)
        require(receipt.get('source_id') == current_source_id and
                receipt.get('source_sha256') == source_digest, 'Current registered source mismatch')
        require(isinstance(proposal, dict) and proposal.get('status') == 'pending' and
                proposal.get('base_workspace_digest') == current_workspace_digest,
                'Proposal is not pending on current workspace')
        hashes = proposal.get('source_hashes')
        require(isinstance(hashes, dict) and hashes and
                all(digest == source_digest for digest in hashes.values()), 'Proposal source binding mismatch')
        native = _read(directory_fd, 'native-export.yaml', MAX_BYTES)
        fresh = import_auto_ontology(native, base_workspace_digest=current_workspace_digest, source_hashes=hashes)
        require(fresh == proposal, 'Proposal differs from exact native export')
        outputs = receipt.get('outputs')
        require(isinstance(outputs, list) and all(isinstance(o, dict) for o in outputs), 'Invalid output manifest')
        require(len({o.get('name') for o in outputs}) == len(outputs), 'Duplicate output manifest name')
        def check_output(name, raw):
            matches = [o for o in outputs if o.get('name') == name]
            require(len(matches) == 1 and matches[0].get('sha256') == _hash(raw) and
                    type(matches[0].get('bytes')) is int and matches[0]['bytes'] == len(raw),
                    'Invocation output digest or byte count mismatch')
        check_output('native-export.yaml', native)
        exported = stages[-1].get('result')
        require(isinstance(exported, dict) and exported.get('sha256') == _hash(native) and
                type(exported.get('bytes')) is int and exported['bytes'] == len(native),
                'Native export stage digest or byte count mismatch')
        snapshot = _read(directory_fd, iid + '.sqlite', 256 * 1024 * 1024)
        require(snapshot == current_source_bytes, 'Invocation snapshot differs from current source')
        check_output(iid + '.sqlite', snapshot)
        schema_raw = _read(directory_fd, 'schema.json', MAX_BYTES)
        check_output('schema.json', schema_raw)
        schema = _json(schema_raw)
        require(isinstance(schema, list) and _hash(json.dumps(schema, sort_keys=True).encode()) ==
                receipt.get('schema_sha256'), 'Schema digest mismatch')
        connector = receipt.get('connector_binding', {})
        require(isinstance(connector, dict) and connector.get('database_name') == iid and
                connector.get('resolver') == 'official_get_connectors' and
                connector.get('snapshot_sha256') == source_digest, 'Connector source binding mismatch')
        require(mode != 'catalog' or receipt.get('semantic_status') == 'not_requested',
                'Catalog receipt cannot claim semantic generation')
        require(mode != 'semantic' or all(isinstance(receipt.get(k), str) and receipt[k]
                for k in ('request_id', 'reservation_id')), 'Missing semantic ledger bindings')
        result.update(status='linked', source_id=current_source_id, source_sha256=source_digest,
                      schema_sha256=receipt['schema_sha256'], export_sha256=_hash(native),
                      export_bytes=len(native), base_workspace_digest=current_workspace_digest,
                      proposal_sha256=_hash(encode(proposal).encode()),
                      source_binding='exact_snapshot_and_current_registered_source',
                      local_source_link_verified=True)
    except (ValueError, TypeError, KeyError, OSError, UnicodeError, RecursionError):
        # Avoid leaking private paths or attacker-controlled exception strings.
        result['errors'].append('Receipt association rejected: invalid, stale, unavailable or untrusted binding')
        result['local_source_link_verified'] = False
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
    if result['raw_receipt_base64'] is None:
        result['losses'].append('Original receipt unavailable or rejected by filesystem/size boundary')
    return result
