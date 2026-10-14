"""Synthetic unit fixtures only; no full source characterization execution."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('domain_sources', Path(__file__).resolve().parents[1] / 'scripts/profile_domain_sources.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class DomainSourcesTests(unittest.TestCase):
    def test_fhir_namespace_collision_and_paths(self):
        resources = [{'resourceType': 'Observation', 'id': 'example',
                      'subject': {'reference': 'Patient/example'},
                      'encounter': {'reference': 'Encounter/example'},
                      'performer': [{'reference': 'Practitioner/other'}],
                      'a/b~c': {'reference': 'Patient/example'},
                      'valueQuantity': {'value': 2, 'system': 'http://unitsofmeasure.org', 'code': 'kg'}},
                     {'resourceType': 'Patient', 'id': 'example'},
                     {'resourceType': 'Encounter', 'id': 'example'}]
        result, sample = m.profile_fhir(resources)
        self.assertEqual(result['typed_key_unique_count'], 3)
        self.assertEqual(result['bare_id_overwrite_losses'], 2)
        self.assertEqual(result['unresolved_in_selected_bundle'], 1)
        self.assertEqual([r['path'] for r in sample['references']],
                         ['/subject/reference', '/encounter/reference', '/performer/0/reference', '/a~1b~0c/reference'])
        self.assertFalse(sample['references'][2]['resolved_in_bundle'])
        self.assertEqual(sample['value_quantities'][0]['code'], 'kg')
        self.assertNotIn('path', sample['pathless_references'][0])

    def test_wikidata_statement_metadata_loss(self):
        claim = {'id': 'Q80$synthetic', 'rank': 'preferred',
                 'mainsnak': {'snaktype': 'value', 'datavalue': {'value': {'id': 'Q1'}}},
                 'qualifiers': {'P580': [{'snaktype': 'value'}, {'snaktype': 'somevalue'}]},
                 'references': [{'snaks': {'P854': [{'snaktype': 'value'}]}}]}
        result, sample = m.profile_wikidata({'entities': {'Q80': {'lastrevid': 123,
            'claims': {'P108': [claim], 'P1': [{'rank': 'deprecated', 'mainsnak': {'snaktype': 'novalue'}}]}}}})
        loss = result['deliberate_subject_property_value_projection']
        self.assertEqual(loss['rows'], 2)
        self.assertEqual(loss['removed_rank_fields'], 2)
        self.assertEqual(loss['removed_qualifier_snaks'], 2)
        self.assertEqual(loss['removed_reference_blocks'], 1)
        self.assertEqual(result['mainsnak_types'], {'value': 1, 'novalue': 1})
        self.assertEqual(sample['employer_P108'][0]['qualifiers'], claim['qualifiers'])
        self.assertEqual(sample['employer_P108'][0]['rank'], 'preferred')
        self.assertEqual(sample['lastrevid'], 123)

    def test_rdf_import_not_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'module.rdf'
            path.write_text('''<!DOCTYPE rdf:RDF [<!ENTITY local "urn:p">]><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:owl="http://www.w3.org/2002/07/owl#"><owl:Ontology rdf:about="urn:module"><owl:imports rdf:resource="file:///definitely-not-existing-import.rdf"/></owl:Ontology><owl:ObjectProperty rdf:about="&local;"/></rdf:RDF>''')
            result = m.profile_fibo(path)
            self.assertEqual(result['imports'], ['file:///definitely-not-existing-import.rdf'])
            self.assertEqual(result['triples'], 3)
            self.assertEqual(result['object_properties'], 1)
            path.write_text('<!DOCTYPE rdf [<!ENTITY remote SYSTEM "https://invalid.example/">]>')
            with self.assertRaises(ValueError):
                m.profile_fibo(path)

    def test_gleif_preserves_periods_and_identifier_types(self):
        rr = {'Relationship.StartNode.NodeID': 'A', 'Relationship.StartNode.NodeIDType': 'LEI',
              'Relationship.EndNode.NodeID': 'B', 'Relationship.EndNode.NodeIDType': 'LEI',
              'Relationship.RelationshipType': 'IS_DIRECTLY_CONSOLIDATED_BY',
              'Relationship.RelationshipStatus': 'ACTIVE', 'Registration.RegistrationStatus': 'PUBLISHED',
              'Relationship.Period.1.startDate': '2020-01-01', 'Relationship.Period.1.endDate': '',
              'Relationship.Period.1.periodType': 'RELATIONSHIP_PERIOD',
              'Relationship.Period.2.periodType': 'ACCOUNTING_PERIOD'}
        re = {'LEI': 'C', 'Exception.Category': 'DIRECT_ACCOUNTING_CONSOLIDATION_PARENT',
              'Exception.Reason.1': 'NATURAL_PERSONS'}
        result, sample = m.profile_gleif([rr], [re])
        self.assertEqual(result['period_types'], {'RELATIONSHIP_PERIOD': 1, 'ACCOUNTING_PERIOD': 1})
        self.assertEqual(result['period_field_nonempty_counts']['Relationship.Period.1.endDate'], 0)
        self.assertEqual(sample['rr_first_three'][0], rr)
        self.assertEqual(sample['repex_first_three'][0], re)

    def test_failed_input_retains_partial_manifest_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'result'
            self.assertEqual(m.run(output, root), 1)
            import json
            result = json.loads((output / 'summary.json').read_text())
            self.assertEqual(result['status'], 'partial_failed')
            self.assertEqual(result['failures'][0]['stage'], 'provenance')
            self.assertTrue((output / 'samples.json').exists())
            self.assertEqual((output / 'source/profile_domain_sources.py').read_bytes(),
                             Path(m.__file__).read_bytes())
            with self.assertRaises(FileExistsError):
                m.run(output, root)


if __name__ == '__main__':
    unittest.main()
