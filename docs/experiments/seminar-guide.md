# LLM 판단을 돕는 의미·추론·검증 — 세미나 자료

[45장 HTML 발표 열기](seminar/index.html) · [45장 PDF](seminar/seminar.pdf)

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

## 01. 소속 변경과 발주 승인

<blockquote>
<p>업무 설명용 합성 시나리오입니다. 판정과 함께 적용한 규칙, 사용한 근거, 재검토 대상을 제시하는 것이 목표입니다.</p>
</blockquote><p><strong>“검토자의 소속 본부가 바뀌었습니다. 이 발주를 그대로 승인해도 되나요?”</strong></p>
<div class="flow story-flow" data-flow="question"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 200" role="img" aria-labelledby="question-title question-desc" font-family="Pretendard, sans-serif"><title id="question-title">구매·승인·감사 담당자의 질문</title><desc id="question-desc">구매 담당자는 진행 여부를 묻고 승인 담당자는 조건을 확인하며 감사 담당자는 근거와 버전을 확인한다.</desc><defs><marker id="question-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6.0" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24.0" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="12" r="7"/><path d="M10 43v-7c0-10 28-10 28 0v7M18 43v-9M30 43v-9"/></svg><text x="74.0" y="51" font-size="21" fill="#14212f" font-weight="700">구매 담당자</text><text x="26.0" y="89" font-size="18" fill="#465970">검토자 소속이 바뀌었는데</text><text x="26.0" y="114" font-size="18" fill="#465970">이 발주를 진행해도 될까?</text></g><path d="M360.3333333333333 95H378.3333333333333" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#question-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="385.3333333333333" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="403.3333333333333" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="12" r="7"/><path d="M10 43v-7c0-10 28-10 28 0v7M18 43v-9M30 43v-9"/></svg><text x="453.3333333333333" y="51" font-size="21" fill="#14212f" font-weight="700">승인 담당자</text><text x="405.3333333333333" y="89" font-size="18" fill="#465970">자격과 소속 관계에</text><text x="405.3333333333333" y="114" font-size="18" fill="#465970">바뀐 규정도 적용됐을까?</text></g><path d="M739.6666666666666 95H757.6666666666666" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#question-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="764.6666666666666" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="782.6666666666666" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="12" r="7"/><path d="M10 43v-7c0-10 28-10 28 0v7M18 43v-9M30 43v-9"/></svg><text x="832.6666666666666" y="51" font-size="21" fill="#14212f" font-weight="700">감사 담당자</text><text x="784.6666666666666" y="89" font-size="18" fill="#465970">어떤 기록과 규정 버전으로</text><text x="784.6666666666666" y="114" font-size="18" fill="#465970">그렇게 판단했을까?</text></g></svg></div>



<details><summary>발표자 노트</summary>

<p>구매 담당자의 실제 업무에서 나올 법한 질문으로 시작한다. 실기업에서 수집한 질문이나 운영 효과를 측정한 사례는 아니며 기존 발주·조직·검토자 합성 스키마를 설명하기 위해 만든 시나리오다. 소속 변경 전후를 추적하는 운영 시스템이 완성됐다는 뜻도 아니다. 뒤의 예제는 본부 충돌 입력으로 실행한다. 변경 후 상태에 해당하는 한 시점의 입력이다. 구매 담당자는 진행 가능 여부를, 승인 담당자는 규정 적용을, 감사 담당자는 판단 근거와 버전을 확인하려 한다. 이 요구에서 출발해 데이터의 의미와 규칙을 시스템 사이에서 공유하는 방식을 살펴본다.</p>

</details>

## 02. 발표 구성

<div class="flow story-flow" data-flow="learning"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 200" role="img" aria-labelledby="learning-title learning-desc" font-family="Pretendard, sans-serif"><title id="learning-title">업무 질문에서 연구 설계까지</title><desc id="learning-desc">업무 질문에서 연구 설계까지</desc><defs><marker id="learning-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6.0" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24.0" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="12" r="7"/><path d="M10 43v-7c0-10 28-10 28 0v7M18 43v-9M30 43v-9"/></svg><text x="74.0" y="51" font-size="21" fill="#14212f" font-weight="700">업무의 질문</text><text x="26.0" y="89" font-size="18" fill="#465970">왜 이 판단이 필요한가</text><text x="26.0" y="114" font-size="18" fill="#465970">어떤 근거를 설명해야 하나</text></g><path d="M360.3333333333333 95H378.3333333333333" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#learning-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="385.3333333333333" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="403.3333333333333" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="10" r="5"/><circle cx="36" cy="24" r="5"/><circle cx="12" cy="38" r="5"/><path d="m16 13 16 9m0 5-16 9M12 15v18"/></svg><text x="453.3333333333333" y="51" font-size="21" fill="#14212f" font-weight="700">작은 부품 예제</text><text x="405.3333333333333" y="89" font-size="18" fill="#465970">표현 → 추론 → 검사</text><text x="405.3333333333333" y="114" font-size="18" fill="#465970">각 도구의 역할 구분</text></g><path d="M739.6666666666666 95H757.6666666666666" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#learning-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="764.6666666666666" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="782.6666666666666" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="10" y="5" width="28" height="38" rx="3"/><path d="m15 16 3 3 5-6M26 16h6m-17 11 3 3 5-6M26 27h6"/></svg><text x="832.6666666666666" y="51" font-size="21" fill="#14212f" font-weight="700">우리 연구의 설계</text><text x="784.6666666666666" y="89" font-size="18" fill="#465970">기존 결과와 남은 질문</text><text x="784.6666666666666" y="114" font-size="18" fill="#465970">공정한 비교와 사례 구성</text></g></svg></div>

<ul>
<li><strong>업무 질문:</strong> 판단에 필요한 데이터와 의미</li>
<li><strong>제조 부품 예제:</strong> 표현·추론·검증의 차이</li>
<li><strong>연구 결과:</strong> 검사한 입력·조건·출력</li>
<li><strong>후속 설계:</strong> 실제 자료의 한계와 데모 화면</li>
</ul>

<details><summary>발표자 노트</summary>

<p>첨부 발표자료의 짧은 설명과 도식 중심 구성을 참고했다. 기술의 전체 목록을 소개하기보다 부품 하나를 끝까지 따라가며 입력, 정의, 추론, 검사, 사실 확인의 차이를 익힌다. 이후 발주 예제와 부품 인증 질문으로 돌아온다. 사용자가 제공한 영상 요약의 개념은 공식 표준과 대조했지만 원영상이나 자막 시각은 확인하지 않았으므로 영상 인용으로 제시하지 않는다. HTML은 외부 네트워크 없이 재생되며 자료 창에 코드와 실제 출력이 들어 있다.</p>

</details>

## 03. 데이터의 의미·연결·시점

<blockquote>
<p><strong>근거</strong>는 판단에 사용한 기록이고 <strong>시맨틱</strong>은 그 기록의 뜻과 관계입니다. 같은 status라도 계약·승인·자격에서 의미가 다릅니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="evidence"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 400" role="img" aria-labelledby="evidence-title evidence-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="evidence-title">시스템별 상태값을 키와 시점으로 연결</title><desc id="evidence-desc">합성 예시다. ERP 부품 상태 Approved, 계약 상태 Active, 검토자 상태 Qualified는 각각 의미가 다르다. 키로 연결하고 부서 변경 이력의 날짜를 확인해야 한다.</desc><defs><marker id="evidence-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="400" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">시스템별 상태값을 키와 시점으로 연결</text>
<text x="1090" y="32" text-anchor="end" font-size="18" font-weight="400" fill="#52677f">설명용 합성 예시 · 실제 스냅샷 아님</text>
<rect x="20" y="62" width="330" height="175" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="36" y="93" text-anchor="start" font-size="22" font-weight="600" fill="#142d49">ERP · 부품</text>
<text x="36" y="130" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">part_id</text>
<text x="334" y="130" text-anchor="end" font-size="20" font-weight="400" fill="#245dc0">P1</text>
<text x="36" y="166" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">status</text>
<text x="334" y="166" text-anchor="end" font-size="20" font-weight="400" fill="#245dc0">Approved</text>
<text x="36" y="202" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">contract_id</text>
<text x="334" y="202" text-anchor="end" font-size="20" font-weight="400" fill="#245dc0">C7</text>
<rect x="395" y="62" width="330" height="175" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="411" y="93" text-anchor="start" font-size="22" font-weight="600" fill="#142d49">계약 시스템</text>
<text x="411" y="130" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">contract_id</text>
<text x="709" y="130" text-anchor="end" font-size="20" font-weight="400" fill="#245dc0">C7</text>
<text x="411" y="166" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">status</text>
<text x="709" y="166" text-anchor="end" font-size="20" font-weight="400" fill="#245dc0">Active</text>
<text x="411" y="202" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">reviewer_id</text>
<text x="709" y="202" text-anchor="end" font-size="20" font-weight="400" fill="#245dc0">R2</text>
<rect x="770" y="62" width="330" height="175" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="786" y="93" text-anchor="start" font-size="22" font-weight="600" fill="#142d49">검토자 명부</text>
<text x="786" y="130" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">reviewer_id</text>
<text x="1084" y="130" text-anchor="end" font-size="20" font-weight="400" fill="#245dc0">R2</text>
<text x="786" y="166" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">status</text>
<text x="1084" y="166" text-anchor="end" font-size="20" font-weight="400" fill="#245dc0">Qualified</text>
<text x="786" y="202" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">division</text>
<text x="1084" y="202" text-anchor="end" font-size="20" font-weight="400" fill="#245dc0">품질팀</text>
<path d="M350 201 L395 201" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#evidence-arrow)"/>
<path d="M725 201 L770 201" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#evidence-arrow)"/>
<text x="560" y="269" text-anchor="middle" font-size="21" font-weight="600" fill="#142d49">같은 status 열 이름 ≠ 같은 판단 기준</text>
<rect x="20" y="288" width="1080" height="77" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="40" y="318" text-anchor="start" font-size="20" font-weight="600" fill="#142d49">R2 부서 이력</text>
<text x="265" y="318" text-anchor="start" font-size="20" font-weight="400" fill="#52677f">2025-01-01 · 구매팀 (old)</text>
<path d="M620 315 L700 315" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#evidence-arrow)"/>
<text x="730" y="318" text-anchor="start" font-size="20" font-weight="400" fill="#245dc0">2025-07-01 · 품질팀 (new)</text>
<text x="40" y="349" text-anchor="start" font-size="19" font-weight="400" fill="#52677f">질문 기준일에 맞는 상태와 소속을 선택해야 한다.</text>
</svg>
</div>

<ul>
<li>키로 연결: 부품 P1 → 계약 C7 → 검토자 R2 → 소속 이력</li>
<li>시점 확인: 승인 당시 소속과 현재 소속이 다르면 어느 규칙을 적용할지 결정</li>
</ul>
<p>설명용 합성 레코드 · 이력은 개념 예시이며 실제 실행 입력은 한 시점의 스냅샷</p>

<details><summary>발표자 노트</summary>

<p>세 시스템에서 승인·조직·정책 정보를 가져와도 바로 결론을 내릴 수는 없다. 같은 status라는 이름도 계약 유효 상태, 검토 결정, 사람의 자격 상태를 가리킬 수 있다. 값의 단위, 식별자 대응, 관계의 방향, 유효 시점을 계약으로 정해야 한다. 근거에는 출처와 시점도 필요하지만 이번 작은 실행 예제가 시간에 따른 변경 이력이나 근거 최신성까지 검증한 것은 아니다. semantic을 어려운 추상 개념 대신 데이터 항목의 뜻과 연결 규칙으로 소개한다. RDF로 변환하는 것만으로 이 의미가 자동 결정되지는 않는다.</p>

