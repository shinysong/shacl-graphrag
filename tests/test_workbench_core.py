import copy
import io
import json
import unittest
import zipfile

from openpyxl import load_workbook
from rdflib import Graph
from pyshacl import validate

from rule_workbench.core import demo_project, run_checks, validate_project
from rule_workbench.exports import export_json, import_json, export_bundle, export_excel


class WorkbenchTests(unittest.TestCase):
    def test_real_shacl_demo_and_portable_graph(self):
        p = demo_project(); r = run_checks(p)
        self.assertEqual(r['counts'], {'pass': 7, 'violation': 3, 'unknown': 2, 'not_applicable': 0})
        data = Graph().parse(data=r['data_ttl'], format='turtle')
        shapes = Graph().parse(data=r['shapes_ttl'], format='turtle')
        self.assertFalse(validate(data, shacl_graph=shapes, meta_shacl=True)[0])
        self.assertEqual(len(r['results']), 12)

    def test_unreviewed_unmapped_empty_not_pass(self):
        p = demo_project(); p['rules'][0]['status'] = 'draft'; p['rules'][1]['column'] = 'missing'; p['tables'][1]['rows'] = []
        r = run_checks(p)
        self.assertEqual(sum(x['row'] is None and x['status'] == 'unknown' for x in r['results']), 2)
        p['tables'][0]['rows'] = []; p['rules'] = [p['rules'][2]]
        self.assertEqual(run_checks(p)['counts']['not_applicable'], 1)

    def test_range_allowed_bad_dates_and_partial_reference(self):
        p = demo_project(); p['rules'] = [copy.deepcopy(p['rules'][0])]; rule = p['rules'][0]
        rule.update(kind='range', column='금액', params={'min': 150, 'max': 350})
        self.assertEqual(run_checks(p)['counts']['violation'], 2)
        p['tables'][0]['rows'][0]['금액'] = 'bad'
        self.assertEqual(run_checks(p)['counts']['unknown'], 1)
        rule.update(kind='allowed', column='업체코드', params={'values': ['A01']})
        self.assertEqual(run_checks(p)['counts']['violation'], 2)
        p = demo_project(); p['tables'][1]['source']['truncated'] = True
        result = run_checks(p)
        self.assertTrue(any(x['row'] == 3 and x['rule_id'] == 'rule-3' and x['status'] == 'unknown' for x in result['results']))
        p['tables'][0]['rows'][0]['납품일'] = '17/10/2026'
        self.assertEqual(run_checks(p)['counts']['unknown'], 4)

    def test_roundtrip_privacy_and_stale_results(self):
        p = demo_project(); p['tables'][0]['source']['password'] = 'do-not-export'
        full = export_json(p, True); imported = import_json(full)
        self.assertNotIn(b'do-not-export', full)
        self.assertEqual(run_checks(imported)['counts'], run_checks(p)['counts'])
        redacted = import_json(export_json(p)); self.assertEqual(redacted['tables'][0]['rows'], [])
        self.assertTrue(redacted['tables'][0]['source']['data_omitted'])
        self.assertEqual(run_checks(redacted)['counts']['pass'], 0)
        self.assertEqual(run_checks(redacted)['counts']['unknown'], 3)
        self.assertEqual(run_checks(redacted)['counts']['not_applicable'], 0)
        p['tables'][1]['rows'].append({'업체코드': 'PRIVATE-REFERENCE-SENTINEL'})
        r = run_checks(p); bundle = zipfile.ZipFile(io.BytesIO(export_bundle(p, r)))
        self.assertNotIn('data.ttl', bundle.namelist()); self.assertIn('shapes.ttl', bundle.namelist())
        self.assertNotIn(b'A01', bundle.read('shapes.ttl'))
        for name in bundle.namelist():
            self.assertNotIn(b'PRIVATE-REFERENCE-SENTINEL', bundle.read(name))
        self.assertNotIn('A01', r['shapes_ttl'])
        self.assertIn('A01', r['data_ttl'])
        p['rules'][0]['text'] += ' 변경'
        with self.assertRaises(ValueError): export_bundle(p, r)

    def test_malformed_parameters_and_precise_bounds(self):
        for value in [None, 123, 'A01']:
            p = demo_project(); p['rules'][0].update(kind='allowed', params={'values': value})
            with self.assertRaises(ValueError): import_json(json.dumps(p).encode())
        p = demo_project(); p['rules'] = [p['rules'][0]]
        p['rules'][0].update(kind='range', column='금액', params={'min': '9007199254740993'})
        p['tables'][0]['rows'] = [{'금액': '9007199254740992'}, {'금액': '9007199254740993'}]
        restored = import_json(export_json(p, True))
        self.assertEqual(restored['rules'][0]['params']['min'], '9007199254740993')
        self.assertEqual(run_checks(restored)['counts']['violation'], 1)

    def test_spreadsheet_formula_and_invalid_import(self):
        p = demo_project(); p['rules'][0]['text'] = '=HYPERLINK("bad")'
        wb = load_workbook(io.BytesIO(export_excel(p)))
        self.assertEqual(wb['규칙']['B2'].data_type, 's')
        self.assertTrue(wb['규칙']['B2'].value.startswith("'="))
        with self.assertRaises(ValueError): import_json(b'{}')
        p['tables'][0]['columns'].append('업체코드')
        with self.assertRaises(ValueError): validate_project(p)


if __name__ == '__main__': unittest.main()
