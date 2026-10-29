"""Build a self-contained seminar HTML from the canonical Markdown and saved examples."""
from __future__ import annotations
import base64
import hashlib
import html
import json
import re
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'docs/experiments/seminar/slides.md'
OUT = DOC.parent
SNIPPETS = ROOT / 'scripts/seminar_examples.py'
COMMIT = '35dfc7ab1d3a0790c86bfe5922faf6cf7cfef9fc'
GITHUB = f'https://github.com/shinysong/shacl-graphrag/blob/{COMMIT}/docs/'


def code(text, label=''):
    return f'<div class="code-block"><div class="code-label">{html.escape(label)}</div><pre><code>{html.escape(text.strip())}</code></pre></div>'


def flow(labels, captions, name):
    steps = ''.join(f'<div class="step" data-step="{i}"><span class="step-no">{i+1:02}</span><strong>{html.escape(label)}</strong><small>{html.escape(captions[i])}</small></div>' for i, label in enumerate(labels))
    return f'<div class="flow" data-flow="{name}"><div class="flow-steps">{steps}</div></div>'


def build():
    examples = json.loads((OUT / 'examples/examples.json').read_text())
    snippets = SNIPPETS.read_text()
    notebook_path = OUT / 'notebooks/manufacturing-shacl.ipynb'
    notebook = json.loads(notebook_path.read_text())
    notebook_cells = {c['id']: c for c in notebook['cells'] if c['cell_type'] == 'code'}
    semantics = json.loads((OUT / 'manufacturing/manufacturing.json').read_text())
    semantic_snippets = (ROOT / 'scripts/seminar_manufacturing_examples.py').read_text()
    mode_labels = {'original': '원본', 'rdfs': 'RDFS 확장', 'owlrl': 'OWL-RL 확장'}
    case_labels = {'valid': '정상 IRI', 'missing': '결측', 'literal': '문자열', 'unverified_iri': '미확인 IRI'}

    def table(headers, rows, caption):
        head = ''.join(f'<th scope="col">{html.escape(str(v))}</th>' for v in headers)
        body = ''.join('<tr>' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in row) + '</tr>' for row in rows)
        return f'<table><caption>{html.escape(caption)}</caption><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'

    inference_table = table(
        ['조회 결과', '원본', 'RDFS', 'OWL-RL'],
        [[label] + ['있음' if r[key] else '없음' for r in semantics['queries']] for key, label in [
            ('P1_is_Component', 'P1 a Component'), ('A1_is_Assembly', 'A1 a Assembly'),
            ('A1_hasPart_P1', 'A1 hasPart P1'), ('manufacturer_recorded', '제조사 기록')]],
        '저장된 조회 결과 · 없음은 현실의 거짓을 뜻하지 않음')
    sensor_table = table(
        ['입력', 'conforms', '위반 조건', '현실의 사실 확인'],
        [[r['added_fact'], str(r['conforms']).lower(), ', '.join(v['component'] for v in r['violations']) or '없음', '미확인'] for r in semantics['shape_cases']],
        '저장된 제조사 Shape 검사 · 네 입력')
    static_demos = {'inference': inference_table, 'sensor': sensor_table,
                    'manufacturer': sensor_table,
                    'discount': code(json.dumps(examples['mini_cases'], ensure_ascii=False, indent=2))}

    def saved_demo(key, records, labels):
        tabs = ''.join(f'<button type="button" data-record="{i}" aria-pressed="{str(i == 0).lower()}">{html.escape(labels[r["mode" if key == "inference" else "case"]])}</button>' for i, r in enumerate(records))
        return (f'<!-- saved-demo:{key} --><div class="demo saved-demo" data-saved-demo="{key}">'
                f'<div class="tabs" role="group" aria-label="저장된 실행 선택">{tabs}</div>'
                '<div class="saved-result" aria-live="polite"></div></div>'
                f'<div class="print-results">{static_demos[key]}</div><!-- /saved-demo -->')
    visual = {
        'journey': (['질문', '데이터', '규칙', '검증', '근거'], ['무엇을 판단할까', '어떤 사실이 있나', '무슨 조건인가', '어떤 조건이 어긋났나', '무엇을 설명할까']),
        'decisions': (['eligible', 'blocked', 'unknown'], ['조건 충족', '명시적 위반', '필수 근거 부족']),
        'triple': (['주어', '술어', '목적어'], ['ex:order1', 'ex:discount', '0.20 (decimal)']),
        'owl': (['공리', '기록된 사실', '함의된 사실'], ['SpecialOrder ⊆ Order', 'order1 ∈ SpecialOrder', 'order1 ∈ Order']),
        'validation': (['입력', 'validate()', '반환값'], ['Data Graph + Shapes Graph', '조건 검사', 'conforms / report / text']),
        'tables': (['발주 요청', '승인 검토', '검토자', '소속 부서', '상위 본부'], ['REQ_2026_01', 'REV_01', 'USER_PRIMARY', 'DEPT_REV1', 'DIV_SALES']),
        'path': (['요청 부서', '요청', '검토', '검토자', '검토자 부서', '상위 본부'], ['DEPT_REQ', '← requestedByDept', 'hasReview →', 'reviewedBy →', 'belongsToDept →', 'parentDivision →']),
        'report': (['어느 개체', '어떤 경로', '어떤 값'], ['focus_node', 'result_path', 'value_node']),
        'refresh': (['최초 판정', 'unknown인 경우', '원천 재평가'], ['제공된 근거 검사', '전체 source_tables 사용', '누락 해소 또는 unknown 유지']),
    }
    def notebook_view(key):
        keys = {'inputs': ['data', 'shape'], 'results': ['validate', 'report']}[key]
        def joined(value):
            return ''.join(value) if isinstance(value, list) else value
        cells = []
        for cell_key in keys:
            cell = notebook_cells[cell_key]
            assert cell.get('execution_count') is not None, cell_key
            assert not any(o['output_type'] == 'error' for o in cell['outputs']), cell_key
            output = ''.join(joined(o.get('text', o.get('data', {}).get('text/plain', ''))) for o in cell['outputs'])
            assert output, cell_key
            uid = f'nb-{cell_key}'
            cells.append(f'<section class="nb-cell"><div class="nb-cell-head"><button type="button" class="nb-run" aria-controls="{uid}" aria-expanded="false" aria-label="{cell_key} 셀의 저장된 결과 표시">▶</button><span>In [{cell["execution_count"]}]</span><span>{html.escape(cell_key)}</span></div><pre class="nb-code"><code>{html.escape(joined(cell["source"]))}</code></pre><div class="nb-output" id="{uid}"><span class="nb-out-label">Out [{cell["execution_count"]}]</span><pre>{html.escape(output.rstrip())}</pre></div></section>')
        return '<div class="seminar-notebook"><div class="nb-bar"><span>manufacturing-shacl.ipynb · Python 3</span><span>저장된 실행 결과 재생</span></div><div class="nb-grid">' + ''.join(cells) + '</div><div class="nb-caption">▶ 셀의 실제 저장 출력 표시 <button type="button" class="nb-download">↓ 실습 노트북 저장</button></div></div>'

    def replace(match):
        kind, key = match.group(1), match.group(2)
        if kind == 'notebook':
            return notebook_view(key)
        if kind == 'view':
            view = (OUT / 'views' / f'{key}.html').read_text()
            view = re.sub(r'<style>.*?</style>', '', view, flags=re.S)
            return f'<div class="seminar-view">{view}</div>'
        if kind == 'code':
            import textwrap
            region = re.search(rf'# region {key}\n(.*?)\n\s*# endregion {key}', snippets, re.S)
            source = 'seminar_examples.py'
            if region is None:
                region = re.search(rf'# region {key}\n(.*?)\n\s*# endregion {key}', semantic_snippets, re.S)
                source = 'seminar_manufacturing_examples.py'
            if region is None:
                raise ValueError(f'Missing source region: {key}')
            text = textwrap.dedent(region.group(1))
            if key in {'shape', 'sensor_data', 'sensor_schema', 'manufacturer_shape', 'type_shape', 'manufacturing_data', 'manufacturing_schema'}:
                text = re.sub(r"^[A-Z_]+ = \'\'\'", '', text).removesuffix("\'\'\'")
            return code(text, f'실행 소스 · scripts/{source}')
        if kind == 'viz':
            return flow(*visual[key], key)
        if kind == 'story':
            svg = (OUT / 'diagrams' / f'{key}.svg').read_text()
            return f'<div class="flow story-flow" data-flow="{key}">{svg}</div>'
        if kind == 'demo' and key in {'inference', 'sensor', 'manufacturer'}:
            return saved_demo(key, semantics['queries' if key == 'inference' else 'shape_cases'], mode_labels if key == 'inference' else case_labels)
        if kind == 'data':
            if key == 'validation_scope':
                return table(['검사 대상', 'Component 타입', '제조사', '위반 수'], [[mode_labels[r['mode']], '충족' if r['P1_is_Component'] else '미충족', '충족' if r['manufacturer_recorded'] else '미충족', len(r['violations'])] for r in semantics['queries']], '저장된 두 Shape 검사 · 모든 호출은 inference=none')
            if key == 'decisions':
                # Deduplicate the three identical results for readable slide size.
                result = examples['project_decisions']['Python']
                return code(json.dumps(result, ensure_ascii=False, indent=2), '실제 출력 · Python = SQLite = SHACL (세 반환값 일치)')
            if key == 'finding':
                return code(json.dumps(examples['project_report']['shacl_validation_results'][0], ensure_ascii=False, indent=2), '실제 출력 발췌 · project-report.json · 첫 검증 결과')
        if kind == 'demo' and key == 'discount':
            return '<div class="demo" id="discount-demo"><div class="tabs" role="group" aria-label="저장된 할인 예제"><button type="button" data-case="0" aria-pressed="true">12% · 정상</button><button type="button" data-case="1" aria-pressed="false">20% · 초과</button><button type="button" data-case="2" aria-pressed="false">결측</button></div><div class="io"><div><h3>INPUT</h3><pre id="demo-input"></pre></div><div><h3>SAVED OUTPUT</h3><pre id="demo-output" aria-live="polite"></pre></div></div></div>'
        if kind == 'demo' and key == 'prompt':
            return code('<QUESTION>요청을 승인할 수 있는가?</QUESTION>\n<SHACL_VALIDATION_REPORT>\n  decision: blocked\n  focus_node: ex:departments/DEPT_REQ\n  value_node: ex:divisions/DIV_SALES\n</SHACL_VALIDATION_REPORT>', 'M2 구조 설명용 축약 · 실제 전체 문자열은 자료 창에서 확인')
        if kind == 'chart':
            return '<div class="chart" aria-label="과거 실험의 계약 일치: 직접 판단 124/189, 판단 전 검사 179/189"><div class="bar-row"><span>직접 판단</span><div class="track"><div class="bar" style="--value:65.61%"></div></div><b>124 / 189</b></div><div class="bar-row"><span>판단 전 검사</span><div class="track"><div class="bar accent" style="--value:94.71%"></div></div><b>179 / 189</b></div></div>'
        raise ValueError((kind, key))

    markdown_text = DOC.read_text()
    body = markdown_text.split('<!-- deck:start -->', 1)[1]
    sections = re.split(r'\n---\n', body.strip())
    slide_count = len(sections)
    assert slide_count > 0
    slides, titles, guide_sections = [], [], []
    chapter = '의미·추론·검증'
    for i, section in enumerate(sections):
        chapter_match = re.search(r'<!-- chapter:(.*?) -->', section)
        if chapter_match:
            chapter = chapter_match.group(1).strip()
        fit_match = re.search(r'<!-- fit:([\w -]+) -->', section)
        fit_class = ' ' + fit_match.group(1).strip() if fit_match else ''
        section = re.sub(r'<!-- (?:chapter|fit):.*? -->\s*', '', section)
        text, notes = section.split('<!-- notes -->', 1)
        title, text = text.strip().split('\n', 1)
        title = re.sub(r'^## \d+\. ', '', title)
        titles.append(title)
        text = re.sub(r'\{\{(\w+):([\w-]+)\}\}', replace, text)
        content = markdown.markdown(text, extensions=['fenced_code', 'tables'])
        content = re.sub(r'((?:<div class="code-block"><div class="code-label">.*?</div><pre>.*?</pre></div>\s*){2,})', r'<div class="code-columns">\1</div>', content, flags=re.S)
        # Put the slide's takeaway directly below its heading.
        takeaways = re.findall(r'<blockquote>.*?</blockquote>', content, flags=re.S)
        content = ''.join(takeaways) + re.sub(r'<blockquote>.*?</blockquote>', '', content, flags=re.S)
        # Keep source links usable when the self-contained HTML is opened from disk.
        def source_link(m):
            target = m.group(1)
            if target.startswith('../records/'):
                target = GITHUB + 'experiments/' + target.removeprefix('../')
            elif target.startswith('../../journal/'):
                target = GITHUB + target.removeprefix('../../')
            return f'href="{html.escape(target, quote=True)}"'
        content = re.sub(r'href="([^"]+)"', source_link, content)
        notes_html = markdown.markdown(notes.strip().split('<!-- HUMANIZE-SUMMARY -->')[0])
        # A static reader-facing companion, without inactive presentation buttons.
        static_content = re.sub(r'<button[^>]*class="nb-run".*?</button>', '', content, flags=re.S)
        static_content = static_content.replace('<button type="button" class="nb-download">↓ 실습 노트북 저장</button>', '<a href="../seminar/notebooks/manufacturing-shacl.ipynb">실습 노트북 다운로드</a>')
        static_content = re.sub(r'<div class="demo" id="discount-demo">.*?</div></div></div>',
                                code(json.dumps(examples['mini_cases'], ensure_ascii=False, indent=2)),
                                static_content, flags=re.S)
        static_content = re.sub(r'<!-- saved-demo:(\w+) -->.*?<!-- /saved-demo -->', lambda m: static_demos[m.group(1)], static_content, flags=re.S)
        guide_sections.append(f'## {i+1:02}. {title}\n\n{static_content}\n\n<details><summary>발표자 노트</summary>\n\n{notes_html}\n\n</details>\n')
        slides.append(f'<section class="slide{fit_class}" id="slide-{i+1}" aria-labelledby="title-{i+1}" {"" if i == 0 else "hidden"}><header class="slide-head"><span class="eyebrow">{html.escape(chapter)}</span><h1 id="title-{i+1}">{html.escape(title)}</h1></header><div class="slide-body">{content}</div><aside class="speaker" hidden><h2>발표자 노트</h2>{notes_html}</aside><footer class="slide-foot"><span>LLM 판단 · 규칙 · 근거</span><span>{i+1:02} / {slide_count}</span></footer></section>')
    assets = {}
    for p in sorted((OUT / 'examples').glob('*')):
        if p.is_file():
            assets[p.name] = p.read_text()
    assets['notebooks/manufacturing-shacl.ipynb'] = notebook_path.read_text()
    assets['seminar_examples.py'] = snippets
    assets['seminar_manufacturing_examples.py'] = semantic_snippets
    for p in sorted((OUT / 'manufacturing').glob('*')):
        if p.is_file():
            assets['manufacturing/' + p.name] = p.read_text()
    for diagram in sorted((OUT / 'diagrams').glob('*.svg')):
        assets[diagram.name] = diagram.read_text()
    assets['발표자-노트.md'] = '\n\n'.join(f'## {i+1}. {titles[i]}\n\n{sections[i].split("<!-- notes -->", 1)[1].strip()}' for i in range(slide_count))
    assets['OFL.txt'] = (OUT / 'OFL.txt').read_text()
    css = (OUT / 'theme.css').read_text()
    js = (OUT / 'app.js').read_text()
    font = base64.b64encode((OUT / 'Pretendard-Regular.woff2').read_bytes()).decode()
    data = json.dumps({'examples': examples, 'semantics': semantics, 'assets': assets}, ensure_ascii=False).replace('<', '\\u003c')
    title_options = ''.join(f'<option value="{i}">{i+1:02}. {html.escape(t)}</option>' for i, t in enumerate(titles))
    result = f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LLM 판단을 돕는 의미·추론·검증 · {slide_count}장 세미나</title><style>@font-face{{font-family:Pretendard;src:url(data:font/woff2;base64,{font}) format('woff2');font-weight:400;font-display:swap}}\n{css}</style></head>
