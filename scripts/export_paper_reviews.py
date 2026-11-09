"""Export 18 paper reviews from docs/journal to _workspace/export-to-blog for shinysong.github.io."""

import json
import re
import shutil
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS_JOURNAL = ROOT / 'docs/journal'
EXPORT_DIR = ROOT / '_workspace/export-to-blog'
POSTS_DIR = EXPORT_DIR / '_posts'

CATEGORY_MAP = {
    'clinical-ontology-rag': ('GraphRAG & Retrieval', ['graphrag', 'neo4j', 'ontology', 'clinical']),
    'rag-vs-graphrag': ('GraphRAG & Retrieval', ['rag', 'graphrag', 'evaluation', 'benchmark']),
    'when-graphs-rag': ('GraphRAG & Retrieval', ['graphrag', 'benchmark', 'cost-efficiency']),
    'rdf2pg': ('Graph Architecture', ['rdf', 'property-graph', 'neo4j', 'sparql', 'cypher']),
    'owl-shacl-semantics': ('SHACL & Knowledge Graphs', ['owl', 'shacl', 'semantics', 'reasoning']),
    'policykg': ('SHACL & Knowledge Graphs', ['shacl', 'policy-kg', 'compliance']),
    'shacl-updates': ('SHACL & Knowledge Graphs', ['shacl', 'incremental-validation', 'constraints']),
    'xpshacl': ('SHACL & Knowledge Graphs', ['shacl', 'explainability', 'validation-report']),
    'shapes-from-examples': ('SHACL & Knowledge Graphs', ['shacl', 'rule-learning', 'ontology']),
    'nl2shacl-bench': ('SHACL & Knowledge Graphs', ['shacl', 'benchmark', 'text2sparql']),
    'shacl-guru': ('SHACL & Knowledge Graphs', ['shacl', 'developer-tools', 'llm-assistant']),
    'shacl-test': ('SHACL & Knowledge Graphs', ['shacl', 'testing', 'validation']),
    'regae': ('Rule Learning', ['regex', 'rule-learning', 'interactive-synthesis']),
    'battery-traceability': ('Manufacturing & Traceability', ['manufacturing', 'traceability', 'battery']),
    'lgmagna-traceability': ('Manufacturing & Traceability', ['manufacturing', 'traceability', 'quality-control']),
    'metalmind': ('Manufacturing & Traceability', ['manufacturing', 'knowledge-graph', 'agent']),
    'meyers-manufacturing': ('Manufacturing & Traceability', ['manufacturing', 'knowledge-graph', 'ontology']),
    'semiconductor-patent-kg': ('Knowledge Graph Extraction', ['patent', 'ner', 'knowledge-graph']),
}


def export_reviews():
    if EXPORT_DIR.exists():
        shutil.rmtree(EXPORT_DIR)
    POSTS_DIR.mkdir(parents=True, exist_ok=True)

    reviews = sorted(DOCS_JOURNAL.glob('*review-*.md'))
    manifest = []

    for source in reviews:
        m = re.match(r'(\d{4}-\d{2}-\d{2})-review-(.+)\.md$', source.name)
        if not m:
            continue
        date_str, slug = m.groups()
        text = source.read_text(encoding='utf-8')
        title_m = re.match(r'^# (.+)\n', text)
        title = title_m.group(1) if title_m else source.stem
        body = text[title_m.end():].lstrip() if title_m else text

        subcat, tags = CATEGORY_MAP.get(slug, ('General Review', ['paper-review']))

        # Rewrite ../assets/ paths to /assets/ for standalone root blog
        body = body.replace('(../assets/', '(/assets/')

        # Extract first substantive paragraph for summary and strip Markdown inline syntax
        paragraphs = [p for p in body.split('\n\n') if len(p) > 30 and not p.startswith(('#', '|', '-', '```', '<'))]
        desc = paragraphs[0].replace('\n', ' ') if paragraphs else ''
        desc = re.sub(r'\*\*([^*]+)\*\*', r'\1', desc)
        desc = re.sub(r'\*([^*]+)\*', r'\1', desc)
        desc = re.sub(r'`([^`]+)`', r'\1', desc)

        has_math = bool(re.search(r'\$\$|\$[^$\n]+\$', body))

        frontmatter = {
            'title': title,
            'date': f'{date_str} 09:00:00 +0900',
            'categories': ['Paper Review', subcat],
            'tags': tags,
            'description': desc,
            'mermaid': bool(re.search(r'^```mermaid', body, re.M)),
        }
        if has_math:
            frontmatter['math'] = True

        out_content = '---\n' + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False) + '---\n\n' + body
        out_path = POSTS_DIR / source.name
        out_path.write_text(out_content, encoding='utf-8')
        manifest.append({
            'file': source.name,
            'title': title,
            'category': subcat,
            'tags': tags,
            'date': date_str,
        })

    # Create README guide in export directory
    readme_text = f"""# Paper Review Export Package (`_workspace/export-to-blog`)

이 디렉터리는 `shacl-graphrag`에서 작성된 **총 {len(manifest)}편의 논문 및 도구 리뷰**를 개인 연구 블로그(`shinysong.github.io`)로 손쉽게 이전하기 위해 패키징한 결과물입니다.

## 1. 이전 대상 리뷰 목록 ({len(manifest)}편)

| 날짜 | 세부 분류 | 제목 | 파일명 |
|---|---|---|---|
"""
    for item in manifest:
        readme_text += f"| {item['date']} | {item['category']} | {item['title']} | `{item['file']}` |\n"

    readme_text += """
## 2. 새 레포지토리 (`shinysong.github.io`) 이전 방법 (1분 가이드)

1. GitHub에서 `shinysong/shinysong.github.io` 저장소 생성 (Chirpy 또는 Quartz 템플릿 적용).
2. 이 디렉터리의 `_posts/` 폴더 안의 모든 `.md` 파일을 새 저장소의 `_posts/` 디렉터리로 복사:
   ```bash
   cp _workspace/export-to-blog/_posts/*.md /path/to/shinysong.github.io/_posts/
   ```
3. 새 저장소에서 커밋 및 푸시:
   ```bash
   git add _posts
   git commit -m "Import 18 paper reviews from shacl-graphrag research lab"
   git push origin main
   ```

## 3. 메타데이터 구성 특징
- 모든 포스트에 2단계 계층 카테고리(`categories: ['Paper Review', '세부주제']`)가 지정되어 있습니다.
- 세부 주제는 5개 축으로 정돈되어 있습니다:
  - `GraphRAG & Retrieval` (의료 온톨로지 RAG, RAG vs GraphRAG, GraphRAG-Bench)
  - `SHACL & Knowledge Graphs` (OWL vs SHACL, PolicyKG, xpSHACL, SHACL Updates, Shapes from Examples 등)
  - `Graph Architecture` (rdf2pg)
  - `Manufacturing & Traceability` (배터리 전극 이력 추적, LG마그나 품질 기록, MetalMind, Meyers 제조 KG)
  - `Knowledge Graph Extraction` (반도체 특허 KG)
- Mermaid 다이어그램이 포함된 문서는 `mermaid: true` 플래그가 자동 활성화되어 있습니다.
"""
    (EXPORT_DIR / 'README.md').write_text(readme_text, encoding='utf-8')
    print(f'Exported {len(manifest)} reviews to {POSTS_DIR} and generated README.md')


if __name__ == '__main__':
    export_reviews()
