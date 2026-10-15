# LLM 주도 조회·온톨로지 도구 첫 실행

이번에는 LLM이 직접 질문을 해석하고 SPARQL을 작성하며 도구를 선택했다. 여섯 업무 질문 유형의 18개 개발 사례를 A/B/C로 실행해 54개 에피소드를 기록했다. 이전의 규칙 기반 업무 실험과 구분되는 실제 OpenRouter 모델 실행이다.

결과는 온톨로지의 성능 우열보다 조회 인터페이스의 문제를 먼저 드러냈다. C에 제공한 검증 도구는 호출되지 않았다. 따라서 이번 실행으로 SHACL 검증의 효과를 판정할 수 없다. 제조업 영향 탐색 정책의 방향 설명 오류도 발견해 해당 사례에 표시했다.

## 전체 결과와 조회 도달률

단순한 상태·값 일치는 조회한 근거가 충분하다는 뜻이 아니다. 빈 결과나 쿼리 오류 뒤 `unknown`을 답했는데 기준도 `unknown`인 경우를 따로 확인했다.

| 조건 | 배정 | 답변 종료 | 상태·값 일치 | 실제 행 조회 성공 | 검증 호출 | 미완료 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 18 | 14 | 6 | 4 | 0 | 4 |
| B | 18 | 12 | 4 | 4 | 0 | 6 |
| C | 18 | 9 | 3 | 0 | 0 | 9 |

A는 조회 도구, B는 온톨로지 설명 추가, C는 검증 도구 추가 조건이다. 모든 조건은 같은 RDFLib 스냅샷을 사용했다. 실제 행 조회 성공은 최소 한 번 빈 결과가 아닌 행을 받은 에피소드 수다. 필요한 근거 전체를 확보했다는 뜻은 아니다.

검증 도구 호출이 없으므로 C의 차이를 검증의 인과 효과로 해석할 수 없다. 한 번씩 실행한 합성 개발 사례이며 RDF·JSON 표현이나 그래프 DB의 성능 비교도 아니다.

| 조건 | 잘못된 단정 상태 | 불필요한 보류 | 상태 일치 중 행을 조회하지 못한 경우 | 인용 ID 정확 일치 |
| --- | ---: | ---: | ---: | ---: |
| A | 2 | 3 | 4 | 5 |
| B | 2 | 4 | 3 | 3 |
| C | 0 | 4 | 3 | 3 |

잘못된 단정 상태는 `known`, `eligible`, `blocked`, `review_ready`, `review_required`, `reported_exception` 중 상태·값이 기준과 다른 답변이다. 불필요한 보류는 기준이 이 단정 상태 중 하나인데 모델이 `unknown`, `incomplete`, `conflict`, `clarification`을 반환한 경우다. 인용 ID 일치는 상태·값과 별도 지표이며 빈 인용끼리 일치하는 경우도 포함한다.

## 실제 질문·조회·답변

아래 카드는 정상 사례 여섯 개의 C 조건 실제 실행이다. 질문은 한국어로 옮겼고 원천 요약과 별도 채점 기준을 함께 적었다. 쿼리는 첫 요청의 앞부분을 표시한다. 전체 원문과 도구 결과는 [실행 과정 JSON](20261015-llm-ontology-tools-traces.json)과 [입력 스냅샷](20261015-llm-ontology-tools-inputs.json)에 있다.

<style>.llm-trace-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.llm-trace-cards img{width:100%;height:auto;border-radius:14px}@media(max-width:680px){.llm-trace-cards{grid-template-columns:1fr}}</style>
<div class="llm-trace-cards">
<a href="/shacl-graphrag/experiments/figures/llm-tools-1.svg"><img src="/experiments/figures/llm-tools-1.svg" alt="업무 질문 1의 실제 LLM 조회·검증·답변" /></a>
<a href="/shacl-graphrag/experiments/figures/llm-tools-2.svg"><img src="/experiments/figures/llm-tools-2.svg" alt="업무 질문 2의 실제 LLM 조회·검증·답변" /></a>
<a href="/shacl-graphrag/experiments/figures/llm-tools-3.svg"><img src="/experiments/figures/llm-tools-3.svg" alt="업무 질문 3의 실제 LLM 조회·검증·답변" /></a>
<a href="/shacl-graphrag/experiments/figures/llm-tools-4.svg"><img src="/experiments/figures/llm-tools-4.svg" alt="업무 질문 4의 실제 LLM 조회·검증·답변" /></a>
<a href="/shacl-graphrag/experiments/figures/llm-tools-5.svg"><img src="/experiments/figures/llm-tools-5.svg" alt="업무 질문 5의 실제 LLM 조회·검증·답변" /></a>
<a href="/shacl-graphrag/experiments/figures/llm-tools-6.svg"><img src="/experiments/figures/llm-tools-6.svg" alt="업무 질문 6의 실제 LLM 조회·검증·답변" /></a>
</div>

