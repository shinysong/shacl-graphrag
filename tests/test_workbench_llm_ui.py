"""Explicit-click UI coverage with all LLM transport functions mocked."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


class WorkbenchLLMUITests(unittest.TestCase):
    def setUp(self):
        self.response = {
            'rules': [{'id': 'offline-rule', 'text': 'Required code',
                       'source': {'file': '직접 입력.md', 'quote': 'Code is required.', 'line': 1},
                       'status': 'confirmed', 'table': '', 'column': '', 'kind': 'required', 'params': {},
                       'llm': {'model': 'test/model', 'request_id': 'offline-request',
                               'rationale': 'Explicit wording', 'questions': ['Which table?'],
                               'source_verified': True}}],
            'notes': ['Review this draft.'], 'model': 'test/model',
            'request_id': 'offline-request', 'cached': False, 'cost_usd': .00001,
        }
        for name, value in [('available_models', ['test/model']), ('budget_status', {
                'configured': True, 'attempts': 0, 'max_calls': 20, 'reserved_usd': 0,
                'max_usd': 2, 'deadline_utc': '2099-01-01T00:00:00Z'})]:
            patcher = patch('rule_workbench.transport.' + name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch('rule_workbench.transport.generate_candidates', return_value=self.response)
        self.generate = patcher.start()
        self.addCleanup(patcher.stop)
        self.at = AppTest.from_file(str(Path('apps/rule_workbench.py').resolve()), default_timeout=30).run()

    def prepare(self):
        next(r for r in self.at.radio if r.label == '후보 추출 방식').set_value('LLM 규칙·연결 제안').run()
        next(t for t in self.at.text_area if t.label == '직접 입력할 규칙 문서').set_value('Code is required.').run()
        self.assertEqual(len(self.at.exception), 0)

    def click_generate(self):
        next(b for b in self.at.button if b.label == 'LLM 규칙·연결 제안 실행').click().run()
        self.assertEqual(len(self.at.exception), 0)

    def test_no_automatic_call_explicit_draft_append_and_cached_dedup(self):
        self.prepare()
        self.at.run()
        self.generate.assert_not_called()
        self.click_generate()
        self.assertEqual(self.generate.call_count, 1)
        project = self.at.session_state['project']
        self.assertEqual(len(project['rules']), 1)
        self.assertEqual(project['rules'][0]['status'], 'draft')
        self.assertEqual(project['rules'][0]['llm']['request_id'], 'offline-request')
        self.assertEqual(len(project['documents']), 1)
        self.assertTrue(any('Which table?' in w.value for w in self.at.warning))
        self.assertFalse(next(c for c in self.at.checkbox if c.label.startswith('원문 해석과')).value)
        self.generate.return_value = {**copy.deepcopy(self.response), 'cached': True}
        self.click_generate()
        self.assertEqual(len(self.at.session_state['project']['rules']), 1)
        self.assertEqual(len(self.at.session_state['project']['documents']), 1)
        self.assertTrue(any('추가 API 호출은 없습니다' in i.value for i in self.at.info))
        self.at.run()
        self.assertEqual(self.generate.call_count, 2)

    def test_failure_does_not_mutate_project_or_retry_on_rerun(self):
        self.prepare()
        original = copy.deepcopy(self.at.session_state['project'])
        self.generate.side_effect = ValueError('SECRET_PROVIDER_DETAIL')
        self.click_generate()
        self.assertEqual(self.at.session_state['project'], original)
        self.assertTrue(self.at.error)
        self.assertFalse(any('SECRET_PROVIDER_DETAIL' in e.value for e in self.at.error))
        self.at.run()
        self.assertEqual(self.generate.call_count, 1)
