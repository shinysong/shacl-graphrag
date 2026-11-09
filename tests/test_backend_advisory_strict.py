import unittest
from scripts.backend_advisory_strict import input_error


class StrictEnvelopeTests(unittest.TestCase):
    def test_input_boundary_rejects_nonstring_and_unknown_fields(self):
        for value in (True, 123, ['a'], {'value': 'a'}):
            self.assertEqual(input_error({'used_input_hash': value}), 'fingerprint_must_be_string_or_null')
        self.assertEqual(input_error({'answer': 'not-checker-input'}), 'unexpected_metadata_field')
        self.assertEqual(input_error(['a']), 'metadata_must_be_object')

    def test_missing_and_malformed_strings_reach_semantic_checker(self):
        for metadata in ({}, {'used_input_hash': None}, {'used_input_hash': ''}, {'current_input_hash': 'a'*64+'\n'}):
            self.assertIsNone(input_error(metadata))