## 오류가 드러난 세 과정

### 문자열 ID를 URI로 조회한 영향 탐색

`case01-C`의 원천에는 `b1`의 subject가 문자열 `"part-A"`로 저장돼 있다. 모델은 이를 `<urn:business-questions:part-A>`라는 URI로 조회했다. 처음에는 namespace 오류가 났고 URI 표기를 고친 다음에도 문자열과 URI의 차이를 고치지 않아 결과가 비었다. 같은 쿼리를 반복한 뒤 `unknown`으로 종료했다. 검증 호출은 0회였다.

이 사례에는 공개 정책의 관계 방향 오류도 있으므로 올바른 영향 답변 능력을 채점하는 사례로 해석하기 어렵다. 다만 저장된 문자열과 조회 URI가 일치하지 않아 행이 반환되지 않았다는 사실은 실제 쿼리에서 확인된다. 원천에 정보가 없는 경우와 다르다.

### PUBLISHED 근거에 붙은 LAPSED 주의 문구

`case16-B`는 “LEI-A의 내부 관계 검토를 완료할 수 있나?”라는 질문이다. 원천에는 ACTIVE·ISSUED 법인 `e1`과 PUBLISHED 직접 회계 관계 `r1`이 함께 있다. 모델은 앞의 두 조회에서 행을 얻지 못했고 세 번째 조회에서 다음 행만 받았다.

```json
{"id": "urn:business-questions:record/r1", "registration_status": "PUBLISHED"}
```

최종 답변은 `unknown`, 인용은 `r1`, 주의 문구는 `LAPSED`였다. 법인 상태를 가져오지 못한 조회 누락과 받은 상태 값에 근거하지 않은 주의 문구를 구분해야 한다. 원천 기준은 `review_ready`지만 실행 중 그 기준을 전달하거나 답을 고치지 않았다.

### 상태는 일치했지만 판단 근거를 가져오지 못한 답변

`case18-B`도 내부 검토 질문이다. 원천의 법인 `e1`은 법적 상태와 등록 상태의 어휘가 뒤바뀌어 있어 기준이 `review_required`다. 모델도 같은 상태를 답했지만 실제 조회한 ID는 관계 `r1`뿐이었고 인용도 `r1`이었다. 문제의 법인 상태를 확인한 답변이라고 볼 수 없다. 이 사례에서는 상태·값은 일치하지만 근거는 일치하지 않는다.

## 공개 정책 오류의 영향 범위

제조업 영향 탐색의 공개 문장은 `part_of`를 역방향으로 탐색한다고 적었다. 실제 데이터에서는 `part_of`를 정방향으로, `contains`를 역방향으로 따라가야 한다. 이는 실험 입력 작성상의 오류다. 실행 도중 발견했으며 동결한 입력과 최초 결과는 보존했다.

영향 탐색 세 사례 × 세 조건의 9개 결과에는 이 한계가 있다. 이를 제외한 나머지 15개 사례의 상태·값 일치는 다음과 같다. 이 분리는 **사후 진단**이며 처음 계획한 54개 분모를 대체하지 않는다.

A: 5/15 / B: 3/15 / C: 2/15

## 비용·한도·보존 기록

모델은 `openai/gpt-4o-mini`다. 실제 API 요청 **253회**, 보고 비용 **0.09770355 USD**, 반환하지 않은 예약 누계 **0.84940785 USD**였다. 예약 누계는 청구액이 아니다. 캠페인 한도 324회·1.50 USD 안에서 종료했고 추가 유료 호출은 시작하지 않았다. AWS 비용과 Codex 사용량은 이 수치에 포함하지 않는다.

초기 연결 점검 `20261015T080650Z-ontology-tools-smoke`의 3개와 본 실행 `20261015T080850Z-ontology-tools-main`의 51개를 합쳤다. 성적이 나쁘다는 이유로 재실행하지 않았다. 독립 방법·구현 검토를 거쳤고, 실행 전 로컬 소프트웨어 검사 237개가 통과했다. 이 검사가 업무 정책의 정확성이나 모델 성능을 검증한 것은 아니다.

[전체 집계 JSON](20261015-llm-ontology-tools-summary.json), [실험 명세](../llm-ontology-tools-study.md), [다음 설계의 우선순위](../../journal/2026-10-15-llm-ontology-tools.md), [입력 정책과 조회 인터페이스 시행착오](../../lessons-learned/2026-10-15-policy-direction-and-query-interface.md)를 함께 남긴다.
