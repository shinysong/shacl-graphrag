"""Saved-generator restoration tests; scripted generator is not an LLM."""
from copy import deepcopy
from unittest.mock import patch
import unittest
from apps.factory_lab import preparation as p
from tests.test_preparation import example
from tests.test_preparation_history import review

class RestoreTests(unittest.TestCase):
    def test_alternative_generator_restores_without_generation(self):
        class Scripted:
            name='scripted-alternative-1'
            def suggest(self,sources):
                result=p.LocalGenerator().suggest(sources)
                for e in result:e['reason']='Scripted test explanation, not model output'
                return result
        draft=review(p.create(*example(),generator=Scripted()))
        bundle=p.freeze(draft)
        with patch.object(p.LocalGenerator,'suggest',side_effect=AssertionError('must not regenerate')):
            restored=p.restore(bundle)
        self.assertEqual(p.freeze(restored),bundle)

    def test_pending_roundtrip_and_tampered_source_rejection(self):
        draft=p.create(*example())
        self.assertEqual(p.restore_draft(draft)['entries'],draft['entries'])
        for mutate in ('source','coverage','approval'):
            bad=deepcopy(draft)
            if mutate=='source':bad['saved_suggestions'][0]['source']['column']='nonexistent'
            elif mutate=='coverage':bad['saved_suggestions'].pop(0)
            else:bad['saved_suggestions'][0]['status']='approved'
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):p.restore_draft(bad)
        bad=deepcopy(draft);bad['sources'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'inspection'):p.restore_draft(bad)

    def test_legacy_without_saved_suggestions(self):
        draft=review(p.create(*example()));draft.pop('saved_suggestions')
        self.assertNotIn('saved_suggestions',p.restore(p.freeze(draft)))
