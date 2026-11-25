"""Durability and isolation checks; fake receipts do not measure reasoning quality."""
import base64
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from apps.factory_lab.workspace_reasoning import (
    LocalReasoner, MAX_INPUT_BYTES, OUTPUT_BYTES, capability, execute,
)
from apps.factory_lab.workspace_store import WorkspaceStore


class WorkspaceReasoningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'workspace.sqlite'
        self.store = WorkspaceStore(self.path)
        self.row = self.store.create('Reasoning fixture', {'sources': [], 'approved': True})
        self.raw = b'<urn:x> <urn:p> <urn:y> .\n'
        self.encoded = base64.b64encode(self.raw).decode()
        self.calls = []
        self.receipt = {'status': 'completed', 'stdout': 'raw output',
                        'binary_sha256': 'a' * 64, 'profile': 'rdfs',
                        'derivation_artifacts': {'derivations.tsv': {'text': 'raw derivation'}}}
        def runner(binary, raw, **kwargs):
            self.calls.append((binary, raw, kwargs))
            return deepcopy(self.receipt)
        self.reasoner = LocalReasoner('/trusted/operator/binary', runner=runner)

    def run_one(self, **kwargs):
        params = dict(store=self.store, reasoner=self.reasoner, key=self.row['id'],
                      revision=1, request_key='once', asserted_base64=self.encoded, profile='rdfs')
        params.update(kwargs)
        return execute(**params)

    def test_receipt_restart_idempotency_and_no_workspace_mutation(self):
        first = self.run_one()
        self.assertEqual(first['operation']['state'], 'completed')
        result = first['operation']['result']
        self.assertEqual(result['receipt'], self.receipt)
        self.assertEqual(result['approval'], 'not_granted')
        self.assertEqual(result['workspace_membership'], 'unverified')
        self.assertEqual(first['operation']['request']['asserted_base64'], self.encoded)
        again = self.run_one(store=WorkspaceStore(self.path), reasoner=None)
        self.assertTrue(again['reused'])
        self.assertEqual(again['operation'], first['operation'])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][2]['max_output_bytes'], OUTPUT_BYTES)
        self.assertEqual(self.store.get(self.row['id']), self.row)
        with self.assertRaises(ValueError):
            self.run_one(profile='owl-rl')

    def test_partial_timeout_and_failure_are_retained_and_never_retried(self):
        for status in ('partial', 'timed_out', 'failed'):
            self.receipt['status'] = status
            out = self.run_one(request_key=status)
            self.assertEqual(out['operation']['state'], 'failed')
            self.assertEqual(out['operation']['result']['receipt'], self.receipt)
            self.assertTrue(self.run_one(request_key=status)['reused'])
        self.assertEqual(len(self.calls), 3)

    def test_invalid_input_and_disabled_service_do_not_begin(self):
        for args in ({'asserted_base64': '!'}, {'profile': 'owl-dl'},
                     {'asserted_base64': base64.b64encode(b'\xff').decode()},
                     {'asserted_base64': base64.b64encode(b'a' * (MAX_INPUT_BYTES + 1)).decode()},
                     {'reasoner': None}):
            with self.subTest(args=list(args)), self.assertRaises(ValueError):
                self.run_one(**args)
        self.assertEqual(self.store.operations(self.row['id']), [])
        self.assertFalse(self.calls)

    def test_reservation_capacity_failure_prevents_launch_and_preserves_attempt(self):
        with patch('apps.factory_lab.workspace_store.MAX_STORED_BYTES', 10000):
            out = self.run_one()
        self.assertEqual(out['operation']['state'], 'failed')
        self.assertEqual(out['operation']['request']['asserted_base64'], self.encoded)
        self.assertFalse(self.calls)
        self.assertTrue(self.run_one()['reused'])

    def test_native_exception_becomes_failed_operation(self):
        self.reasoner.runner = lambda *args, **kwargs: (_ for _ in ()).throw(OSError('private path'))
        out = self.run_one()
        self.assertEqual(out['operation']['state'], 'failed')
        self.assertNotIn('private path', out['operation']['error'])
        self.assertTrue(self.run_one()['reused'])

    def test_stale_and_archived_revisions_cannot_launch(self):
        self.store.save(self.row['id'], {'sources': [], 'changed': True}, 1)
        with self.assertRaises(ValueError):
            self.run_one()
        self.store.archive(self.row['id'])
        with self.assertRaises(ValueError):
            self.run_one(revision=2)
        self.assertFalse(self.calls)

    def test_cancel_capability_and_terminal_noop(self):
        self.run_one()
        progress = self.store.request_cancel(self.row['id'], 'once')
        self.assertEqual(progress['state'], 'completed')
        self.assertEqual('cooperative_owned_process', capability(self.reasoner)['cancellation'])
        self.assertNotIn('binary', capability(self.reasoner))

    def test_interrupted_attempt_never_restarts(self):
        out = self.run_one()
        with self.store.connect() as db:
            db.execute("UPDATE operations SET state='running' WHERE id=?", (out['operation']['id'],))
        self.store.recover_interrupted()
        self.assertEqual(self.run_one()['operation']['state'], 'interrupted')
        self.assertEqual(len(self.calls), 1)