</details>

## 04. 규칙 변경의 담당자와 요구사항

<blockquote>
<p>기존 Python·SQL·룰 엔진·DAG로도 구현할 수 있습니다. 연구의 관심은 변경된 의미와 규칙을 여러 소비처에 일관되게 전달하는 방법입니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="change"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 380" role="img" aria-labelledby="change-title change-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="change-title">담당자별로 다른 변경 판단 근거</title><desc id="change-desc">정책 담당자가 의미와 적용 범위를 정하고 개발 담당자가 매핑과 검사를 수정하며 운영 담당자가 적용 버전과 소비처를 확인한다.</desc><defs><marker id="change-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="380" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">담당자별로 다른 변경 판단 근거</text>
<circle cx="65" cy="81" r="13" fill="#d9e7fb" stroke="#245dc0"/><path d="M42 119 Q42 97 65 97 Q88 97 88 119" fill="#d9e7fb" stroke="#245dc0" stroke-width="2"/>
<text x="110" y="104" text-anchor="start" font-size="23" font-weight="600" fill="#142d49">정책 담당자</text>
<path d="M280 98 L390 98" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#change-arrow)"/>
<text x="425" y="91" text-anchor="start" font-size="23" font-weight="600" fill="#142d49">변경할 의미와 적용 범위</text>
<text x="425" y="123" text-anchor="start" font-size="20" font-weight="400" fill="#52677f">본부 분리 조건 · 적용 시점 · 예외</text>
<circle cx="65" cy="185" r="13" fill="#d9e7fb" stroke="#245dc0"/><path d="M42 223 Q42 201 65 201 Q88 201 88 223" fill="#d9e7fb" stroke="#245dc0" stroke-width="2"/>
<text x="110" y="208" text-anchor="start" font-size="23" font-weight="600" fill="#142d49">개발 담당자</text>
<path d="M280 202 L390 202" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#change-arrow)"/>
<text x="425" y="195" text-anchor="start" font-size="23" font-weight="600" fill="#142d49">스키마·매핑·검사의 변경</text>
<text x="425" y="227" text-anchor="start" font-size="20" font-weight="400" fill="#52677f">관계 경로 · Shape · 반례와 회귀 검사</text>
<circle cx="65" cy="289" r="13" fill="#d9e7fb" stroke="#245dc0"/><path d="M42 327 Q42 305 65 305 Q88 305 88 327" fill="#d9e7fb" stroke="#245dc0" stroke-width="2"/>
<text x="110" y="312" text-anchor="start" font-size="23" font-weight="600" fill="#142d49">운영 담당자</text>
<path d="M280 306 L390 306" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#change-arrow)"/>
<text x="425" y="299" text-anchor="start" font-size="23" font-weight="600" fill="#142d49">버전 배포와 영향 대상 확인</text>
<text x="425" y="331" text-anchor="start" font-size="20" font-weight="400" fill="#52677f">소비 시스템 · 적용 버전 · 재검토 요청</text>
</svg>
</div>

<ul>
<li>공유 JSON·스키마 레지스트리·공통 라이브러리도 비교 대상</li>
<li>표준 형식 도입만으로 변경 비용과 배포 문제가 사라지지는 않음</li>
</ul>

<details><summary>발표자 노트</summary>

<p>기존 시스템이 이 일을 할 수 없어서 연구를 시작한 것은 아니다. SQL 조인이나 Python 함수, 룰 엔진, DAG 기반 파이프라인으로 같은 결정을 구현할 수 있다. 규칙이 바뀔 때 그 의미를 어디에서 관리하고 어떤 시스템에 변경을 반영해야 하는지 추적하는 문제에 관심을 둔다. DAG는 실행 순서와 의존성을 표현하는 데 쓸 수 있고 노드에 공유 규칙을 연결할 수도 있다. 따라서 DAG와 의미 계층은 배타적인 대안이 아니다. 시스템별 복제만을 기존 방식의 필연적 한계로 설정하지 않는다. 사람의 변경 작업 시간, 자연 발생 배포 오류율, 표준 도입의 장기 비용 절감은 이번 자료에서 측정하지 않았다.</p>

</details>

## 05. 공유 의미와 검사 계약

<blockquote>
<p>연구 의도는 의미와 검사 조건을 공통 자산으로 관리하는 것입니다. 매핑, 버전 배포, 접근 제어와 회귀 테스트는 별도로 구현해야 합니다.</p>
</blockquote><div class="flow story-flow" data-flow="shared"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 265" role="img" aria-labelledby="shared-title shared-desc" font-family="Pretendard, sans-serif"><title id="shared-title">하나의 의미·검사 계약을 여러 시스템에서 사용</title><desc id="shared-desc">목표 구조. 기존 데이터 원본과 업무 실행 시스템은 유지하면서 공통 계약을 연결한다. 자동 배포 기능이나 측정된 운영 효과를 뜻하지 않는다.</desc><defs><marker id="shared-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="230" y="5" width="660" height="108" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="248" y="20" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="10" r="5"/><circle cx="36" cy="24" r="5"/><circle cx="12" cy="38" r="5"/><path d="m16 13 16 9m0 5-16 9M12 15v18"/></svg><text x="298" y="46" font-size="21" fill="#14212f" font-weight="700">공유 의미·검사 계약</text><text x="250" y="84" font-size="18" fill="#465970">식별자 · 관계 · OWL 공리 · SHACL Shape · 버전</text></g><path d="M560 113V130H180V147" stroke="#879bb6" fill="none" stroke-width="1.8" marker-end="url(#shared-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="6" y="152" width="348" height="103" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24" y="167" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="7" width="38" height="27" rx="3"/><path d="M24 34v8M14 42h20M12 15h24M12 22h15"/></svg><text x="74" y="193" font-size="21" fill="#14212f" font-weight="700">발주 서비스</text><text x="26" y="231" font-size="18" fill="#465970">필요한 데이터 투영</text></g><path d="M560 113V130H560V147" stroke="#879bb6" fill="none" stroke-width="1.8" marker-end="url(#shared-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="386" y="152" width="348" height="103" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="404" y="167" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="7" width="38" height="27" rx="3"/><path d="M24 34v8M14 42h20M12 15h24M12 22h15"/></svg><text x="454" y="193" font-size="21" fill="#14212f" font-weight="700">승인 워크플로</text><text x="406" y="231" font-size="18" fill="#465970">조회·판정·예외 처리</text></g><path d="M560 113V130H940V147" stroke="#879bb6" fill="none" stroke-width="1.8" marker-end="url(#shared-arrow)"/><g class="step story-step" data-step="3"><rect class="story-box" x="766" y="152" width="348" height="103" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="784" y="167" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="7" width="38" height="27" rx="3"/><path d="M24 34v8M14 42h20M12 15h24M12 22h15"/></svg><text x="834" y="193" font-size="21" fill="#14212f" font-weight="700">감사 서비스</text><text x="786" y="231" font-size="18" fill="#465970">근거·적용 버전 확인</text></g></svg></div>

<table>
<thead>
<tr>
<th>구성</th>
<th>공유하려는 내용</th>
</tr>
</thead>
<tbody>
<tr>
<td>RDF</td>
<td>개체의 식별자와 관계 표현</td>
</tr>
<tr>
<td>OWL</td>
<td>클래스·관계의 공리와 함의의 기준</td>
</tr>
<tr>
<td>SHACL / Shape</td>
<td>검사 대상과 조건을 담은 규칙 구조</td>
</tr>
<tr>
<td>pySHACL</td>
<td>Shape를 실행해 표준 검증 보고서 생성</td>
</tr>
</tbody>
</table>

<p>출처: <a href="https://www.w3.org/TR/rdf11-primer/">RDF</a> · <a href="https://www.w3.org/TR/owl2-primer/">OWL</a> · <a href="https://www.w3.org/TR/shacl/">SHACL</a> · <a href="https://github.com/RDFLib/pySHACL">pySHACL</a></p>

<details><summary>발표자 노트</summary>

<p>그림은 지향하는 공유 구조이며 실제 세 시스템을 배포해 유지보수 개선을 측정한 결과가 아니다. 데이터 원본을 모두 RDF 저장소로 옮길 필요 없이 필요한 부분만 공통 식별자와 관계로 투영할 수 있다. OWL로 클래스와 관계의 논리 의미를 선언하고 SHACL Shape로 업무 검사 조건을 표현한다. 특정 애플리케이션 안에만 숨기지 않고 검토·교환 가능한 형태로 두려 한다. 이식성은 사용하는 언어 기능, 추론 프로파일, 엔진 지원을 확인해야 한다. 공통 JSON이나 라이브러리도 공유할 수 있으므로 표준 형식이라는 이유만으로 더 우수하다고 결론 내리지 않는다. RDF는 데이터 모델이고 Turtle은 표기 형식이다. OWL 추론과 SHACL 검증은 별개이며 통합 진단은 OWL-RL을 실행하지 않는다.</p>

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
<p>언어·정의와 실행 도구를 구분합니다. 파일을 읽는 것만으로 추론이 켜지지는 않습니다.</p>
</blockquote><table>
<thead>
<tr>
<th>구성</th>
<th>역할</th>
<th>부품 P1 예</th>
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
<td>볼트는 부품, 부품은 구성 부품</td>
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
<td>제조사 식별자가 기록됐는가</td>
</tr>
</tbody>
</table>

<p>출처: <a href="https://www.w3.org/TR/rdf11-primer/">RDF</a> · <a href="https://www.w3.org/TR/rdf-schema/">RDFS</a> · <a href="https://www.w3.org/TR/owl2-primer/">OWL</a> · <a href="https://www.w3.org/TR/shacl/">SHACL</a></p>

<details><summary>발표자 노트</summary>

<p>온톨로지와 지식 그래프를 구분한다. 클래스와 속성의 의미를 정한 정의를 바탕으로 구체적 개체의 기록을 연결한다. RDFS와 OWL의 정의도 RDF로 표현할 수 있다. 추론기는 이런 언어의 일부 또는 프로파일을 지원하는 소프트웨어다. pySHACL은 Python에서 SHACL을 실행하는 도구이며 추론 옵션도 제공하지만 추론과 검증은 서로 다른 단계다.</p>

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

<p>사용자가 제공한 자막 요약에서 지적한 개체·클래스 혼동을 개념 수준에서 바로잡았다. 원영상의 특정 시점이 실제로 어떤 표현을 썼는지는 확인하지 않았다. 이 발표에서 P1은 개별 부품이고 Bolt와 Fastener는 클래스다. 고급 OWL 모델링에서 한 IRI를 여러 역할로 쓰는 기능은 이 입문 예제의 범위 밖이다.</p>

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

<p>예를 들어 장비와 사람이 뒤바뀐 관계를 넣어도 domain과 range만으로 잘못된 입력이라고 차단하지 않는다. 관계에 따라 타입이 붙는다. 별도로 배타적인 클래스 공리를 선언했고 같은 개체가 양쪽에 속하게 되면 논리 충돌이 생길 수 있다. RDFS 자체에는 OWL의 배타 클래스 공리가 없다는 점도 구분한다. 입력 단계에서 기대 타입을 확인하려면 명시적인 검증 정책이 필요하다.</p>

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
<p>제조사 기록이 없다는 사실만으로 제조사가 존재하지 않는다고 결론 내릴 수 없습니다. 제출 자료의 필수 항목 검사는 별도로 선언합니다.</p>
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
<li>OWL: 추가 근거가 없으면 제조사에 대한 판단을 유보</li>
<li>SHACL: 제출된 P1 기록에 제조사 IRI가 없으면 <code>minCount</code> 위반</li>
</ul>
<p>출처: <a href="https://www.w3.org/TR/owl2-primer/">OWL 열린 세계 가정</a></p>

