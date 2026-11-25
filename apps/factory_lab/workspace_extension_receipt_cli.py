"""Associate an existing pending import with a private local invocation receipt.

No server route accepts these filesystem paths. This command trusts the local
operator and registry, preserves the original proposal, and grants no approval.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from .workspace_database import SQLiteSources
from .workspace_extension_receipt import associate_invocation
from .workspace_store import WorkspaceStore, encode

OPERATION_KIND = 'extension_invocation_association'


def associate_saved_import(store, registry, *, workspace_id, revision, import_operation_id,
                           invocation_dir, operator_id, request_key):
    """Persist once; replay never reads invocation artifacts or source registry.

    Registry must be a trusted local SQLiteSources instance (or equivalent).
    Filesystem arguments and operator identity are audit annotations, not signed
    credentials. Use a new request key for an explicitly inspected retry.
    """
    request = {'import_operation_id': import_operation_id,
               'invocation_directory': str(Path(invocation_dir).absolute()),
               'operator_id': operator_id}
    operation, created = store.begin(workspace_id, revision, request_key, OPERATION_KIND, request)
    if not created:
        return {'operation': store.operation(workspace_id, operation['id']), 'reused': True}
    result = {'format': 'workspace-invocation-association-1', 'status': 'rejected',
              'import_operation_id': import_operation_id, 'approval': 'not_granted',
              'producer_authenticated': False, 'upstream_input_verified': False,
              'local_source_link_verified': False, 'raw_receipt_base64': None,
              'losses': ['Receipt not read because source or import preflight failed']}
    try:
        row = store.get(workspace_id)
        imported = store.operation(workspace_id, import_operation_id)
        if (row['revision'] != revision or imported['revision'] != revision or
                imported['kind'] != 'extension_import' or imported['state'] != 'completed'):
            raise ValueError('Import must belong to current workspace revision')
        draft = row['draft']
        if draft.get('adapter') != 'registered-database-1':
            raise ValueError('Registered database workspace required')
        proposal = imported['result']
        expected = {s['name']: s['sha256'] for s in draft['sources']}
        if (proposal.get('base_workspace_digest') != row['digest'] or
                proposal.get('source_hashes') != expected or
                len(expected) != len(draft['sources'])):
            raise ValueError('Import source binding is stale')
        source_id = draft['database']['source_id']
        record = registry._record(source_id)
        source = registry._data(record)
        if sha256(source).hexdigest() != draft['database']['snapshot_sha256']:
            raise ValueError('Current source digest differs from workspace')
        result = associate_invocation(proposal, invocation_dir=invocation_dir,
            current_source_id=source_id, current_source_bytes=source,
            current_workspace_digest=row['digest'], operator_id=operator_id)
        result.update(import_operation_id=import_operation_id,
                      import_proposal_sha256=sha256(encode(proposal).encode()).hexdigest(),
                      workspace_id=workspace_id, revision=revision)
        # A concurrently edited workspace invalidates this new association.
        current = store.get(workspace_id)
        if current['revision'] != revision or current['digest'] != row['digest']:
            result['status'] = 'rejected'
            result['local_source_link_verified'] = False
            result['errors'].append('Workspace changed during receipt association')
        store.finish(operation['id'], 'completed' if result['status'] == 'linked' else 'failed',
                     result=result, error=None if result['status'] == 'linked' else 'Receipt association rejected')
    except (ValueError, KeyError, TypeError, OSError):
        result['status'] = 'rejected'
        result['local_source_link_verified'] = False
        try:
            store.finish(operation['id'], 'failed', result=result,
                         error='Receipt association preflight or persistence failed; inspect retained attempt')
        except ValueError:
            store.fail_preserving_checkpoint(operation['id'],
                'Receipt association failed; new receipt evidence could not be stored. '
                'Original import preserved; inspect local invocation files before an explicit retry.')
    return {'operation': store.operation(workspace_id, operation['id']), 'reused': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', required=True, type=Path)
    parser.add_argument('--registry', required=True, type=Path)
    parser.add_argument('--workspace-id', required=True)
    parser.add_argument('--revision', required=True, type=int)
    parser.add_argument('--import-operation-id', required=True)
    parser.add_argument('--invocation-dir', required=True, type=Path)
    parser.add_argument('--operator-id', required=True)
    parser.add_argument('--request-key', required=True)
    args = parser.parse_args(argv)
    if not args.store.is_file():
        parser.error('Existing workspace store required')
    # Defer registry creation/read until after durable replay. No source access
    # is necessary to view a completed, failed or interrupted prior attempt.
    class DeferredRegistry:
        def _record(self, source_id):
            if not args.registry.is_dir():
                raise ValueError('Existing registry required')
            self.registry = SQLiteSources(args.registry)
            return self.registry._record(source_id)

        def _data(self, record):
            return self.registry._data(record)
    try:
        saved = associate_saved_import(WorkspaceStore(args.store), DeferredRegistry(),
            workspace_id=args.workspace_id, revision=args.revision,
            import_operation_id=args.import_operation_id, invocation_dir=args.invocation_dir,
            operator_id=args.operator_id, request_key=args.request_key)
    except (ValueError, OSError):
        parser.exit(1, 'Association rejected; inspect existing operation history.\n')
    print(json.dumps(saved, indent=2, ensure_ascii=False))
    return 0 if saved['operation']['state'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
