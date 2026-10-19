import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest


class WorkbenchUITests(unittest.TestCase):
    def test_demo_run_edit_stale_and_rerun(self):
        at = AppTest.from_file(str(Path('apps/rule_workbench.py').resolve()), default_timeout=30).run()
        self.assertEqual(len(at.exception), 0)
        next(b for b in at.button if b.label == '예제 프로젝트 불러오기').click().run()
        self.assertEqual(len(at.exception), 0)
        next(c for c in at.checkbox if c.label.startswith('저장된 규칙과')).check().run()
        next(b for b in at.button if b.label == '검사 실행').click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.session_state['result']['counts']['violation'], 3)
        # Change first rule to draft via actual form and verify old results withheld.
        next(c for c in at.checkbox if c.label.startswith('원문 해석과')).uncheck()
        next(b for b in at.button if b.label == '규칙 저장').click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertTrue(any('이전 결과는 숨겼습니다' in w.value for w in at.warning))
        next(b for b in at.button if b.label == '검사 실행').click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.session_state['result']['counts']['unknown'], 3)
        self.assertEqual(at.session_state['previous_result']['counts']['violation'], 3)

    def test_manual_document_candidates_stay_draft(self):
        at = AppTest.from_file(str(Path('apps/rule_workbench.py').resolve()), default_timeout=30).run()
        next(t for t in at.text_area if t.label == '직접 입력할 규칙 문서').set_value('업체코드는 필수입니다.').run()
        next(b for b in at.button if b.label == '문서 추가 및 후보 추출').click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.session_state['project']['rules'][0]['status'], 'draft')
        self.assertEqual(at.session_state['project']['rules'][0]['source']['line'], 1)


if __name__ == '__main__': unittest.main()