<details><summary>발표자 노트</summary>

<p>긍정 사실을 도출하지 못했다는 것과 부정 사실을 도출했다는 것은 다르다. 별도 공리나 명시적 부정으로 결론을 낼 수 있는 경우는 이 설명에서 제외한다. 여기서는 그런 추가 정보가 없는 상황을 설명한다. SHACL로 제출 자료의 필수 값 누락을 검사하면서 업무 판정을 unknown으로 정하는 방식도 가능하다. 이는 애플리케이션 정책이다.</p>

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
<li>다른 회사임을 명시하려면 별도 동일성·차이 선언과 근거 검토</li>
</ul>
<p>출처: <a href="https://www.w3.org/TR/owl2-primer/">OWL 제약과 동일성</a></p>

<details><summary>발표자 노트</summary>

<p>모든 값 제한은 존재를 보장하지 않는다. 반면 존재 제한은 모델에서 어떤 대상이 존재해야 함을 뜻하지만 원본 파일에 이름 붙은 값을 채워 주는 입력 폼 검사가 아니다. 두 이름을 쓴 사실만으로 서로 다른 회사라고 확정하지 않으며 differentFrom 등 추가 선언이 필요할 수 있다. SHACL은 선택한 그래프에서 속성 경로의 값 노드를 세므로 동일성 추론을 사전에 적용할지에 따라서도 정책을 정해야 한다.</p>

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

## 17. 조회 실패와 현실의 거짓

<blockquote>
<p>단순 ASK의 false는 선택한 그래프에서 해당 패턴을 찾지 못했다는 뜻입니다. 현실에서 거짓이라는 판정과 구분합니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="querymeaning"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 350" role="img" aria-labelledby="querymeaning-title querymeaning-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="querymeaning-title">ASK 결과는 선택한 그래프의 패턴 일치 여부</title><desc id="querymeaning-desc">ASK P1 a Component는 원본에서는 false, 타입 추론으로 확장한 그래프에서는 true다. 현실의 사실 확인과는 별개다.</desc><defs><marker id="querymeaning-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="350" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">ASK 결과는 선택한 그래프의 패턴 일치 여부</text>
<rect x="160" y="65" width="800" height="50" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="560" y="98" text-anchor="middle" font-size="24" font-weight="400" fill="#245dc0">ASK { ex:P1 a ex:Component }</text>
<rect x="100.0" y="156" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="190" y="192" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<rect x="475.0" y="156" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="565" y="192" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Bolt</text>
<rect x="840.0" y="156" width="230" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="955" y="192" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:Component</text>
<path d="M280 185 L475 185" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#querymeaning-arrow)"/>
<text x="377.5" y="173.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">rdf:type</text>
<path d="M655 185 L840 185" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#querymeaning-arrow)"/>
<text x="747.5" y="173.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">하위 클래스 연결</text>
<text x="280" y="275" text-anchor="middle" font-size="20" font-weight="400" fill="#52677f">원본: 해당 타입 트리플 없음 → false</text>
<text x="815" y="275" text-anchor="middle" font-size="20" font-weight="400" fill="#245dc0">확장: 해당 타입 트리플 도출 → true</text>
<text x="28" y="330" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">false는 현실의 거짓이 아니다. true도 외부 사실 검증을 대신하지 않는다.</text>
</svg>
</div>

<pre><code class="language-sparql">ASK { ex:P1 a ex:Component }  # P1의 Component 타입이 조회되는가
</code></pre>
<ul>
<li>원본 false → 확장본 true: 새 사실을 외부에서 확인한 것이 아니라 정의를 적용한 결과</li>
</ul>

<details><summary>발표자 노트</summary>

<p>SPARQL ASK는 질의 패턴이 활성 그래프와 적용된 entailment regime에서 해를 갖는지 반환한다. 여기서는 직접 트리플 멤버십과 동등한 단일 패턴을 설명한다. 명시적 부정이나 추가 공리를 이용하는 다른 논리 판단까지 같은 설명으로 뭉뚱그리지 않는다. 원본 조회 결과와 추론 그래프의 조회 결과가 달라져도 원본 파일이 저절로 수정된 것은 아니다.</p>

</details>

## 18. 다단계 관계의 고정점 계산

<blockquote>
<p>여러 관계를 합쳐 도달 가능한 대상 쌍을 계산합니다. 가능한 모든 경로를 나열하는 작업과는 다릅니다.</p>
</blockquote>
<div class="flow story-flow" data-flow="reachability"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 360" role="img" aria-labelledby="reachability-title reachability-desc" font-family="Pretendard, Noto Sans KR, sans-serif"><title id="reachability-title">경로 탐색은 연결된 시작점 · 끝점 쌍을 반환</title><desc id="reachability-desc">P1에서 A1을 거쳐 PRODUCT_X에 도달한다. SPARQL 속성 경로의 결과는 시작점과 끝점 쌍이며 경로 자체가 아니다.</desc><defs><marker id="reachability-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#245dc0" stroke-width="1.5"/></marker></defs><rect width="1120" height="360" rx="12" fill="white"/>
<text x="26" y="32" text-anchor="start" font-size="22" font-weight="700" fill="#142d49">경로 탐색은 연결된 시작점 · 끝점 쌍을 반환</text>
<rect x="70.0" y="116" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="160" y="152" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:P1</text>
<rect x="470.0" y="116" width="180" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="560" y="152" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:A1</text>
<rect x="835.0" y="116" width="250" height="58" rx="9" fill="#f4f8fd" stroke="#c7d5e5" stroke-width="1.5"/>
<text x="960" y="152" text-anchor="middle" font-size="23" font-weight="600" fill="#142d49">ex:PRODUCT_X</text>
<path d="M250 145 L470 145" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#reachability-arrow)"/>
<text x="360.0" y="133.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">ex:installedIn</text>
<path d="M650 145 L835 145" fill="none" stroke="#245dc0" stroke-width="2.5" marker-end="url(#reachability-arrow)"/>
<text x="742.5" y="133.0" text-anchor="middle" font-size="19" font-weight="400" fill="#245dc0">ex:installedIn</text>
<path d="M160 176 V245 H960 V176" fill="none" stroke="#245dc0" stroke-width="2.5" stroke-dasharray="8 6" marker-end="url(#reachability-arrow)"/>
<text x="560" y="231" text-anchor="middle" font-size="21" font-weight="400" fill="#245dc0">ex:installedIn+ · 한 번 이상 연결</text>
<text x="28" y="340" text-anchor="start" font-size="18" font-weight="400" fill="#52677f">반환 예: (P1, A1), (P1, PRODUCT_X) · 통과한 노드 목록이나 경로 수를 뜻하지 않는다.</text>
</svg>
</div>

<pre><code class="language-text">edge(P1, A1), edge(A1, PRODUCT_X)
reach(X, Y) ← edge(X, Y)                  # 직접 연결도 도달
reach(X, Z) ← reach(X, Y), edge(Y, Z)     # 도달 관계를 연장
</code></pre>
<ul>
<li>실제 Python 집합 계산의 추가 결과: <code>(P1, PRODUCT_X)</code></li>
</ul>

<details><summary>발표자 노트</summary>

<p>규칙은 설명용 Datalog식 표기다. 실제 제조 교육용 실행은 동일한 양의 관계를 Python 집합으로 고정점까지 계산했다. 별도 Datalog 엔진을 실행한 것은 아니다. 이 결과 자체로 재검토 의무나 제품 안전성을 결정하지 않는다. 원천 관계와 적용 정책은 별도로 검토한다.</p>

</details>

## 19. SKOS 용어 분류와 OWL 클래스

<blockquote>
<p>용어집의 상하 개념, 클래스 포함 관계, 개체의 타입은 서로 다른 관계입니다. 같은 “볼트”라는 말도 모델링 역할을 구분합니다.</p>
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
<li>SKOS: 용어·라벨·분류 체계의 연결</li>
<li>OWL/RDFS: 개체가 어떤 클래스에 속하는지와 논리적 관계 정의</li>
</ul>
<p>출처: <a href="https://www.w3.org/TR/skos-primer/">SKOS Primer</a> · <a href="https://www.w3.org/TR/skos-reference/">SKOS Reference</a></p>

<details><summary>발표자 노트</summary>

<p>이 그림은 직접 작성한 제조 용어 예시이며 표준 제조 온톨로지를 수입한 결과가 아니다. skos:broader는 rdfs:subClassOf와 같지 않고 자체가 전이 속성으로 선언되어 있지도 않다. 계층 탐색의 전이 관계는 broaderTransitive와 구분한다. SKOS 개념을 특정 OWL 클래스에 대응시키려면 별도 매핑을 정의해야 한다.</p>

</details>

## 20. SHACL의 입력과 검사 결과

<blockquote>
<p>SHACL 통과는 선언한 조건의 충족입니다. 제조사 정보가 현실에서 참이라는 인증은 아닙니다.</p>
</blockquote><div class="flow story-flow" data-flow="shaclconcept"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 200" role="img" aria-labelledby="shaclconcept-title shaclconcept-desc" font-family="Pretendard, sans-serif"><title id="shaclconcept-title">데이터 그래프와 Shape의 검사</title><desc id="shaclconcept-desc">데이터 그래프와 Shape의 검사</desc><defs><marker id="shaclconcept-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6.0" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24.0" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><ellipse cx="24" cy="10" rx="16" ry="6"/><path d="M8 10v27c0 8 32 8 32 0V10M8 23c0 8 32 8 32 0"/></svg><text x="74.0" y="51" font-size="21" fill="#14212f" font-weight="700">Data Graph</text><text x="26.0" y="89" font-size="18" fill="#465970">P1의 장착·제조사 기록</text><text x="26.0" y="114" font-size="18" fill="#465970">검사할 데이터</text></g><path d="M360.3333333333333 95H378.3333333333333" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#shaclconcept-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="385.3333333333333" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="403.3333333333333" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="10" y="5" width="28" height="38" rx="3"/><path d="m15 16 3 3 5-6M26 16h6m-17 11 3 3 5-6M26 27h6"/></svg><text x="453.3333333333333" y="51" font-size="21" fill="#14212f" font-weight="700">Shapes Graph</text><text x="405.3333333333333" y="89" font-size="18" fill="#465970">P1의 제조사는 필수</text><text x="405.3333333333333" y="114" font-size="18" fill="#465970">값은 IRI 식별자</text></g><path d="M739.6666666666666 95H757.6666666666666" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#shaclconcept-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="764.6666666666666" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="782.6666666666666" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="24" r="19"/><path d="m14 24 7 7 14-16"/></svg><text x="832.6666666666666" y="51" font-size="21" fill="#14212f" font-weight="700">Validation Report</text><text x="784.6666666666666" y="89" font-size="18" fill="#465970">conforms와 위반 목록</text><text x="784.6666666666666" y="114" font-size="18" fill="#465970">어느 노드·어느 조건인가</text></g></svg></div>

