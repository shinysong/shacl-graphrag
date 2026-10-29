# 실행 기록

- [2026-10-28 BPI 2019 원본 로그 적합성 집계](20261028-bpi2019-suitability.json) · [해석과 후속 관문](../../journal/2026-10-28-bpi2019-suitability.md) — 전체 로그 기술 통계이며 모델 성능 실험이 아닙니다.

- [2026-10-22 독립 문서 규칙 추가 비교](20261022-rule-extension.json) · [입력·정책·출력 검토 묶음](20261022-rule-extension-review-bundle.json)

- [2026-10-15 YAGO 원본 데이터의 LLM 조회·검증 연결](20261015-yago-native-tools.md)

실행기가 생성한 결과를 날짜순으로 모은다. 수치는 각 run의 입력과 환경에서 얻은 관찰값이다. 해석과 다음 결정은 [연구 일지](../../journal/index.md)에 남긴다.

기존 기록의 E0와 실행 ID의 `e0`는 합성 RDF를 사용한 사전 점검을 뜻한다. 과거 기록의 파일명·JSON·측정값은 유지한다.

<!-- RUNS -->

- [2026-10-15 LLM 주도 조회·온톨로지 도구](20261015-llm-ontology-tools.md) — 54개 실제 모델 실행, 조회 실패·미완료·입력 정책 오류 보존

- [2026-10-14 금융·제조업 여섯 업무 질문](20261014-business-questions.md)

- [2026-10-14 부품 변경의 영향 경로와 완전성](20261014-change-impact.md) — 192개 합성 사례, 2,304행과 경로·표현 일치 검증
- [2026-10-14 실제 원천의 관계·시점·출처](20261014-domain-characteristics.md) — GLEIF·FIBO·FHIR·YAGO·Wikidata·문서의 제한된 구조 점검

- [2026-10-14 제한된 추가조회와 장애 시 답 보존](20261014-bounded-refresh.md) — 첫 실행 331,776행, 보완 파생 평가 110,592행, 실제 GLEIF 주소 사례

- [2026-10-14 업무·버전·의미의 선택적 검사](20261014-semantic-guards.md) — 기존 12,288행 재사용, 221,184개 검사 판정과 과잉 보류 비교

- [2026-10-14 공통 의미 규칙과 업무 변경](20261014-shared-semantics.md) — 12,288행, 정상 갱신과 설정·추출본·매핑 오류 분리

- [2026-10-14 JSON·Neo4j 변경 반영](20261014-graph-lifecycle.md) — 세 비교군 2,880행, 실제 Cypher와 변경 전후 대조

- [2026-10-13 개념 통합과 명시적 추론](20261013-ontology-reasoning.md) — 오프라인 1,920행, JSON·OWL-RL 질의 640개 일치

- [2026-10-13 최소 온톨로지 개입 비교](20261013-hybrid-comparison.md) — 공통 완료 189개 문항 실행, 미수신 2회·미실행 범위 보존

- [2026-10-13 의미 판단 후속 실행](20261013-semantic-comparison.md) — 합성 개발 180행·대응 점검 36행, 첫 형식 실패 실행 180행 보존


- [2026-10-13 확대 비교](20261013-expanded-comparison.md) — 개발 1,296개·별도 평가 3,240개·Jev 개발 216개 결과

- [20261013T075333Z-gleif-comparison-7b979a6a](20261013T075333Z-gleif-comparison-7b979a6a.md) — completed, development model smoke
- [20261013T075145Z-gleif-comparison-648a2ddf](20261013T075145Z-gleif-comparison-648a2ddf.md) — completed, development deterministic

- [20261012T123009Z-yago-selective-abb7e636](20261012T123009Z-yago-selective-abb7e636.md) — completed, pilot

- [20261012T122943Z-yago-selective-dad1f7f7](20261012T122943Z-yago-selective-dad1f7f7.md) — completed, development

- [20261012T120139Z-yago-2af3a4ef](20261012T120139Z-yago-2af3a4ef.md) — validated, pilot

- [20261012T120020Z-yago-8dab226c](20261012T120020Z-yago-8dab226c.md) — completed, development

- [20261012T115954Z-yago-7c6ab413](20261012T115954Z-yago-7c6ab413.md) — completed, development

- [20261012T115923Z-yago-b7f30599](20261012T115923Z-yago-b7f30599.md) — functional_mismatch, development

- [20261012T115545Z-yago-8219f568](20261012T115545Z-yago-8219f568.md) — functional_mismatch, development

- [20261012T111331Z-gleif-c4fa23cb](20261012T111331Z-gleif-c4fa23cb.md) — completed, pilot

- [20261012T111127Z-gleif-2609aca2](20261012T111127Z-gleif-2609aca2.md) — completed, development

- [20261012T111057Z-gleif-1ac30548](20261012T111057Z-gleif-1ac30548.md) — completed, development

- [20261012T071247495865Z-e0-129aec82](20261012T071247495865Z-e0-129aec82.md) — passed

- [20261012T070907787564Z-e0-674d84f2](20261012T070907787564Z-e0-674d84f2.md) — passed