<body><nav class="toolbar" aria-label="발표 제어"><a class="brand" href="#1">SEMINAR <span>/ {slide_count}</span></a><select id="slide-select" aria-label="슬라이드 선택">{title_options}</select><div class="tools"><button id="prev" title="이전 (←)" aria-label="이전 슬라이드">←</button><button id="next" title="다음 (→)" aria-label="다음 슬라이드">→</button><button id="notes" aria-pressed="false">노트 N</button><button id="assets">자료</button><button id="fullscreen">전체 화면 F</button><button id="print">인쇄 P</button></div></nav><div class="progress"><div id="progress"></div></div><main>{''.join(slides)}</main><div class="hint">← → 이동 · Space 다음 슬라이드 · N 노트 · F 전체 화면 · P 인쇄 / PDF</div>
<dialog id="asset-dialog"><div class="dialog-head"><h2>실행 자료</h2><button id="close-dialog" aria-label="자료 창 닫기">닫기 ×</button></div><p>이 HTML에 포함된 실행 자료입니다. 인터넷 연결 없이 열고 저장할 수 있습니다.</p><select id="asset-select" aria-label="자료 파일 선택"></select><button id="download-asset">선택 파일 저장</button><pre id="asset-content" tabindex="0"></pre></dialog>
<script id="deck-data" type="application/json">{data}</script><script>{js}</script></body></html>'''
    (OUT / 'index.html').write_text(result)
    guide = f'# LLM 판단을 돕는 의미·추론·검증 — 세미나 자료\n\n[{slide_count}장 HTML 발표 열기](seminar/index.html) · [{slide_count}장 PDF](seminar/seminar.pdf)\n\n흰 배경과 Pretendard를 사용한 50~65분 발표 자료다. HTML은 폰트·코드·입출력 자료를 포함하며 인터넷 없이 실행된다. ←/→로 이동, Space로 다음 슬라이드, N으로 노트, F로 전체 화면, P로 인쇄한다. 자료 버튼에서 예제 파일을 저장할 수 있다.\n\n편집 원본은 `docs/experiments/seminar/slides.md`, 생성기는 `scripts/build_seminar.py`다. 아래는 발표 내용을 정적으로 펼친 안내문이다.\n\n'
    view_css = css.split('/* VIEW STYLES START:', 1)[1].split('*/', 1)[1].split('/* VIEW STYLES END */', 1)[0]
    (ROOT / 'docs/experiments/seminar-guide.md').write_text(guide + '<style>\n' + view_css + '\n</style>\n\n' + '\n'.join(guide_sections))
    (OUT / 'build-manifest.json').write_text(json.dumps({'slides': slide_count, 'notebook_sha256': hashlib.sha256(notebook_path.read_bytes()).hexdigest(), 'manufacturing_sha256': hashlib.sha256((OUT / 'manufacturing/manufacturing.json').read_bytes()).hexdigest(), 'source': str(DOC.relative_to(ROOT)), 'source_sha256': hashlib.sha256(DOC.read_bytes()).hexdigest(), 'examples_sha256': hashlib.sha256((OUT / 'examples/examples.json').read_bytes()).hexdigest(), 'embedded_font': 'Pretendard Regular 1.3.9 / SIL OFL 1.1', 'llm_calls': 0, 'presentation_browser_executes_python': False}, ensure_ascii=False, indent=2))
    print(f'Built {OUT / "index.html"}: {slide_count} slides, {len(assets)} embedded files, {len(result.encode()):,} bytes')

if __name__ == '__main__':
    build()