<p><strong>SHACL</strong>: Shapes Constraint Language. <strong>Shape</strong>: 검사 대상과 조건을 묶은 구조.</p>
<ul>
<li>Data Graph: 검사할 부품 기록</li>
<li>Shapes Graph: “P1에 제조사 IRI가 하나 이상 있어야 한다”</li>
<li>Validation Report: 어떤 개체·속성이 어떤 조건을 어겼는지 기록</li>
</ul>

<p>출처: <a href="https://www.w3.org/TR/shacl/">SHACL</a></p>

<details><summary>발표자 노트</summary>

<p>SHACL Shape 역시 RDF로 표현한다. 그림은 사람의 규정 문장을 조건으로 명시하고 데이터에 적용하는 흐름이다. 전체 세계가 닫혀 있다고 선언하는 것보다는 주어진 그래프를 정해진 검사 대상으로 삼는다고 설명하는 편이 정확하다. 필수 값이 없는 것은 minCount 위반이며 이 결과를 거부나 보류로 해석하는 것은 애플리케이션 정책이다.</p>

</details>

## 21. 업무 문장의 Shape 변환

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
<li>문법이 맞는 Shape도 잘못된 업무 조건을 검사할 수 있음</li>
</ul>

<details><summary>발표자 노트</summary>

<p>Shape를 작성할 때는 도구 선택에 앞서 요구사항을 명확히 한다. 검사 대상, 속성, 자료형·개수·범위, 결측 처리와 적용 버전을 먼저 정한다. targetClass로 클래스 전체를 대상으로 삼을 수도 있다. 자동 생성된 Shape가 문법 검사를 통과해도 순금액 대신 총금액을 검사하거나 불필요한 조건을 넣을 수 있으므로 정상·위반·결측·무관 변형 사례를 함께 확인한다. LLM이 만든 초안을 실행 전 정답으로 수리하는 실험을 뜻하지 않는다.</p>

</details>

## 22. LLM으로 RDF·Shape 초안 작성

<div class="seminar-view"><div class="columns"><div class="screen"><div class="screen-bar">① 문서와 요구 조건을 프롬프트로 전달</div><section class="panel"><h3>입력</h3><p>문서: “볼트 P1은 조립품 A1에 장착된다.”</p><p>업무 조건: “P1의 제조사를 IRI로 하나 이상 기록해야 한다.”</p><h3>프롬프트 예시</h3><p>문서의 사실을 <code>data.ttl</code>로, 업무 조건을 SHACL 문법의 <code>shapes.ttl</code>로 작성해 줘.</p><p>타입은 <code>Bolt</code>, 관계는 <code>installedIn</code>과 <code>manufacturer</code>를 사용해. 제조사 값은 문서에 없으니 data에는 추가하지 마.</p></section></div><div class="screen"><div class="screen-bar">② RDF와 Shape 초안 · 기대 출력 예시</div><pre><code># data.ttl
ex:P1 a ex:Bolt ;
  ex:installedIn ex:A1 .

# shapes.ttl
ex:ManufacturerShape a sh:NodeShape ;
  sh:targetNode ex:P1 ;
  sh:property [
    sh:path ex:manufacturer ;
    sh:minCount 1 ;
    sh:nodeKind sh:IRI
  ] .</code></pre><p>③ 파일 저장 → RDF 파싱 → pySHACL 실행<br>다음 실습에서 이 데이터와 조건을 직접 검사한다.</p></div></div><p class="small">발표자가 작성한 대화·출력 예시 · 실제 LLM 호출 아님 · 접두사는 실습 노트북에 포함</p></div>

<details><summary>발표자 노트</summary>

<p>LLM으로 지식 그래프의 사실 데이터와 검사 조건을 함께 초안 작성하는 방법을 소개한다. 입력 문서와 별도 업무 요구를 나눠 제공하고 data.ttl과 shapes.ttl을 각각 요청한다. 제조사 필수 조건은 문서에서 추측한 것이 아니라 사용자가 명시한 업무 조건이다. 문서에 제조사가 없으므로 RDF에는 제조사 값을 넣지 않지만 Shape에는 필수 조건을 담는다. 화면의 대화와 출력은 발표자가 만든 예시이며 실제 LLM 측정 결과가 아니다. 접두사 생략은 화면 공간을 위한 것이며 노트북에는 완전한 정의가 있다.</p>

</details>

## 23. 직접 스키마 작성과 표 데이터 변환

<blockquote>
<p>클래스·속성·IRI를 먼저 정하고 원천의 열을 그 정의에 연결합니다. 편집 도구·변환 도구·검증 도구의 역할을 나누면 작업을 재현하기 쉽습니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns"><section class="panel"><h3>스키마 먼저 · 편집 작업의 개념도</h3><div class="screen"><div class="screen-bar">클래스 계층 / 속성 / 개체</div><pre><code>Component
└─ Fastener
   └─ Bolt

installedIn: Component → Assembly
P1: Bolt → installedIn → A1</code></pre></div><p>Protégé / WebProtégé에서 클래스·속성·공리를 편집하고 저장한다.</p></section><section class="panel"><h3>행 데이터에서 그래프까지</h3><table><thead><tr><th>작업</th><th>도구·산출물</th></tr></thead><tbody><tr><td>CSV 정리·ID 맞추기</td><td>OpenRefine</td></tr><tr><td>열 → IRI·관계 매핑</td><td>RDF Transform 확장</td></tr><tr><td>반복 가능한 변환</td><td>Python + RDFLib</td></tr><tr><td>RDF·Shape 직접 작성</td><td>텍스트 편집기 + Turtle</td></tr><tr><td>조건 검사</td><td>pySHACL + 보고서</td></tr></tbody></table><p>UI는 기능 설명용 재구성이다. 설치·실행 캡처가 아니며 RDF 확장 호환성은 확인해야 한다.</p></section></div></div>

<p>출처: <a href="https://protege.stanford.edu/software/">Protégé / WebProtégé</a> · <a href="https://openrefine.org/extensions">OpenRefine 확장 목록</a> · <a href="https://rdflib.readthedocs.io/">RDFLib</a></p>

<details><summary>발표자 노트</summary>

<p>공식 문서를 확인해 대표적인 도구의 역할을 소개했다. 인기 순위 비교나 사용자 점유율 주장은 아니다. Protégé와 WebProtégé는 OWL 편집을 지원한다. SHACL 조건은 별도 파일·지원 도구로 작성하고 pySHACL로 실행할 수 있다. OpenRefine의 RDF 출력은 확장 기능이며 본체만 설치하면 자동 제공된다고 설명하지 않는다. 이번 발표를 위해 이 도구들을 설치하거나 운영한 것은 아니다.</p>

</details>

## 24. 노트북 실습 — 데이터와 Shape 준비

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

## 25. 노트북 실습 — 검사와 보고서 확인

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

## 26. 제조사 입력별 검사 결과

<blockquote>
<p>네 번째 입력의 제조사 IRI도 형식·개수 조건은 통과합니다. <strong>그 회사가 실제 제조사인지는 확인하지 않았습니다.</strong></p>
</blockquote><table><caption>저장된 제조사 Shape 검사 · 네 입력</caption><thead><tr><th scope="col">입력</th><th scope="col">conforms</th><th scope="col">위반 조건</th><th scope="col">현실의 사실 확인</th></tr></thead><tbody><tr><td>ex:P1 ex:manufacturer ex:MakerA .</td><td>true</td><td>없음</td><td>미확인</td></tr><tr><td>(제조사 기록 없음)</td><td>false</td><td>MinCountConstraintComponent</td><td>미확인</td></tr><tr><td>ex:P1 ex:manufacturer &quot;MakerA&quot; .</td><td>false</td><td>NodeKindConstraintComponent</td><td>미확인</td></tr><tr><td>ex:P1 ex:manufacturer ex:UnverifiedMaker .</td><td>true</td><td>없음</td><td>미확인</td></tr></tbody></table>

<details><summary>발표자 노트</summary>

<p>부품의 기본 데이터에 제조사 IRI를 넣은 사례, 제조사 값이 없는 사례, IRI 대신 문자열을 넣은 사례, 확인되지 않은 다른 IRI를 넣은 사례를 실제 실행했다. 마지막 IRI에 대해서는 외부 사실 확인을 하지 않았다. 실제로 틀렸는지도 검증하지 않았다. 이 예제로 conformance와 외부 사실의 참을 구분한다. 브라우저 버튼은 저장된 pySHACL 결과를 보여 주며 새 실행이나 실제 API 호출을 하지 않는다.</p>

</details>

## 27. 검사 범위와 추론 설정

<blockquote>
<p>두 검사에서 제조사 기록 부재는 남습니다. 이 예제는 <code>sh:class</code> 대신 명시적 타입 값의 존재를 검사해 입력 범위 차이를 보여 줍니다.</p>
</blockquote><table><caption>저장된 두 Shape 검사 · 모든 호출은 inference=none</caption><thead><tr><th scope="col">검사 대상</th><th scope="col">Component 타입</th><th scope="col">제조사</th><th scope="col">위반 수</th></tr></thead><tbody><tr><td>원본</td><td>미충족</td><td>미충족</td><td>2</td></tr><tr><td>RDFS 확장</td><td>충족</td><td>미충족</td><td>1</td></tr><tr><td>OWL-RL 확장</td><td>충족</td><td>미충족</td><td>1</td></tr></tbody></table>

<pre><code class="language-turtle"># 두 번째 Shape: Component 타입 트리플이 실제로 있어야 함
sh:path rdf:type ; sh:hasValue ex:Component .
</code></pre>


<details><summary>발표자 노트</summary>

<p>동일한 두 Shape를 원본, RDFS 확장본, OWL-RL 확장본에 적용했다. 제조사 minCount와 rdf:type 경로의 hasValue Component를 검사한다. 원본에서는 둘 다 위반하고 확장본에서는 제조사만 위반한다. SHACL의 class 검사는 데이터 그래프의 하위 클래스 관계도 반영할 수 있으므로 sh:class가 무조건 원본에서 실패한다고 설명하지 않는다. 또한 추론으로 검사 대상 클래스가 늘거나 값 개수가 달라질 수 있으므로 검사 범위를 실행 전에 정해야 한다.</p>

</details>

## 28. 발주·승인·조직의 연결 키

<blockquote>
<p>테이블 이름보다 연결 키를 먼저 봅니다. 이 예제는 요청 부서와 검토자 부서가 같은 본부로 연결되는 합성 입력입니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns compact"><section class="panel"><h3>① 발주</h3><table><thead><tr><th>request_id</th><th>item_id</th><th>req_dept_id</th></tr></thead><tbody><tr><td>REQ_2026_01</td><td>ITEM_101</td><td>DEPT_REQ</td></tr></tbody></table></section><section class="panel"><h3>② 승인 기록</h3><table><thead><tr><th>request_id</th><th>reviewer_id</th><th>review_role</th></tr></thead><tbody><tr><td>REQ_2026_01</td><td>USER_PRIMARY</td><td>Primary</td></tr><tr><td>REQ_2026_01</td><td>USER_AUDIT</td><td>Audit</td></tr></tbody></table></section><section class="panel"><h3>③ 검토자</h3><table><thead><tr><th>reviewer_id</th><th>belongs_to_dept_id</th><th>qualification_status</th></tr></thead><tbody><tr><td>USER_PRIMARY</td><td>DEPT_REV1</td><td>Qualified</td></tr><tr><td>USER_AUDIT</td><td>DEPT_REV2</td><td>Qualified</td></tr></tbody></table></section><section class="panel"><h3>④ 조직</h3><table><thead><tr><th>dept_id</th><th>parent_division_id</th></tr></thead><tbody><tr><td>DEPT_REQ</td><td>DIV_SALES</td></tr><tr><td>DEPT_REV1</td><td>DIV_SALES</td></tr><tr><td>DEPT_REV2</td><td>DIV_AUDIT</td></tr></tbody></table></section></div><p class="small">⑤ 계약: ITEM_101 · Active · 할인 상한 0.15 / 발주 할인 0.12 · 순금액 85000 — 저장된 JSON 발췌</p></div>