class ReviewedRealBinarySmoke(unittest.TestCase):
    @unittest.skipUnless(__import__('os').environ.get('FACTORY_OO_REVIEWED_SMOKE') == '1',
                         'Requires completed review and explicit operator opt-in')
    def test_explicitly_pinned_local_binary(self):
        import os
        from hashlib import sha256
        binary = Path(os.environ['FACTORY_OO_BINARY']).resolve(strict=True)
        self.assertEqual(sha256(binary.read_bytes()).hexdigest(), os.environ['FACTORY_OO_BINARY_SHA256'])
        with tempfile.TemporaryDirectory() as folder:
            store = WorkspaceStore(Path(folder) / 'workspace.sqlite')
            row = store.create('Bounded smoke only', {'sources': []})
            raw = (b'@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
                   b'<urn:A> rdfs:subClassOf <urn:B> . <urn:x> a <urn:A> .\n')
            out = execute(store, LocalReasoner(binary), row['id'], 1, 'reviewed-smoke',
                          base64.b64encode(raw).decode(), 'rdfs')
            self.assertEqual(out['operation']['state'], 'completed')
            receipt = out['operation']['result']['receipt']
            self.assertEqual(receipt['binary_sha256'], os.environ['FACTORY_OO_BINARY_SHA256'])
            from rdflib import Graph, RDF, URIRef
            graph = Graph().parse(data=receipt['closure_turtle'], format='turtle')
            self.assertIn((URIRef('urn:x'), RDF.type, URIRef('urn:B')), graph)
            self.assertEqual(store.get(row['id']), row)


class ServerReasoningConfiguration(unittest.TestCase):
    def test_operator_opt_in_and_saved_receipt_without_gateway(self):
        from apps.factory_lab.public_runtime import Demo
        from apps.factory_lab.public_server import make_server
        with tempfile.TemporaryDirectory() as folder:
            demo = Demo(Path(folder))
            server = make_server(demo, 0)
            try:
                row = server.workspace.handle({'action': 'example', 'domain': 'commerce'})
                self.assertFalse(row['local_reasoning']['enabled'])
            finally:
                server.server_close()
            server = make_server(demo, 0, workspace_reasoner_binary='/usr/bin/true')
            try:
                self.assertIsNone(demo.gateway)
                service = server.workspace
                receipt = {'status': 'completed', 'profile': 'rdfs', 'binary_sha256': 'a' * 64}
                with patch.object(service.local_reasoner, 'run', return_value=receipt) as run:
                    payload = {'action': 'local_reasoning', 'id': row['id'], 'revision': row['revision'],
                               'request_key': 'server-configuration', 'profile': 'rdfs',
                               'asserted_base64': base64.b64encode(b'<urn:x> <urn:p> <urn:y>.').decode()}
                    with self.assertRaises(ValueError):
                        service.handle({**payload, 'binary': '/untrusted/from/browser'})
                    result = service.handle(payload)
                    self.assertEqual(result['operation']['result']['receipt'], receipt)
                    self.assertEqual(result['operation']['state'], 'completed')
                    self.assertEqual(run.call_count, 1)
                service.local_reasoner = None
                self.assertTrue(service.handle(payload)['reused'])
            finally:
                server.server_close()
