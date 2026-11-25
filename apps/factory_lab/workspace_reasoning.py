"""Optional synchronous reasoning of an uploaded snapshot, never workspace approval.

Trusted deployment code constructs LocalReasoner. Uploaded content cannot configure
its executable. Snapshot membership/completeness relative to workspace is unverified.
"""
from __future__ import annotations

import base64
import binascii
import inspect
from hashlib import sha256

from .open_ontologies_runner import reason_snapshot
from .workspace_store import encode, cancellation_callback, check_cancel, ExecutionCancelled

MAX_INPUT_BYTES = 64 * 1024
OUTPUT_BYTES = 128 * 1024
# Nine bounded text copies (stdout also parsed as events), worst JSON escaping,
# plus input and metadata fit this reservation. Store enforces the final bound.
RECEIPT_RESERVATION = 12 * 1024 * 1024


class LocalReasoner:
    """Operator-only configuration; no executable path accepted by execute()."""

    def __init__(self, binary, *, timeout=60, runner=reason_snapshot):
        if type(timeout) is not int or not 1 <= timeout <= 120:
            raise ValueError('Timeout must be 1..120 seconds')
        self.binary = binary
        self.timeout = timeout
        self.runner = runner

    def run(self, raw, profile, *, cancel_requested=None):
        check_cancel(cancel_requested)
        kwargs = dict(profile=profile, timeout=self.timeout, max_output_bytes=OUTPUT_BYTES)
        # Legacy trusted injected runners keep their two-argument protocol. Do
        # not catch TypeError and retry a runner that may already have executed.
        signature = inspect.signature(self.runner)
        if 'cancel_requested' in signature.parameters or any(
                p.kind == p.VAR_KEYWORD for p in signature.parameters.values()):
            kwargs['cancel_requested'] = cancel_requested
        return self.runner(self.binary, raw, **kwargs)


def capability(reasoner):
    return {'enabled': reasoner is not None, 'profiles': ['rdfs', 'owl-rl'],
            'input': 'uploaded_utf8_turtle', 'max_input_bytes': MAX_INPUT_BYTES,
            'output_file_bytes': OUTPUT_BYTES, 'execution': 'synchronous',
            'cancellation': 'cooperative_owned_process',
            'scope': 'uploaded snapshot only; workspace membership unverified',
            'policy': 'advisory', 'approval': 'not_granted'}


def execute(store, reasoner, key, revision, request_key, asserted_base64, profile):
    """Save one immutable attempt with pre-launch receipt capacity reservation.

    Failed/interrupted attempts are replayed, never retried under the same key.
    Original Turtle (including any inline ontology axioms) remains in the request.
    Built-in inference rules are identified by profile and binary hash in receipt.
    """
    if type(revision) is not int or revision < 1:
        raise ValueError('Invalid revision')
    if not isinstance(profile, str) or profile not in ('rdfs', 'owl-rl'):
        raise ValueError('Unsupported reasoning profile')
    if not isinstance(asserted_base64, str) or len(asserted_base64) > 4 * ((MAX_INPUT_BYTES + 2) // 3):
        raise ValueError('Snapshot exceeds input limit')
    try:
        raw = base64.b64decode(asserted_base64, validate=True)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError('Snapshot exceeds input limit')
        raw.decode('utf-8', 'strict')
    except (binascii.Error, UnicodeError) as exc:
        raise ValueError('Snapshot must be base64 encoded UTF-8 Turtle') from exc
    row = store.get(key, revision)
    request = {'asserted_base64': asserted_base64, 'input_sha256': sha256(raw).hexdigest(),
               'input_bytes': len(raw), 'profile': profile,
               'base_workspace_digest': row['digest'],
               'scope': 'uploaded snapshot only', 'workspace_membership': 'unverified',
               'ontology_axioms': 'inline in uploaded snapshot',
               'inference_rules': 'upstream built-in profile; binary hash in receipt'}
    # Disabled configurations can still replay saved evidence. A new request must
    # not reserve an execution while the optional operator configuration is absent.
    if reasoner is None:
        existing = [op for op in store.operations(key) if op['request_key'] == request_key]
        if not existing:
            raise ValueError('Local reasoning is not configured')
    operation, created = store.begin(key, revision, request_key, 'local_reasoning', request)
    if not created:
        return {'operation': store.operation(key, operation['id']), 'reused': True}
    oid = operation['id']
    evidence = {'format': 'workspace-reasoning-1', 'policy': 'advisory',
                'approval': 'not_granted', 'scope': request['scope'],
                'workspace_membership': 'unverified',
                'base_workspace_digest': row['digest'],
                'input_sha256': request['input_sha256'], 'receipt': None}
    try:
        # Reservation is real stored payload, so concurrent operations cannot use
        # this capacity. No process starts if the store cannot retain it.
        store.checkpoint(oid, {**evidence, 'status': 'reserved_before_launch',
                               'storage_reservation': ' ' * RECEIPT_RESERVATION})
        cancel = cancellation_callback(store, oid)
        check_cancel(cancel)
        receipt = reasoner.run(raw, profile, cancel_requested=cancel)
        evidence['receipt'] = receipt
        if len(encode(evidence).encode('utf-8')) > RECEIPT_RESERVATION:
            raise ValueError('Reasoning receipt exceeds reserved storage boundary')
        state = 'cancelled' if receipt.get('status') == 'cancelled' or store.cancel_requested(oid) else ('completed' if receipt.get('status') == 'completed' else 'failed')
        store.finish(oid, state, result=evidence,
                     error=None if state == 'completed' else 'Reasoning did not complete; raw receipt retained')
    except Exception as exc:
        # Expected native failures are receipts. Exceptions here concern launch,
        # persistence or the trusted adapter; never use arbitrary error text as UI.
        error = 'Local reasoning failed (' + type(exc).__name__ + '); inspect retained attempt before retry'
        try:
            if evidence['receipt'] is not None and len(encode(evidence).encode('utf-8')) > RECEIPT_RESERVATION:
                evidence['receipt'] = None
                evidence['receipt_error'] = 'Trusted runner violated configured receipt bound; receipt not stored'
            store.finish(oid, 'cancelled' if isinstance(exc, ExecutionCancelled) else 'failed', result=evidence, error=error)
        except Exception:
            store.fail_preserving_checkpoint(oid, error)
    return {'operation': store.operation(key, oid), 'reused': False}