<ul>
<li>목적: 승인 표시가 있어도 R3 본부 분리 조건을 위반하는지 확인</li>
</ul>

<details><summary>발표자 노트</summary>

<p>기초 할인 예제를 저장소의 실제 함수로 확장한다. 그래프 표현으로 바꾸기 전부터 행 사이의 외래키 의미가 정해져 있어야 한다. 전체 JSON은 자료 창에서 볼 수 있다. 오늘의 충돌 예제는 Primary 검토자와 요청 부서의 본부를 DIV_SALES로 맞췄다. 다른 조건은 정상으로 두어 설명에 집중한다.</p>

</details>

## 29. R0–R3의 업무 조건

<blockquote>
<p>R3의 SHACL 경로는 역방향 1개와 순방향 4개입니다. 전 라운드에서 같은 RDF 투영기를 사용합니다.</p>
</blockquote><table>
<thead>
<tr>
<th>라운드</th>
<th>추가하는 조건</th>
</tr>
</thead>
<tbody>
<tr>
<td>R0</td>
<td>Active 계약, 할인 상한, 순금액 ≤ 100000, 적격 Primary 승인</td>
</tr>
<tr>
<td>R1</td>
<td>달성 마진율 ≥ 최소 마진율</td>
</tr>
<tr>
<td>R2</td>
<td>적격 Audit 승인도 요구</td>
</tr>
<tr>
<td>R3</td>
<td>요청 부서와 검토자 부서의 상위 본부 분리</td>
</tr>
</tbody>
</table>
<div class="flow" data-flow="path"><div class="flow-steps"><div class="step" data-step="0"><span class="step-no">01</span><strong>요청 부서</strong><small>DEPT_REQ</small></div><div class="step" data-step="1"><span class="step-no">02</span><strong>요청</strong><small>← requestedByDept</small></div><div class="step" data-step="2"><span class="step-no">03</span><strong>검토</strong><small>hasReview →</small></div><div class="step" data-step="3"><span class="step-no">04</span><strong>검토자</strong><small>reviewedBy →</small></div><div class="step" data-step="4"><span class="step-no">05</span><strong>검토자 부서</strong><small>belongsToDept →</small></div><div class="step" data-step="5"><span class="step-no">06</span><strong>상위 본부</strong><small>parentDivision →</small></div></div></div>


<p>출처: <a href="https://github.com/shinysong/shacl-graphrag/blob/35dfc7ab1d3a0790c86bfe5922faf6cf7cfef9fc/docs/experiments/records/20261022-unified-rule-lifecycle.md">통합 진단의 정정 기록</a></p>

<details><summary>발표자 노트</summary>

<p>R2는 Primary와 Audit 역할의 적격 승인을 각각 요구하지만 두 역할을 반드시 서로 다른 사람이 맡는지 검사하지 않는다. R3 경로는 요청 부서에서 요청으로 역방향 이동한 뒤 검토, 검토자, 검토자 부서, 상위 본부로 이동한다. 공통 투영기를 유지해도 Shape 작성과 Python의 결측 처리는 필요하다.</p>

</details>

## 30. 본부 충돌 예제의 실행 코드

