"""Offline contract tests; mocked HTTP is never experiment measurement."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from scripts import run_graph_lifecycle_study as m


class LifecycleTests(unittest.TestCase):
    def test_all_checkpoint_parity_and_reversals(self):
        with tempfile.TemporaryDirectory() as tmp:
            canonical = m.generate(100, 19)
            backends = [m.JsonBackend(False, Path(tmp) / 'scan.json'),
                        m.JsonBackend(True, Path(tmp) / 'indexed.json')]
            outputs = {}
            for checkpoint in m.CHECKPOINTS:
                change = m.mutation(checkpoint, 100)
                if checkpoint != 'initial':
                    m.apply(canonical, change)
                for backend in backends:
                    backend.update(initial=canonical) if checkpoint == 'initial' else backend.update(change=change)
                    self.assertEqual(json.loads(backend.location.read_text()), {k: canonical[k] for k in ('nodes', 'edges')})
                outputs[checkpoint] = {}
                for subject in ['p0', 'p2', 'p3', 'p17', 'new0', 'missing']:
                    expected = m.evaluate(canonical, subject)
                    for backend in backends:
                        self.assertEqual(backend.query(subject, canonical['config']), expected)
                    outputs[checkpoint][subject] = expected
            self.assertEqual(outputs['initial']['p0']['countries'], ['c0'])
            self.assertEqual(outputs['change_region']['p0']['countries'], ['c1'])
            self.assertEqual(outputs['delete_supply']['p2'], {'countries': [], 'paths': []})
            self.assertEqual(outputs['restore_supply']['p2'], outputs['change_region']['p2'])
            self.assertEqual(outputs['add_backup']['p3']['countries'], ['c1'])
            self.assertEqual(outputs['allow_backup']['p3']['countries'], ['c1', 'c2'])
            self.assertEqual(outputs['revert_rule']['p3'], outputs['add_backup']['p3'])
            self.assertEqual(outputs['initial']['new0']['countries'], [])
            self.assertEqual(outputs['add_products']['new0']['countries'], ['c0'])
            for checkpoint in outputs:
                self.assertEqual(outputs[checkpoint]['missing'], {'countries': [], 'paths': []})

    def test_config_only_update_preserves_graph_file_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            backend = m.JsonBackend(True, Path(tmp) / 'graph.json')
            backend.update(initial=m.generate(20, 1))
            before = backend.location.read_bytes()
            index = backend.adjacency
            with patch.object(m, 'atomic_json', side_effect=AssertionError('graph rewrite')):
                timing = backend.update(change=m.mutation('allow_backup', 20))
            self.assertEqual(timing['rebuild_index_ms'], 0.0)
            self.assertEqual(timing['serialization_fsync_replace_ms'], 0.0)
            self.assertIs(backend.adjacency, index)
            self.assertEqual(backend.location.read_bytes(), before)
            self.assertNotIn('config', json.loads(before))
            self.assertEqual(backend.snapshot['config'], m.rule(['primary', 'backup']))

    def test_mutation_restores_exact_source_and_rule_is_config_only(self):
        source = m.generate(20, 0)
        original = copy.deepcopy(source)
        m.apply(source, m.mutation('delete_supply', 20))
        m.apply(source, m.mutation('restore_supply', 20))
        self.assertEqual(sorted(source['edges'], key=lambda e: e['id']),
                         sorted(original['edges'], key=lambda e: e['id']))
        for checkpoint in ('allow_backup', 'revert_rule'):
            change = m.mutation(checkpoint, 20)
            self.assertFalse(change['add_edges'] or change['delete_ids'] or change['add_nodes'])
            m.apply(source, change)
        self.assertEqual(source['config'], original['config'])
        with self.assertRaises(ValueError):
            m.rule(['unbounded'])
        with self.assertRaises(ValueError):
            m.rule(['primary', 'primary'])

    def test_missing_middle_path_and_multi_path_country_deduplication(self):
        source = m.generate(20, 1)
        m.apply(source, dict(add_nodes=[], delete_ids=['location0'], add_edges=[], config=None))
        self.assertEqual(m.evaluate(source, 'p0'), {'countries': [], 'paths': []})
        source = m.generate(20, 1)
        source['edges'].append(m.edge('alternative', 'p0', 's4', 'SUPPLIED_BY', 'primary'))
        result = m.evaluate(source, 'p0')
        self.assertEqual(result['countries'], ['c0'])
        self.assertEqual(len(result['paths']), 2)

    def test_atomic_persistence_failure_leaves_prior_file_and_no_temporary(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'graph.json'
            m.atomic_json(target, {'old': True})
            with patch.object(m.os, 'replace', side_effect=OSError('injected')):
                with self.assertRaises(OSError):
                    m.atomic_json(target, {'new': True})
            self.assertEqual(json.loads(target.read_text()), {'old': True})
            self.assertEqual(list(Path(tmp).iterdir()), [target])

    def test_http_parameterization_atomic_replace_and_cleanup(self):
        requests = []
        malicious_subject = "p0'}) DETACH DELETE n //"
        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            results = []
            for statement in body['statements']:
                self.assertEqual(statement['parameters']['run_id'], 'owned-namespace')
                self.assertNotIn(malicious_subject, statement['statement'])
                results.append({'columns': [], 'data': []})
            return httpx.Response(200, json={'errors': [], 'results': results})
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            backend = m.Neo4jBackend(client, m.local_endpoint('http://127.0.0.1:7474'), 'owned-namespace')
            backend.update(change=m.mutation('change_region', 100))
            self.assertEqual(len(requests), 1)
            self.assertEqual(len(requests[0]['statements']), 2)
            self.assertEqual(requests[0]['statements'][0]['statement'], m.DELETE)
            self.assertEqual(requests[0]['statements'][1]['parameters']['edges'][0]['id'], 'location0')
            self.assertEqual(backend.query(malicious_subject, m.rule(['primary'])), {'countries': [], 'paths': []})
            self.assertEqual(requests[-1]['statements'][0]['parameters']['subject'], malicious_subject)
            backend.cleanup()
            self.assertEqual(requests[-1]['statements'][0]['statement'], m.CLEANUP)
            count = len(requests)
            backend.update(change=m.mutation('allow_backup', 100))
            self.assertEqual(len(requests), count)  # Config passed at query time, not rewritten into facts.
        for unsafe in ('http://example.org:7474', 'http://127.0.0.1:7474/evil', 'http://127.0.0.1:65536'):
            with self.assertRaises(ValueError):
                m.local_endpoint(unsafe)

    def test_database_error_is_not_empty_answer(self):
        def respond(request):
            return httpx.Response(200, json={'errors': [{'code': 'Injected', 'message': 'failed'}], 'results': []})
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            backend = m.Neo4jBackend(client, 'http://127.0.0.1:7474/db/neo4j/tx/commit', 'owned')
            with self.assertRaises(RuntimeError):
                backend.query('p0', m.rule(['primary']))

    def test_plan_denominator_unique_rows_and_paired_queries(self):
        rows = m.plan_rows([100, 1000, 5000], 2)
        self.assertEqual(len(rows), 2880)
        self.assertEqual(len({r['id'] for r in rows}), len(rows))
        for checkpoint in m.CHECKPOINTS:
            for arm in m.ARMS:
                subjects = {r['subject'] for r in rows if r['checkpoint'] == checkpoint and r['arm'] == arm}
                self.assertEqual(subjects, {*[f'p{i}' for i in range(18)], 'new0', 'missing'})


if __name__ == '__main__':
    unittest.main()
