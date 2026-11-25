"""Authenticated deployment's injected upstream boundary; no implicit configuration.

The caller owns authentication, authorization, campaign metering and serialization.
This service never reads credentials or starts a gateway. The injected invocation
must call the pinned native bridge with its own fixed operator configuration.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re

from .workspace_database_adapter import DatabaseWorkspaceAdapter
from .workspace_extensions import MAX_BYTES, UPSTREAM, _load


KIND = 'extension_generation'
_STATUSES = {'returned_requires_review', 'failed', 'timed_out',
             'interrupted_or_launch_failed', 'source_copy_changed',
             'rejected_or_launch_failed'}
_SECRET_KEYS = {'password', 'passwd', 'secret', 'token', 'api_key', 'apikey',
                'access_token', 'authorization', 'connection_string', 'credentials',
                'connection_url', 'postgres_config', 'gateway'}


def _reject_configuration(value):
    """Do not publish an export carrying operator configuration fields."""
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r'[^a-z0-9]+', '_', key.lower()).strip('_')
            if normalized in _SECRET_KEYS or normalized.endswith(('_password', '_api_key', '_secret', '_token')):
                raise ValueError('Native export contains private configuration fields')
            _reject_configuration(child)
    elif isinstance(value, list):
        for child in value:
            _reject_configuration(child)


class SharedExtensions:
    """One synchronous native attempt, followed by pending import only.

    invocation(registry, source_id, *, output_root, mode) returns the bridge
    receipt. It must retain native files beneath output_root/invocation_id.
    Replays never invoke, re-import, or inspect native files again.
    """

    def __init__(self, workspace, registry, invocation, outputroot):
        if not callable(invocation):
            raise ValueError('Trusted invocation callable required')
        self.workspace = workspace
        self.registry = registry
        self.adapter = DatabaseWorkspaceAdapter(registry)
        self.invocation = invocation
        self.outputroot = Path(outputroot).resolve()
        self.outputroot.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.outputroot.chmod(0o700)

    def handle(self, body):
        return self.start(body)

    def start(self, body):
        if (not isinstance(body, dict) or set(body) != {'id', 'revision', 'request_key', 'mode'}
                or body['mode'] not in ('catalog', 'semantic')
                or not isinstance(body['id'], str) or type(body['revision']) is not int):
            raise ValueError('Provide workspace identity, revision, request key and catalog/semantic mode')
        store = self.workspace.store
        row = store.get(body['id'], body['revision'])
        draft = row['draft']
        if draft.get('adapter') != 'registered-database-1':
            raise ValueError('Upstream generation requires a registered database workspace')
        request = {'mode': body['mode'], 'base_digest': row['digest']}
        operation, created = store.begin(body['id'], body['revision'], body['request_key'], KIND, request)
        oid = operation['id']
        if not created:
            return {'operation': store.operation(body['id'], oid), 'reused': True}
        evidence = {'format': 'shared-extension-generation-1', 'mode': body['mode'],
                    'status': 'reserved_before_launch', 'approval': 'not_granted',
                    'import_operation_id': None,
                    'input_scope': ('complete_source_metadata_only' if body['mode'] == 'catalog'
                                    else 'complete_small_source_semantic'),
                    'paid': body['mode'] == 'semantic'}
        private = self.outputroot / oid
        try:
            private.mkdir(mode=0o700, exist_ok=False)
            # Restore against this invocation's registry, not a browser source ID.
            restored = self.adapter.restore(draft)
            database = restored['database']
            source_id, fingerprint = database['source_id'], database['snapshot_sha256']
            evidence.update(source_id=source_id, source_sha256=fingerprint,
                            upstream_commit=UPSTREAM['commit'])
            store.checkpoint(oid, evidence)
            receipt = self.invocation(self.registry, source_id,
                                      output_root=private / 'invocations', mode=body['mode'])
            # Retain exact native receipt privately; no native error/log/path fields
            # are copied into workspace API results.
            raw_receipt = json.dumps(receipt, ensure_ascii=False, allow_nan=False).encode()
            descriptor = os.open(private / 'returned-receipt.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw_receipt)
            if not isinstance(receipt, dict) or receipt.get('status') not in _STATUSES:
                raise ValueError('Unsupported native receipt')
            evidence['status'] = receipt['status']
            evidence['receipt_sha256'] = hashlib.sha256(raw_receipt).hexdigest()
            if body['mode'] == 'semantic':
                observed = receipt.get('gateway_observation')
                required_observation = {'new_provider_attempts', 'new_cache_hits', 'internal_model_error_observed'}
                if (not isinstance(observed, dict) or not required_observation <= set(observed)
                        or set(observed) - required_observation - {'requested_description_language'}
                        or ('requested_description_language' in observed
                            and observed['requested_description_language'] != 'ko')
                        or any(type(observed[k]) is not int or observed[k] < 0 for k in
                               ('new_provider_attempts', 'new_cache_hits'))
                        or type(observed['internal_model_error_observed']) is not bool):
                    raise ValueError('Verified native model execution observation required')
                evidence['native_model_execution'] = observed
                if observed['internal_model_error_observed'] or not (
                        observed['new_provider_attempts'] or observed['new_cache_hits']):
                    raise ValueError('Model work failed or was not observed; native export is not semantic success')
            store.checkpoint(oid, evidence)
            if receipt['status'] != 'returned_requires_review':
                raise ValueError('Native invocation did not complete')
            if (receipt.get('source_id') != source_id or receipt.get('source_sha256') != fingerprint
                    or receipt.get('mode') != body['mode'] or receipt.get('upstream_commit') != UPSTREAM['commit']):
                raise ValueError('Native receipt does not match the registered source')
            native_id = receipt.get('invocation_id')
            if not isinstance(native_id, str) or not re.fullmatch(r'[a-f0-9]{32}', native_id):
                raise ValueError('Invalid native invocation identity')
            export = private / 'invocations' / native_id / 'native-export.yaml'
            # The child is trusted; nevertheless never follow an artifact symlink
            # outside the operator-owned invocation directory.
            if export.is_symlink() or export.resolve().parent != (private / 'invocations' / native_id).absolute():
                raise ValueError('Invalid native export location')
            with export.open('rb') as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('Native export exceeds import boundary')
            fingerprint_export = hashlib.sha256(raw).hexdigest()
            outputs = receipt.get('outputs', [])
            if not isinstance(outputs, list) or not any(isinstance(item, dict)
                    and item.get('name') == 'native-export.yaml'
                    and item.get('bytes') == len(raw) and item.get('sha256') == fingerprint_export
                    for item in outputs):
                raise ValueError('Native export does not match receipt')
            _reject_configuration(_load(raw))
            # Recheck binding after native work, before saving a new import.
            current = store.get(body['id'])
            if current['revision'] != body['revision'] or current['digest'] != row['digest'] or current['archived']:
                raise ValueError('Workspace changed during native execution')
            self.adapter.restore(current['draft'])
            evidence.update(native_invocation_id=native_id, export_sha256=fingerprint_export,
                            export_bytes=len(raw), status='export_ready_for_pending_import')
            store.checkpoint(oid, evidence)
            imported = self.workspace.handle({'action': 'extension_import', 'id': body['id'],
                'revision': body['revision'], 'request_key': 'native-import-' + oid,
                'raw_base64': base64.b64encode(raw).decode('ascii')})['operation']
            evidence['import_operation_id'] = imported['id']
            if imported['state'] != 'completed':
                evidence['status'] = 'pending_import_failed'
                raise ValueError('Native export import failed')
            evidence['status'] = 'pending_review'
            store.finish(oid, 'completed', result=evidence)
        except BaseException as exc:
            # Fixed public message: upstream exceptions can contain config paths.
            evidence['last_stage'] = evidence['status']
            evidence['status'] = 'failed'
            evidence['failure_class'] = type(exc).__name__
            try:
                store.finish(oid, 'failed', result=evidence,
                             error='Upstream generation or pending import failed; private artifacts retained. No automatic retry.')
            except Exception:
                store.fail_preserving_checkpoint(oid, 'Upstream attempt failed; retained checkpoint and private artifacts require inspection.')
            if not isinstance(exc, Exception):
                raise
        return {'operation': store.operation(body['id'], oid), 'reused': False}