<blockquote>
<p>세 구현은 같은 입력과 R3 정책을 사용합니다. 이 사례에서는 모두 본부 충돌을 이유로 blocked를 반환했습니다.</p>
</blockquote>
<ul>
<li>목적: 합성 입력 생성 → 세 구현 판정 → 보고서와 프롬프트 구성</li>
</ul>
<div class="seminar-view"><pre><code>tables = make_valid_base_tables(rev1_div=&#x27;DIV_SALES&#x27;)  # 본부가 겹치는 입력
decisions = {  # 동일한 R3 정책을 세 구현에서 검사
    &#x27;Python&#x27;: evaluate_arm_p_python(tables, &#x27;R3&#x27;),  # Python 함수
    &#x27;SQLite&#x27;: evaluate_arm_s_sqlite(tables, &#x27;R3&#x27;),  # SQL 조회·판정
    &#x27;SHACL&#x27;: evaluate_arm_g_shacl(tables, &#x27;R3&#x27;),    # RDF·Shape 검사
}
report = extract_shacl_llm_report(tables, &#x27;R3&#x27;)  # 보고서를 JSON 필드로 정리
prompts = build_llm_prompt_modes(tables, round_id=&#x27;R3&#x27;)  # 입력문만 생성</code></pre><table><thead><tr><th>실제 저장 출력</th><th>판정</th><th>위반</th></tr></thead><tbody><tr><td>Python = SQLite = SHACL</td><td>blocked</td><td>division-separation</td></tr></tbody></table></div>

<p>실행 코드에 설명 주석만 추가 · 전체 원본은 자료 창의 seminar_examples.py</p>

<details><summary>발표자 노트</summary>

<p>이 코드는 이번 발표 자료를 만들 때 실제 실행했다. rev1_div 인자 하나를 DIV_SALES로 바꾸면 요청 부서와 Primary 검토자의 상위 본부가 겹친다. Python, SQLite, SHACL이 같은 조건을 구현한다. 반환값 전체의 일치도 확인했다. 실험 전체를 재실행하거나 기존 결과를 덮어쓰지는 않았다.</p>

</details>

## 31. 검증 보고서의 근거 필드

<blockquote>
<p>보고서는 “왜 차단됐는가”를 개체·관계 경로·값으로 나눕니다. <code>conforms</code>와 최종 업무 판정은 같은 필드가 아닙니다.</p>
</blockquote>
<ul>
<li>목적: 실제 보고서의 필드를 설명에 사용할 근거로 읽기</li>
</ul>
<div class="seminar-view"><div class="columns"><section class="panel"><h3>실제 출력 발췌 · JSON</h3><pre><code>{
  &quot;focus_node&quot;: &quot;ex:departments/DEPT_REQ&quot;,
  &quot;value_node&quot;: &quot;ex:divisions/DIV_SALES&quot;,
  &quot;constraint_component&quot;: &quot;sh:DisjointConstraintComponent&quot;
}</code></pre></section><section class="panel"><h3>각 필드의 역할</h3><table><thead><tr><th>필드</th><th>읽는 법</th></tr></thead><tbody><tr><td>focus_node</td><td>요청 부서 DEPT_REQ가 검사 대상</td></tr><tr><td>result_path</td><td>요청→검토→검토자→부서→본부를 따라간 경로</td></tr><tr><td>value_node</td><td>겹치는 본부 DIV_SALES</td></tr><tr><td>constraint_component</td><td>두 값 집합의 겹침을 금지하는 Disjoint 검사</td></tr></tbody></table></section></div></div>

<ul>
<li>경로: 요청 부서 ← 요청 → 검토 → 검토자 → 소속 부서 → 본부</li>
<li>표준 RDF 보고서를 이 JSON으로 변환하는 코드는 저장소에서 직접 구현</li>
</ul>

<details><summary>발표자 노트</summary>

<p>상단 JSON에는 실제 실행 결과 중 첫 번째 검증 결과를 발췌해 담았다. 초점 개체, 경로, 값, 제약 종류를 따로 읽을 수 있다. report의 원시 RDF를 JSON으로 바꾸는 extract_shacl_llm_report는 저장소의 사용자 정의 코드다. 표준 필드의 존재와 사람이 이해하기 쉬운 출력 인터페이스를 만드는 비용을 구분한다.</p>

</details>

## 32. LLM 입력으로 전달할 검사 근거

<blockquote>
<p>검증기의 출력은 LLM이 사용할 설명 재료가 됩니다. 여기서는 프롬프트를 만들었으며 LLM 응답 정확도는 측정하지 않았습니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns"><section class="panel"><h3>입력 자료의 구성 비교</h3><table><thead><tr><th>구성</th><th>LLM 앞에 놓는 자료</th></tr></thead><tbody><tr><td>M0</td><td>질문 + 규정 + 원천 테이블</td></tr><tr><td>M1</td><td>질문 + 테이블 + 함수 판정·규칙명</td></tr><tr><td>M2</td><td>질문 + 판정·개체·경로·값 보고서</td></tr></tbody></table><p>목적: 모델이 설명에 사용할 근거가 어떤 형태로 전달되는지 확인.</p></section><div class="screen"><div class="screen-bar">M2 입력문 일부 · 구조 설명용</div><pre><code>질문: 이 요청을 승인할 수 있는가?

검사 결과: blocked
위반 규칙: division-separation
검사 대상: DEPT_REQ
충돌 값: DIV_SALES

지시: 위 근거를 사용해 설명하라.</code></pre><p>이 화면은 프롬프트 구성이다.<br>이번 진단에서는 모델 응답을 받지 않았다.</p></div></div></div>

<ul>
<li>같은 보고서를 만드는 Python·SQL 조건과의 모델 비교는 별도 과제</li>
</ul>
<p>출처: <a href="https://github.com/shinysong/shacl-graphrag/blob/35dfc7ab1d3a0790c86bfe5922faf6cf7cfef9fc/docs/experiments/records/20261022-unified-rule-lifecycle.md">실행 기록</a></p>

<details><summary>발표자 노트</summary>

<p>자료 창에서 전체 M0, M1, M2 문자열을 확인할 수 있다. 그림은 목표 역할 분담을 나타낸다. LLM이 근거에 충실하게 설명했는지는 측정하지 않았다. 최종 업무 승인과 예외 판단의 책임은 조직의 정책에 따라 사람이 맡는다. 이 세 구성은 제공 정보와 지시문도 함께 달라진다. 따라서 모델을 호출하더라도 SHACL 유무 하나만의 효과로 해석해서는 안 된다. M0의 필드 부재는 원천 정보 자체가 없다는 뜻이 아니다. 모델은 원천 테이블을 읽을 수 있다.</p>

</details>

## 33. 반례와 근거 상태 진단

<blockquote>
<p>반례는 잘못 옮긴 조건을 찾기 위한 진단입니다. 근거 상태 비교에서는 검색 누락과 원천 부재를 구분합니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns"><section class="panel"><h3>1단계 · 잘못 옮긴 규칙 찾기</h3><p><b>입력</b> 24항목 × 정상·경계 위반·무관 변화·결측 반례</p><p><b>조건</b> 의도적으로 틀린 함수 / 기준 구현</p><p><b>출력</b> 네 반례에서 모두 기대 판정과 일치한 항목</p><table><thead><tr><th>오류 함수</th><th>기준 구현</th></tr></thead><tbody><tr><td>0/24</td><td>24/24</td></tr></tbody></table></section><section class="panel"><h3>2단계 · 부족한 근거 처리</h3><p><b>입력</b> 동일 업무 정책, 여섯 근거 상태 × 60개 ID</p><p><b>처리</b> unknown → 전체 원천을 한 번 재평가</p><p><b>출력</b> 누락이 채워지면 재판정, 원천에도 없으면 보류</p><table><thead><tr><th>S2 계약 판정 일치</th><th>외부 합성 진실 오류</th></tr></thead><tbody><tr><td>360/360</td><td>사실 치환 60/60</td></tr></tbody></table></section></div></div>

<ul>
<li>고정 함수를 오프라인으로 비교했다. 자연어를 자동 이해한 성능이 아님</li>
</ul>
<p>출처: <a href="https://github.com/shinysong/shacl-graphrag/blob/35dfc7ab1d3a0790c86bfe5922faf6cf7cfef9fc/docs/experiments/records/20261022-unified-rule-lifecycle.md">실행 기록</a></p>

<details><summary>발표자 노트</summary>

<p>1단계는 12개 정책 계열에 두 언어 라벨을 붙인 24항목이다. 같은 테이블과 오류 함수를 재사용했으며 자연어 컴파일이나 언어 간 성능을 측정하지 않았다. 2단계에서는 검색 누락 60건과 원천 부재 60건에 각각 재평가하므로 팔마다 120번 시도한다. 원천 부재는 보류로 남는다. S2는 오승인 0/360, 불필요 보류 0/240이지만 외부 진실 오류는 남는다. 실제 GLEIF 전이 24건 주장은 철회했으며 not_executed로 기록했다.</p>

</details>

## 34. 규칙 추가와 보고서 필드 진단

<blockquote>
<p>규칙이 늘어날 때 판정이 같은지, 설명에 필요한 필드가 채워지는지를 각각 확인했습니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns"><section class="panel"><h3>3단계 · 규칙 추가 후 판정 비교</h3><p><b>입력</b> 같은 테이블의 6패턴</p><p><b>변경</b> R0 → 마진 R1 → Audit R2 → 본부 분리 R3</p><p><b>출력</b> Python·SQLite·SHACL의 반환값 비교</p><p class="metric">960 / 960 일치</p><p>6패턴 × 40반복 × 4라운드. 실제 사람의 수정 시간을 잰 결과는 아니다.</p></section><section class="panel"><h3>4단계 · 보고서의 설명 재료</h3><p><b>입력</b> 4위반 패턴 × 60반복</p><p><b>출력</b> 프롬프트에 채워진 필드 수</p><table><thead><tr><th>구성</th><th>판정</th><th>개체·경로</th><th>값</th></tr></thead><tbody><tr><td>M0</td><td>0</td><td>0 · 0</td><td>0</td></tr><tr><td>M1</td><td>240</td><td>0 · 0</td><td>0</td></tr><tr><td>M2</td><td>240</td><td>240 · 240</td><td>180</td></tr></tbody></table><p>각 분모 240. 기수성 위반 60건에는 충돌 값이 없다.</p></section></div></div>

<ul>
<li>출력 일치·필드 개수로 유지보수 시간이나 LLM 설명 정확도를 대신 평가할 수 없음</li>
</ul>
<p>출처: <a href="https://github.com/shinysong/shacl-graphrag/blob/35dfc7ab1d3a0790c86bfe5922faf6cf7cfef9fc/docs/experiments/records/20261022-unified-rule-lifecycle.md">실행 기록</a></p>

<details><summary>발표자 노트</summary>

<p>960회는 고유 패턴·라운드 조합 24개를 반복한 횟수다. 독립 사례 960개로 세지 않는다. 코드 줄 수는 설명용 문자열 차이였으며 실제 버전별 수정 이력이나 유지보수 시간 측정이 아니다. 배포 불일치 비교도 실제 세 서비스를 배포한 실험이 아니므로 본 발표에서는 우위 수치로 제시하지 않는다. 필드 수 역시 근거의 완전성이나 모델 설명 정확도를 측정하지 않는다.</p>

</details>

## 35. 계산된 근거와 LLM 판단

<blockquote>
<p>별도 선행 실험에서는 원시 근거와 계산된 보고서를 제공했을 때 LLM의 계약 일치를 비교했습니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns"><section class="panel"><h3>비교한 처리 흐름</h3><p>① 질문 + 원시 근거 → <b>LLM 직접 판단</b></p><p>② 같은 정책의 계산 결과 + 근거 → <b>LLM 판단</b></p><p>목적: 미리 계산한 관계·조건 정보가 계약에 맞는 판단에 도움을 주는지 확인.</p><p>189개 완료 묶음: 첫 반복 120 + 두 번째 반복 69.</p></section><section class="panel"><h3>저장된 관측값</h3><table><thead><tr><th>지표</th><th>직접</th><th>판단 전 검사</th></tr></thead><tbody><tr><td>계약 일치</td><td>124/189</td><td>179/189</td></tr><tr><td>잘못된 긍정</td><td>15</td><td>0</td></tr><tr><td>불필요한 부정 / 보류</td><td>26 / 3</td><td>9 / 1</td></tr><tr><td>무관 정보 후 판정 변화</td><td>21/77</td><td>1/77</td></tr></tbody></table><p>계약 일치는 외부 사실 정확도와 구분한다.</p></section></div></div>

<ul>
<li>이번 M0·M1·M2 진단 결과가 아니다. 계산된 정보를 제공한 효과와 RDF 고유 효과를 구분</li>
</ul>
<p>출처: <a href="https://github.com/shinysong/shacl-graphrag/blob/35dfc7ab1d3a0790c86bfe5922faf6cf7cfef9fc/docs/experiments/records/20261013-hybrid-comparison.md">실행 기록</a></p>

<details><summary>발표자 노트</summary>

<p>189는 독립 질문 수가 아니다. 중단과 재개가 포함된 완료 묶음의 분모다. 원시 근거를 주는 조건과 계산된 보고서를 먼저 제공하는 조건의 차이를 보여 준다. 코드와 SHACL은 같은 선언 정책을 구현했다. 관측된 이점은 계산된 정보를 제공한 효과로 해석해야 한다. 모델 내부에서 실제로 어떤 추론 오류가 일어났는지는 관찰하지 않았다. 계약 일치는 외부 사실 정확도와 다르다.</p>

</details>

## 36. 동일 의미의 Python·OWL-RL 비교

<blockquote>
<p>기존 추론 연구에서는 동일한 정의를 받은 Python과 OWL-RL이 같은 결론을 내리는지 확인했습니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns"><section class="panel"><h3>입력·조건·출력</h3><p><b>입력</b> 64개 합성 그래프의 사실과 동일한 공리</p><p><b>질문</b> 직접 쓰지 않은 타입·역관계·도달 관계도 찾는가?</p><p><b>조건</b> 명시 조회 / JSON·Python 규칙 / RDF·OWL-RL</p><p><b>출력</b> 640질의의 결론과 배타 클래스 충돌 증거</p></section><section class="panel"><h3>같은 의미를 받은 두 구현</h3><table><thead><tr><th>지표</th><th>명시 조회</th><th>Python</th><th>OWL-RL</th></tr></thead><tbody><tr><td>질의 일치</td><td>504/640</td><td>640/640</td><td>640/640</td></tr><tr><td>놓친 도출 답</td><td>136</td><td>0</td><td>0</td></tr><tr><td>충돌 그래프 탐지</td><td>0/32</td><td>32/32</td><td>32/32</td></tr></tbody></table><p>추론을 추가한 효과와 RDF 형식의 효과를 분리한다. LLM 호출 없음.</p></section></div></div>

<ul>
<li>제한된 양의 규칙과 지정 충돌 증거의 결과다. 전체 OWL의 완전성·실제 업무 정확도는 미평가</li>
</ul>
<p>출처: <a href="https://github.com/shinysong/shacl-graphrag/blob/35dfc7ab1d3a0790c86bfe5922faf6cf7cfef9fc/docs/experiments/records/20261013-ontology-reasoning.md">실행 기록</a></p>

<details><summary>발표자 노트</summary>

<p>기존 연구에는 추론 실험도 있었다. 개념 계층, 전이 관계, 역관계, 관계 합성, 어휘 매핑을 제한된 합성 구조에서 비교했다. 두 구현은 동일한 의미를 받았고 결과가 일치했다. 명시 조회는 추론을 제거한 대조군이다. 질의 640개는 독립적인 실제 업무 표본이 아니며 구조와 어휘 변형을 재사용했다. 440개 질의의 미확인은 현실에서 거짓이라는 뜻이 아니다. 충돌 탐지는 그래프 전체의 배타 클래스 증거 검사이며 완전한 OWL 일관성 검사는 아니다.</p>

</details>

## 37. 실제 GLEIF의 관계·등록 상태

<blockquote>
<p>실제 데이터에는 관계의 유무뿐 아니라 관계 종류·등록 상태·유효 시점이 함께 기록됩니다. 기록된 사실과 의사결정 채택 기준을 분리해야 합니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns"><div class="screen"><div class="screen-bar">실제 GLEIF 저장 원천 · RR 10행 발췌</div><table><thead><tr><th>필드</th><th>값</th></tr></thead><tbody><tr><td>StartNode.NodeID</td><td>010PWNH4K3BLIC3I7R03</td></tr><tr><td>EndNode.NodeID</td><td>549300COKYB5EGSU1838</td></tr><tr><td>RelationshipType</td><td>IS_DIRECTLY_CONSOLIDATED_BY</td></tr><tr><td>RelationshipStatus</td><td>ACTIVE</td></tr><tr><td>RegistrationStatus</td><td>LAPSED</td></tr></tbody></table></div><section class="panel"><h3>레슨런 · 기록과 채택 기준 분리</h3><p><b>기록 사실</b> 직접 회계 연결 관계가 원천에 있다.</p><p><b>상태 의미</b> 관계 ACTIVE와 등록 LAPSED는 다른 필드다.</p><p><b>이번 정책</b> PUBLISHED만 채택하므로 판단은 보류했다.</p><p><b>후속 화면</b> “관계가 없음” 대신 “보고된 관계는 있으나 채택 기준 미충족”으로 표시한다.</p></section></div></div>

<p>출처: <a href="https://github.com/shinysong/shacl-graphrag/blob/35dfc7ab1d3a0790c86bfe5922faf6cf7cfef9fc/docs/experiments/records/20261014-business-questions.md">실제 GLEIF 예시와 정책 선택</a></p>

<details><summary>발표자 노트</summary>

<p>2026-10-12 Golden Copy에서 선택한 실제 RR 10행을 이미 저장된 summary JSON으로 제시한다. 현재 실시간 관계 상태를 확인한 것이 아니다. 편의 표본의 미채점 예시이며 제조 도메인 전이나 독립 업무 정확도 벤치마크가 아니다. LAPSED라고 관계가 거짓인 것은 아니다. 이 파일은 실제 관계가 있는데 이번 채택 정책이 보류한 사례다. 가상의 근거 누락 테이블과 구분한다.</p>

</details>

## 38. 부품 인증 만료의 영향 범위

<blockquote>
<p>후속 설계안입니다. 재검토 후보 도출은 물리적 고장 예측이나 제품 안전성 판정이 아닙니다.</p>
</blockquote><div class="flow story-flow" data-flow="impact"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 300" role="img" aria-labelledby="impact-title impact-desc" font-family="Pretendard, sans-serif"><title id="impact-title">인증 만료의 잠재 영향 범위</title><desc id="impact-desc">설계 예시. 인증서에서 부품, 조립품, 완제품을 연결하고 부품 유형과 적용 규정을 함께 확인한다. 물리적 손상이나 승인 여부를 자동 확정하지 않는다.</desc><defs><marker id="impact-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6" y="10" width="268" height="115" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="10" y="5" width="28" height="38" rx="3"/><path d="m15 16 3 3 5-6M26 16h6m-17 11 3 3 5-6M26 27h6"/></svg><text x="74" y="51" font-size="21" fill="#14212f" font-weight="700">인증서</text><text x="26" y="89" font-size="18" fill="#465970">만료 상태 확인</text></g><path d="M274 68h12" stroke="#879bb6" marker-end="url(#impact-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="286" y="10" width="268" height="115" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="304" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><ellipse cx="24" cy="10" rx="16" ry="6"/><path d="M8 10v27c0 8 32 8 32 0V10M8 23c0 8 32 8 32 0"/></svg><text x="354" y="51" font-size="21" fill="#14212f" font-weight="700">부품</text><text x="306" y="89" font-size="18" fill="#465970">인증 대상</text></g><path d="M554 68h12" stroke="#879bb6" marker-end="url(#impact-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="566" y="10" width="268" height="115" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="584" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="10" r="5"/><circle cx="36" cy="24" r="5"/><circle cx="12" cy="38" r="5"/><path d="m16 13 16 9m0 5-16 9M12 15v18"/></svg><text x="634" y="51" font-size="21" fill="#14212f" font-weight="700">조립품</text><text x="586" y="89" font-size="18" fill="#465970">부품 사용</text></g><path d="M834 68h12" stroke="#879bb6" marker-end="url(#impact-arrow)"/><g class="step story-step" data-step="3"><rect class="story-box" x="846" y="10" width="268" height="115" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="864" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><ellipse cx="24" cy="10" rx="16" ry="6"/><path d="M8 10v27c0 8 32 8 32 0V10M8 23c0 8 32 8 32 0"/></svg><text x="914" y="51" font-size="21" fill="#14212f" font-weight="700">완제품</text><text x="866" y="89" font-size="18" fill="#465970">조립품 구성</text></g><path d="M420 125v50M700 175V125" stroke="#879bb6" fill="none"/><g class="step story-step" data-step="4"><rect class="story-box" x="286" y="175" width="268" height="115" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="304" y="190" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="10" r="5"/><circle cx="36" cy="24" r="5"/><circle cx="12" cy="38" r="5"/><path d="m16 13 16 9m0 5-16 9M12 15v18"/></svg><text x="354" y="216" font-size="21" fill="#14212f" font-weight="700">부품 유형</text><text x="306" y="254" font-size="18" fill="#465970">하위·상위 분류</text></g><g class="step story-step" data-step="5"><rect class="story-box" x="566" y="175" width="268" height="115" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="584" y="190" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="10" y="5" width="28" height="38" rx="3"/><path d="m15 16 3 3 5-6M26 16h6m-17 11 3 3 5-6M26 27h6"/></svg><text x="634" y="216" font-size="21" fill="#14212f" font-weight="700">적용 규정</text><text x="586" y="254" font-size="18" fill="#465970">재검토 조건</text></g><path d="M554 230h12" stroke="#879bb6" marker-end="url(#impact-arrow)"/></svg></div>

<p>“이 부품의 인증서가 만료됐습니다. <strong>어떤 완제품을 재검토해야 하나요?</strong>”</p>
<ul>
<li>사용 관계: 인증서 → 부품 → 조립품 → 완제품</li>
<li>적용 조건: 부품 유형 → 상위 유형 → 적용 규정</li>
<li>판정: 해당 시점·규정에서 재검토 후보인지 확인</li>
</ul>


<details><summary>발표자 노트</summary>

<p>기존 change-impact 연구와 관련된 질문이다. 이 도식의 새 결합 설계는 실행하지 않았다. 부품 인증, 구성 관계, 분류, 적용 규정, 시점과 버전이 함께 필요하다. 인증 만료라는 상태와 재검토 의무를 연결하는 규정은 제공된 계약으로 따로 명시해야 한다. 연결된 모든 제품이 곧바로 위험하다고 결론 내리지 않는다. 공개 ERP 스키마를 참고해 만든 거래·구성 사례는 여전히 합성 자료다.</p>

</details>

## 39. 원천 부재와 검색 누락의 차이

<blockquote>
<p>추가 관계나 정의를 제거했을 때 답이 달라지는 대응 사례가 필요합니다. 홉 수만 늘리는 것으로 온톨로지의 효과가 입증되지는 않습니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns"><section class="panel"><h3>원천에도 관계가 없는 경우</h3><table><thead><tr><th>원천 BOM</th><th>parent</th><th>child</th></tr></thead><tbody><tr><td>b1</td><td>A1</td><td>P1</td></tr><tr><td>—</td><td>PRODUCT_X</td><td>미기록</td></tr></tbody></table><table><thead><tr><th>검색 반환</th><th>parent</th><th>child</th></tr></thead><tbody><tr><td>b1</td><td>A1</td><td>P1</td></tr></tbody></table><p>새 검색만으로 빠진 관계를 만들 수 없다.<br><b>출력: 완제품 범위 확인 불가</b></p></section><section class="panel"><h3>원천에는 있지만 검색에서 누락</h3><table><thead><tr><th>원천 BOM</th><th>parent</th><th>child</th></tr></thead><tbody><tr><td>b1</td><td>A1</td><td>P1</td></tr><tr><td>b2</td><td>PRODUCT_X</td><td>A1</td></tr></tbody></table><table><thead><tr><th>검색 반환</th><th>parent</th><th>child</th></tr></thead><tbody><tr><td>b1</td><td>A1</td><td>P1</td></tr></tbody></table><p>반환 범위를 보완하면 b2를 찾을 수 있다.<br><b>출력: 보완 후 PRODUCT_X 후보</b></p></section></div><p class="small">작성한 설명용 데이터. 원천 스냅샷을 따로 보존해야 두 실패를 구분할 수 있다.</p></div>

<ul>
<li>같은 질문: “P1과 연결된 완제품의 재검토 범위는?”</li>
<li>상위 유형 규정 적용은 명시적 정책으로 선언; subclass만으로 임의 규정이 복사되지 않음</li>
</ul>

<details><summary>발표자 노트</summary>

<p>각 단계는 추가 정보가 있어야 정답이 달라지는 대응 사례를 요구한다. 그래프의 홉만 늘리거나 합성 노드의 이름만 산업 용어로 바꾸는 것은 실제 도메인 전이 증거가 아니다. 분류에 따라 규정이 적용되도록 하려면 명시적인 클래스 제한이나 규칙·질의의 의미를 정의해야 한다. 직접 부품 관계와 간접 구성 관계도 분리해 의도치 않은 전이 추론을 막는다.</p>

</details>

## 40. 후속 가설과 평가 지표

<blockquote>
<p>모두 <strong>제안 가설</strong>입니다. 완료된 연구의 사전등록 가설이나 새 측정 결과로 제시하지 않습니다.</p>
</blockquote><table>
<thead>
<tr>
<th>제안 가설</th>
<th>통제할 것</th>
<th>관측할 것</th>
</tr>
</thead>
<tbody>
<tr>
<td>관계 계산이 LLM의 누락·오연결을 줄이는가</td>
<td>같은 질문·입력·정책</td>
<td>후보 재현율·정밀도, 잘못된 확답</td>
</tr>
<tr>
<td>공유 의미 정의가 질문 간 불일치를 줄이는가</td>
<td>동일 버전·정보 접근</td>
<td>질문 간 모순, 변경 후 회귀 오류</td>
</tr>
<tr>
<td>구현 차이가 변경·근거 추적 비용에 나타나는가</td>
<td>동등한 공리·규칙</td>
<td>실제 수정·테스트·추적 작업량</td>
</tr>
<tr>
<td>불완전한 근거에서 균형 있게 보류하는가</td>
<td>답변 가능 여부</td>
<td>잘못된 확답 + 불필요한 보류</td>
</tr>
</tbody>
</table>


<details><summary>발표자 노트</summary>

<p>공유 방식의 효과와 구현 언어의 효과를 섞지 않는다. 공유 코드·공유 JSON과 공유 OWL·SHACL을 대등하게 비교하고 동일한 버전 장애 조건을 적용해야 한다. 비용 지표는 사람의 실제 작업 시간을 측정할 계획이 있을 때만 유지보수 시간이라고 부른다. 단순 코드 줄 수나 반복 출력 수를 독립 관측값으로 취급하지 않는다. 가설과 분석 계획은 새 평가 자료를 보기 전에 고정해야 한다.</p>

</details>

## 41. 동일 의미·정보를 받은 비교 조건

<blockquote>
<p>순서·도구 호출은 DAG로 구성할 수 있습니다. 모든 조합을 한꺼번에 돌리기보다 하나의 효과씩 분리합니다.</p>
</blockquote><div class="flow story-flow" data-flow="comparators"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 200" role="img" aria-labelledby="comparators-title comparators-desc" font-family="Pretendard, sans-serif"><title id="comparators-title">동일한 의미를 받은 구현의 비교</title><desc id="comparators-desc">동일한 의미를 받은 구현의 비교</desc><defs><marker id="comparators-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6.0" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24.0" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="10" y="5" width="28" height="38" rx="3"/><path d="m15 16 3 3 5-6M26 16h6m-17 11 3 3 5-6M26 27h6"/></svg><text x="74.0" y="51" font-size="21" fill="#14212f" font-weight="700">공통 계약</text><text x="26.0" y="89" font-size="18" fill="#465970">같은 분류·관계·정책</text><text x="26.0" y="114" font-size="18" fill="#465970">같은 입력과 증거 범위</text></g><path d="M360.3333333333333 95H378.3333333333333" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#comparators-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="385.3333333333333" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="403.3333333333333" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="7" width="38" height="27" rx="3"/><path d="M24 34v8M14 42h20M12 15h24M12 22h15"/></svg><text x="453.3333333333333" y="51" font-size="21" fill="#14212f" font-weight="700">각 구현</text><text x="405.3333333333333" y="89" font-size="18" fill="#465970">Python / SQL / JSON</text><text x="405.3333333333333" y="114" font-size="18" fill="#465970">RDF / OWL / SHACL</text></g><path d="M739.6666666666666 95H757.6666666666666" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#comparators-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="764.6666666666666" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="782.6666666666666" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="24" r="19"/><path d="m14 24 7 7 14-16"/></svg><text x="832.6666666666666" y="51" font-size="21" fill="#14212f" font-weight="700">별도 평가</text><text x="784.6666666666666" y="89" font-size="18" fill="#465970">결론 일치·누락·근거</text><text x="784.6666666666666" y="114" font-size="18" fill="#465970">변경 비용은 따로 측정</text></g></svg></div>

<table>
<thead>
<tr>
<th>대조</th>
<th>분리하려는 차이</th>
</tr>
</thead>
<tbody>
<tr>
<td>명시 조회 ↔ 같은 정책의 관계 계산</td>
<td>계산을 추가한 효과</td>
</tr>
<tr>
<td>Python·재귀 SQL ↔ RDF·규칙/OWL</td>
<td>같은 의미의 구현 방식</td>
</tr>
<tr>
<td>개별 설정 ↔ 공유 JSON/스키마 ↔ 공유 온톨로지</td>
<td>의미·버전 공유 방식</td>
</tr>
<tr>
<td>동일 보고서 유무를 바꾼 LLM</td>
<td>계산된 근거를 제공한 효과</td>
</tr>
</tbody>
</table>


<details><summary>발표자 노트</summary>

<p>추론 기능이 없는 대조군을 OWL보다 못한 구현이라고 평가해서는 안 된다. 명시 조회는 기능 제거 대조다. 구현 비교에서는 동일한 공리와 규칙, 입력, 결측 정책, 결과 범위와 근거 제공 수준을 맞춘다. 공유 기능이 있는 Python 대조군도 필요하다. SQL과 OWL의 표현력 전체가 동일하다는 주장이 아니라 선택한 유한 업무 규칙을 동등하게 구현하는 설계다. 새 유료 LLM 실험은 별도 범위와 예산 승인이 필요하다.</p>

</details>

## 42. 여섯 가지 근거 상태

<blockquote>
<p>같은 질문에 서로 다른 근거 상태를 만들어 잘못된 확답과 불필요한 보류를 함께 확인합니다. 아래는 후속 데이터셋의 설명용 설계입니다.</p>
</blockquote>
<div class="seminar-view"><table><thead><tr><th>상태</th><th>작은 레코드 예</th><th>확인할 출력</th></tr></thead><tbody><tr><td>충분한 근거</td><td>b1: A1→P1 / b2: X→A1</td><td>X와 근거 b1,b2</td></tr><tr><td>원천 부재</td><td>source에 b2 없음</td><td>확인 불가</td></tr><tr><td>검색 누락</td><td>source에는 b2 / retrieved에는 없음</td><td>검색 보완 여부</td></tr><tr><td>시점·버전 불일치</td><td>valid_to=2025 / 질문=2026</td><td>현재 적용 여부</td></tr><tr><td>자료 충돌</td><td>v1: P1→A1 / v2: P1→A2</td><td>선택 근거 또는 보류</td></tr><tr><td>일관된 거짓 입력</td><td>P1→A1 기록, 현장 증거는 다름</td><td>검증 통과와 외부 오류 분리</td></tr></tbody></table></div>

<ul>
<li>원천·검색 반환·질문 시점·평가 기준을 별도로 저장</li>
<li>숨은 평가 기준으로 실행 답을 수정하지 않음</li>
</ul>

<details><summary>발표자 노트</summary>

<p>여섯 상태는 새 데이터셋 설계 제안이다. 과거 연구에서는 일부 조건을 다뤘다. 모든 조건을 한 코호트에서 새로 실행한 것은 아니다. 원천 부재와 검색 누락은 원천 스냅샷과 실제 반환 자료를 따로 저장해야 구분할 수 있다. 충돌의 우선순위 정책은 평가 전에 정한다. 내부적으로 일관된 거짓 입력은 외부 평가 자료로만 드러날 수 있고 그 기준을 런타임 오라클로 전달해서는 안 된다.</p>

</details>

## 43. 원천·합성·평가 자료의 구분

<blockquote>
<p>실제 스키마를 참고해 만든 거래 데이터는 합성 데이터입니다. 사용한 코호트를 새 held-out 자료처럼 재사용하지 않습니다.</p>
</blockquote><div class="flow story-flow" data-flow="provenance"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 200" role="img" aria-labelledby="provenance-title provenance-desc" font-family="Pretendard, sans-serif"><title id="provenance-title">실제 자료와 작성한 자료의 구분</title><desc id="provenance-desc">실제 자료와 작성한 자료의 구분</desc><defs><marker id="provenance-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#879bb6" stroke-width="1.4"/></marker></defs><g class="step story-step" data-step="0"><rect class="story-box" x="6.0" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="24.0" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><ellipse cx="24" cy="10" rx="16" ry="6"/><path d="M8 10v27c0 8 32 8 32 0V10M8 23c0 8 32 8 32 0"/></svg><text x="74.0" y="51" font-size="21" fill="#14212f" font-weight="700">실제 원천 자료</text><text x="26.0" y="89" font-size="18" fill="#465970">출처·버전·해시 보존</text><text x="26.0" y="114" font-size="18" fill="#465970">실제 확인한 관계만 표시</text></g><path d="M360.3333333333333 95H378.3333333333333" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#provenance-arrow)"/><g class="step story-step" data-step="1"><rect class="story-box" x="385.3333333333333" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="403.3333333333333" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="10" y="5" width="28" height="38" rx="3"/><path d="m15 16 3 3 5-6M26 16h6m-17 11 3 3 5-6M26 27h6"/></svg><text x="453.3333333333333" y="51" font-size="21" fill="#14212f" font-weight="700">작성한 규칙·사례</text><text x="405.3333333333333" y="89" font-size="18" fill="#465970">합성 거래·관계·정책</text><text x="405.3333333333333" y="114" font-size="18" fill="#465970">공개 스키마 참고도 합성</text></g><path d="M739.6666666666666 95H757.6666666666666" fill="none" stroke="#879bb6" stroke-width="2" marker-end="url(#provenance-arrow)"/><g class="step story-step" data-step="2"><rect class="story-box" x="764.6666666666666" y="10" width="349.3333333333333" height="170" rx="9" fill="#fff" stroke="#c5d2e4"/><svg x="782.6666666666666" y="25" width="38" height="38" viewBox="0 0 48 48" fill="none" stroke="#245dc0" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="24" cy="24" r="19"/><path d="m14 24 7 7 14-16"/></svg><text x="832.6666666666666" y="51" font-size="21" fill="#14212f" font-weight="700">평가 자료</text><text x="784.6666666666666" y="89" font-size="18" fill="#465970">개발·평가 사용 이력 기록</text><text x="784.6666666666666" y="114" font-size="18" fill="#465970">정답은 실행 중 제공 안 함</text></g></svg></div>

<ul>
<li>원천: 파일·해시·출처·사용 조건·시점·버전</li>
<li>작성 부분: 합성 관계와 가정한 규칙을 별도 표시</li>
<li>실행 근거: 실제 검색 반환과 추론·검증 설정 저장</li>
<li>평가 기준: 계약 일치와 외부 사실 판단을 별도 기록</li>
</ul>


<details><summary>발표자 노트</summary>

<p>다음 단계에서는 사례별로 어떤 추가 관계와 의미 정의가 답을 바꾸는지 표로 고정한다. 새 대규모 실행은 하지 않는다. 실제 공개 원천에서 확인한 관계와 연구자가 작성한 관계·규칙을 나눠야 한다. 기존 실제 자료의 출처와 라이선스를 유지하고 수집 실패도 남긴다. 평가 기준 답은 실행 경로에 전달하지 않는다. 계약 일치와 외부 사실 정확도를 같은 열에 합치지 않는다.</p>

</details>

## 44. 관계 변경과 스키마 관리

<blockquote>
<p>관계는 바뀝니다. 안정된 식별자, 입력 매핑, 의미 변경, 시점·버전을 구분해 관리하는 범위를 작게 시작할 필요가 있습니다.</p>
</blockquote>
<div class="seminar-view"><div class="columns"><section class="panel"><h3>속성명 변경과 의미 변경의 분리</h3><table><thead><tr><th>변경 예</th><th>권장 처리</th></tr></thead><tbody><tr><td>maker → manufacturer</td><td>뜻이 같다면 안정 IRI 유지 + 입력 매핑 변경</td></tr><tr><td>assembledIn → installedIn</td><td>동일 의미인지 먼저 검토; 이름만 보고 통합 금지</td></tr><tr><td>소유 → 운용</td><td>다른 역할이면 별도 속성·정의</td></tr><tr><td>설치 위치의 시점 변경</td><td>관계 레코드에 유효 기간·출처·버전 저장</td></tr></tbody></table></section><section class="panel"><h3>작은 공통 계약 + 도메인 확장</h3><pre><code>원천 필드 / 버전
       ↓ 매핑
안정된 관계 IRI + 역할 정의
       ↓
질문별 규칙·Shape + 회귀 사례
       ↓
영향받는 조회·소비처 확인</code></pre><p>모든 관계를 미리 표준화하기보다 반복 질문에 필요한 범위를 우선 관리한다. 유지보수 비용은 남는다.</p></section></div></div>

<ul>
<li>운영 설계 제안: 영향받는 질의·Shape·소비처를 회귀 사례로 확인</li>
<li>실제 유지보수 시간과 장기 비용 절감은 아직 측정하지 않음</li>
</ul>

<details><summary>발표자 노트</summary>

<p>제안하는 운영 절차에서 정책 담당자는 뜻과 적용 범위를 정한다. 개발 담당자가 매핑·규칙·테스트를 변경한 뒤 운영 담당자가 버전을 배포하고 영향받는 요청을 재검토한다. 표준 스키마를 만든 뒤에도 유지보수는 필요하다. 공유 JSON, 공통 라이브러리, 스키마 레지스트리도 같은 절차에 들어갈 수 있다. 연구에서는 같은 정책과 같은 정보를 제공하는 비교를 유지해야 한다. 형식에 맞는 거짓 사실, 숨은 원천 누락, 잘못 선택한 질문 계약은 검증 통과만으로 해결되지 않는다.</p>

</details>

## 45. 근거를 포함한 검토 화면

<blockquote>
<p>최종 화면에는 답뿐 아니라 적용한 규칙과 근거가 함께 보여야 합니다. 다음 데모 개발은 이 구조를 실제 사용자 흐름으로 연결하는 작업입니다.</p>
</blockquote>
<div class="seminar-view"><div class="screen"><div class="screen-bar">발주 검토 · 실제 저장 결과로 구성한 발표용 화면</div><div class="columns"><section class="panel"><h3>질문과 입력</h3><p><b>REQ_2026_01을 승인할 수 있는가?</b></p><table><thead><tr><th>조건</th><th>저장된 입력</th></tr></thead><tbody><tr><td>계약 / 할인</td><td>Active / 0.12 ≤ 0.15</td></tr><tr><td>검토자</td><td>USER_PRIMARY · Qualified</td></tr><tr><td>요청 본부</td><td>DIV_SALES</td></tr><tr><td>검토자 본부</td><td>DIV_SALES</td></tr></tbody></table></section><section class="panel"><h3>검사 결과와 근거</h3><p class="metric">blocked · 승인 조건 미충족</p><p>R3 본부 분리 조건에서 동일 본부가 확인됐다.</p><table><thead><tr><th>보고서 필드</th><th>값</th></tr></thead><tbody><tr><td>focus_node</td><td>DEPT_REQ</td></tr><tr><td>value_node</td><td>DIV_SALES</td></tr><tr><td>violations</td><td>division-separation</td></tr></tbody></table><p>설명은 발표자가 작성했다. 실제 LLM 응답이나 운영 서비스 화면은 아니다.</p></section></div><p class="small">자료 창에서 project-input.json · project-report.json · 실제 호출 코드 열기</p></div></div>

<details><summary>발표자 노트</summary>

<p>도입의 소속 변경 질문으로 돌아온다. 실제 코드는 변경 후 한 시점의 합성 입력으로 실행했다. 여기서 말하는 답은 그 실행을 설명하는 예시다. 정책 판정 blocked, 위반 division-separation, 요청 부서 DEPT_REQ, 검토자 USER_PRIMARY, 공통 본부 DIV_SALES는 저장된 입력과 보고서로 확인할 수 있다. 한국어 문장은 발표자가 작성한 요약이며 LLM의 실제 응답이 아니다. 변경 전후 비교·재검토 대상 자동 선정·실운영 승인 이력 관리는 목표 업무 흐름으로 설명했으며 이번 작은 예제에서 측정하지 않았다. 전체 예제와 프롬프트는 자료 버튼에서 확인하고 저장할 수 있다. 다음 검증에서는 같은 구조화 보고서를 제공하는 Python·SQL·SHACL 조건, 자연어 계약 선택 오류, 설명의 근거 일치, 실제 유지보수 작업을 분리해 측정해야 한다.</p>

</details>
