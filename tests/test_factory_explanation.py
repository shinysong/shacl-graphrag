"""Actual local engines with authored fixtures; no model efficacy measurement."""
import copy
import unittest
import json
import tempfile
import threading
from pathlib import Path
from hashlib import sha256
import httpx
from rdflib import Graph, RDF, URIRef
from apps.factory_lab.diagnostics import run_case, historical_trace, historical_examples, selected_owl, ASSERTED, ONTOLOGY, ROOT
from apps.factory_lab.public_runtime import Demo
from apps.factory_lab.public_server import make_server
from apps.factory_lab.explanation import shacl_trace, owl_trace
from apps.factory_lab.review import SHAPES, SH


class ExplanationTests(unittest.TestCase):
    def test_actual_report_and_native_focus(self):
        d = run_case('applicability')
        t = d['shacl']
        self.assertFalse(t['conforms'])
        self.assertIn('qualification-not-applicable', [r['message'] for r in t['results']])
        g = Graph().parse(data=t['raw_report_turtle'], format='turtle')
        self.assertEqual(len(list(g.subjects(RDF.type, SH.ValidationResult))), len(t['results']))
        self.assertTrue(all(r['focus_node'] and r['source_shape'] for r in t['results']))
        self.assertEqual(t['same_policy_python_flags'], [{'candidate': r['candidate'], 'code': r['message']} for r in t['results']])
        self.assertEqual(d['answer_effect']['status'], 'unmeasured')

    def test_pass_is_not_truth_and_no_targets_not_pass(self):
        d = run_case('conforming')
        self.assertTrue(d['shacl']['conforms'])
        self.assertEqual(d['shacl']['results'], [])
        no = shacl_trace([])
        self.assertEqual(no['assessment'], 'not_assessed')
        self.assertIsNone(no['conforms'])
        self.assertIsNone(no['raw_report_turtle'])

    def test_deliberate_retrieval_omission(self):
        d = run_case('omitted')
        self.assertFalse(d['projection']['qualification_query_executed'])
        self.assertEqual(len(d['evidence']), 1)
        self.assertIn('qualification-not-retrieved', [r['message'] for r in d['shacl']['results']])
        self.assertIn('source absence versus retrieval omission', d['shacl']['scope'])

    def test_fact_and_shape_changes_change_explanation(self):
        evidence = copy.deepcopy(run_case('conforming')['evidence'])
        evidence[0]['rows'][0]['machine']['status'] = 'unavailable'
        changed = shacl_trace(evidence)
        self.assertIn('status-not-available', [r['message'] for r in changed['results']])
        revised = shacl_trace(evidence, SHAPES.replace('"available"', '"unavailable"'))
        self.assertNotIn('status-not-available', [r['message'] for r in revised['results']])
        self.assertNotEqual(changed['shapes_sha256'], revised['shapes_sha256'])

    def test_owl_actual_closure_and_mutated_axiom(self):
        t = owl_trace(ASSERTED, ONTOLOGY)
        self.assertEqual(len(t['witnesses']), 1)
        conclusion = t['witnesses'][0]['conclusion']
        graph = Graph().parse(data=t['inferred_ntriples'], format='nt')
        self.assertIn(tuple(URIRef(x[1:-1]) for x in conclusion), graph)
        self.assertFalse(t['proof_trace_available'])
        self.assertEqual(owl_trace(ASSERTED, '')['witnesses'], [])
        self.assertEqual(owl_trace('', ONTOLOGY)['witnesses'], [])

    def test_invalid_cases_and_malformed_shapes_fail(self):
        with self.assertRaises(ValueError): run_case('../../.env')
        with self.assertRaises(Exception): shacl_trace([], 'not turtle')
        no = selected_owl({'calls':[]})
        self.assertEqual(no['assessment'], 'not_assessed')
        self.assertEqual(no['witnesses'], [])

    def test_source_contradiction_can_conform(self):
        d = run_case('altered')
        self.assertTrue(d['shacl']['conforms'])
        self.assertNotEqual(d['intervention']['source_value'], d['intervention']['injected_value'])
        self.assertNotIn('source_value', json.dumps(d['shacl']))

    def test_historical_original_strings_reports_and_quotes(self):
        for record in historical_examples():
            path = ROOT / record['provenance']['source_path']
            self.assertEqual(sha256(path.read_bytes()).hexdigest(), record['provenance']['source_sha256'])
            events = json.loads(path.read_text())['events']
            self.assertEqual(record['draft'], next(e['payload']['text'] for e in events if e['kind']=='draft'))
            self.assertEqual(record['finals'], {e['payload']['arm']:e['payload']['text'] for e in events if e['kind']=='branch_final'})
            self.assertIn(record['observation']['draft_quote'], record['draft'])
            self.assertIn(record['observation']['shacl_quote'], record['finals']['shacl'])
            traced = historical_trace(record['id'])
            flags = [{'candidate':r['candidate'], 'code':r['message']} for r in traced['shacl']['results']]
            self.assertEqual(flags, record['reports']['shacl']['flags'])
            self.assertEqual(set(traced['line_diffs']), {'self','python','shacl'})

    def test_http_diagnostics_gates_lock_and_release_after_error(self):
        with tempfile.TemporaryDirectory() as directory:
            demo = Demo(Path(directory));server = make_server(demo, 0)
            thread = threading.Thread(target=server.serve_forever);thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with httpx.Client(trust_env=False) as client:
                    url = base + '/api/diagnostics';body = {'case_id':'conforming'}
                    headers = {'X-CSRF-Token':client.get(base+'/api/config').json()['csrf']}
                    self.assertEqual(client.post(url,json=body).status_code,403)
                    self.assertEqual(client.post(url,json=body,headers=headers|{'Origin':'http://evil.test'}).status_code,403)
                    demo.lock.acquire()
                    try:self.assertEqual(client.post(url,json=body,headers=headers).status_code,409)
                    finally:demo.lock.release()
                    self.assertEqual(client.post(url,json={'case_id':'missing'},headers=headers).status_code,400)
                    response=client.post(url,json=body,headers=headers)
                    self.assertEqual(response.status_code,200)
                    self.assertTrue(response.json()['shacl']['conforms'])
                    self.assertEqual(demo.store.budget()['attempts'],0)
            finally:server.shutdown();server.server_close();thread.join()


if __name__ == '__main__': unittest.main()
