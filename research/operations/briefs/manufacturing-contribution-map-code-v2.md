# Supplemental code and questions
Underlying sources, upstream builder and old19questions omitted/unverified. See the supplied report packet for scope.

## Static presentation builder
```python
"""Add scope/navigation to the existing saved-result demo; no DB or API calls."""
import runpy
import tempfile
from pathlib import Path

OUT = Path('docs/experiments/seminar/manufacturing-trace.html')
UPSTREAM = Path('research/manufacturing-model-change-1/import-demo-001/build.py')
OLD = '<p>같은 값을 조회해도 질문에 필요한 근거를 모두 전달한 것은 아닙니다. 작업표와 코드북의 원문 셀, 조회 결과, 입력 항목 점검을 연결해 봅니다. 제조 사례가 중심이며, 실제 버전 변경은 SBOM 보조 사례에서 따로 확인합니다.</p>'
NEW = '''<section id="research-scope" class="card">
<h2>독립된 두 제조 자료의 검토</h2>
<p>용접 자료에서는 작업표·코드북·측정값 해석을, 공개 MachineTool 모델에서는 타입 관계와 실제 버전 변경을 점검했습니다. 두 자료가 같은 설비를 가리킨다는 연결은 검증하지 않았습니다. 하나의 현장 시스템을 끝까지 검증한 결과가 아닙니다.</p>
<p>이 화면은 저장된 개발 결과를 재생합니다. SHACL의 추가 답변 개선 효과, 사람의 검토 시간, DB 성능 우열은 확인되지 않았습니다. SBOM은 별도의 보조 사례입니다.</p>
<nav aria-label="연구 결과 탐색"><a href="#question-title">용접 근거</a> · <a href="#hierarchy-demo">모델·추론·변경</a> · <a href="#import-context-demo">외부 정의 추가</a> · <a href="measurement-review.html">실제 LLM 답변</a> · <a href="../../journal/2026-11-07-manufacturing-research-map/">질문·구현·기여 정리</a></nav>
</section>'''


def build():
    upstream = runpy.run_path(str(UPSTREAM))
    with tempfile.TemporaryDirectory(dir='_workspace') as directory:
        temporary = Path(directory) / 'base.html'
        upstream['build'](temporary)
        source = temporary.read_text()
    if source.count(OLD) != 1 or 'id="research-scope"' in source:
        raise ValueError('unexpected_upstream_presentation')
    OUT.write_text(source.replace(OLD, NEW))
    return {'scope_section': 1, 'upstream_result_data_unchanged': True,
            'db_or_api_called': False}


if __name__ == '__main__':
    print(build())

```

Full25catalog and executed source excerpts omitted. Coordinator will validate original19questiontext preservation,25uniqueIDs,artifact existence and exact AST spans/source hash against prelaunch-v4. Reviewers must mark these unverified.
