# LLM 판단을 돕는 의미·추론·검증 — 세미나 자료

[25장 HTML 발표 열기](seminar/index.html) · [25장 PDF](seminar/seminar.pdf)

흰 배경과 Pretendard를 사용한 50~65분 발표 자료다. HTML은 폰트·코드·입출력 자료를 포함하며 인터넷 없이 실행된다. ←/→로 이동, Space로 다음 슬라이드, N으로 노트, F로 전체 화면, P로 인쇄한다. 자료 버튼에서 예제 파일을 저장할 수 있다.

편집 원본은 `docs/experiments/seminar/slides.md`, 생성기는 `scripts/build_seminar.py`다. 아래는 발표 내용을 정적으로 펼친 안내문이다.

<style>

.seminar-view{font-family:Pretendard,system-ui,sans-serif;color:#14212f;line-height:1.5;min-width:0}
.seminar-view *{box-sizing:border-box}
.seminar-view .columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:22px;align-items:start}
.seminar-view .columns.three{grid-template-columns:repeat(3,minmax(0,1fr))}
.seminar-view .panel{border:1px solid #dce2e9;border-radius:8px;background:#fff;padding:18px 20px;min-width:0}
.seminar-view .screen{border:1px solid #cfd9e5;border-radius:9px;background:#fff;box-shadow:0 4px 16px #14212f08;overflow:hidden;min-width:0}
.seminar-view .screen-head,.seminar-view .screen-bar{display:flex;justify-content:space-between;align-items:center;gap:10px;background:#f4f7fb;border-bottom:1px solid #dce2e9;padding:11px 16px;font-size:14px;font-weight:700;color:#334b66}
.seminar-view .screen-body{padding:16px 18px}
.seminar-view h2,.seminar-view h3,.seminar-view h4{font-size:19px;line-height:1.35;margin:0 0 12px;color:#1b3554}
.seminar-view p{margin:0 0 12px}.seminar-view p:last-child{margin-bottom:0}
.seminar-view .label,.seminar-view .caption,.seminar-view .small{font-size:13px;color:#596777}
.seminar-view .badge{display:inline-block;padding:3px 8px;border-radius:4px;background:#eaf1fc;color:#245dc0;font-size:12px;white-space:nowrap}
.seminar-view .compact{font-size:16px}.seminar-view .compact pre{font-size:13px}
.seminar-view table{border-collapse:collapse;width:100%;font-size:15px;line-height:1.5;margin:0}
.seminar-view caption{text-align:left;font-size:12px;color:#596777;padding:0 0 7px}
.seminar-view th,.seminar-view td{text-align:left;padding:8px 10px;border-bottom:1px solid #dce2e9;vertical-align:top;overflow-wrap:anywhere}
.seminar-view th{color:#596777;background:#f7f9fc;font-size:13px;font-weight:600}
.seminar-view tr:last-child td{border-bottom:0}
.seminar-view pre{margin:0;padding:14px 16px;white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;border:1px solid #e6eaf0;border-radius:6px;font:14px/1.5 ui-monospace,'DejaVu Sans Mono',monospace}
.seminar-view code{font-family:ui-monospace,'DejaVu Sans Mono',monospace}
.seminar-view .annotated-code{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:16px;align-items:start}
.seminar-view .annotation{font-size:16px;padding:10px 14px;border-left:3px solid #a8c2e7;background:#f7f9fc;margin:0 0 10px}
.seminar-view .annotation strong{color:#245dc0}
.seminar-view .code-line{display:block}.seminar-view .code-line.marked{background:#e8f0fc;border-left:3px solid #245dc0;padding-left:8px}
.seminar-view .callout{padding:12px 16px;border-left:3px solid #245dc0;background:#f4f7fc;font-size:16px;margin:12px 0}
.seminar-view .result{font-size:18px;color:#245dc0;font-weight:700}
.seminar-view .flow-arrow{text-align:center;color:#6c82a0;font-size:24px;padding:6px}
@media(max-width:760px){.seminar-view .columns,.seminar-view .columns.three,.seminar-view .annotated-code{grid-template-columns:1fr;gap:14px}.seminar-view .panel{padding:14px}.seminar-view pre{font-size:12px}.seminar-view table{font-size:13px}.seminar-view th,.seminar-view td{padding:7px}.seminar-view .screen-body{padding:12px}.seminar-view h3{font-size:17px}}
@media print{.seminar-view .columns{gap:18px}.seminar-view .panel{padding:14px 16px}.seminar-view pre{font-size:12px;line-height:1.4}.seminar-view table{font-size:14px}.seminar-view th,.seminar-view td{padding:7px 9px}.seminar-view .annotation{font-size:15px}.seminar-view .screen-body{padding:13px 15px}.seminar-view .screen-head,.seminar-view .screen-bar{padding:8px 14px}.compact .slide-body{font-size:18px}}
.seminar-view .validation-capture{border:1px solid #cfd9e5;border-radius:9px;background:#fff;overflow:hidden}
.seminar-view .validation-capture-header{display:flex;justify-content:space-between;gap:12px;padding:10px 18px;background:#f4f7fb;border-bottom:1px solid #dce2e9;font-size:14px}
.seminar-view .validation-return-grid{display:grid;grid-template-columns:1fr 1.2fr;gap:22px;padding:16px 18px;font-size:15px}
.seminar-view .validation-false{font:700 29px/1.3 ui-monospace,monospace;color:#b33131}
.seminar-view .validation-return-grid dl{display:grid;grid-template-columns:90px minmax(0,1fr);gap:5px;font-size:13px;margin:0 0 10px}
.seminar-view .validation-return-grid dt{color:#596777}.seminar-view .validation-return-grid dd{margin:0;font-family:ui-monospace,monospace;overflow-wrap:anywhere}
.seminar-view .validation-terminal{padding:0 18px 14px}.seminar-view .validation-terminal pre{font-size:13px;line-height:1.4}
.seminar-view details{font-size:12px;margin:0 18px 12px}.seminar-view summary{cursor:pointer;color:#596777}
@media(max-width:760px){.seminar-view .validation-return-grid{grid-template-columns:1fr}.seminar-view .validation-capture-header{flex-wrap:wrap}}
@media print{.seminar-view .validation-capture details{display:none}.seminar-view .validation-return-grid{padding:12px 16px;gap:18px;font-size:14px}.seminar-view .validation-terminal pre{font-size:12px}}
.seminar-view .screen>p{margin:12px 16px;font-size:16px}.seminar-view .screen>pre{border:0;border-radius:0}
.seminar-view .screen>.panel{border:0;border-radius:0;border-bottom:1px solid #dce2e9;font-size:17px}
.seminar-view .metric{font-size:29px;font-weight:700;color:#245dc0}
.seminar-view .validation-source{padding:0 18px 12px;font-size:12px;color:#596777}


.code-block{min-width:0}.code-block .code-label{margin-bottom:5px}.code-columns{display:grid;grid-template-columns:1fr 1fr;gap:18px}.code-columns pre{font-size:13px;line-height:1.5}
.seminar-view{font-size:19px}.compact .seminar-view{font-size:17px}
.compact .seminar-view .panel{padding:12px 14px}.compact .seminar-view .columns{gap:14px}.compact .seminar-view h3{font-size:17px;margin-bottom:8px}
.compact .seminar-view p{margin-bottom:8px}.compact .seminar-view table{font-size:14px}.compact .seminar-view th,.compact .seminar-view td{padding:6px 8px}.compact .seminar-view .metric{font-size:25px}
@media(max-width:760px){.code-columns{grid-template-columns:1fr}.seminar-view{font-size:17px}}
@media print{.story-flow>svg{max-height:260px}.compact .story-flow>svg{max-height:230px}.code-columns pre{font-size:13px}}

.seminar-view .validation-capture{display:grid;grid-template-columns:.9fr 1fr 1.25fr;gap:16px;padding:0 16px 12px}
.seminar-view .validation-capture-header{grid-column:1/-1;margin:0 -16px;padding:10px 16px}
.seminar-view .validation-return-grid{display:contents}.seminar-view .validation-return-grid>section{min-width:0;font-size:15px}
.seminar-view .validation-return-grid dl{display:block}.seminar-view .validation-return-grid dd{margin:0 0 8px}
.seminar-view .validation-terminal{padding:0}.seminar-view .validation-terminal pre{font-size:13px;padding:12px;line-height:1.5}
.seminar-view .validation-capture>details{margin:0}.seminar-view .validation-source{grid-column:1/-1;padding:0;margin:0;font-size:11px}
@media(min-width:1100px){.compact .seminar-view .panel{padding:10px 12px}.compact .seminar-view .columns{gap:12px}.compact .seminar-view th,.compact .seminar-view td{padding:5px 8px}.compact .seminar-view h3{margin-bottom:6px}}
@media(min-width:1100px) and (max-height:750px){.diagram-small .story-flow>svg{max-height:180px}}
@media(max-width:760px){.seminar-view .validation-capture{display:block;padding:0 14px 12px}.seminar-view .validation-capture-header{margin:0 -14px 14px}.seminar-view .validation-return-grid{display:block}.seminar-view .validation-return-grid>section{margin-bottom:18px}.seminar-view .validation-capture>details{margin:12px 0}}
.seminar-view table tbody tr,.seminar-view table tbody td{background:#fff!important;color:#14212f!important}

/* Executed notebook cells; outputs stay visible in the static guide and PDF. */
.seminar-notebook{border:1px solid #d9e1eb;border-radius:8px;overflow:hidden;background:#fff;color:#14212f;font-size:15px}
.nb-bar{display:flex;justify-content:space-between;padding:10px 16px;background:#f5f7fa;border-bottom:1px solid #d9e1eb;font-size:13px;color:#53667d}
.nb-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:14px}
.nb-cell{min-width:0;border:1px solid #e1e6ed;border-left:3px solid #3270b7;border-radius:4px}
.nb-cell-head{display:flex;align-items:center;gap:12px;height:35px;padding:3px 10px;background:#f7f9fc;font:12px ui-monospace,monospace;color:#53667d}
.nb-cell-head span:last-child{margin-left:auto}.nb-run{border:0;background:transparent;color:#245dc0;font-size:16px;padding:2px 8px}
.nb-code,.nb-output pre{border:0!important;border-radius:0!important;background:#fff!important;color:#14212f!important;margin:0!important;padding:10px 12px!important;font:12px/1.45 ui-monospace,'DejaVu Sans Mono',monospace!important;white-space:pre-wrap;overflow-wrap:anywhere}
.nb-output{border-top:1px solid #e1e6ed;padding:9px 0 0;min-height:70px;white-space:normal}
.nb-out-label{color:#7b557d;font:12px ui-monospace,monospace;padding-left:12px}.nb-output pre{padding-top:5px!important}
.slide .nb-output{visibility:hidden}.slide .nb-output.shown{visibility:visible;animation:nb-reveal .2s ease}
.nb-caption{display:flex;align-items:center;justify-content:space-between;font-size:12px;color:#596777;padding:8px 16px;background:#f9fafc;border-top:1px solid #e1e6ed}
.nb-download{font-size:12px;padding:4px 10px}.nb-grid .nb-cell:only-child{grid-column:1/-1}
@keyframes nb-reveal{from{transform:translateY(3px)}to{transform:none}}
@media(max-width:760px){.nb-grid{grid-template-columns:1fr}.nb-bar{flex-wrap:wrap;gap:5px}.nb-caption{flex-wrap:wrap;gap:8px}}
@media print{.slide .nb-output{visibility:visible!important;animation:none}.nb-run,.nb-download{display:none!important}.nb-grid{padding:10px;gap:14px}.nb-code,.nb-output pre{font-size:12px!important}}

@media(min-width:1100px) and (max-height:800px){.nb-bar{padding:8px 16px}.nb-grid{padding:10px}.nb-cell-head{height:30px}.nb-output{min-height:55px}.nb-caption{padding:6px 16px}}
@media print{.nb-bar{padding:8px 16px}.nb-cell-head{height:30px}.nb-output{min-height:55px}.nb-caption{padding:6px 16px}}
.seminar-notebook .nb-output{padding-top:5px}.seminar-notebook .nb-output pre{padding-bottom:6px!important}

</style>

## 01. 설비 중단과 대체 배정 판단

<blockquote>
<p>지금 연구에서 온톨로지와 SHACL의 가장 설득력 있는 역할은 LLM의 지능을 높이는 것보다 여러 구성요소가 같은 의미로 데이터를 읽고 판단하도록 만드는 것입니다.</p>
</blockquote><p><strong>“설비 M02가 멈췄습니다. 주문 O17과 O18을 M03으로 돌려도 되나요?”</strong></p>
<div class="flow story-flow" data-flow="question"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 200" role="img" aria-labelledby="question-title question-desc" font-family="Pretendard, sans-serif"><title id="question-title">현장·품질·감사 담당자의 설비 대체 질문</title><desc id="question-desc">현장 담당자는 M03 대체 배정 가능 여부를 묻고 품질 담당자는 Q03R의 제품·기간 적용 범위를 확인하며 감사 담당자는 판단 근거와 규칙 버전을 확인한다.</desc><defs><marker id="question-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6.0" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24.0" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="12" r="7"/><path d="M10 43v-7c0-10 28-10 28 0v7M18 43v-9M30 43v-9"/></svg><text x="74.0" y="51" font-size="21" fill="#14212f" font-weight="700">현장 배정 담당자</text><text x="26.0" y="89" font-size="18" fill="#465970">M02가 멈췄는데 O17·O18을</text><text x="26.0" y="114" font-size="18" fill="#465970">설비 M03으로 돌려도 될까?</text></g><path d="M360.3333333333333 95H378.3333333333333" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#question-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="385.3333333333333" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="403.3333333333333" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="12" r="7"/><path d="M10 43v-7c0-10 28-10 28 0v7M18 43v-9M30 43v-9"/></svg><text x="453.3333333333333" y="51" font-size="21" fill="#14212f" font-weight="700">품질·자격 담당자</text><text x="405.3333333333333" y="89" font-size="18" fill="#465970">갱신 기록 Q03R이 두 제품의</text><text x="405.3333333333333" y="114" font-size="18" fill="#465970">역량·유효기간에 모두 맞을까?</text></g><path d="M739.6666666666666 95H757.6666666666666" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#question-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="764.6666666666666" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="782.6666666666666" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="12" r="7"/><path d="M10 43v-7c0-10 28-10 28 0v7M18 43v-9M30 43v-9"/></svg><text x="832.6666666666666" y="51" font-size="21" fill="#14212f" font-weight="700">감사·운영 담당자</text><text x="784.6666666666666" y="89" font-size="18" fill="#465970">어떤 기록과 규칙 버전으로</text><text x="784.6666666666666" y="114" font-size="18" fill="#465970">판단했고 무엇을 재검토할까?</text></g></svg></div>



<details><summary>발표자 노트</summary>

<p>답변 정확도만 보면 온톨로지와 SHACL이 만드는 가치의 일부를 놓칠 수 있다. 공장 사례에서 M02가 멈추고 M03의 자격 갱신 소식이 들릴 때 현장 담당자는 대체 배정 가능 여부를 묻고 품질 담당자는 자격의 제품·기간 범위를 확인하며 감사 담당자는 판단 근거와 규칙 버전을 기록하려 한다. 다만 온톨로지와 SHACL은 구분해야 한다. 온톨로지는 무엇을 어떤 관계로 표현하고 해석할지 다루며 SHACL은 그 데이터가 특정 용도의 조건을 만족하는지를 다룬다. 둘 중 하나만 쓰는 설계도 가능하다.</p>

</details>

## 02. 발표 구성

<div class="flow story-flow" data-flow="learning"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 200" role="img" aria-labelledby="learning-title learning-desc" font-family="Pretendard, sans-serif"><title id="learning-title">의미 공유에서 도입 판단까지 25장 구성</title><desc id="learning-desc">업무 의미와 규칙 공유에서 시작해 RDF·OWL·SHACL 실습을 거쳐 도구 계약·검토 기록·도입 기준으로 이어진다.</desc><defs><marker id="learning-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6.0" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24.0" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="12" r="7"/><path d="M10 43v-7c0-10 28-10 28 0v7M18 43v-9M30 43v-9"/></svg><text x="74.0" y="51" font-size="21" fill="#14212f" font-weight="700">01–05 · 업무 의미와 규칙</text><text x="26.0" y="89" font-size="18" fill="#465970">대체 가능의 네 층위 구분</text><text x="26.0" y="114" font-size="18" fill="#465970">공통 규칙 공유와 적재·통합 점검</text></g><path d="M360.3333333333333 95H378.3333333333333" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#learning-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="385.3333333333333" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="403.3333333333333" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="10" r="5"/><circle cx="36" cy="24" r="5"/><circle cx="12" cy="38" r="5"/><path d="m16 13 16 9m0 5-16 9M12 15v18"/></svg><text x="453.3333333333333" y="51" font-size="21" fill="#14212f" font-weight="700">06–21 · 추론과 SHACL 실습</text><text x="405.3333333333333" y="89" font-size="18" fill="#465970">RDF · RDFS · OWL · SHACL 구분</text><text x="405.3333333333333" y="114" font-size="18" fill="#465970">제조 부품 예제와 노트북 실행</text></g><path d="M739.6666666666666 95H757.6666666666666" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#learning-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="764.6666666666666" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="782.6666666666666" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="10" y="5" width="28" height="38" rx="3"/><path d="m15 16 3 3 5-6M26 16h6m-17 11 3 3 5-6M26 27h6"/></svg><text x="832.6666666666666" y="51" font-size="21" fill="#14212f" font-weight="700">22–25 · 도구·기록·도입 기준</text><text x="784.6666666666666" y="89" font-size="18" fill="#465970">LLM 도구 계약 · 검토 근거 보존</text><text x="784.6666666666666" y="114" font-size="18" fill="#465970">저장소 대조(48쌍)와 도입 질문</text></g></svg></div>

<ul>
<li><strong>연구 방향:</strong> 온톨로지·SHACL의 역할 구분과 여섯 가지 실무 가치</li>
<li><strong>의미와 추론:</strong> 제조 부품 예제로 보는 RDF·RDFS·OWL과 추론의 경계</li>
<li><strong>SHACL 검증:</strong> 조건 명세, 노트북 실습, 저장소·도구·검토 기록 연결</li>
<li><strong>도입 기준:</strong> 공유 Python 대안과의 비교, 도입 판단 질문</li>
</ul>

<details><summary>발표자 노트</summary>

<p>25장으로 압축한 세미나 구성이다. 온톨로지를 쓰면 LLM이 더 똑똑해진다는 주장 대신 LLM이 사용하는 근거와 판단 조건을 명시하고 공유하며 변경과 오류를 추적할 수 있게 한다는 연구 방향을 먼저 제시한다. 이어서 작은 제조 부품 예제를 끝까지 따라가며 표현, 추론, 검증, 외부 사실 확인의 차이를 코드와 실행 결과로 살펴본다. 마지막에는 LLM 도구 계약, 구조화된 검토 기록, 저장소 이식성과 현실적인 도입 기준을 정리한다.</p>

</details>

## 03. 데이터 구조에 업무 의미 남기기

<blockquote>
<p>공장 사례에서 <code>M03 → Q03R</code>이라는 연결만으로는 부족합니다. 기능적 가능, 유효 자격, 일정 여유, 사용 승인을 구분해 명시해야 개발자와 LLM이 모두 ‘대체 가능’으로 뭉뚱그리지 않습니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="evidence"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 380" role="img" aria-labelledby="evidence-title evidence-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="evidence-title">대체 가능이라는 말에 섞이기 쉬운 네 가지 업무 의미</title><desc id="evidence-desc">설비 M03과 자격 기록 Q03, Q03R에서 기능적 작업 가능, 제품·기간별 유효 자격, 생산 일정 배정 여유, 사용 승인을 구분해 명시한다.</desc><defs><marker id="evidence-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="380" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">‘대체 가능’으로 뭉뚱그리기 쉬운 네 가지 업무 의미 구분</text>
<text x="1090" y="32" text-anchor="end" font-size="17" font-weight="400" fill="#52677f">가상 공장 실험 사례 (M03 · Q03R · O17/O18)</text>
<rect x="20" y="56" width="250" height="190" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="36" y="88" font-size="20" font-weight="700" fill="#245dc0">① 기능적 작업 가능</text>
<text x="36" y="122" font-size="18" font-weight="600" fill="#142d49">M03 → CAP-CUT</text>
<text x="36" y="154" font-size="16" fill="#52677f">절단 역량이 등록된 설비</text>
<text x="36" y="182" font-size="16" fill="#52677f">O17·O18 모두 기능 후보</text>
<text x="36" y="220" font-size="15" font-weight="600" fill="#334b66">자격·일정은 미확인</text>
<rect x="296" y="56" width="250" height="190" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="312" y="88" font-size="20" font-weight="700" fill="#245dc0">② 유효한 제품 자격</text>
<text x="312" y="122" font-size="18" font-weight="600" fill="#142d49">M03 → Q03R (P-A)</text>
<text x="312" y="154" font-size="16" fill="#52677f">Q03R은 제품 P-A만 유효</text>
<text x="312" y="182" font-size="16" fill="#52677f">O18(제품 P-B)은 범위 불일치</text>
<text x="312" y="220" font-size="15" font-weight="600" fill="#b33131">제품·역량·기간 동시 충족 필요</text>
<rect x="572" y="56" width="250" height="190" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="588" y="88" font-size="20" font-weight="700" fill="#245dc0">③ 일정 배정 가능</text>
<text x="588" y="122" font-size="18" font-weight="600" fill="#142d49">available ≠ 일정 여유</text>
<text x="588" y="154" font-size="16" fill="#52677f">설비 상태값만으로는</text>
<text x="588" y="182" font-size="16" fill="#52677f">실제 부하·납기 판단 불가</text>
<text x="588" y="220" font-size="15" font-weight="600" fill="#334b66">별도 스케줄 확인 대상</text>
<rect x="848" y="56" width="252" height="190" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="864" y="88" font-size="20" font-weight="700" fill="#245dc0">④ 사용 승인 완료</text>
<text x="864" y="122" font-size="18" font-weight="600" fill="#142d49">운영·품질 변경 승인</text>
<text x="864" y="154" font-size="16" fill="#52677f">현장 소문(“갱신했다더라”)</text>
<text x="864" y="182" font-size="16" fill="#52677f">≠ 공식 승인된 배정 변경</text>
<text x="864" y="220" font-size="15" font-weight="600" fill="#334b66">담당자 확인·승인 절차 분리</text>
<rect x="20" y="268" width="1080" height="86" rx="9" fill="#f7f9fc" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="40" y="302" text-anchor="start" font-size="19" font-weight="700" fill="#142d49">온톨로지의 역할: 관계를 무조건 늘리는 것이 아니라 위 네 가지 구분을 데이터 구조에 명시하는 것</text>
<text x="40" y="334" text-anchor="start" font-size="17" font-weight="400" fill="#52677f">다만 RDF로 표현한다고 구분이 저절로 생기지는 않으므로, 개념과 적용 조건을 직접 설계해야 한다.</text>
</svg></div>

<ul>
<li>자격 범위: <code>Q03R</code>이 어떤 제품(<code>P-A</code> / <code>P-B</code>)·역량(<code>CAP-CUT</code>)·유효기간에 적용되는지 구분</li>
<li>상태 의미: 설비의 <code>available</code>이 생산 일정상 여유까지 뜻하는지 별도 정의</li>
</ul>

<details><summary>발표자 노트</summary>

<p>온톨로지의 역할은 관계를 많이 만드는 것이 아니라 업무상 구분을 명시하는 데 있다. 기능적으로 작업할 수 있는 설비, 해당 제품의 유효한 자격을 가진 설비, 실제 일정에 배정할 수 있는 설비, 사용 승인을 받은 설비를 나눠야 한다. 이 구분이 없으면 개발자나 LLM이 모두 대체 가능이라는 말로 뭉뚱그리기 쉽다. 우리가 가상 공장 실험에서 실제로 부딪힌 문제와 가까운 가치다. 다만 RDF로 표현한다고 구분이 자동으로 생기는 것은 아니므로 모델링 단계에서 개념과 관계를 분명히 정의해야 한다.</p>

</details>

## 04. 공통 규칙 공유와 공정한 비교 기준

<blockquote>
<p>SHACL을 공통 규칙 산출물로 두면 여러 서비스가 어떤 버전의 조건으로 검사했는지 추적하기 쉬워집니다. 공정한 비교 대상은 공유 스키마·규칙·버전 관리를 갖춘 Python 시스템입니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="change"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 360" role="img" aria-labelledby="change-title change-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="change-title">여러 서비스의 공통 규칙 공유와 공정한 비교 대상</title><desc id="change-desc">챗봇, 검색 API, 품질 점검, 데이터 적재가 공통 자격 조건을 공유하고 버전별로 추적한다. 공정한 비교 대상은 공유 스키마·규칙·버전 관리를 갖춘 Python 시스템이다.</desc><defs><marker id="change-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="360" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">여러 서비스의 규칙 공유 구조와 공정한 비교 기준</text>
<rect x="20" y="56" width="520" height="275" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="42" y="90" font-size="20" font-weight="700" fill="#142d49">공통 규칙 산출물 (SHACL 또는 공유 선언 규칙)</text>
<rect x="42" y="108" width="476" height="58" rx="7" fill="#fff" stroke="#245dc0" stroke-width="1.8"/>
<text x="280" y="135" text-anchor="middle" font-size="18" font-weight="700" fill="#245dc0">자격 조건 계약 v3 · 제품 + 역량 + 기준일 유효기간</text>
<text x="280" y="156" text-anchor="middle" font-size="15" fill="#52677f">어느 서비스가 어떤 버전의 조건으로 검사했는지 해시·버전 기록</text>
<path d="M150 166 V202" fill="none" stroke="#245dc0" stroke-width="2" marker-end="url(#change-arrow)"/>
<path d="M410 166 V202" fill="none" stroke="#245dc0" stroke-width="2" marker-end="url(#change-arrow)"/>
<rect x="42" y="210" width="225" height="46" rx="6" fill="#fff" stroke="#c7d5e5"/>
<text x="154" y="239" text-anchor="middle" font-size="17" font-weight="600" fill="#142d49">챗봇 · 검색 API</text>
<rect x="293" y="210" width="225" height="46" rx="6" fill="#fff" stroke="#c7d5e5"/>
<text x="405" y="239" text-anchor="middle" font-size="17" font-weight="600" fill="#142d49">품질 점검 · 데이터 적재</text>
<text x="42" y="298" font-size="16" fill="#52677f">개별 서비스마다 조건을 따로 코딩하면 한쪽만 수정될 위험</text>
<rect x="570" y="56" width="530" height="275" rx="9" fill="#f7f9fc" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="592" y="90" font-size="20" font-weight="700" fill="#142d49">무엇과 비교해야 공정한가?</text>
<rect x="592" y="110" width="486" height="82" rx="7" fill="#fff" stroke="#c7d5e5"/>
<text x="612" y="140" font-size="18" font-weight="700" fill="#b33131">부적절한 대조군: 정리되지 않은 개별 Python 코드</text>
<text x="612" y="170" font-size="16" fill="#52677f">규칙 분산 문제를 언어 자체의 한계로 오해하기 쉬움</text>
<rect x="592" y="208" width="486" height="98" rx="7" fill="#fff" stroke="#245dc0" stroke-width="1.8"/>
<text x="612" y="238" font-size="18" font-weight="700" fill="#245dc0">공정한 대조군: 공유 스키마·규칙·버전 관리 Python</text>
<text x="612" y="266" font-size="16" fill="#142d49">동일 정책·동일 버전 메타데이터를 제공한 뒤</text>
<text x="612" y="290" font-size="16" fill="#52677f">애플리케이션 결합도와 다중 도구 재사용성 차이를 비교</text>
</svg></div>

<ul>
<li>챗봇·검색 API·품질 점검·데이터 적재가 각각 조건을 구현하면 한쪽만 수정될 위험</li>
<li>차이는 규칙이 특정 애플리케이션 코드에 묶이는 정도와 다른 도구에서 재사용할 수 있는 정도</li>
</ul>

<details><summary>발표자 노트</summary>

<p>같은 자격 조건을 챗봇, 검색 API, 품질 점검, 데이터 적재에서 각각 구현하면 어느 한쪽만 수정될 수 있다. SHACL을 공통 규칙 산출물로 두면 이 서비스가 어떤 버전의 조건으로 검사했는지를 추적하기 쉬운 구조를 만들 수 있다. 물론 Python도 공통 라이브러리나 선언형 설정으로 충분히 할 수 있다. 비교 대상은 잘 정리되지 않은 Python 코드가 아니라 공유 스키마, 규칙, 버전 관리를 갖춘 Python 시스템이어야 공정하다.</p>

</details>

## 05. 파이프라인 전반의 품질 관리 지점

<blockquote>
<p>SHACL은 최종 답변 직전뿐 아니라 데이터 적재·통합·정책 변경·질의 전달 단계에서도 유용합니다. 다만 검사 통과가 사실의 진위를 보증하지는 않습니다.</p>
</blockquote><div class="flow story-flow" data-flow="shared"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 200" role="img" aria-labelledby="shared-title shared-desc" font-family="Pretendard, sans-serif"><title id="shared-title">데이터 적재부터 질의 전달까지 네 곳의 품질 관리 지점</title><desc id="shared-desc">새 데이터 적재, 데이터 통합, 자격·정책 변경, 질의 결과 전달 단계에서 각각 필수 조건을 검사하되 원천 결함과 조회 누락을 구분한다.</desc><defs><marker id="shared-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6" y="12" width="256" height="172" rx="9" fill="#fff" stroke="#c5d2e4"/><text x="24" y="48" font-size="20" fill="#245dc0" font-weight="700">1. 새 데이터 적재</text><text x="24" y="84" font-size="17" fill="#14212f" font-weight="600">필수 식별자·타입·참조</text><text x="24" y="116" font-size="16" fill="#465970">누락·자료형 오류를</text><text x="24" y="142" font-size="16" fill="#465970">적재 직후 확인</text></g><path d="M266 98H286" stroke="#879bb6" fill="none" stroke-width="2" marker-end="url(#shared-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="290" y="12" width="256" height="172" rx="9" fill="#fff" stroke="#c5d2e4"/><text x="308" y="48" font-size="20" fill="#245dc0" font-weight="700">2. 데이터 통합</text><text x="308" y="84" font-size="17" fill="#14212f" font-weight="600">출처 간 관계 의미 대조</text><text x="308" y="116" font-size="16" fill="#465970">같은 관계명을 다른 뜻으로</text><text x="308" y="142" font-size="16" fill="#465970">쓰지 않는지 점검</text></g><path d="M550 98H570" stroke="#879bb6" fill="none" stroke-width="2" marker-end="url(#shared-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="574" y="12" width="256" height="172" rx="9" fill="#fff" stroke="#c5d2e4"/><text x="592" y="48" font-size="20" fill="#245dc0" font-weight="700">3. 자격·정책 변경</text><text x="592" y="84" font-size="17" fill="#14212f" font-weight="600">기존 기록의 재검토 범위</text><text x="592" y="116" font-size="16" fill="#465970">바뀐 조건을 만족하지 못하는</text><text x="592" y="142" font-size="16" fill="#465970">후보만 표적 추출</text></g><path d="M834 98H854" stroke="#879bb6" fill="none" stroke-width="2" marker-end="url(#shared-arrow)"/><g class="step story-step" data-step="3"><rect class="story-box" x="858" y="12" width="256" height="172" rx="9" fill="#fff" stroke="#c5d2e4"/><text x="876" y="48" font-size="20" fill="#245dc0" font-weight="700">4. 질의 결과 전달</text><text x="876" y="84" font-size="17" fill="#14212f" font-weight="600">판단 근거의 입력 완전성</text><text x="876" y="116" font-size="16" fill="#465970">원천 결함과 조회 누락을</text><text x="876" y="142" font-size="16" fill="#465970">구분해 LLM에 전달</text></g></svg></div>

<table>
<thead>
<tr>
<th>지점</th>
<th>확인할 수 있는 내용</th>
</tr>
</thead>
<tbody>
<tr>
<td>새 데이터 적재</td>
<td>필수 식별자·타입·참조가 갖춰졌는가</td>
</tr>
<tr>
<td>데이터 통합</td>
<td>두 출처가 같은 관계를 서로 다른 의미로 쓰고 있지는 않은가</td>
</tr>
<tr>
<td>자격·정책 변경</td>
<td>새 규칙에서 어떤 기존 기록이 조건을 만족하지 못하는가</td>
</tr>
<tr>
<td>질의 결과 전달</td>
<td>이번 판단에 필요한 필드와 연결이 제공됐는가</td>
</tr>
</tbody>
</table>


<details><summary>발표자 노트</summary>

<p>SHACL은 최종 답변 직전뿐 아니라 데이터 적재와 변경 단계의 품질 관리에도 쓸 만하다. 특히 검색 결과 일부를 검사할 때는 원본 데이터의 결함인지, 조회 과정에서 빠진 것인지 구분해야 한다. 검사 통과는 선언한 조건의 충족일 뿐 사실의 진위를 보증하지 않는다. 원천 부재와 조회 누락, 그리고 외부 사실 여부를 가르는 경계는 우리 연구에서 계속 유지할 가치가 있다.</p>

</details>

## 06. 추론·검증·사실 확인의 구분

<blockquote>
<p>입력이 틀리면 논리적으로 일관된 결론도 현실에서는 틀릴 수 있습니다.</p>
</blockquote><div class="flow story-flow" data-flow="threequestions"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 200" role="img" aria-labelledby="threequestions-title threequestions-desc" font-family="Pretendard, sans-serif"><title id="threequestions-title">추론·검증·사실 확인은 서로 다른 작업</title><desc id="threequestions-desc">추론·검증·사실 확인은 서로 다른 작업</desc><defs><marker id="threequestions-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6.0" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24.0" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="10" r="5"/><circle cx="36" cy="24" r="5"/><circle cx="12" cy="38" r="5"/><path d="m16 13 16 9m0 5-16 9M12 15v18"/></svg><text x="74.0" y="51" font-size="21" fill="#14212f" font-weight="700">추론</text><text x="26.0" y="89" font-size="18" fill="#465970">정의와 기록으로부터</text><text x="26.0" y="114" font-size="18" fill="#465970">어떤 결론이 따라오는가</text></g><path d="M360.3333333333333 95H378.3333333333333" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#threequestions-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="385.3333333333333" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="403.3333333333333" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="24" r="19"/><path d="m14 24 7 7 14-16"/></svg><text x="453.3333333333333" y="51" font-size="21" fill="#14212f" font-weight="700">데이터 검증</text><text x="405.3333333333333" y="89" font-size="18" fill="#465970">제출한 데이터가</text><text x="405.3333333333333" y="114" font-size="18" fill="#465970">정해 둔 조건을 만족하는가</text></g><path d="M739.6666666666666 95H757.6666666666666" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#threequestions-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="764.6666666666666" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="782.6666666666666" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="12" r="7"/><path d="M10 43v-7c0-10 28-10 28 0v7M18 43v-9M30 43v-9"/></svg><text x="832.6666666666666" y="51" font-size="21" fill="#14212f" font-weight="700">현실의 사실 확인</text><text x="784.6666666666666" y="89" font-size="18" fill="#465970">원천 근거·현장·전문가로</text><text x="784.6666666666666" y="114" font-size="18" fill="#465970">입력과 결론을 확인</text></g></svg></div>

<table>
<thead>
<tr>
<th>작업</th>
<th>묻는 질문</th>
<th>필요한 근거</th>
</tr>
</thead>
<tbody>
<tr>
<td>추론</td>
<td>정의와 기록에서 어떤 결론이 따라오는가</td>
<td>입력 사실 + 공리·규칙</td>
</tr>
<tr>
<td>데이터 검증</td>
<td>제출한 데이터가 조건을 만족하는가</td>
<td>검사할 그래프 + Shape</td>
</tr>
<tr>
<td>현실의 사실 확인</td>
<td>기록과 결론이 실제 업무에서 맞는가</td>
<td>독립 자료·현장 확인·전문가 판단</td>
</tr>
</tbody>
</table>


<details><summary>발표자 노트</summary>

<p>이 발표의 핵심 구분이다. 추론은 주어진 전제에 대한 작업이고 검증은 지정한 데이터 범위와 조건에 대한 작업이다. 둘 다 외부 사실을 자동으로 확인하지 않는다. 예를 들어 제조사가 다른 회사로 잘못 기록되어도 IRI 형식과 개수 조건은 만족할 수 있다. 사실 확인에는 별도 근거가 필요하며 전문가 판단도 그 출처와 절차를 기록해야 한다.</p>

</details>

## 07. RDF·RDFS·OWL·SHACL의 역할

<blockquote>
<p>온톨로지는 무엇을 어떤 관계로 해석할지 정하고 SHACL은 특정 용도의 조건 충족을 검사합니다. 둘 중 하나만 쓰는 설계도 가능합니다.</p>
</blockquote><table>
<thead>
<tr>
<th>구성</th>
<th>역할</th>
<th>제조·설비 예</th>
</tr>
</thead>
<tbody>
<tr>
<td>RDF</td>
<td>개체·관계를 트리플로 표현</td>
<td>P1은 조립품 A1에 장착된다</td>
</tr>
<tr>
<td>RDFS</td>
<td>클래스 포함 관계, domain/range 등 정의</td>
<td>볼트는 체결 부품, 체결 부품은 구성 부품</td>
</tr>
<tr>
<td>OWL</td>
<td>더 풍부한 논리적 공리 표현</td>
<td>역관계, 클래스 조합·배타성, 동일성</td>
</tr>
<tr>
<td>추론기</td>
<td>지원하는 공리·규칙의 결론 계산</td>
<td>P1도 구성 부품이라는 타입 도출</td>
</tr>
<tr>
<td>SHACL</td>
<td>주어진 RDF의 조건 충족 검사</td>
<td>필수 제조사·자격 범위가 기록됐는가</td>
</tr>
</tbody>
</table>

<p>출처: <a href="https://www.w3.org/TR/rdf11-primer/">RDF</a> · <a href="https://www.w3.org/TR/rdf-schema/">RDFS</a> · <a href="https://www.w3.org/TR/owl2-primer/">OWL</a> · <a href="https://www.w3.org/TR/shacl/">SHACL</a></p>

<details><summary>발표자 노트</summary>

<p>온톨로지와 SHACL을 구분한다. 클래스와 속성의 의미를 정한 정의를 바탕으로 구체적 개체의 기록을 연결한다. RDFS와 OWL의 정의도 RDF로 표현할 수 있다. 추론기는 이런 언어의 일부 또는 프로파일을 지원하는 소프트웨어다. pySHACL은 Python에서 SHACL을 실행하는 도구이며 추론 옵션도 제공하지만 추론과 검증은 서로 다른 단계다.</p>

</details>

## 08. RDF 트리플과 제조 부품

<blockquote>
<p>RDF는 개체와 관계를 식별자로 연결합니다. Turtle은 그 그래프를 텍스트로 적는 형식입니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="sensortriple"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 320" role="img" aria-labelledby="sensortriple-title sensortriple-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="sensortriple-title">관계 하나를 주어 · 술어 · 목적어로 기록</title><desc id="sensortriple-desc">개별 부품 P1에서 조립품 A1로 installedIn 화살표가 연결된다. 주어는 P1, 술어는 installedIn, 목적어는 A1이다.</desc><defs><marker id="sensortriple-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="320" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">관계 하나를 주어 · 술어 · 목적어로 기록</text>
<rect x="115.0" y="116" width="180" height="80" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="205" y="152" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<text x="205" y="179" text-anchor="middle" font-size="18" font-weight="400" fill="#52677f">개별 부품</text>
<rect x="825.0" y="116" width="180" height="80" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="915" y="152" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:A1</text>
<text x="915" y="179" text-anchor="middle" font-size="18" font-weight="400" fill="#52677f">개별 조립품</text>
<path d="M295 145 L825 145" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#sensortriple-arrow)"/>
<text x="560.0" y="133.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">ex:installedIn</text>
<text x="205" y="242" text-anchor="middle" font-size="20" font-weight="400" fill="#52677f">주어 subject</text>
<text x="560" y="242" text-anchor="middle" font-size="20" font-weight="400" fill="#52677f">술어 predicate</text>
<text x="915" y="242" text-anchor="middle" font-size="20" font-weight="400" fill="#52677f">목적어 object</text>
<text x="28" y="300" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">ex: = https://example.org/manufacturing/</text>
</svg>
</div>

<pre><code class="language-turtle">@prefix ex: &lt;https://example.org/manufacturing/&gt; .
ex:P1 a ex:Bolt ;                # P1은 볼트 개체
    ex:installedIn ex:A1 .       # P1은 조립품 A1에 장착
</code></pre>
<ul>
<li>입력은 설명용 합성 부품 기록이며 실제 설치 사실 확인과는 별개</li>
</ul>

<details><summary>발표자 노트</summary>

<p>P1과 A1는 교육용 합성 식별자다. ex: 접두사는 긴 IRI를 줄여 적은 것이며 a는 rdf:type의 축약이다. 주어와 술어와 목적어는 각각 누가, 어떤 관계로, 무엇과 연결되는지를 표현한다. 목적어는 이 예제처럼 다른 개체일 수도 있고 숫자나 문자열 리터럴일 수도 있다. 부품 예제 원본은 자료 창의 manufacturing-data.ttl이다.</p>

</details>

## 09. 개체·클래스·포함 관계

<blockquote>
<p>P1은 하나의 부품이고 Bolt는 그 부품이 속한 클래스입니다. 클래스 간 포함 관계와 개체의 소속을 구분합니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="instance"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 330" role="img" aria-labelledby="instance-title instance-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="instance-title">개체의 타입과 클래스의 포함 관계</title><desc id="instance-desc">개별 부품 P1은 Bolt 타입이며 Bolt 클래스는 Fastener의 하위 클래스다.</desc><defs><marker id="instance-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="330" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">개체의 타입과 클래스의 포함 관계</text>
<rect x="70.0" y="131" width="180" height="80" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="160" y="167" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<text x="160" y="194" text-anchor="middle" font-size="18" font-weight="400" fill="#52677f">개체</text>
<rect x="460.0" y="131" width="180" height="80" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="550" y="167" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Bolt</text>
<text x="550" y="194" text-anchor="middle" font-size="18" font-weight="400" fill="#52677f">클래스</text>
<rect x="850.0" y="131" width="220" height="80" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="960" y="167" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Fastener</text>
<text x="960" y="194" text-anchor="middle" font-size="18" font-weight="400" fill="#52677f">클래스</text>
<path d="M250 160 L460 160" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#instance-arrow)"/>
<text x="355.0" y="148.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">rdf:type</text>
<path d="M640 160 L850 160" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#instance-arrow)"/>
<text x="745.0" y="148.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">rdfs:subClassOf</text>
<text x="28" y="310" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">rdf:type은 개체 → 클래스, rdfs:subClassOf는 클래스 → 클래스 관계다.</text>
</svg>
</div>

<pre><code class="language-turtle">ex:P1 a ex:Bolt .                         # 개체 → 클래스
ex:Bolt rdfs:subClassOf ex:Fastener .      # 클래스 → 상위 클래스
</code></pre>
<p>출처: <a href="https://www.w3.org/TR/rdf-schema/">RDFS 클래스와 인스턴스</a></p>

<details><summary>발표자 노트</summary>

<p>개체와 클래스의 구분은 데이터 모델링의 출발점이다. 이 발표에서 P1은 개별 부품이고 Bolt와 Fastener는 클래스다. rdf:type은 개별 개체가 어떤 범주에 속하는지 나타내고 rdfs:subClassOf는 한 범주가 더 넓은 범주에 포함됨을 뜻한다.</p>

</details>

## 10. RDFS 클래스 계층과 타입 추론

<blockquote>
<p>하위 클래스의 개체는 상위 클래스에도 속합니다. 점선은 정의를 적용해 얻는 추가 결론입니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="sensorclasses"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 380" role="img" aria-labelledby="sensorclasses-title sensorclasses-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="sensorclasses-title">클래스 포함 관계에서 개체 타입 도출</title><desc id="sensorclasses-desc">P1은 Bolt이고 Bolt는 Fastener, Fastener는 Component의 하위 클래스다. P1의 Component 타입은 추론된다.</desc><defs><marker id="sensorclasses-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="380" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">클래스 포함 관계에서 개체 타입 도출</text>
<rect x="55.0" y="106" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="145" y="142" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<rect x="330.0" y="106" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="420" y="142" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Bolt</text>
<rect x="595.0" y="106" width="210" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="700" y="142" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Fastener</text>
<rect x="880.0" y="106" width="220" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="990" y="142" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Component</text>
<path d="M235 135 L330 135" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#sensorclasses-arrow)"/>
<text x="282.5" y="123.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">rdf:type</text>
<path d="M510 135 L595 135" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#sensorclasses-arrow)"/>
<text x="552.5" y="123.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">⊆</text>
<path d="M805 135 L880 135" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#sensorclasses-arrow)"/>
<text x="842.5" y="123.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">⊆</text>
<path d="M145 166 V260 H990 V166" fill="none" stroke="#245dc0" stroke-width="2.5" stroke-dasharray="8 6" marker-end="url(#sensorclasses-arrow)"/>
<text x="560" y="247" text-anchor="middle" font-size="22" font-weight="400" fill="#245dc0">추론: ex:P1 rdf:type ex:Component</text>
<text x="28" y="360" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">⊆ = rdfs:subClassOf · 실선은 명시한 관계, 점선은 규칙으로 도출한 관계</text>
</svg>
</div>

<ul>
<li>입력: <code>P1 a Bolt</code> + <code>Bolt ⊆ Fastener ⊆ Component</code></li>
<li>출력: <code>P1 a Fastener</code>, <code>P1 a Component</code></li>
<li>실제 부품의 정체가 맞는지는 원천 자료로 별도 확인</li>
</ul>
<p>출처: <a href="https://www.w3.org/TR/rdf-schema/">RDFS</a></p>

<details><summary>발표자 노트</summary>

<p>하위 클래스의 모든 인스턴스가 상위 클래스에도 속한다는 정의를 사용한다. P1을 Component로 직접 입력하지 않아도 추론 결과에서 조회할 수 있다. 실제 실행 예제에서는 원본 조회, RDFS 규칙 적용, OWL-RL 규칙 적용의 결과를 별도로 저장했다. 이 예시로 전체 RDFS 또는 OWL 기능의 정확성을 평가하지 않는다.</p>

</details>

## 11. domain·range의 타입 해석

<blockquote>
<p>domain과 range는 관계의 주어·목적어를 어떤 타입으로 해석할지 정합니다. 입력을 거부하는 검증 규칙과는 다릅니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="domainrange"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 380" role="img" aria-labelledby="domainrange-title domainrange-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="domainrange-title">domain · range는 관계 양끝의 타입을 도출</title><desc id="domainrange-desc">installedIn의 domain은 Component, range는 Assembly다. P1 installedIn A1에서 두 타입을 추론한다.</desc><defs><marker id="domainrange-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="380" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">domain · range는 관계 양끝의 타입을 도출</text>
<rect x="445.0" y="61" width="230" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="560" y="97" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:installedIn</text>
<rect x="85.0" y="141" width="230" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="200" y="177" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Component</text>
<rect x="805.0" y="141" width="230" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="920" y="177" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Assembly</text>
<path d="M445 95 L250 140" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#domainrange-arrow)"/>
<text x="347.5" y="105.5" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">rdfs:domain</text>
<path d="M675 95 L870 140" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#domainrange-arrow)"/>
<text x="772.5" y="105.5" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">rdfs:range</text>
<rect x="110.0" y="256" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="200" y="292" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<rect x="830.0" y="256" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="920" y="292" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:A1</text>
<path d="M290 285 L830 285" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#domainrange-arrow)"/>
<text x="560.0" y="273.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">ex:installedIn</text>
<path d="M200 255 L200 203" fill="none" stroke="#245dc0" stroke-width="2.5" stroke-dasharray="8 6" marker-end="url(#domainrange-arrow)"/>
<text x="290" y="230" text-anchor="middle" font-size="18" font-weight="400" fill="#245dc0">rdf:type</text>
<path d="M920 255 L920 203" fill="none" stroke="#245dc0" stroke-width="2.5" stroke-dasharray="8 6" marker-end="url(#domainrange-arrow)"/>
<text x="1010" y="230" text-anchor="middle" font-size="18" font-weight="400" fill="#245dc0">rdf:type</text>
<text x="28" y="360" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">타입 추론 규칙이다. 허용 타입을 검사하는 입력 검증 규칙과 구분한다.</text>
</svg>
</div>

<pre><code class="language-turtle">ex:installedIn rdfs:domain ex:Component ; # 주어는 구성 부품
               rdfs:range ex:Assembly . # 목적어는 조립품
</code></pre>
<p>출처: <a href="https://www.w3.org/TR/rdf-schema/">RDFS domain/range</a></p>

<details><summary>발표자 노트</summary>

<p>예를 들어 장비와 사람이 뒤바뀐 관계를 넣어도 domain과 range만으로 잘못된 입력이라고 차단하지 않는다. 관계에 따라 타입이 추론되어 붙는다. 별도로 배타적인 클래스 공리를 선언했고 같은 개체가 양쪽에 속하게 되면 논리 충돌이 생길 수 있다. 입력 단계에서 기대 타입을 확인하려면 SHACL이나 코드 기반의 명시적인 검증 정책이 필요하다.</p>

</details>

## 12. OWL 공리와 역관계

<blockquote>
<p>OWL의 공리는 관계와 클래스의 논리적 의미를 명시합니다. 실제 계산 범위는 선택한 추론기의 지원 기능에 달려 있습니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="inverse"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 350" role="img" aria-labelledby="inverse-title inverse-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="inverse-title">역속성 정의로 반대 방향 관계 도출</title><desc id="inverse-desc">installedIn과 hasPart를 역속성으로 선언하면 P1 installedIn A1에서 A1 hasPart P1을 추론한다.</desc><defs><marker id="inverse-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="350" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">역속성 정의로 반대 방향 관계 도출</text>
<text x="560" y="83" text-anchor="middle" font-size="22" font-weight="400" fill="#245dc0">ex:installedIn   owl:inverseOf   ex:hasPart</text>
<rect x="120.0" y="156" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="210" y="192" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<rect x="820.0" y="156" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="910" y="192" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:A1</text>
<path d="M300 165 L820 165" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#inverse-arrow)"/>
<text x="560.0" y="153.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">ex:installedIn</text>
<path d="M820 208 L300 208" fill="none" stroke="#245dc0" stroke-width="2.5" stroke-dasharray="8 6" marker-end="url(#inverse-arrow)"/>
<text x="560.0" y="243.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">ex:hasPart · 추론</text>
<text x="28" y="330" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">역방향 관계는 owl:inverseOf 선언이 있을 때 도출한다.</text>
</svg>
</div>

<ul>
<li><code>inverseOf</code>: P1이 A1에 장착되면 A1은 P1을 포함</li>
<li><code>equivalentClass</code>: “인증 부품이면서 체결 부품” 같은 분류 정의</li>
<li><code>disjointWith</code> / <code>sameAs</code>: 배타 분류 / 동일 개체 선언</li>
</ul>
<p>출처: <a href="https://www.w3.org/TR/owl2-primer/">OWL 2 Primer</a></p>

<details><summary>발표자 노트</summary>

<p>역관계는 실제 작은 제조 예제에서 실행했다. 동치 클래스·배타 클래스·동일성은 기능 설명이다. 이 예제에서 모든 OWL 기능을 실행하거나 검증하지 않았다. 논리적 동치는 업무 의미 검토를 요구하며 같은 이름이라는 이유로 sameAs를 선언해서는 안 된다.</p>

</details>

## 13. 열린 세계와 기록 부재

<blockquote>
<p>기록이 없다는 사실만으로 현실에서 거짓이라고 결론 내릴 수 없습니다. 제출 자료의 필수 항목 검사는 별도로 선언합니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="openworld"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 390" role="img" aria-labelledby="openworld-title openworld-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="openworld-title">제조사 기록의 결측과 현실의 존재는 다른 판단</title><desc id="openworld-desc">P1의 제조사 값이 없는 입력 그래프는 현실에 제조사가 없다는 뜻이 아니다. minCount 1은 이 입력을 위반으로 판정한다.</desc><defs><marker id="openworld-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="390" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">제조사 기록의 결측과 현실의 존재는 다른 판단</text>
<rect x="25" y="65" width="500" height="245" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="50" y="98" text-anchor="start" font-size="21" font-weight="600" fill="#142d49">현재 입력 그래프</text>
<rect x="50.0" y="146" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="140" y="182" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<path d="M230 175 L370 175" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#openworld-arrow)"/>
<text x="300.0" y="163.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">manufacturer</text>
<text x="435" y="182" text-anchor="middle" font-size="22" font-weight="400" fill="#142d49">값 없음</text>
<text x="275" y="270" text-anchor="middle" font-size="20" font-weight="400" fill="#52677f">제조사 트리플이 저장되지 않음</text>
<path d="M550 142 L630 142" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#openworld-arrow)"/>
<text x="660" y="115" text-anchor="start" font-size="22" font-weight="600" fill="#142d49">현실에 제조사가 있는가?</text>
<text x="660" y="153" text-anchor="start" font-size="21" font-weight="400" fill="#52677f">이 기록만으로는 알 수 없음</text>
<path d="M550 255 L630 255" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#openworld-arrow)"/>
<text x="660" y="228" text-anchor="start" font-size="22" font-weight="600" fill="#142d49">필수 기록 조건을 충족하는가?</text>
<text x="660" y="266" text-anchor="start" font-size="21" font-weight="400" fill="#245dc0">sh:minCount 1 → 위반</text>
<text x="28" y="370" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">OWL의 열린 세계 해석과 SHACL의 입력 그래프 검사를 구분한다.</text>
</svg>
</div>

<ul>
<li>OWL: 추가 근거가 없으면 제조사나 갱신 자격의 실제 존재 판단을 유보</li>
<li>SHACL: 제출된 기록에 필수 식별자가 없으면 <code>minCount</code> 위반</li>
</ul>
<p>출처: <a href="https://www.w3.org/TR/owl2-primer/">OWL 열린 세계 가정</a></p>

<details><summary>발표자 노트</summary>

<p>긍정 사실을 도출하지 못했다는 것과 부정 사실을 도출했다는 것은 다르다. 가상 공장 실험에서도 조회되지 않은 자격이나 일정 정보를 원본에 없는 것으로 단정하지 않도록 구분했다. SHACL로 제출 자료의 필수 값 누락을 검사하면서 업무 판정을 unknown으로 정하는 방식도 가능하다. 이는 애플리케이션 정책이다.</p>

</details>

## 14. 전체 조건·존재 조건·동일성

<blockquote>
<p>“모두 인증 부품”이라는 조건은 연결 대상의 존재를 보장하지 않습니다. 식별자 두 개도 서로 다른 실체 둘을 자동으로 뜻하지 않습니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="quantifiers"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 400" role="img" aria-labelledby="quantifiers-title quantifiers-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="quantifiers-title">모든 값의 타입 제한과 값의 존재 요구</title><desc id="quantifiers-desc">값이 없는 P1은 모든 제조사 값이 Manufacturer여야 한다는 보편 제한과 모순되지 않는다. 존재 제한은 이름 있는 제조사 트리플을 자동 생성하지 않는다.</desc><defs><marker id="quantifiers-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="400" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">모든 값의 타입 제한과 값의 존재 요구</text>
<rect x="20" y="60" width="525" height="260" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<rect x="575" y="60" width="525" height="260" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="282" y="96" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">∀ · owl:allValuesFrom</text>
<rect x="50.0" y="146" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="140" y="182" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<text x="365" y="180" text-anchor="middle" font-size="20" font-weight="400" fill="#52677f">연결된 값 없음</text>
<text x="282" y="250" text-anchor="middle" font-size="20" font-weight="400" fill="#52677f">값이 있다면 Manufacturer 타입</text>
<text x="282" y="285" text-anchor="middle" font-size="20" font-weight="400" fill="#245dc0">이 제한만으로 존재를 요구하지 않음</text>
<text x="838" y="96" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">∃ · owl:someValuesFrom</text>
<rect x="610.0" y="146" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="700" y="182" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<rect x="950.0" y="146" width="100" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="1000" y="182" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">?</text>
<path d="M790 175 L950 175" fill="none" stroke="#245dc0" stroke-width="2.5" stroke-dasharray="8 6" marker-end="url(#quantifiers-arrow)"/>
<text x="870.0" y="163.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">manufacturer</text>
<text x="838" y="250" text-anchor="middle" font-size="19" font-weight="400" fill="#52677f">해석상 Manufacturer 값이 하나 이상 존재</text>
<text x="838" y="285" text-anchor="middle" font-size="20" font-weight="400" fill="#245dc0">특정 IRI의 기록을 자동 생성하지 않음</text>
<text x="28" y="380" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">점선의 ?는 의미상 존재 요구를 나타낸다. 저장된 트리플이나 생성된 개체가 아니다.</text>
</svg>
</div>

<ul>
<li><code>allValuesFrom</code>: 연결된 대상이 있다면 지정 클래스에 속함</li>
<li><code>someValuesFrom</code>: 지정 클래스에 속한 대상의 존재를 요구</li>
<li>다른 개체임을 명시하려면 별도 동일성·차이 선언과 근거 검토</li>
</ul>
<p>출처: <a href="https://www.w3.org/TR/owl2-primer/">OWL 제약과 동일성</a></p>

<details><summary>발표자 노트</summary>

<p>모든 값 제한은 존재를 보장하지 않는다. 반면 존재 제한은 모델에서 어떤 대상이 존재해야 함을 뜻하지만 원본 파일에 이름 붙은 값을 채워 주는 입력 폼 검사가 아니다. 두 이름을 쓴 사실만으로 서로 다른 회사라고 확정하지 않으며 differentFrom 등 추가 선언이 필요할 수 있다.</p>

</details>

## 15. 추론으로 추가되는 조회 결과

<p><strong>추론을 쓰는 목적:</strong> 직접 입력하지 않은 결론도 정의를 따라 찾아내는 것</p>
<div class="seminar-view"><div class="columns"><section class="panel"><h3>기록과 정의</h3><p><b>입력 기록</b><br>P1은 볼트다.<br>P1은 조립품 A1에 장착된다.</p><hr><p><b>함께 제공한 정의</b><br>볼트 ⊆ 체결 부품 ⊆ 구성 부품<br>장착된다 ↔ 포함한다 (역관계)</p></section><section class="panel"><h3>추론 후 추가로 조회할 수 있는 결론</h3><p class="metric">P1은 구성 부품이다.</p><p class="metric">A1은 P1을 포함한다.</p><p>직접 적지 않은 타입과 역방향 관계를<br>입력과 정의를 결합해 계산한다.</p></section></div></div>

<ul>
<li>다음 장에서는 같은 입력에 RDFS·OWL-RL을 적용한 실제 조회 결과를 비교한다.</li>
</ul>

<details><summary>발표자 노트</summary>

<p>이 장은 구현 방법의 구분보다 추론의 용도를 설명한다. P1의 볼트 타입과 A1 장착 관계에 클래스 계층·역관계 정의를 적용하면 Component 타입과 hasPart 관계를 얻는다. 제조사처럼 전제가 없는 값을 새로 알아내는 것은 아니다. 원본 복사와 실행 코드는 공유 노트북에 두고 화면에서는 결과의 차이를 먼저 설명한다.</p>

</details>

## 16. 원본·RDFS·OWL-RL의 조회 결과

<blockquote>
<p>같은 입력이라도 적용한 정의와 조회 범위에 따라 보이는 결론이 달라집니다. 제조사 기록은 세 조건 모두 비어 있습니다.</p>
</blockquote>
<table><caption>저장된 조회 결과 · 없음은 현실의 거짓을 뜻하지 않음</caption><thead><tr><th scope="col">조회 결과</th><th scope="col">원본</th><th scope="col">RDFS</th><th scope="col">OWL-RL</th></tr></thead><tbody><tr><td>P1 a Component</td><td>없음</td><td>있음</td><td>있음</td></tr><tr><td>A1 a Assembly</td><td>없음</td><td>있음</td><td>있음</td></tr><tr><td>A1 hasPart P1</td><td>없음</td><td>없음</td><td>있음</td></tr><tr><td>제조사 기록</td><td>없음</td><td>없음</td><td>없음</td></tr></tbody></table>

<details><summary>발표자 노트</summary>

<p>이번 발표를 위해 작은 부품 그래프에 직접 기록만 조회하는 조건, RDFS 규칙 확장, OWL-RL 규칙 확장을 실행했다. 수치는 벤치마크가 아니라 교육 예제의 참·거짓 멤버십 검사다. true는 해당 그래프에서 트리플을 찾았다는 뜻이다. 원본 데이터와 스키마 및 세 결과 그래프는 자료 창의 manufacturing 관련 파일에서 볼 수 있다. 제조사를 알려 주는 전제가 없으므로 추론이 제조사를 만들어 채우지 않는다.</p>

</details>

## 17. 다단계 관계와 SKOS·OWL 구분

<blockquote>
<p>다단계 연결 계산은 도달 가능한 대상 쌍을 구하며 용어 분류(<code>skos:broader</code>)와 클래스 포함(<code>rdfs:subClassOf</code>)은 서로 다른 관계입니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="skos_owl"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 390" role="img" aria-labelledby="skos_owl-title skos_owl-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="skos_owl-title">개념 분류와 클래스 분류의 서로 다른 연결</title><desc id="skos_owl-desc">SKOS 개념 BoltConcept에서 FastenerConcept로 broader가 연결된다. OWL 클래스 Bolt에서 Fastener로 subClassOf가 연결되고 개체 P1은 Bolt 타입이다.</desc><defs><marker id="skos_owl-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="390" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">개념 분류와 클래스 분류의 서로 다른 연결</text>
<rect x="20" y="60" width="520" height="265" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<rect x="570" y="60" width="530" height="265" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="280" y="96" text-anchor="middle" font-size="22" font-weight="600" fill="#142d49">SKOS · 용어와 개념의 조직</text>
<rect x="55.0" y="146" width="220" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="165" y="182" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">BoltConcept</text>
<rect x="260.0" y="241" width="250" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="385" y="277" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">FastenerConcept</text>
<path d="M205 210 L285 242" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#skos_owl-arrow)"/>
<text x="380" y="223" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">skos:broader</text>
<text x="835" y="96" text-anchor="middle" font-size="22" font-weight="600" fill="#142d49">OWL / RDFS · 클래스와 개체</text>
<rect x="610.0" y="141" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="700" y="177" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Bolt</text>
<rect x="860.0" y="141" width="220" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="970" y="177" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Fastener</text>
<path d="M790 170 L860 170" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#skos_owl-arrow)"/>
<text x="825.0" y="158.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">⊆</text>
<rect x="610.0" y="241" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="700" y="277" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<path d="M700 240 L700 201" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#skos_owl-arrow)"/>
<text x="805" y="229" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">rdf:type</text>
<text x="28" y="370" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">skos:broader와 rdfs:subClassOf는 다른 의미다. broader 자체를 추이적 속성으로 읽지 않는다.</text>
</svg>
</div>

<ul>
<li>다단계 도달: <code>(P1, A1), (A1, PRODUCT_X)</code>에서 <code>(P1, PRODUCT_X)</code> 도출</li>
<li>모델링 역할 구분: SKOS는 용어·분류 체계 연결, OWL/RDFS는 개체 타입과 논리 관계 정의</li>
</ul>
<p>출처: <a href="https://www.w3.org/TR/skos-primer/">SKOS Primer</a> · <a href="https://www.w3.org/TR/owl2-primer/">OWL 2 Primer</a></p>

<details><summary>발표자 노트</summary>

<p>여러 관계를 합쳐 도달 가능한 대상 쌍을 계산하는 작업과 용어·클래스 계층을 정의하는 작업은 구분해야 한다. skos:broader는 rdfs:subClassOf와 같지 않고 그 자체로 전이 속성도 아니다. SKOS 개념을 특정 OWL 클래스에 대응시키려면 별도 매핑을 정의해야 한다.</p>

</details>

## 18. SHACL의 입력과 검사 결과

<blockquote>
<p>SHACL 통과는 선언한 조건의 충족입니다. 기록된 정보가 현실에서 참이라는 인증은 아닙니다.</p>
</blockquote><div class="flow story-flow" data-flow="shaclconcept"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 200" role="img" aria-labelledby="shaclconcept-title shaclconcept-desc" font-family="Pretendard, sans-serif"><title id="shaclconcept-title">데이터 그래프와 Shape의 검사</title><desc id="shaclconcept-desc">데이터 그래프와 Shape의 검사</desc><defs><marker id="shaclconcept-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6.0" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24.0" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><ellipse cx="24" cy="10" rx="16" ry="6"/><path d="M8 10v27c0 8 32 8 32 0V10M8 23c0 8 32 8 32 0"/></svg><text x="74.0" y="51" font-size="21" fill="#14212f" font-weight="700">Data Graph</text><text x="26.0" y="89" font-size="18" fill="#465970">P1의 장착·제조사 기록</text><text x="26.0" y="114" font-size="18" fill="#465970">검사할 데이터</text></g><path d="M360.3333333333333 95H378.3333333333333" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#shaclconcept-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="385.3333333333333" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="403.3333333333333" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="10" y="5" width="28" height="38" rx="3"/><path d="m15 16 3 3 5-6M26 16h6m-17 11 3 3 5-6M26 27h6"/></svg><text x="453.3333333333333" y="51" font-size="21" fill="#14212f" font-weight="700">Shapes Graph</text><text x="405.3333333333333" y="89" font-size="18" fill="#465970">P1의 제조사는 필수</text><text x="405.3333333333333" y="114" font-size="18" fill="#465970">값은 IRI 식별자</text></g><path d="M739.6666666666666 95H757.6666666666666" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#shaclconcept-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="764.6666666666666" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="782.6666666666666" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="24" r="19"/><path d="m14 24 7 7 14-16"/></svg><text x="832.6666666666666" y="51" font-size="21" fill="#14212f" font-weight="700">Validation Report</text><text x="784.6666666666666" y="89" font-size="18" fill="#465970">conforms와 위반 목록</text><text x="784.6666666666666" y="114" font-size="18" fill="#465970">어느 노드·어느 조건인가</text></g></svg></div>

<p><strong>SHACL</strong>: Shapes Constraint Language. <strong>Shape</strong>: 검사 대상과 조건을 묶은 구조.</p>
<ul>
<li>Data Graph: 검사할 부품·설비 기록</li>
<li>Shapes Graph: “필수 식별자와 적용 범위 조건이 기록돼야 한다”</li>
<li>Validation Report: 어떤 개체·속성이 어떤 조건을 어겼는지 구조화해 기록</li>
</ul>

<p>출처: <a href="https://www.w3.org/TR/shacl/">SHACL</a></p>

<details><summary>발표자 노트</summary>

<p>SHACL Shape 역시 RDF로 표현한다. 그림은 사람의 규정 문장을 조건으로 명시하고 데이터에 적용하는 흐름이다. 전체 세계가 닫혀 있다고 선언하는 것보다는 주어진 그래프를 정해진 검사 대상으로 삼는다고 설명하는 편이 정확하다. 필수 값이 없는 것은 minCount 위반이며 이 결과를 거부나 보류로 해석하는 것은 애플리케이션 정책이다.</p>

</details>

## 19. 업무 문장의 Shape 변환

<blockquote>
<p>Shape 작성은 요구 문장을 검사 대상·속성·개수·값 종류로 나누는 과정입니다. 뜻이 맞는지는 정상·위반·결측 반례로 확인합니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="shapebuild"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 380" role="img" aria-labelledby="shapebuild-title shapebuild-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="shapebuild-title">문장의 각 조건을 Shape 속성에 대응</title><desc id="shapebuild-desc">P1은 제조사를 하나 이상 IRI로 기록한다는 문장을 targetNode, path, minCount, nodeKind에 대응한다. targetClass나 다른 개수 제한은 요구가 다를 때 선택한다.</desc><defs><marker id="shapebuild-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="380" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">문장의 각 조건을 Shape 속성에 대응</text>
<text x="145" y="102" text-anchor="middle" font-size="27" font-weight="600" fill="#142d49">P1은</text>
<path d="M50 115 H240" stroke="#245dc0" stroke-width="3"/>
<path d="M145 128 L145 185" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#shapebuild-arrow)"/>
<rect x="20" y="197" width="250" height="82" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="145" y="228" text-anchor="middle" font-size="22" font-weight="600" fill="#245dc0">sh:targetNode</text>
<text x="145" y="260" text-anchor="middle" font-size="21" font-weight="400" fill="#142d49">ex:P1</text>
<text x="420" y="102" text-anchor="middle" font-size="27" font-weight="600" fill="#142d49">제조사를</text>
<path d="M325 115 H515" stroke="#245dc0" stroke-width="3"/>
<path d="M420 128 L420 185" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#shapebuild-arrow)"/>
<rect x="295" y="197" width="250" height="82" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="420" y="228" text-anchor="middle" font-size="22" font-weight="600" fill="#245dc0">sh:path</text>
<text x="420" y="260" text-anchor="middle" font-size="21" font-weight="400" fill="#142d49">ex:manufacturer</text>
<text x="700" y="102" text-anchor="middle" font-size="27" font-weight="600" fill="#142d49">하나 이상</text>
<path d="M605 115 H795" stroke="#245dc0" stroke-width="3"/>
<path d="M700 128 L700 185" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#shapebuild-arrow)"/>
<rect x="575" y="197" width="250" height="82" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="700" y="228" text-anchor="middle" font-size="22" font-weight="600" fill="#245dc0">sh:minCount</text>
<text x="700" y="260" text-anchor="middle" font-size="21" font-weight="400" fill="#142d49">1</text>
<text x="975" y="102" text-anchor="middle" font-size="27" font-weight="600" fill="#142d49">IRI로 기록</text>
<path d="M880 115 H1070" stroke="#245dc0" stroke-width="3"/>
<path d="M975 128 L975 185" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#shapebuild-arrow)"/>
<rect x="850" y="197" width="250" height="82" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="975" y="228" text-anchor="middle" font-size="22" font-weight="600" fill="#245dc0">sh:nodeKind</text>
<text x="975" y="260" text-anchor="middle" font-size="21" font-weight="400" fill="#142d49">sh:IRI</text>
<text x="560" y="323" text-anchor="middle" font-size="19" font-weight="400" fill="#52677f">대상 선택: targetNode / targetClass   ·   개수 조건: minCount / maxCount</text>
<text x="28" y="360" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">Shape는 요구사항을 명시한다. 검사 통과가 제조사의 실제 존재나 정확성을 증명하지는 않는다.</text>
</svg>
</div>

<ul>
<li><code>targetNode</code>는 특정 개체, <code>targetClass</code>는 클래스의 대상 개체를 선택</li>
<li>문법이 맞는 Shape도 잘못된 업무 조건을 검사할 수 있으므로 반례 점검이 필수</li>
</ul>

<details><summary>발표자 노트</summary>

<p>Shape를 작성할 때는 도구 선택에 앞서 요구사항을 명확히 한다. 검사 대상, 속성, 자료형·개수·범위, 결측 처리와 적용 버전을 먼저 정한다. 자동 생성된 Shape가 문법 검사를 통과해도 순금액 대신 총금액을 검사하거나 불필요한 조건을 넣을 수 있으므로 정상·위반·결측·무관 변형 사례를 함께 확인한다.</p>

</details>

## 20. 노트북 실습 — 데이터와 Shape 준비

<ul>
<li>P1의 기록과 제조사 필수 조건을 각각 RDF 그래프로 읽는다.</li>
</ul>
<div class="seminar-notebook"><div class="nb-bar"><span>manufacturing-shacl.ipynb · Python 3</span><span>저장된 실행 결과 재생</span></div><div class="nb-grid"><section class="nb-cell"><div class="nb-cell-head"><span>In [2]</span><span>data</span></div><pre class="nb-code"><code>DATA = &quot;&quot;&quot;ex:P1 a ex:Bolt ;
    ex:installedIn ex:A1 .&quot;&quot;&quot;
data = Graph().parse(data=PREFIX + DATA, format=&quot;turtle&quot;)
print(f&quot;데이터: {len(data)}개 트리플&quot;)</code></pre><div class="nb-output" id="nb-data"><span class="nb-out-label">Out [2]</span><pre>데이터: 2개 트리플</pre></div></section><section class="nb-cell"><div class="nb-cell-head"><span>In [3]</span><span>shape</span></div><pre class="nb-code"><code>SHAPE = &quot;&quot;&quot;ex:ManufacturerShape a sh:NodeShape ;
    # 이 검사는 P1의 제조사 기록만 확인한다.
    sh:targetNode ex:P1 ;
    sh:property [
        sh:path ex:manufacturer ;
        # 값이 하나 이상이고 IRI인지 검사한다.
        sh:minCount 1 ;
        sh:nodeKind sh:IRI ;
        sh:message &quot;제조사 식별자를 하나 이상 기록하세요.&quot;
    ] .&quot;&quot;&quot;
shapes = Graph().parse(data=PREFIX + SHAPE, format=&quot;turtle&quot;)
print(f&quot;Shape: {len(shapes)}개 트리플&quot;)</code></pre><div class="nb-output" id="nb-shape"><span class="nb-out-label">Out [3]</span><pre>Shape: 7개 트리플</pre></div></section></div><div class="nb-caption">▶ 셀의 실제 저장 출력 표시 <a href="../seminar/notebooks/manufacturing-shacl.ipynb">실습 노트북 다운로드</a></div></div>

<details><summary>발표자 노트</summary>

<p>실행한 공유용 manufacturing-shacl.ipynb의 data와 shape 셀을 그대로 보여 준다. 위쪽 설정 셀에서 Graph와 PREFIX를 준비했다. ▶는 Python을 브라우저에서 실행하지 않고 이미 실행한 셀 출력을 표시한다. 노트북은 데이터와 Shape를 포함하므로 저장소 파일 없이 위에서부터 실행할 수 있다. 인쇄와 정적 안내문에서는 출력이 처음부터 보인다.</p>

</details>

## 21. 노트북 실습 — 검사와 보고서 확인

<ul>
<li><code>conforms</code>는 조건 충족 여부, <code>report</code>는 위반 근거, <code>report_text</code>는 텍스트 보고서다.</li>
</ul>
<div class="seminar-notebook"><div class="nb-bar"><span>manufacturing-shacl.ipynb · Python 3</span><span>저장된 실행 결과 재생</span></div><div class="nb-grid"><section class="nb-cell"><div class="nb-cell-head"><span>In [4]</span><span>validate</span></div><pre class="nb-code"><code>conforms, report, report_text = validate(
    data, shacl_graph=shapes, inference=&quot;none&quot;)
print(&quot;conforms =&quot;, bool(conforms))</code></pre><div class="nb-output" id="nb-validate"><span class="nb-out-label">Out [4]</span><pre>conforms = False</pre></div></section><section class="nb-cell"><div class="nb-cell-head"><span>In [5]</span><span>report</span></div><pre class="nb-code"><code>for result in report.subjects(RDF.type, SH.ValidationResult):
    print(&quot;대상:&quot;, report.value(result, SH.focusNode).n3(data.namespace_manager))
    print(&quot;속성:&quot;, report.value(result, SH.resultPath).n3(data.namespace_manager))
    print(&quot;조건:&quot;, str(report.value(result, SH.sourceConstraintComponent)).split(&quot;#&quot;)[-1])
    print(&quot;메시지:&quot;, report.value(result, SH.resultMessage))</code></pre><div class="nb-output" id="nb-report"><span class="nb-out-label">Out [5]</span><pre>대상: ex:P1
속성: ex:manufacturer
조건: MinCountConstraintComponent
메시지: 제조사 식별자를 하나 이상 기록하세요.</pre></div></section></div><div class="nb-caption">▶ 셀의 실제 저장 출력 표시 <a href="../seminar/notebooks/manufacturing-shacl.ipynb">실습 노트북 다운로드</a></div></div>

<details><summary>발표자 노트</summary>

<p>실행한 노트북의 validate와 report 셀이다. report는 앞 셀에서 계산한 RDF 그래프이며 다음 셀에서 검사 대상, 속성, 조건과 메시지를 읽는다. HTML은 각 셀의 저장된 출력을 독립적으로 보여 준다. 실제 노트북에서는 위에서부터 순서대로 실행한다. 전체 텍스트·Turtle 보고서, 제조사 추가 후 재검사, 간단한 OWL-RL 추론 예제도 노트북에 포함했다. False는 지정 조건의 불충족이며 현실의 사실이 거짓이라는 뜻은 아니다.</p>

</details>

## 22. LLM 도구 설계의 명시적 계약

<blockquote>
<p>미리 만든 쿼리를 LLM이 선택하는 구조에서는 도구마다 반환 범위와 후속 확인 조건을 계약으로 선언해 프롬프트 속 숨은 가정을 시스템 구성요소로 옮길 수 있습니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns">
  <section class="panel">
    <h3>도구 계약 선언 · <code>replacement_candidates(order_id)</code></h3>
    <div class="annotation">
      “이 도구는 요구 역량(<code>CAP-CUT</code>)을 갖춘 <b>기능적 후보 설비</b>만 반환한다. 자격이나 일정 여유까지 확인하지 않으므로 다음 판단에는 별도 자격 조회(<code>qualification_records</code>)가 필요하다.”
    </div>
    <table>
      <thead><tr><th>도구 이름</th><th>반환하는 근거</th><th>단독으로 확정할 수 없는 것</th></tr></thead>
      <tbody>
        <tr><td><code>replacement_candidates</code></td><td>요구 역량을 갖춘 설비 후보</td><td>제품별 유효 자격 · 실제 일정 여유</td></tr>
        <tr><td><code>qualification_records</code></td><td>설비의 자격 코드·제품·유효기간</td><td>작업장 부하 · 납기 준수 · 현장 승인</td></tr>
        <tr><td><code>impacted_orders</code></td><td>특정 설비에 배정된 주문 목록</td><td>대체 설비의 적격 여부</td></tr>
      </tbody>
    </table>
  </section>
  <section class="panel">
    <h3>온톨로지 · SHACL · 검사기의 역할 분담</h3>
    <div class="annotation"><strong>온톨로지 (개념 정렬):</strong> 도구가 반환하는 <code>Machine</code>, <code>Capability</code>, <code>Qualification</code>의 관계와 상태 정의를 통일</div>
    <div class="annotation"><strong>SHACL (입력 근거 검사):</strong> 최종 판단 전에 선택된 후보에 대해 제품·역량·기준일 자격 근거가 실제로 조회됐는지 확인</div>
    <div class="annotation"><strong>명시적 한계:</strong> LLM이 질문을 잘못 해석했거나 엉뚱한 도구를 선택한 문제까지 검사기가 자동으로 해결하지는 못함</div>
    <p class="small">출처: <code>apps/factory_lab/graph.py</code> · <code>docs/journal/2026-11-10-factory-query-tools-and-branches.md</code></p>
  </section>
</div></div>

<ul>
<li>온톨로지는 개념을 정렬하고 SHACL은 입력 조건 충족을 검사하되 도구 오선택·질문 오해석까지 해결하지는 못함</li>
</ul>

<details><summary>발표자 노트</summary>

<p>미리 작성한 쿼리 템플릿을 LLM이 선택하는 구조에서는 도구마다 무엇을 반환하고 무엇을 확인하지 않는지 선언해 둘 수 있다. 예를 들어 replacement_candidates는 기능적 후보만 반환하며 자격이나 일정까지 확인하지 않으므로 별도 자격 조회가 필요하다. 온톨로지는 도구들이 사용하는 개념을 맞추고 SHACL은 반환된 근거가 정해진 입력 조건을 갖췄는지 검사한다. 다만 LLM이 도구를 잘못 골랐거나 질문을 잘못 해석한 문제까지 검사기가 해결하지는 못한다.</p>

</details>

## 23. 사람이 검토할 구조화된 근거 기록

<blockquote>
<p>최종 답변이 “M03은 안 됩니다”로 끝나는 것과 판단 대상·적용 조건·확인 기록·구체적 사유·규칙 버전을 구조화해 남기는 것은 다릅니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns">
  <section class="panel">
    <h3>단순 자연어 거절 vs 구조화된 검토 기록</h3>
    <div class="annotation"><strong>단순 답변:</strong> “M03은 안 됩니다.” → 왜 안 되는지, 어떤 기록을 봤는지, 규정 변경 시 다시 봐야 하는지 알 수 없음</div>
    <div class="screen">
      <div class="screen-bar"><span>구조화된 검토 기록 (O18 · M03 사례)</span><span class="badge">별도 보존</span></div>
      <table>
        <tbody>
          <tr><th scope="row">판단 대상</th><td>주문 <code>O18</code>(<code>P-B</code>)에 대한 대체 후보 <code>M03</code></td></tr>
          <tr><th scope="row">적용 조건</th><td>단일 자격 내 제품(<code>P-B</code>)·역량(<code>CAP-CUT</code>)·유효기간 충족</td></tr>
          <tr><th scope="row">확인한 기록</th><td><code>Q03</code>(만료), <code>Q03R</code>(<code>P-A</code> 전용 · 2026-11-09 기준 유효)</td></tr>
          <tr><th scope="row">구체적 문제</th><td>자격 기록은 있으나 제품 범위 불일치 (<code>qualification-not-applicable</code>)</td></tr>
          <tr><th scope="row">데이터·규칙 버전</th><td>데이터 스냅샷 <code>factory-v3</code> · 자격 정책 계약 <code>v1</code></td></tr>
        </tbody>
      </table>
    </div>
  </section>
  <section class="panel">
    <h3>이번 실험에서 드러난 보존 필요성</h3>
    <p>가상 공장 갱신 실험(<code>factory-renewal-live</code>)에서 LLM 최종 자연어 요약은 후보별 설명과 요약표에서 <b>자격 범위 불일치(<code>not-applicable</code>)</b>와 <b>자격 미조회(<code>not-retrieved</code>)</b>를 섞어 표현했다.</p>
    <table>
      <thead><tr><th>활용 장면</th><th>구조화된 기록이 하는 역할</th></tr></thead>
      <tbody>
        <tr><td>이의 제기 · 감사</td><td>어떤 근거 ID(<code>Q03</code>, <code>Q03R</code>)로 배정을 보류했는지 즉시 대조</td></tr>
        <tr><td>오류 재현 · 디버깅</td><td>조회 누락인지 자격 불일치인지 자연어 환각 없이 분리</td></tr>
        <tr><td>담당자 인계</td><td>품질팀에 <code>P-B</code> 추가 인증 여부를 물을지 명확히 전달</td></tr>
        <tr><td>정책·데이터 변경</td><td>새 자격 <code>Q03R</code> 추가 시 <code>O17</code>만 해소되고 <code>O18</code>은 유지됨을 추적</td></tr>
      </tbody>
    </table>
    <p class="small">출처: <code>docs/experiments/records/2026-11-10-factory-renewal-live.json</code></p>
  </section>
</div></div>

<ul>
<li>최종 자연어가 사유(<code>not-applicable</code> vs <code>not-retrieved</code>)를 혼용해도 구조화 기록을 별도 보존해 감사·오류 재현·인계·재검토에 활용</li>
</ul>

<details><summary>발표자 노트</summary>

<p>최종 답변이 M03은 안 됩니다로 끝나는 것과 판단 대상, 적용한 조건, 확인한 기록, 구체적 문제, 사용한 데이터와 규칙 버전을 함께 남기는 것은 다르다. 가상 공장 실험에서 Q03R이 제품 P-A에만 유효하고 O18의 P-B에는 적용되지 않는 상황일 때 최종 자연어 요약이 자격 범위 불일치와 자격 미조회를 섞어 표현하는 사례가 관찰됐다. 이 때문에 오히려 구조화된 검토 기록을 자연어 답변과 별도로 보존할 필요가 드러났다.</p>

</details>

## 24. 저장소 변경 시 의미를 유지하는 기준

<blockquote>
<p>Neo4j와 RDF 저장소는 표현과 쿼리가 달라도 “같은 후보·같은 근거·같은 조건”을 반환해야 비교가 가능합니다. 공통 의미 모델은 이때 기준점이 됩니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns">
  <section class="panel">
    <h3>저장소·표현이 달라도 같은 기준 유지</h3>
    <p>Neo4j(Cypher)와 RDF 저장소(SPARQL)는 내부 구조와 질의어가 다르므로 <b>같은 후보·근거·조건</b>을 반환하는 공통 의미 모델이 비교 기준이 된다.</p>
    <table>
      <thead><tr><th>실험 범위</th><th>비교 대상</th><th>관측 결과</th></tr></thead>
      <tbody>
        <tr><td>가상 공장 도구 대조</td><td>Neo4j Cypher vs RDFLib SPARQL (3버전 × 16호출)</td><td><b>48쌍 조회 100% 일치</b> · 6개 묶음 플래그 일치</td></tr>
        <tr><td>기본 그래프 패턴</td><td>SQL/Python · RDFLib · Neo4j · Neptune</td><td>실행된 36개 슬롯 모두 고정 참조값과 일치</td></tr>
        <tr><td>계층 추론·삭제·복원</td><td>Python · 외부 RDFS · Neo4j+n10s · Neptune</td><td>갱신 조건 32/32 일치 · 미갱신 불일치 4건 포착</td></tr>
      </tbody>
    </table>
  </section>
  <section class="panel">
    <h3>변경 후 재검토 범위를 좁히는 질문 계약</h3>
    <p>데이터·규칙 변경 후 전체 묶음 해시만 비교하면 답이 같은 결과에도 경고가 붙는다. 선언한 질문 대상·연결 경로 해시를 쓰면 불일치 8건은 유지한 채 경고를 줄인다.</p>
    <table>
      <thead><tr><th>확인 범위 정책 (160개 결과 재검사)</th><th>전체 경고</th><th>실제 불일치 포착</th><th>일치 결과에 붙은 경고</th></tr></thead>
      <tbody>
        <tr><td>전체 묶음 해시 비교</td><td>32</td><td>8 / 8</td><td>24</td></tr>
        <tr><td>선언한 질문 유형별 범위</td><td>20</td><td>8 / 8</td><td>12</td></tr>
        <tr><td>선언한 조회 대상·연결 경로</td><td><b>10</b></td><td><b>8 / 8</b></td><td><b>2</b></td></tr>
      </tbody>
    </table>
    <p class="small">작은 증거: 기준 구현·확인 가능성 입증 · 가상 공장 48쌍의 Neptune 실증이나 유지보수 비용 절감을 뜻하지는 않음</p>
  </section>
</div></div>

<ul>
<li>가상 공장 <strong>48쌍</strong> 조회 일치 및 백엔드 변경 실험 검토 범위 축소(<code>32 → 20 → 10</code>) 확인 (<a href="https://github.com/shinysong/shacl-graphrag/blob/35dfc7ab1d3a0790c86bfe5922faf6cf7cfef9fc/docs/journal/2026-11-06-backend-inference-review.md">백엔드 검토 일지</a> · <a href="https://github.com/shinysong/shacl-graphrag/blob/35dfc7ab1d3a0790c86bfe5922faf6cf7cfef9fc/docs/experiments/records/2026-11-10-factory-rdf-parity.json">가상 공장 대조 기록</a>)</li>
</ul>

<details><summary>발표자 노트</summary>

<p>Neo4j와 RDF 저장소는 표현과 쿼리가 달라도 같은 후보, 같은 근거, 같은 조건을 반환해야 비교가 가능하다. 공통 의미 모델은 이때 기준점이 된다. 가상 공장 로컬 비교에서는 정해진 48쌍의 조회 결과가 일치했고 Python과 SHACL 검토기도 6개 근거 묶음 모두에서 같은 플래그를 냈다. 별도 백엔드 실험에서는 Neo4j+n10s와 Neptune+외부 RDFS의 계층 추론 및 삭제·복원 후 재검토 범위를 확인했다. 이는 기준을 구현하고 확인할 수 있다는 작은 증거일 뿐 가상 공장 48쌍의 Neptune 실증이나 유지보수 비용 절감을 입증한 것은 아니다.</p>

</details>

## 25. 도입 판단 기준과 연구의 의의

<blockquote>
<p>지금 연구의 방향은 “온톨로지를 쓰면 LLM이 더 똑똑해진다”보다 “LLM이 사용하는 근거와 판단 조건을 명시하고 공유하며 변경과 오류를 추적할 수 있게 한다”입니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns">
  <section class="panel">
    <h3>언제 Python과 타입 스키마로 충분한가?</h3>
    <div class="callout">
      <b>서비스 하나 · 데이터 출처 하나 · 규칙 몇 개가 안정적으로 유지되는 상황</b>이라면 공유 Python 라이브러리와 타입 스키마로 끝내는 편이 더 단순하다. RDF·OWL·SHACL 도입에는 모델링·매핑·버전 관리라는 새로운 부담이 따른다.
    </div>
    <h3>도입 시점을 판단하는 네 가지 질문 (데이터 건수보다 중요)</h3>
    <table>
      <tbody>
        <tr><th scope="row">1. 의미 중복</th><td>같은 업무 의미를 여러 팀·서비스가 반복해서 정의하고 있는가?</td></tr>
        <tr><th scope="row">2. 변경 위치</th><td>자격·정책 규칙이 바뀔 때 수정할 위치를 찾기 어려운가?</td></tr>
        <tr><th scope="row">3. 감사·설명</th><td>판단의 근거와 적용한 규칙 버전을 나중에 설명해야 하는가?</td></tr>
        <tr><th scope="row">4. 저장소 전환</th><td>출처나 저장소(Neo4j · RDF · SQL)가 달라도 같은 해석을 유지해야 하는가?</td></tr>
      </tbody>
    </table>
  </section>
  <section class="panel">
    <h3>연구의 핵심 방향과 검증 분리</h3>
    <div class="annotation"><strong>지양하는 주장:</strong> “온톨로지를 쓰면 LLM이 저절로 더 똑똑해진다.”</div>
    <div class="annotation"><strong>설득력 있는 방향:</strong> “LLM이 사용하는 근거와 판단 조건을 명시하고 공유하며, 변경과 오류를 추적할 수 있게 한다.”</div>
    <table>
      <thead><tr><th>검증 축</th><th>무엇을 어떻게 보여줄 것인가</th></tr></thead>
      <tbody>
        <tr><td>답변 품질 개선</td><td>다중 후보·조건 변경 등 특정 상황에서 구조화된 보고서가 가져오는 효과로 검증</td></tr>
        <tr><td>구조 자체의 장점</td><td>규칙 재사용 · 변경 시 재검토 범위 축소 · 판단 근거 추적 가능성으로 별도 입증</td></tr>
      </tbody>
    </table>
  </section>
</div></div>

<ul>
<li>답변 개선은 특정 상황에서 가져올 수 있는 효과로 검증하고 구조 자체의 장점은 <strong>재사용·변경 절차·추적 가능성</strong>으로 따로 평가</li>
</ul>

<details><summary>발표자 노트</summary>

<p>서비스 하나, 데이터 출처 하나, 규칙 몇 개가 안정적으로 유지되는 상황이라면 Python과 타입 스키마로 끝내는 편이 더 단순할 수 있다. RDF·OWL·SHACL을 도입하면 모델링, 매핑, 버전 관리라는 새로운 부담도 생긴다. 도입 시점은 데이터 건수보다 같은 의미를 여러 팀·서비스가 반복 정의하는지, 규칙 변경 때 수정 위치를 찾기 어려운지, 판단 근거와 규칙 버전을 나중에 설명해야 하는지, 출처나 저장소가 달라도 같은 해석을 유지해야 하는지로 판단하는 것이 좋다.</p>

</details>
